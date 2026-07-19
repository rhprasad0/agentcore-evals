"""Tests for the Week 10 held-out local Strands experiment."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from evals.evaluators.weather_calculator_judge import WeatherCalculatorJudgeEvaluator
from scripts.run_week_10_predeployment_evals import build_heldout_cases, summarize_reports
from scripts.judge_weather_calculator import JudgeInputError
from strands_evals.types.trace import TextContent


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
                {"name": "slice-01", "evaluator": "week10_custom_judge"},
                {"name": "slice-02", "evaluator": "week10_custom_judge"},
                {"name": "slice-01", "evaluator": "selection"},
                {"name": "slice-02", "evaluator": "selection"},
            ],
            scores=[1.0, 0.0, 1.0, 0.0],
            test_passes=[True, False, True, False],
            detailed_results=[
                [SimpleNamespace(label="pass/pass", reason="Both required calls were observed in order.")],
                [SimpleNamespace(label="fail/not_applicable", reason="Weather output could not be traced into calculator input.")],
                [SimpleNamespace(label="pass")],
                [SimpleNamespace(label="fail")],
            ],
        )

        outcomes = summarize_reports([report], case_ids, {"slice-02": ("selection",)})

        self.assertEqual("pass", outcomes[0]["evaluators"]["selection"]["label"])
        self.assertEqual("not_applicable", outcomes[1]["evaluators"]["selection"]["label"])
        self.assertEqual(
            "Weather output could not be traced into calculator input.",
            outcomes[1]["evaluators"]["week10_custom_judge"]["rationale"],
        )
        self.assertNotIn("rationale", outcomes[0]["evaluators"]["selection"])

    def test_report_summary_rejects_a_custom_judge_without_a_verdict(self) -> None:
        report = SimpleNamespace(
            cases=[{"name": "slice-01", "evaluator": "week10_custom_judge"}],
            scores=[0.0],
            test_passes=[False],
            detailed_results=[[]],
        )

        with self.assertRaisesRegex(JudgeInputError, "has no verdict"):
            summarize_reports([report], ["slice-01"], {})

    def test_custom_judge_normalizes_conversion_tool_outputs(self) -> None:
        captured: dict[str, Any] = {}

        def provider(prompt: str) -> dict[str, object]:
            captured.update(json.loads(prompt.partition("Evidence:\n")[2]))
            return {
                "case_id": "slice-03",
                "selection_verdict": "pass",
                "parameter_verdict": "pass",
                "evidence_codes": [],
                "rationale": "Observed normalized weather and calculator results.",
            }

        trace = SimpleNamespace(
            session_history=[
                SimpleNamespace(content=[TextContent(text="Convert Oslo weather to Fahrenheit.")]),
                [
                    SimpleNamespace(
                        tool_call=SimpleNamespace(
                            name="get_current_weather", arguments={"city": "Oslo", "units": "metric"}
                        ),
                        tool_result=SimpleNamespace(
                            content='{"ok":true,"temp":7,"units":"metric"}', error=None
                        ),
                    ),
                    SimpleNamespace(
                        tool_call=SimpleNamespace(
                            name="calculator", arguments={"expression": "7 * 9 / 5 + 32"}
                        ),
                        tool_result=SimpleNamespace(content='{"ok":true,"value":"44.6"}', error=None),
                    ),
                ],
            ]
        )
        case = SimpleNamespace(
            name="slice-03",
            metadata={"expectation": {"orderedToolSequence": ["weather.get_current_weather", "calculator.calculate"]}},
        )
        evaluator = WeatherCalculatorJudgeEvaluator(provider=provider)

        with patch.object(evaluator, "_get_last_turn", return_value=trace):
            evaluator.evaluate(cast(Any, case))

        observed_calls = captured["observed_evidence"]["observed_calls"]
        self.assertEqual({"ok": True, "temp": 7, "units": "metric"}, observed_calls[0]["result"]["output"])
        self.assertNotIn("content", observed_calls[0]["result"])
        self.assertEqual({"ok": True, "value": "44.6"}, observed_calls[1]["result"]["output"])


if __name__ == "__main__":
    unittest.main()
