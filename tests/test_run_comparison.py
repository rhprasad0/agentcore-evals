"""Tests for same-experiment Week 7 run comparison."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.run_comparison import compare_projection_runs


REPO_ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = REPO_ROOT / "tests/fixtures/telemetry/canonical/weather-success.json"


class ProjectionRunComparisonTests(unittest.TestCase):
    def _write_run(self, root: Path, run_id: str, trace: dict) -> Path:
        run = root / run_id
        case = run / "cases" / "tc-0001"
        case.mkdir(parents=True)
        (run / "run-manifest.json").write_text(
            json.dumps(
                {
                    "experimentId": "sha256:" + "a" * 64,
                    "runId": run_id,
                }
            ),
            encoding="utf-8",
        )
        (run / "summary.json").write_text(
            json.dumps(
                {
                    "cases": [
                        {
                            "exampleId": "tc-0001",
                            "scenarioFamily": "straightforward",
                            "status": "completed",
                            "errorKind": None,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (case / "canonical-trace.json").write_text(json.dumps(trace), encoding="utf-8")
        return run

    def test_reasoning_only_change_preserves_tool_sequence_but_changes_projection(self) -> None:
        left_trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
        right_trace = deepcopy(left_trace)
        right_trace["spans"][1]["selectionReasoning"] = "A different observed text block."

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = self._write_run(root, "12345678-1234-4abc-8def-1234567890ab", left_trace)
            right = self._write_run(root, "22345678-1234-4abc-8def-1234567890ab", right_trace)

            comparison = compare_projection_runs(left, right)

        self.assertEqual(1, comparison["counts"]["comparedCases"])
        self.assertEqual(1, comparison["counts"]["equalToolSequences"])
        self.assertEqual(0, comparison["counts"]["equalCanonicalProjections"])
        self.assertTrue(comparison["cases"][0]["toolSequenceEqual"])
        self.assertFalse(comparison["cases"][0]["canonicalProjectionEqual"])

    def test_argument_change_changes_tool_sequence_and_projection(self) -> None:
        left_trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
        right_trace = deepcopy(left_trace)
        right_trace["spans"][1]["arguments"]["city"] = "Bergen"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = self._write_run(root, "12345678-1234-4abc-8def-1234567890ab", left_trace)
            right = self._write_run(root, "22345678-1234-4abc-8def-1234567890ab", right_trace)

            comparison = compare_projection_runs(left, right)

        self.assertFalse(comparison["cases"][0]["toolSequenceEqual"])
        self.assertFalse(comparison["cases"][0]["canonicalProjectionEqual"])


if __name__ == "__main__":
    unittest.main()
