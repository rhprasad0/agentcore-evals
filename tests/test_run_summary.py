"""Tests for public-safe Week 7 batch-run summaries."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from src.run_summary import summarize_projection_run


REPO_ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = REPO_ROOT / "tests/fixtures/telemetry/canonical/weather-success.json"
SCHEMA_PATH = REPO_ROOT / "schemas/run-summary.schema.json"


class ProjectionRunSummaryTests(unittest.TestCase):
    def test_summary_aggregates_semantics_without_raw_case_content(self) -> None:
        trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
        trace["spans"][1]["selectionReasoning"] = "I will check the current weather."
        outcomes = [
            {
                "exampleId": "tc-0001",
                "scenarioFamily": "straightforward",
                "status": "completed",
                "trace": trace,
                "errorKind": None,
            },
            {
                "exampleId": "tc-0004",
                "scenarioFamily": "failure-injection",
                "status": "instrument-error",
                "trace": None,
                "errorKind": "UnknownMockFixtureError",
            },
        ]

        summary = summarize_projection_run(
            outcomes,
            experiment_id="sha256:" + "a" * 64,
            run_id="12345678-1234-4abc-8def-1234567890ab",
            projection={
                "projectionId": "datasets.weather_only",
                "version": "1.0.0",
                "artifactSha256": "b" * 64,
            },
        )

        self.assertEqual(2, summary["counts"]["totalCases"])
        self.assertEqual(1, summary["counts"]["completedCases"])
        self.assertEqual(1, summary["counts"]["instrumentErrors"])
        self.assertEqual(1, summary["counts"]["toolCalls"])
        self.assertEqual(
            {"present": 1, "null": 0, "totalToolCalls": 1},
            summary["selectionReasoning"],
        )
        self.assertEqual(
            {"UnknownMockFixtureError": 1},
            summary["instrumentErrorKinds"],
        )
        serialized = json.dumps(summary, sort_keys=True)
        for forbidden in ("prompt", "response", "arguments", "result", "diagnostic"):
            self.assertNotIn(f'"{forbidden}"', serialized)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(summary)


if __name__ == "__main__":
    unittest.main()
