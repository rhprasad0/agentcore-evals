"""Tests for the canonical Week 6 execution-trace contract."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from src.telemetry_normalization import (
    canonical_projection_bytes,
    normalize_strands_telemetry,
    selection_reasoning_by_call_id,
    validate_agentcore_evaluation_input,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "execution-trace.schema.json"
VALID_TRACE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "telemetry" / "canonical" / "weather-success.json"
)
INLINE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "telemetry" / "strands-inline" / "weather-success.json"
)
ADOT_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "telemetry" / "strands-adot" / "weather-success.json"
)
AGENTCORE_INPUT_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "telemetry"
    / "agentcore-evaluation-input"
    / "session-spans.json"
)
SELECTION_REASONING_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "telemetry"
    / "strands-inline"
    / "selection-reasoning-cases.json"
)


class ExecutionTraceSchemaTests(unittest.TestCase):
    def test_schema_declares_draft_and_versioned_identity(self) -> None:
        self.assertTrue(
            SCHEMA_PATH.is_file(),
            f"missing schema: {SCHEMA_PATH.relative_to(REPO_ROOT)}",
        )
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            schema.get("$schema"),
        )
        self.assertEqual(
            "urn:agentcore-evals:schema:execution-trace:1.0.0",
            schema.get("$id"),
        )
        Draft202012Validator.check_schema(schema)

    def test_realistic_canonical_trace_is_valid(self) -> None:
        self.assertTrue(
            VALID_TRACE_PATH.is_file(),
            f"missing fixture: {VALID_TRACE_PATH.relative_to(REPO_ROOT)}",
        )
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        trace = json.loads(VALID_TRACE_PATH.read_text(encoding="utf-8"))

        errors = list(Draft202012Validator(schema).iter_errors(trace))

        self.assertEqual([], [error.message for error in errors])

    def test_canonical_projection_orders_spans_and_rejects_ambiguous_sequences(self) -> None:
        trace = json.loads(VALID_TRACE_PATH.read_text(encoding="utf-8"))
        reversed_trace = deepcopy(trace)
        reversed_trace["spans"].reverse()
        duplicate_sequence = deepcopy(trace)
        duplicate_sequence["spans"][1]["sequence"] = 0

        self.assertEqual(
            canonical_projection_bytes(trace),
            canonical_projection_bytes(reversed_trace),
        )
        with self.assertRaisesRegex(ValueError, "contiguous and unique"):
            canonical_projection_bytes(duplicate_sequence)


class StrandsTelemetryNormalizationTests(unittest.TestCase):
    def test_selection_reasoning_is_block_local_and_message_local(self) -> None:
        cases = json.loads(SELECTION_REASONING_PATH.read_text(encoding="utf-8"))

        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(
                    case["expected"],
                    selection_reasoning_by_call_id(case["messages"]),
                )

    def test_inline_normalizer_correlates_pre_tool_text_by_call_id(self) -> None:
        source = json.loads(INLINE_PATH.read_text(encoding="utf-8"))
        source["agentManifest"]["version"] = "4.0.0"
        source["spans"].append(
            {
                "traceId": "11111111111111111111111111111111",
                "spanId": "3333333333333333",
                "parentSpanId": "1111111111111111",
                "name": "chat",
                "scope": {"name": "strands.telemetry.tracer"},
                "startTimeUnixNano": 1020000000,
                "endTimeUnixNano": 1040000000,
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "session.id": "synthetic-session-inline",
                },
                "events": [
                    {
                        "name": "gen_ai.choice",
                        "attributes": {
                            "message": json.dumps(
                                [
                                    {"text": "I will check Oslo."},
                                    {
                                        "toolUse": {
                                            "toolUseId": "synthetic-tool-call-1",
                                            "name": "get_current_weather",
                                            "input": {"city": "Oslo", "units": "metric"},
                                        }
                                    },
                                ],
                                separators=(",", ":"),
                            )
                        },
                    }
                ],
            }
        )

        trace = normalize_strands_telemetry(source, repo_root=REPO_ROOT)
        tool_span = next(
            span for span in trace["spans"] if span["operationName"] == "execute_tool"
        )

        self.assertEqual("I will check Oslo.", tool_span["selectionReasoning"])

    def test_inline_events_normalize_to_expected_canonical_trace(self) -> None:
        source = json.loads(INLINE_PATH.read_text(encoding="utf-8"))
        expected = json.loads(VALID_TRACE_PATH.read_text(encoding="utf-8"))

        actual = normalize_strands_telemetry(source, repo_root=REPO_ROOT)

        self.assertEqual(expected, actual)

    def test_inline_and_adot_profiles_have_byte_identical_canonical_projections(self) -> None:
        inline_source = json.loads(INLINE_PATH.read_text(encoding="utf-8"))
        adot_source = json.loads(ADOT_PATH.read_text(encoding="utf-8"))

        inline = normalize_strands_telemetry(inline_source, repo_root=REPO_ROOT)
        adot = normalize_strands_telemetry(adot_source, repo_root=REPO_ROOT)

        self.assertEqual(
            canonical_projection_bytes(inline),
            canonical_projection_bytes(adot),
        )

    def test_source_profile_rejects_version_or_scope_drift(self) -> None:
        source = json.loads(INLINE_PATH.read_text(encoding="utf-8"))
        wrong_version = deepcopy(source)
        wrong_version["sourceProfile"]["producer"]["version"] = "1.47.0"
        wrong_scope = deepcopy(source)
        wrong_scope["spans"][0]["scope"]["name"] = "other.tracer"

        with self.assertRaisesRegex(ValueError, "strands-agents==1.46.0"):
            normalize_strands_telemetry(wrong_version, repo_root=REPO_ROOT)
        with self.assertRaisesRegex(ValueError, "span scope"):
            normalize_strands_telemetry(wrong_scope, repo_root=REPO_ROOT)

    def test_adot_correlation_and_tool_identity_fail_loudly(self) -> None:
        adot = json.loads(ADOT_PATH.read_text(encoding="utf-8"))
        orphaned = deepcopy(adot)
        orphaned["eventRecords"][0]["spanId"] = "7777777777777777"
        duplicated = deepcopy(adot)
        duplicated["eventRecords"].append(deepcopy(duplicated["eventRecords"][0]))
        unknown_tool = json.loads(INLINE_PATH.read_text(encoding="utf-8"))
        unknown_tool["spans"][0]["attributes"]["gen_ai.tool.name"] = "unknown_tool"

        with self.assertRaisesRegex(ValueError, "missing event record correlation"):
            normalize_strands_telemetry(orphaned, repo_root=REPO_ROOT)
        with self.assertRaisesRegex(ValueError, "duplicate event record correlation"):
            normalize_strands_telemetry(duplicated, repo_root=REPO_ROOT)
        with self.assertRaisesRegex(ValueError, "does not resolve to one exact contract"):
            normalize_strands_telemetry(unknown_tool, repo_root=REPO_ROOT)

    def test_failure_result_preserves_kind_retryability_and_bounded_diagnostic(self) -> None:
        source = json.loads(INLINE_PATH.read_text(encoding="utf-8"))
        tool_span = source["spans"][0]
        tool_span["attributes"]["agentcore_evals.failure.source"] = "transport"
        tool_span["attributes"]["agentcore_evals.failure.code"] = "SYNTHETIC_TIMEOUT"
        tool_span["events"][1]["attributes"]["message"] = (
            '[{"text":"{\\"ok\\":false,\\"error\\":'
            '{\\"kind\\":\\"timeout\\",\\"message\\":\\"synthetic timeout\\",'
            '\\"retryable\\":true}}"}]'
        )

        trace = normalize_strands_telemetry(source, repo_root=REPO_ROOT)

        result = trace["spans"][1]["result"]
        self.assertEqual("timeout", result["failureKind"])
        self.assertIs(result["retryable"], True)
        self.assertEqual(
            {"source": "transport", "code": "SYNTHETIC_TIMEOUT"},
            result["diagnostic"],
        )

    def test_normalizer_rejects_schema_valid_trace_with_contract_invalid_arguments(self) -> None:
        source = json.loads(INLINE_PATH.read_text(encoding="utf-8"))
        source["spans"][0]["events"][0]["attributes"]["content"] = (
            '{"city":"Oslo","units":"kelvin"}'
        )

        with self.assertRaisesRegex(
            ValueError,
            r"spans\[1\]\.arguments.*weather\.get_current_weather@2\.0\.0",
        ):
            normalize_strands_telemetry(source, repo_root=REPO_ROOT)


class AgentCoreEvaluationInputFixtureTests(unittest.TestCase):
    def test_session_spans_fixture_satisfies_union_and_documented_bounds(self) -> None:
        fixture = json.loads(AGENTCORE_INPUT_PATH.read_text(encoding="utf-8"))

        validate_agentcore_evaluation_input(fixture)

        with self.assertRaisesRegex(ValueError, "between 1 and 1000"):
            validate_agentcore_evaluation_input({"sessionSpans": []})
        with self.assertRaisesRegex(ValueError, "between 1 and 1000"):
            validate_agentcore_evaluation_input({"sessionSpans": [{}] * 1001})
        with self.assertRaisesRegex(ValueError, "union member"):
            validate_agentcore_evaluation_input(
                {"sessionSpans": fixture["sessionSpans"], "otherMember": {}}
            )


if __name__ == "__main__":
    unittest.main()
