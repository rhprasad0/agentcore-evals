"""Tests for the Week 8 fixture-only Stage B harness."""

from __future__ import annotations

from contextlib import ExitStack
from hashlib import sha256
from importlib.util import find_spec
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evals.harness import (
    HarnessEvidenceError,
    StageBResult,
    load_stage_b_evidence,
    run_stage_b,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "evals/fixtures/weather-only-62"


class FixturePreflightTests(unittest.TestCase):
    def test_preflight_accounts_for_all_cases_and_excludes_instrument_errors(self) -> None:
        evidence = load_stage_b_evidence(REPO_ROOT)

        self.assertEqual(60, len(evidence.eligible_cases))
        self.assertEqual(2, len(evidence.instrument_errors))
        self.assertEqual(62, len(evidence.accounted_case_ids))
        self.assertEqual(
            set(evidence.accounted_case_ids),
            {case.name for case in evidence.eligible_cases}
            | {receipt.example_id for receipt in evidence.instrument_errors},
        )
        for case in evidence.eligible_cases:
            with self.subTest(case=case.name):
                self.assertIn(case.name, evidence.traces_by_case_name)
                self.assertNotIn("trace", case.metadata)
                self.assertEqual("canonical-trace", case.metadata["fixture"]["status"])

    def test_preflight_rejects_fixture_hash_drift_before_case_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory) / "weather-only-62"
            shutil.copytree(FIXTURE_ROOT, fixture_root)
            (fixture_root / "traces/tc-0001.json").write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(HarnessEvidenceError, "fixture hash mismatch"):
                load_stage_b_evidence(REPO_ROOT, fixture_root=fixture_root)

    def test_preflight_rejects_missing_or_extra_case_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory) / "weather-only-62"
            shutil.copytree(FIXTURE_ROOT, fixture_root)
            manifest_path = fixture_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["expectedCaseIds"].append("tc-9999")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(HarnessEvidenceError, "expected case IDs"):
                load_stage_b_evidence(REPO_ROOT, fixture_root=fixture_root)

    def test_preflight_rejects_a_trace_prompt_that_differs_from_case_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory) / "weather-only-62"
            shutil.copytree(FIXTURE_ROOT, fixture_root)
            trace_path = fixture_root / "traces/tc-0001.json"
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            trace["prompt"] = "Different synthetic prompt"
            payload = (json.dumps(trace, ensure_ascii=False, indent=2) + "\n").encode()
            trace_path.write_bytes(payload)
            manifest_path = fixture_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            next(
                entry
                for entry in manifest["fixtures"]
                if entry["exampleId"] == "tc-0001"
            )["sha256"] = sha256(payload).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(HarnessEvidenceError, "prompt does not match dataset"):
                load_stage_b_evidence(REPO_ROOT, fixture_root=fixture_root)


class StageBExecutionTests(unittest.TestCase):
    def test_stage_b_replays_only_canonical_traces_through_all_gates(self) -> None:
        result = run_stage_b(REPO_ROOT)

        self.assertEqual(60, result.eligible_case_count)
        self.assertEqual(2, len(result.instrument_errors))
        self.assertTrue(result.report.cases)
        self.assertEqual(
            {
                "ExpectedToolsGate",
                "ArgConstraintGate",
                "FailureBehaviorGate",
                "NoToolGate",
            },
            {row["evaluator"] for row in result.report.cases},
        )
        self.assertFalse(
            [
                reason
                for reason in result.report.reasons
                if reason.startswith("Evaluator error:")
            ],
            "all prevalidated traces must produce gate verdicts rather than SDK errors",
        )
        instrument_error_ids = {receipt.example_id for receipt in result.instrument_errors}
        self.assertFalse(
            instrument_error_ids.intersection(
                {row["name"] for row in result.report.cases}
            )
        )


class StageBOfflineTests(unittest.TestCase):
    @staticmethod
    def _mechanical_projection(result: StageBResult) -> dict[str, object]:
        report = result.report
        return {
            "experimentId": result.experiment_id,
            "fixtureSetId": result.fixture_set_id,
            "eligibleCaseCount": result.eligible_case_count,
            "instrumentErrorIds": sorted(
                receipt.example_id for receipt in result.instrument_errors
            ),
            "evaluatorRows": sorted(
                (row["name"], row["evaluator"], score, passed)
                for row, score, passed in zip(
                    report.cases,
                    report.scores,
                    report.test_passes,
                    strict=True,
                )
            ),
        }

    def test_stage_b_makes_no_live_dependency_calls_and_is_repeatable(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "AGENT_OBSERVABILITY_ENABLED": "",
                    "AWS_EC2_METADATA_DISABLED": "true",
                },
                clear=False,
            ),
            ExitStack() as guards,
        ):
            guards.enter_context(
                patch("socket.create_connection", side_effect=AssertionError("socket"))
            )
            guards.enter_context(
                patch("socket.socket.connect", side_effect=AssertionError("socket"))
            )
            guards.enter_context(
                patch("urllib.request.urlopen", side_effect=AssertionError("http"))
            )
            guards.enter_context(
                patch(
                    "src.agents.weather_specimen.build_specimen",
                    side_effect=AssertionError("live specimen"),
                )
            )
            if find_spec("boto3") is not None:
                guards.enter_context(
                    patch("boto3.client", side_effect=AssertionError("boto3 client"))
                )
                guards.enter_context(
                    patch("boto3.session.Session", side_effect=AssertionError("boto3 session"))
                )

            first = run_stage_b(REPO_ROOT)
            second = run_stage_b(REPO_ROOT)

        self.assertEqual(
            self._mechanical_projection(first),
            self._mechanical_projection(second),
        )


if __name__ == "__main__":
    unittest.main()
