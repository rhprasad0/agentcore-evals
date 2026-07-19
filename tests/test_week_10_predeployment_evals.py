"""Tests for the Week 10 held-out local Strands experiment."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.run_week_10_predeployment_evals import build_heldout_cases, summarize_reports


REPO_ROOT = Path(__file__).resolve().parents[1]


class Week10PredeploymentTests(unittest.TestCase):
    def test_heldout_cases_are_exactly_the_six_behavioral_gold_rows(self) -> None:
        cases = build_heldout_cases(REPO_ROOT)

        self.assertEqual([f"slice-{index:02}" for index in range(1, 7)], [case.name for case in cases])
        self.assertTrue(all(case.metadata["automated_judge_eligible"] for case in cases))
        self.assertEqual(
            ["tc-0001", "tc-0021", "tc-0006", "tc-0097", "tc-0098", "tc-0073"],
            [case.metadata["example_id"] for case in cases],
        )

    def test_report_summary_keeps_each_evaluator_on_its_own_case_row(self) -> None:
        case_ids = ["slice-01", "slice-02"]
        report = SimpleNamespace(
            cases=[
                {"name": "slice-01", "evaluator": "custom"},
                {"name": "slice-02", "evaluator": "custom"},
                {"name": "slice-01", "evaluator": "selection"},
                {"name": "slice-02", "evaluator": "selection"},
            ],
            scores=[1.0, 0.0, 1.0, 0.0],
            test_passes=[True, False, True, False],
            detailed_results=[
                [SimpleNamespace(label="pass/pass")],
                [SimpleNamespace(label="fail/not_applicable")],
                [SimpleNamespace(label="pass")],
                [SimpleNamespace(label="fail")],
            ],
        )

        outcomes = summarize_reports([report], case_ids, {"slice-02": ("selection",)})

        self.assertEqual("pass", outcomes[0]["evaluators"]["selection"]["label"])
        self.assertEqual("not_applicable", outcomes[1]["evaluators"]["selection"]["label"])


if __name__ == "__main__":
    unittest.main()
