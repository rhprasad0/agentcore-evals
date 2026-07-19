"""Run the frozen Week 10 custom judge through local Strands Evals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from strands import Agent
from strands_evals import Case, Experiment, TracedHandler, eval_task
from strands_evals.evaluators import (
    ToolParameterAccuracyEvaluator,
    ToolSelectionAccuracyEvaluator,
)

from evals.evaluators.weather_calculator_judge import WeatherCalculatorJudgeEvaluator
from scripts.judge_weather_calculator import (
    HELDOUT_CASE_IDS,
    JUDGE_MODEL_ID,
    JudgeInputError,
    bedrock_provider,
    load_frozen_calibration_receipt,
    prompt_digest,
)
from src.agents.weather_specimen import build_mock_weather_tool, build_specimen_model
from src.contracts import validate_tool_portfolio
from src.deterministic_mocks import MockRegistry
from src.production_slice_dataset import SlicePaths, load_slice, validate_slice
from src.tools.calculator import calculator


MANIFEST_RELATIVE = Path("contracts/manifests/agents.weather/3.0.0.json")
LOCAL_TWO_TOOL_PROMPT = """Use current-weather only for a named current location. Use calculator only for explicit numeric arithmetic. For conversions, first obtain the weather value and then pass that exact value into calculator. Stop after a weather failure. Ask for a location when the request does not name one."""


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise JudgeInputError(f"cannot load {path}: {error}") from error
    if not all(isinstance(row, dict) for row in rows):
        raise JudgeInputError(f"{path} must contain only JSON objects")
    return rows


def build_heldout_cases(repo_root: Path) -> list[Case]:
    """Construct exactly the frozen six behavioral rows before model construction."""

    paths = SlicePaths.from_repo_root(repo_root)
    snapshot = load_slice(paths)
    if issues := validate_slice(snapshot, paths):
        raise JudgeInputError(f"production slice is invalid: {issues[0].path}: {issues[0].message}")
    gold_rows = _jsonl(paths.gold_path)
    expected_ids = [f"slice-{index:02}" for index in range(1, 7)]
    eligible_gold = [row for row in gold_rows if row.get("automated_judge_eligible") is True]
    if [row.get("case_id") for row in eligible_gold] != expected_ids:
        raise JudgeInputError("heldout gold rows are not the exact six eligible cases")
    draft_by_case_id = {row.get("goldDraft", {}).get("caseId"): row for row in snapshot.rows}
    if set(draft_by_case_id) != HELDOUT_CASE_IDS | {"slice-07", "slice-08"}:
        raise JudgeInputError("production slice draft does not account for all eight frozen IDs")
    cases: list[Case] = []
    for gold in eligible_gold:
        case_id = gold["case_id"]
        draft = draft_by_case_id.get(case_id)
        if not isinstance(draft, dict):
            raise JudgeInputError(f"missing draft row for {case_id}")
        example_id = draft.get("exampleId")
        prompt = draft.get("prompt")
        if not isinstance(example_id, str) or not isinstance(prompt, str):
            raise JudgeInputError(f"draft row {case_id} lacks exampleId or prompt")
        cases.append(
            Case(
                name=case_id,
                session_id=f"week-10-predeployment:{case_id}",
                input=prompt,
                metadata={
                    "example_id": example_id,
                    "automated_judge_eligible": True,
                    "expectation": gold["expectation"],
                },
            )
        )
    return cases


def summarize_reports(
    reports: list[Any], case_ids: list[str], not_applicable: dict[str, tuple[str, ...]]
) -> list[dict[str, Any]]:
    """Group Strands' evaluator-major flattened report back into case rows."""

    outcomes = {case_id: {"caseId": case_id, "evaluators": {}} for case_id in case_ids}
    for report in reports:
        for case, score, test_pass, details in zip(
            report.cases, report.scores, report.test_passes, report.detailed_results, strict=True
        ):
            case_id = case.get("name")
            evaluator = case.get("evaluator")
            if case_id not in outcomes or not isinstance(evaluator, str):
                raise JudgeInputError("Strands report has an unexpected case or evaluator")
            first_detail = details[0] if details else None
            label = getattr(first_detail, "label", None)
            if evaluator == "week10_custom_judge" and not isinstance(label, str):
                raise JudgeInputError(f"custom judge {case_id} has no verdict")
            outcome = {
                "score": score,
                "testPass": test_pass,
                "label": label,
            }
            rationale = getattr(first_detail, "reason", None)
            if evaluator == "week10_custom_judge" and isinstance(rationale, str):
                outcome["rationale"] = rationale
            outcomes[case_id]["evaluators"][evaluator] = outcome
    for case_id, evaluator_names in not_applicable.items():
        for evaluator in evaluator_names:
            outcomes[case_id]["evaluators"][evaluator] = {
                "score": None,
                "testPass": None,
                "label": "not_applicable",
            }
    return [outcomes[case_id] for case_id in case_ids]


