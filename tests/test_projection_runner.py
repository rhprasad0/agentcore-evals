"""Offline tests for resumable Week 7 projection execution."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.projection_runner import run_projection_batch


REPO_ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = REPO_ROOT / "tests/fixtures/telemetry/canonical/weather-success.json"


class ProjectionRunnerTests(unittest.TestCase):
    def test_batch_persists_completed_and_instrument_error_cases_in_source_order(self) -> None:
        trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
        rows = (
            {"exampleId": "tc-0001", "scenarioFamily": "straightforward"},
            {"exampleId": "tc-0004", "scenarioFamily": "failure-injection"},
        )
        manifest = {
            "experimentId": "sha256:" + "a" * 64,
            "runId": "12345678-1234-4abc-8def-1234567890ab",
            "outputs": None,
        }
        calls: list[str] = []

        def execute(row, session_id):
            calls.append(row["exampleId"])
            if row["exampleId"] == "tc-0001":
                return {
                    "status": "completed",
                    "trace": deepcopy(trace),
                    "source": {"synthetic": True},
                    "error": None,
                }
            return {
                "status": "instrument-error",
                "trace": None,
                "source": None,
                "error": {"kind": "SyntheticCaptureError", "message": "bounded synthetic failure"},
            }

        with tempfile.TemporaryDirectory() as directory:
            result = run_projection_batch(
                rows,
                manifest=manifest,
                run_store=Path(directory),
                projection={
                    "projectionId": "datasets.weather_only",
                    "version": "1.0.0",
                    "artifactSha256": "b" * 64,
                },
                execute_case=execute,
            )
            run_directory = Path(directory) / manifest["runId"]
            summary = json.loads((run_directory / "summary.json").read_text(encoding="utf-8"))
            aggregate_lines = (run_directory / "canonical-traces.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()

            self.assertEqual(["tc-0001", "tc-0004"], calls)
            self.assertEqual("completed", result["outputs"]["status"])
            self.assertEqual(1, summary["counts"]["completedCases"])
            self.assertEqual(1, summary["counts"]["instrumentErrors"])
            self.assertEqual(1, len(aggregate_lines))
            self.assertTrue((run_directory / "cases/tc-0001/canonical-trace.json").is_file())
            self.assertTrue((run_directory / "cases/tc-0001/raw/strands-inline.json").is_file())
            self.assertTrue((run_directory / "cases/tc-0004/instrument-error.json").is_file())

    def test_resume_reuses_finished_case_outcomes_without_reinvocation(self) -> None:
        trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
        rows = ({"exampleId": "tc-0001", "scenarioFamily": "straightforward"},)
        manifest = {
            "experimentId": "sha256:" + "a" * 64,
            "runId": "12345678-1234-4abc-8def-1234567890ab",
            "outputs": None,
        }

        with tempfile.TemporaryDirectory() as directory:
            run_projection_batch(
                rows,
                manifest=manifest,
                run_store=Path(directory),
                projection={
                    "projectionId": "datasets.weather_only",
                    "version": "1.0.0",
                    "artifactSha256": "b" * 64,
                },
                execute_case=lambda row, session_id: {
                    "status": "completed",
                    "trace": deepcopy(trace),
                    "source": {"synthetic": True},
                    "error": None,
                },
            )
            resumed = deepcopy(manifest)
            resumed["outputs"] = None

            def must_not_run(row, session_id):
                self.fail("completed case was invoked again during resume")

            result = run_projection_batch(
                rows,
                manifest=resumed,
                run_store=Path(directory),
                projection={
                    "projectionId": "datasets.weather_only",
                    "version": "1.0.0",
                    "artifactSha256": "b" * 64,
                },
                execute_case=must_not_run,
            )

            self.assertEqual("completed", result["outputs"]["status"])


if __name__ == "__main__":
    unittest.main()
