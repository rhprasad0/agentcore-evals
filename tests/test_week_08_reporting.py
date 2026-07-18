"""Tests for the Week 8 canonical report contract and renderers."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any
import unittest

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas/eval-report.schema.json"
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/eval-reports"
VALID_FIXTURE = FIXTURE_ROOT / "valid-minimal.json"
INVALID_RAW_PROMPT = FIXTURE_ROOT / "invalid-raw-prompt.json"
INVALID_MISSING_DENOMINATOR = FIXTURE_ROOT / "invalid-missing-denominator.json"


class Week08ReportingScaffoldTests(unittest.TestCase):
    def test_report_schema_exists(self) -> None:
        self.assertTrue(SCHEMA_PATH.is_file())

    def test_synthetic_report_fixtures_have_expected_shapes(self) -> None:
        valid = json.loads(VALID_FIXTURE.read_text(encoding="utf-8"))
        unsafe = json.loads(INVALID_RAW_PROMPT.read_text(encoding="utf-8"))
        missing_denominator = json.loads(
            INVALID_MISSING_DENOMINATOR.read_text(encoding="utf-8")
        )

        self.assertEqual("1.0.0", valid["schemaVersion"])
        self.assertEqual(62, valid["counts"]["projectedCases"])
        self.assertEqual(60, valid["counts"]["evidenceValidCases"])
        self.assertEqual(2, valid["counts"]["instrumentErrors"])
        self.assertEqual("What is the weather in Oslo?", unsafe["prompt"])
        self.assertNotIn("denominator", missing_denominator["metrics"]["selection"])

    def test_valid_fixture_matches_report_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        report = json.loads(VALID_FIXTURE.read_text(encoding="utf-8"))

        Draft202012Validator(schema).validate(report)

    def test_invalid_report_fixtures_fail_schema_validation(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)

        for fixture_path in (INVALID_RAW_PROMPT, INVALID_MISSING_DENOMINATOR):
            with self.subTest(fixture=fixture_path.name):
                report = json.loads(fixture_path.read_text(encoding="utf-8"))
                self.assertTrue(list(validator.iter_errors(report)))

    def test_summarize_run_cli_exists(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "scripts.summarize_run", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)


class Week08AggregateTests(unittest.TestCase):
    def test_stage_b_aggregate_accounts_evidence_and_keeps_slices_comparable(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import build_stage_b_aggregate

        result = run_stage_b(REPO_ROOT)
        aggregate = build_stage_b_aggregate(result.evidence, result.report)

        self.assertEqual(62, aggregate["counts"]["projectedCases"])
        self.assertEqual(60, aggregate["counts"]["evidenceValidCases"])
        self.assertEqual(2, aggregate["counts"]["instrumentErrors"])
        self.assertEqual(
            {
                "selection",
                "parameter",
                "execution",
                "failureBehavior",
                "noTool",
                "instrumentValidity",
            },
            set(aggregate["metrics"]),
        )
        for slices in (aggregate["byTag"], aggregate["byFailureKind"]):
            for diagnostic_slice in slices.values():
                self.assertEqual(set(aggregate["metrics"]), set(diagnostic_slice))
        serialized = json.dumps(aggregate, sort_keys=True)
        for forbidden in (
            "input",
            "actual_output",
            "actual_trajectory",
            "arguments",
            "result",
            "diagnostic",
        ):
            self.assertNotIn(f'"{forbidden}"', serialized)

    def test_selection_failure_changes_selection_only(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import build_stage_b_aggregate

        result = run_stage_b(REPO_ROOT)
        baseline = build_stage_b_aggregate(result.evidence, result.report)
        mutated = self._mutated_report(
            result,
            evaluator="ExpectedToolsGate",
            reason="synthetic selection failure",
            passed=False,
        )
        changed = build_stage_b_aggregate(result.evidence, mutated)

        self.assertEqual(
            baseline["metrics"]["selection"]["denominator"],
            changed["metrics"]["selection"]["denominator"],
        )
        self.assertEqual(
            baseline["metrics"]["selection"]["numerator"] - 1,
            changed["metrics"]["selection"]["numerator"],
        )
        self.assertEqual(
            baseline["metrics"]["parameter"],
            changed["metrics"]["parameter"],
        )

    def test_argument_failure_changes_parameter_only(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import build_stage_b_aggregate

        result = run_stage_b(REPO_ROOT)
        baseline = build_stage_b_aggregate(result.evidence, result.report)
        mutated = self._mutated_report(
            result,
            evaluator="ArgConstraintGate",
            reason="synthetic argument failure",
            passed=False,
        )
        changed = build_stage_b_aggregate(result.evidence, mutated)

        self.assertEqual(
            baseline["metrics"]["selection"],
            changed["metrics"]["selection"],
        )
        self.assertEqual(
            baseline["metrics"]["parameter"]["denominator"],
            changed["metrics"]["parameter"]["denominator"],
        )
        self.assertEqual(
            baseline["metrics"]["parameter"]["numerator"] - 1,
            changed["metrics"]["parameter"]["numerator"],
        )

    def test_gate_error_is_counted_and_excluded_from_behavioral_denominator(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import build_stage_b_aggregate

        result = run_stage_b(REPO_ROOT)
        baseline = build_stage_b_aggregate(result.evidence, result.report)
        mutated = self._mutated_report(
            result,
            evaluator="ExpectedToolsGate",
            reason="Evaluator error: synthetic gate error",
            passed=False,
        )
        changed = build_stage_b_aggregate(result.evidence, mutated)

        self.assertEqual(1, changed["counts"]["gateErrors"])
        self.assertEqual(
            baseline["metrics"]["selection"]["denominator"] - 1,
            changed["metrics"]["selection"]["denominator"],
        )
        self.assertEqual(
            baseline["metrics"]["selection"]["numerator"] - 1,
            changed["metrics"]["selection"]["numerator"],
        )

    def test_stage_b_aggregate_passes_schema_and_arithmetic_validation(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import build_stage_b_aggregate, validate_report

        result = run_stage_b(REPO_ROOT)
        aggregate = build_stage_b_aggregate(result.evidence, result.report)

        validate_report(aggregate, repo_root=REPO_ROOT)

    def test_invalid_public_report_fixtures_are_rejected(self) -> None:
        from evals.reporting import ReportContractError, validate_report

        for fixture_path in (INVALID_RAW_PROMPT, INVALID_MISSING_DENOMINATOR):
            with self.subTest(fixture=fixture_path.name):
                report = json.loads(fixture_path.read_text(encoding="utf-8"))
                with self.assertRaises(ReportContractError):
                    validate_report(report, repo_root=REPO_ROOT)

    def test_non_empty_metric_with_wrong_rate_is_rejected(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import ReportContractError, build_stage_b_aggregate, validate_report

        result = run_stage_b(REPO_ROOT)
        aggregate = build_stage_b_aggregate(result.evidence, result.report)
        aggregate["metrics"]["selection"]["rate"] = 0.0

        with self.assertRaisesRegex(ReportContractError, "rate"):
            validate_report(aggregate, repo_root=REPO_ROOT)

    def test_shared_no_tool_gate_error_is_counted_once_at_report_level(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import build_stage_b_aggregate

        result = run_stage_b(REPO_ROOT)
        mutated = self._mutated_report(
            result,
            case_name="tc-0003",
            evaluator="NoToolGate",
            reason="Evaluator error: synthetic no-tool gate error",
            passed=False,
        )

        changed = build_stage_b_aggregate(result.evidence, mutated)

        self.assertEqual(1, changed["counts"]["gateErrors"])

    def test_renderers_are_repeatable_and_public_safe(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import (
            build_stage_b_aggregate,
            render_json,
            render_markdown,
            render_text,
            validate_report,
        )

        result = run_stage_b(REPO_ROOT)
        aggregate = build_stage_b_aggregate(result.evidence, result.report)
        validate_report(aggregate, repo_root=REPO_ROOT)
        json_output = render_json(aggregate)
        text_output = render_text(aggregate)
        markdown_output = render_markdown(aggregate)

        self.assertEqual(aggregate, json.loads(json_output))
        self.assertEqual(json_output, render_json(aggregate))
        self.assertEqual(text_output, render_text(aggregate))
        self.assertEqual(markdown_output, render_markdown(aggregate))
        for output in (json_output, text_output, markdown_output):
            self.assertIn("Mechanical contract compliance only", output)
            self.assertNotIn("What is the current weather in Oslo?", output)
            self.assertNotIn("actual_trajectory", output)
            self.assertNotIn("tool_arguments", output)

    @staticmethod
    def _mutated_report(
        result: Any,
        *,
        case_name: str = "tc-0001",
        evaluator: str,
        reason: str,
        passed: bool,
    ) -> SimpleNamespace:
        report = result.report
        cases = deepcopy(report.cases)
        scores = list(report.scores)
        test_passes = list(report.test_passes)
        reasons = list(report.reasons)
        index = next(
            index
            for index, row in enumerate(cases)
            if row["name"] == case_name and row["evaluator"] == evaluator
        )
        scores[index] = 1.0 if passed else 0.0
        test_passes[index] = passed
        reasons[index] = reason
        return SimpleNamespace(
            cases=cases,
            scores=scores,
            test_passes=test_passes,
            reasons=reasons,
        )


class Week08ReportingCliTests(unittest.TestCase):
    def test_cli_json_matches_python_api_aggregate(self) -> None:
        from evals.harness import run_stage_b
        from evals.reporting import build_stage_b_aggregate

        result = run_stage_b(REPO_ROOT)
        expected = build_stage_b_aggregate(result.evidence, result.report)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.summarize_run",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--format",
                    "json",
                    "--output",
                    str(output_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("", completed.stdout)
            self.assertEqual(expected, json.loads(output_path.read_text(encoding="utf-8")))

    def test_cli_text_and_markdown_outputs_are_public_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            for output_format in ("text", "markdown"):
                output_path = Path(temporary_directory) / f"report.{output_format}"
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.summarize_run",
                        "--repo-root",
                        str(REPO_ROOT),
                        "--format",
                        output_format,
                        "--output",
                        str(output_path),
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                rendered = output_path.read_text(encoding="utf-8")
                self.assertIn("Mechanical contract compliance only", rendered)
                self.assertNotIn("What is the current weather in Oslo?", rendered)


if __name__ == "__main__":
    unittest.main()