def _case_name(case: Case) -> str:
    if not isinstance(case.name, str):
        raise JudgeInputError("heldout case lacks a name")
    return case.name


def _requires_tools(case: Case) -> bool:
    metadata = case.metadata
    expectation = metadata.get("expectation") if isinstance(metadata, dict) else None
    if not isinstance(expectation, dict):
        raise JudgeInputError(f"{_case_name(case)} lacks expectation metadata")
    return bool(expectation.get("orderedToolSequence"))


def run_heldout_experiment(repo_root: Path, calibration_receipt: Path) -> dict[str, Any]:
    """Run all six frozen behavioral rows after the caller authorizes Bedrock use."""

    frozen_calibration = load_frozen_calibration_receipt(calibration_receipt)
    cases = build_heldout_cases(repo_root)
    registry = MockRegistry.from_repo_root(repo_root)
    model = build_specimen_model()
    handler = TracedHandler()

    @eval_task(handler)
    def local_task(case: Case) -> Agent:
        metadata = case.metadata or {}
        example_id = metadata.get("example_id")
        if not isinstance(example_id, str):
            raise JudgeInputError(f"{case.name} lacks example ID")
        tools = validate_tool_portfolio(
            [build_mock_weather_tool(registry, example_id), calculator],
            manifest_path=repo_root / MANIFEST_RELATIVE,
        )
        return Agent(
            model=model,
            system_prompt=LOCAL_TWO_TOOL_PROMPT,
            tools=tools,
            callback_handler=None,
            trace_attributes={"session.id": case.session_id, "gen_ai.conversation.id": case.session_id},
        )

    evaluator_names = ("week10_builtin_tool_selection", "week10_builtin_tool_parameters")
    tool_cases = [case for case in cases if _requires_tools(case)]
    no_tool_cases = [case for case in cases if case not in tool_cases]
    reports = [
        Experiment(
            cases=tool_cases,
            evaluators=[
                WeatherCalculatorJudgeEvaluator(provider=bedrock_provider),
                ToolSelectionAccuracyEvaluator(model=JUDGE_MODEL_ID, name=evaluator_names[0]),
                ToolParameterAccuracyEvaluator(model=JUDGE_MODEL_ID, name=evaluator_names[1]),
            ],
        ).run_evaluations(local_task)
    ]
    if no_tool_cases:
        reports.append(
            Experiment(
                cases=no_tool_cases,
                evaluators=[WeatherCalculatorJudgeEvaluator(provider=bedrock_provider)],
            ).run_evaluations(local_task)
        )
    outcomes = summarize_reports(
        reports,
        [_case_name(case) for case in cases],
        {_case_name(case): evaluator_names for case in no_tool_cases},
    )
    return {
        "judgeModelId": JUDGE_MODEL_ID,
        "judgePromptSha256": prompt_digest(),
        "calibrationPromptSha256": frozen_calibration["promptSha256"],
        "caseIds": [_case_name(case) for case in cases],
        "outcomes": outcomes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-live-bedrock", action="store_true")
    parser.add_argument("--calibration-receipt", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if not arguments.confirm_live_bedrock:
        parser.error("--confirm-live-bedrock is required for the all-six local evaluation")
    print(
        json.dumps(
            run_heldout_experiment(Path(__file__).resolve().parents[1], arguments.calibration_receipt),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
