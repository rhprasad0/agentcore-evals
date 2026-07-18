"""Tests for deterministic Week 8 offline tool-contract gates."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from strands_evals.types.evaluation import EvaluationData

from evals.adapters.cases import build_projection_cases

from evals.evaluators.gates import (
    ArgConstraintGate,
    ExpectedToolsGate,
    FailureBehaviorGate,
    GateEvidenceError,
    NoToolGate,
    read_gate_evidence,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "evals/fixtures/weather-only-62"


def tool_span(
    tool_id: str,
    arguments: dict[str, object],
    *,
    result: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "operationName": "execute_tool",
        "tool": {"toolId": tool_id},
        "arguments": arguments,
        "result": result or {"ok": True},
    }


def evaluation_data(
    *,
    expected: dict[str, object],
    spans: list[object],
    response: str = "response",
    failure_injection: dict[str, object] | None = None,
) -> EvaluationData:
    return EvaluationData(
        input="prompt",
        actual_output=response,
        actual_trajectory=spans,
        metadata={"expected": expected, "failureInjection": failure_injection},
    )


class GateEvidenceTests(unittest.TestCase):
    def test_gate_evidence_requires_expected_mapping(self) -> None:
        data = EvaluationData(
            input="prompt",
            actual_output="response",
            actual_trajectory=[],
            metadata={},
        )

        with self.assertRaisesRegex(GateEvidenceError, "metadata.expected"):
            read_gate_evidence(data)


class ExpectedToolsGateTests(unittest.TestCase):
    def test_expected_tools_passes_when_required_ids_and_bounds_match(self) -> None:
        data = evaluation_data(
            expected={
                "toolIds": ["weather.get_current_weather"],
                "mustNotCall": ["search.web_search"],
                "minCalls": 1,
                "maxCalls": 1,
                "argConstraints": [],
            },
            spans=[tool_span("weather.get_current_weather", {"city": "Oslo"})],
        )

        outputs = ExpectedToolsGate().evaluate(data)

        self.assertEqual(1, len(outputs))
        self.assertEqual("pass", outputs[0].label)
        self.assertEqual(1.0, outputs[0].score)
        self.assertTrue(outputs[0].test_pass)

    def test_expected_tools_fails_when_required_tool_is_missing(self) -> None:
        data = evaluation_data(
            expected={
                "toolIds": ["weather.get_current_weather"],
                "mustNotCall": [],
                "minCalls": 1,
                "maxCalls": 1,
                "argConstraints": [],
            },
            spans=[],
        )

        output = ExpectedToolsGate().evaluate(data)[0]

        self.assertEqual("fail", output.label)
        self.assertFalse(output.test_pass)
        self.assertIn("required tools missing", output.reason or "")

    def test_expected_tools_fails_for_unexpected_or_forbidden_calls(self) -> None:
        expected = {
            "toolIds": ["weather.get_current_weather"],
            "mustNotCall": ["search.web_search"],
            "minCalls": 1,
            "maxCalls": 1,
            "argConstraints": [],
        }
        for tool_id, reason in (
            ("calculator.calculate", "unexpected tools called"),
            ("search.web_search", "forbidden tools called"),
        ):
            with self.subTest(tool_id=tool_id):
                output = ExpectedToolsGate().evaluate(
                    evaluation_data(
                        expected=expected,
                        spans=[tool_span(tool_id, {})],
                    )
                )[0]

                self.assertEqual("fail", output.label)
                self.assertIn(reason, output.reason or "")

    def test_expected_tools_fails_outside_inclusive_call_bounds(self) -> None:
        expected = {
            "toolIds": ["weather.get_current_weather"],
            "mustNotCall": [],
            "minCalls": 1,
            "maxCalls": 1,
            "argConstraints": [],
        }
        output = ExpectedToolsGate().evaluate(
            evaluation_data(
                expected=expected,
                spans=[
                    tool_span("weather.get_current_weather", {"city": "Oslo"}),
                    tool_span("weather.get_current_weather", {"city": "Bergen"}),
                ],
            )
        )[0]

        self.assertEqual("fail", output.label)
        self.assertIn("outside inclusive bounds", output.reason or "")

    def test_expected_tools_is_not_applicable_for_no_tool_expectations(self) -> None:
        output = ExpectedToolsGate().evaluate(
            evaluation_data(
                expected={
                    "toolIds": [],
                    "mustNotCall": ["weather.get_current_weather"],
                    "minCalls": 0,
                    "maxCalls": 0,
                    "argConstraints": [],
                },
                spans=[],
            )
        )[0]

        self.assertEqual("not_applicable", output.label)
        self.assertTrue(output.test_pass)


class ArgConstraintGateTests(unittest.TestCase):
    def _output(
        self,
        constraint: dict[str, object],
        spans: list[object],
    ):
        return ArgConstraintGate().evaluate(
            evaluation_data(
                expected={
                    "toolIds": ["weather.get_current_weather"],
                    "mustNotCall": [],
                    "minCalls": 1,
                    "maxCalls": 3,
                    "argConstraints": [constraint],
                },
                spans=spans,
            )
        )[0]

    def test_equals_requires_an_exact_present_value(self) -> None:
        constraint = {
            "toolId": "weather.get_current_weather",
            "path": "$.city",
            "equals": "Oslo",
        }
        passed = self._output(
            constraint,
            [tool_span("weather.get_current_weather", {"city": "Oslo"})],
        )
        failed = self._output(
            constraint,
            [tool_span("weather.get_current_weather", {"city": "Bergen"})],
        )

        self.assertEqual("pass", passed.label)
        self.assertEqual("fail", failed.label)
        self.assertIn("equals", failed.reason or "")

    def test_in_set_and_not_contains_enforce_their_declared_predicates(self) -> None:
        for constraint, arguments, expected_label in (
            (
                {
                    "toolId": "weather.get_current_weather",
                    "path": "$.units",
                    "inSet": ["metric", "imperial"],
                },
                {"units": "metric"},
                "pass",
            ),
            (
                {
                    "toolId": "weather.get_current_weather",
                    "path": "$.units",
                    "inSet": ["metric", "imperial"],
                },
                {"units": "standard"},
                "fail",
            ),
            (
                {
                    "toolId": "weather.get_current_weather",
                    "path": "$.city",
                    "notContains": "INJECTION_CANARY_DO_NOT_FOLLOW",
                },
                {"city": "Oslo"},
                "pass",
            ),
            (
                {
                    "toolId": "weather.get_current_weather",
                    "path": "$.city",
                    "notContains": "INJECTION_CANARY_DO_NOT_FOLLOW",
                },
                {"city": "INJECTION_CANARY_DO_NOT_FOLLOW"},
                "fail",
            ),
        ):
            with self.subTest(constraint=constraint):
                output = self._output(
                    constraint,
                    [tool_span("weather.get_current_weather", arguments)],
                )
                self.assertEqual(expected_label, output.label)

    def test_covers_exactly_once_accepts_a_multiset_and_rejects_duplicates(self) -> None:
        constraint = {
            "toolId": "weather.get_current_weather",
            "path": "$.city",
            "coversExactlyOnce": ["Oslo", "Bergen"],
        }
        passed = self._output(
            constraint,
            [
                tool_span("weather.get_current_weather", {"city": "Oslo"}),
                tool_span("weather.get_current_weather", {"city": "Bergen"}),
            ],
        )
        failed = self._output(
            constraint,
            [
                tool_span("weather.get_current_weather", {"city": "Oslo"}),
                tool_span("weather.get_current_weather", {"city": "Oslo"}),
            ],
        )

        self.assertEqual("pass", passed.label)
        self.assertEqual("fail", failed.label)
        self.assertIn("coversExactlyOnce", failed.reason or "")

    def test_absent_requires_the_property_to_be_missing(self) -> None:
        constraint = {
            "toolId": "weather.get_current_weather",
            "path": "$.units",
            "absent": True,
        }
        passed = self._output(
            constraint,
            [tool_span("weather.get_current_weather", {"city": "Oslo"})],
        )
        failed = self._output(
            constraint,
            [tool_span("weather.get_current_weather", {"units": "metric"})],
        )

        self.assertEqual("pass", passed.label)
        self.assertEqual("fail", failed.label)
        self.assertIn("absent", failed.reason or "")

    def test_argument_gate_is_not_applicable_without_a_matching_call(self) -> None:
        output = self._output(
            {
                "toolId": "weather.get_current_weather",
                "path": "$.city",
                "equals": "Oslo",
            },
            [],
        )

        self.assertEqual("not_applicable", output.label)

    def test_argument_gate_rejects_nested_paths_as_evidence_errors(self) -> None:
        with self.assertRaisesRegex(GateEvidenceError, "root property"):
            self._output(
                {
                    "toolId": "weather.get_current_weather",
                    "path": "$.city.name",
                    "equals": "Oslo",
                },
                [tool_span("weather.get_current_weather", {"city": "Oslo"})],
            )


class NoToolGateTests(unittest.TestCase):
    def test_no_tool_gate_passes_without_execute_tool_spans(self) -> None:
        output = NoToolGate().evaluate(
            evaluation_data(
                expected={
                    "toolIds": [],
                    "mustNotCall": ["weather.get_current_weather"],
                    "minCalls": 0,
                    "maxCalls": 0,
                    "argConstraints": [],
                },
                spans=[{"operationName": "chat"}],
            )
        )[0]

        self.assertEqual("pass", output.label)

    def test_no_tool_gate_fails_when_any_tool_is_called(self) -> None:
        output = NoToolGate().evaluate(
            evaluation_data(
                expected={
                    "toolIds": [],
                    "mustNotCall": ["weather.get_current_weather"],
                    "minCalls": 0,
                    "maxCalls": 0,
                    "argConstraints": [],
                },
                spans=[tool_span("weather.get_current_weather", {"city": "Oslo"})],
            )
        )[0]

        self.assertEqual("fail", output.label)

    def test_no_tool_gate_is_not_applicable_when_tools_are_expected(self) -> None:
        output = NoToolGate().evaluate(
            evaluation_data(
                expected={
                    "toolIds": ["weather.get_current_weather"],
                    "mustNotCall": [],
                    "minCalls": 1,
                    "maxCalls": 1,
                    "argConstraints": [],
                },
                spans=[],
            )
        )[0]

        self.assertEqual("not_applicable", output.label)


class FailureBehaviorGateTests(unittest.TestCase):
    def test_failure_gate_matches_configured_failure_envelope(self) -> None:
        output = FailureBehaviorGate().evaluate(
            evaluation_data(
                expected={
                    "toolIds": ["weather.get_current_weather"],
                    "mustNotCall": [],
                    "minCalls": 1,
                    "maxCalls": 1,
                    "argConstraints": [],
                },
                failure_injection={
                    "toolId": "weather.get_current_weather",
                    "kind": "timeout",
                    "retryable": True,
                },
                spans=[
                    tool_span(
                        "weather.get_current_weather",
                        {"city": "Reykjavík"},
                        result={
                            "ok": False,
                            "failureKind": "timeout",
                            "retryable": True,
                        },
                    )
                ],
            )
        )[0]

        self.assertEqual("pass", output.label)

    def test_failure_gate_fails_for_success_or_mismatched_envelope(self) -> None:
        expected = {
            "toolIds": ["weather.get_current_weather"],
            "mustNotCall": [],
            "minCalls": 1,
            "maxCalls": 1,
            "argConstraints": [],
        }
        injection = {
            "toolId": "weather.get_current_weather",
            "kind": "timeout",
            "retryable": True,
        }
        for result in (
            {"ok": True, "failureKind": None, "retryable": None},
            {"ok": False, "failureKind": "network", "retryable": True},
            {"ok": False, "failureKind": "timeout", "retryable": False},
        ):
            with self.subTest(result=result):
                output = FailureBehaviorGate().evaluate(
                    evaluation_data(
                        expected=expected,
                        failure_injection=injection,
                        spans=[
                            tool_span(
                                "weather.get_current_weather",
                                {"city": "Reykjavík"},
                                result=result,
                            )
                        ],
                    )
                )[0]
                self.assertEqual("fail", output.label)

    def test_failure_gate_uses_one_based_configured_occurrence(self) -> None:
        output = FailureBehaviorGate().evaluate(
            evaluation_data(
                expected={
                    "toolIds": ["weather.get_current_weather"],
                    "mustNotCall": [],
                    "minCalls": 1,
                    "maxCalls": 2,
                    "argConstraints": [],
                },
                failure_injection={
                    "toolId": "weather.get_current_weather",
                    "kind": "timeout",
                    "retryable": True,
                    "occurrence": 2,
                },
                spans=[
                    tool_span(
                        "weather.get_current_weather",
                        {"city": "Reykjavík"},
                        result={"ok": True, "failureKind": None, "retryable": None},
                    ),
                    tool_span(
                        "weather.get_current_weather",
                        {"city": "Reykjavík"},
                        result={
                            "ok": False,
                            "failureKind": "timeout",
                            "retryable": True,
                        },
                    ),
                ],
            )
        )[0]

        self.assertEqual("pass", output.label)

    def test_failure_gate_is_not_applicable_without_an_injection(self) -> None:
        output = FailureBehaviorGate().evaluate(
            evaluation_data(
                expected={
                    "toolIds": [],
                    "mustNotCall": [],
                    "minCalls": 0,
                    "maxCalls": 0,
                    "argConstraints": [],
                },
                spans=[],
            )
        )[0]

        self.assertEqual("not_applicable", output.label)


class CommittedFixtureSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = {
            case.name: case
            for case in build_projection_cases(
                REPO_ROOT / "datasets/projections/weather-only-62.json",
                repo_root=REPO_ROOT,
            )
        }

    def _evaluation_data_from_trace(self, trace_path: Path) -> EvaluationData:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        case = self.cases[trace_path.stem]
        return EvaluationData(
            input=case.input,
            actual_output=trace["response"],
            actual_trajectory=trace["spans"],
            metadata=case.metadata,
        )

    def test_all_canonical_trace_spans_can_be_read_as_gate_evidence(self) -> None:
        trace_paths = sorted((FIXTURE_ROOT / "traces").glob("*.json"))

        self.assertEqual(60, len(trace_paths))
        for trace_path in trace_paths:
            with self.subTest(trace=trace_path.name):
                evidence = read_gate_evidence(self._evaluation_data_from_trace(trace_path))
                self.assertIsInstance(evidence.spans, tuple)

    def test_known_retry_and_no_tool_fixtures_reach_their_applicable_gates(self) -> None:
        retry_output = FailureBehaviorGate().evaluate(
            self._evaluation_data_from_trace(FIXTURE_ROOT / "traces/tc-0004.json")
        )[0]
        no_tool_output = NoToolGate().evaluate(
            self._evaluation_data_from_trace(FIXTURE_ROOT / "traces/tc-0064.json")
        )[0]

        self.assertEqual("pass", retry_output.label)
        self.assertEqual("pass", no_tool_output.label)

    def test_instrument_error_receipts_are_rejected_as_gate_evidence(self) -> None:
        error_paths = sorted((FIXTURE_ROOT / "errors").glob("*.json"))

        self.assertEqual(2, len(error_paths))
        for error_path in error_paths:
            with self.subTest(receipt=error_path.name):
                receipt = json.loads(error_path.read_text(encoding="utf-8"))
                with self.assertRaisesRegex(GateEvidenceError, "expected"):
                    read_gate_evidence(
                        EvaluationData(
                            input="",
                            actual_output=None,
                            actual_trajectory=[],
                            metadata=receipt,
                        )
                    )


if __name__ == "__main__":
    unittest.main()
