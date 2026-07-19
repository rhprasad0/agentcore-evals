"""Thin Strands Evals adapter for the frozen Week 10 structured judge."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from strands_evals.evaluators import Evaluator
from strands_evals.types.evaluation import EvaluationData, EvaluationOutput
from strands_evals.types.trace import EvaluationLevel, TextContent

from scripts.judge_weather_calculator import JudgeInputError, judge_case
from src.strands_evals_compatibility import parse_native_tool_result


_RUNTIME_TO_CONTRACT = {
    "get_current_weather": "weather.get_current_weather",
    "calculator": "calculator.calculate",
}


class WeatherCalculatorJudgeEvaluator(Evaluator[str, str]):
    """Expose the one frozen judge contract as a trace-level SDK evaluator."""

    evaluation_level = EvaluationLevel.TRACE_LEVEL

    def __init__(self, *, provider: Callable[[str], Mapping[str, Any]], name: str = "week10_custom_judge") -> None:
        super().__init__(name=name)
        self._provider = provider

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        if not isinstance(evaluation_case.metadata, dict) or not isinstance(evaluation_case.name, str):
            raise JudgeInputError("custom judge requires named cases with expectation metadata")
        expected = evaluation_case.metadata.get("expectation")
        if not isinstance(expected, Mapping):
            raise JudgeInputError(f"custom judge {evaluation_case.name} lacks expectation metadata")
        trace = self._get_last_turn(evaluation_case)
        observed_calls = []
        user_request = ""
        for entry in trace.session_history:
            if isinstance(entry, list):
                for execution in entry:
                    runtime_name = execution.tool_call.name
                    tool_id = _RUNTIME_TO_CONTRACT.get(runtime_name)
                    if tool_id is None:
                        raise JudgeInputError(f"unrecognized runtime tool {runtime_name!r}")
                    observed_calls.append(
                        {
                            "tool_id": tool_id,
                            "arguments": execution.tool_call.arguments,
                            "result": {
                                "output": parse_native_tool_result(execution.tool_result.content),
                                "error": execution.tool_result.error,
                            },
                        }
                    )
            elif not user_request and entry.content and isinstance(entry.content[0], TextContent):
                user_request = entry.content[0].text
        if not user_request:
            raise JudgeInputError(f"custom judge {evaluation_case.name} has no user request")
        verdict = judge_case(
            case_id=evaluation_case.name,
            expected=expected,
            evidence={"user_request": user_request, "observed_calls": observed_calls},
            provider=self._provider,
        )
        passed = verdict.label == "pass"
        return [
            EvaluationOutput(
                score=1.0 if passed else 0.0,
                test_pass=passed,
                label=f"{verdict.selection_verdict}/{verdict.parameter_verdict}",
                reason=verdict.rationale,
            )
        ]
