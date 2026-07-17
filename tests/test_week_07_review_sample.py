"""Tests for the frozen Week 7 ten-row human-review sample."""

from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from src.review_sample import load_frozen_review_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = REPO_ROOT / "datasets/reviews/week-07-ten-row-sample.json"
PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"


class Week07ReviewSampleTests(unittest.TestCase):
    def test_sample_is_frozen_against_exact_projection_bytes_and_source_rows(self) -> None:
        sample = load_frozen_review_sample(
            SAMPLE_PATH,
            projection_path=PROJECTION_PATH,
            repo_root=REPO_ROOT,
        )

        self.assertEqual(10, len(sample.rows))
        self.assertEqual(
            Counter(
                {
                    "straightforward": 2,
                    "multi-call": 2,
                    "no-tool": 2,
                    "failure-injection": 2,
                    "adversarial-ambiguous": 1,
                    "dependency-stop": 1,
                }
            ),
            Counter(row["scenarioFamily"] for row in sample.rows),
        )
        self.assertEqual(
            (
                "tc-0001",
                "tc-0020",
                "tc-0002",
                "tc-0058",
                "tc-0003",
                "tc-0065",
                "tc-0004",
                "tc-0076",
                "tc-0005",
                "tc-0098",
            ),
            tuple(row["exampleId"] for row in sample.rows),
        )

    def test_sample_predeclares_triage_without_review_outcomes(self) -> None:
        sample = load_frozen_review_sample(
            SAMPLE_PATH,
            projection_path=PROJECTION_PATH,
            repo_root=REPO_ROOT,
        )

        self.assertEqual(
            {"dataset-bug", "agent-bug", "contract-ambiguity", "instrument-error"},
            set(sample.document["triageRules"]),
        )
        self.assertNotIn("reviews", sample.document)
        self.assertNotIn("findings", sample.document)


if __name__ == "__main__":
    unittest.main()
