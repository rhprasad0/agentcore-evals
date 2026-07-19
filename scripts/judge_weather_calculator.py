"""Bounded Week 10 custom judge and calibration entry point."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel
from strands import Agent

from src.production_slice_dataset import SlicePaths, load_slice, validate_slice


REPO_ROOT = Path(__file__).resolve().parents[1]
HELDOUT_CASE_IDS = frozenset(
    {"slice-01", "slice-02", "slice-03", "slice-04", "slice-05", "slice-06"}
)
HELDOUT_EXAMPLE_IDS = frozenset(
    {"tc-0001", "tc-0021", "tc-0006", "tc-0097", "tc-0098", "tc-0073"}
)
FROZEN_GOLD_RELATIVE = Path("datasets/labels/production-slice-8-human.jsonl")
CALIBRATION_RELATIVE = Path("datasets/labels/week-10-judge-calibration.jsonl")
JUDGE_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
JUDGE_RUBRIC_VERSION = "v1"
JUDGE_RUBRIC = """Assess only the supplied tool-call evidence against the supplied expectation.
Selection passes only when required calls occur in order, prohibited calls do not occur,
and a failure stops later forbidden tools. Parameters pass only when observed arguments
meet the supplied constraints. Use not_applicable only when selection fails before a
parameter judgment can be meaningful. Do not infer missing evidence. Return concise,
inspectable evidence codes and a rationale under 240 characters. evidence_codes must
contain only: wrong_selection, wrong_parameter, wrong_order, missing_call, extra_call,
stop_after_failure, lineage, no_tool. Return [] when both verdicts pass."""
ALLOWED_CODES = {
    "wrong_selection",
    "wrong_parameter",
    "wrong_order",
    "missing_call",
    "extra_call",
    "stop_after_failure",
    "lineage",
    "no_tool",
}


class JudgeInputError(ValueError):
    """Judge evidence or calibration data violates the frozen contract."""


class JudgeOutputError(ValueError):
    """A provider response does not match the bounded verdict contract."""


@dataclass(frozen=True)
class CalibrationVector:
    vector_id: str
    source_example_id: str
    expected_label: str
    document: Mapping[str, Any]


@dataclass(frozen=True)
class JudgeVerdict:
    case_id: str
    selection_verdict: Literal["pass", "fail"]
    parameter_verdict: Literal["pass", "fail", "not_applicable"]
    evidence_codes: tuple[str, ...]
    rationale: str

    @property
    def label(self) -> str:
        return "pass" if self.selection_verdict == "pass" and self.parameter_verdict in {"pass", "not_applicable"} else "fail"


class _ProviderVerdict(BaseModel):
    case_id: str
    selection_verdict: Literal["pass", "fail"]
    parameter_verdict: Literal["pass", "fail", "not_applicable"]
    evidence_codes: list[str]
    rationale: str


def _expected_label(document: Mapping[str, Any]) -> str:
    verdict = document.get("expected_verdict")
    if not isinstance(verdict, Mapping):
        raise JudgeInputError("expected_verdict must be an object")
    selection = verdict.get("selection_verdict")
    parameters = verdict.get("parameter_verdict")
    if selection not in {"pass", "fail"}:
        raise JudgeInputError("expected_verdict.selection_verdict must be pass or fail")
    if parameters not in {"pass", "fail", "not_applicable"}:
        raise JudgeInputError("expected_verdict.parameter_verdict is invalid")
    return "pass" if selection == "pass" and parameters in {"pass", "not_applicable"} else "fail"


def load_calibration_vectors(path: Path) -> tuple[CalibrationVector, ...]:
    """Load the fixed, disjoint six-vector calibration pack."""

    try:
        documents = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise JudgeInputError(f"cannot load calibration pack: {error}") from error
    vectors: list[CalibrationVector] = []
    for index, document in enumerate(documents, start=1):
        if not isinstance(document, Mapping):
            raise JudgeInputError(f"calibration line {index} must be an object")
        vector_id = document.get("vector_id")
        source_example_id = document.get("source_example_id")
        if not isinstance(vector_id, str) or not isinstance(source_example_id, str):
            raise JudgeInputError(f"calibration line {index} has invalid identifiers")
        vectors.append(CalibrationVector(vector_id, source_example_id, _expected_label(document), document))
    if [vector.vector_id for vector in vectors] != [f"cal-{index:02}" for index in range(1, 7)]:
        raise JudgeInputError("calibration vector IDs must be cal-01 through cal-06 in order")
    if {vector.source_example_id for vector in vectors} & HELDOUT_EXAMPLE_IDS:
        raise JudgeInputError("calibration source IDs must not name heldout examples")
    labels = [vector.expected_label for vector in vectors]
    if labels.count("pass") != 3 or labels.count("fail") != 3:
        raise JudgeInputError("calibration pack must contain three pass and three fail vectors")
    return tuple(vectors)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def prompt_digest() -> str:
    return sha256(JUDGE_RUBRIC.encode("utf-8")).hexdigest()


def _judge_prompt(case_id: str, expected: Mapping[str, Any], evidence: Mapping[str, Any]) -> str:
    payload = {"case_id": case_id, "expectation": expected, "observed_evidence": evidence}
    return f"{JUDGE_RUBRIC}\n\nEvidence:\n{_canonical_json(payload)}"


def parse_verdict(case_id: str, document: Mapping[str, Any]) -> JudgeVerdict:
    try:
        parsed = _ProviderVerdict.model_validate(document)
    except Exception as error:
        raise JudgeOutputError(f"invalid provider verdict: {error.__class__.__name__}") from error
    if parsed.case_id != case_id:
        raise JudgeOutputError("provider verdict case_id does not match request")
    codes = tuple(parsed.evidence_codes)
    if len(codes) > 4 or any(code not in ALLOWED_CODES for code in codes):
        raise JudgeOutputError("provider verdict has invalid evidence codes")
    rationale = parsed.rationale.strip()
    if not rationale or len(rationale) > 240:
        raise JudgeOutputError("provider rationale must be 1-240 characters")
    return JudgeVerdict(parsed.case_id, parsed.selection_verdict, parsed.parameter_verdict, codes, rationale)


def judge_evidence(
    *, case_id: str, expected: Mapping[str, Any], evidence: Mapping[str, Any], provider: Callable[[str], Mapping[str, Any]]
) -> JudgeVerdict:
    """Evaluate one already-authorized evidence object through an injected provider."""

    return parse_verdict(case_id, provider(_judge_prompt(case_id, expected, evidence)))


def judge_case(
    *, case_id: str, expected: Mapping[str, Any], evidence: Mapping[str, Any], provider: Callable[[str], Mapping[str, Any]]
) -> JudgeVerdict:
    """Reject non-behavior rows before the provider can be touched."""

    if case_id not in HELDOUT_CASE_IDS:
        raise JudgeInputError(f"case {case_id!r} is not eligible for the Week 10 judge")
    return judge_evidence(case_id=case_id, expected=expected, evidence=evidence, provider=provider)


def bedrock_provider(prompt: str) -> Mapping[str, Any]:
    """Invoke the one pinned provider only after an explicit CLI confirmation."""

    result = Agent(model=JUDGE_MODEL_ID, callback_handler=None)(prompt, structured_output_model=_ProviderVerdict)
    return result.structured_output.model_dump()


def run_dry_run(repo_root: Path) -> dict[str, Any]:
    """Account for every frozen row before any provider can be constructed."""

    path = repo_root / FROZEN_GOLD_RELATIVE
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise JudgeInputError(f"cannot load frozen gold: {error}") from error
    expected_ids = [f"slice-{index:02}" for index in range(1, 9)]
    if [row.get("case_id") for row in rows] != expected_ids:
        raise JudgeInputError("frozen gold case IDs must be slice-01 through slice-08 in order")
    eligible = [row["case_id"] for row in rows if row.get("automated_judge_eligible") is True]
    excluded = [row["case_id"] for row in rows if row.get("automated_judge_eligible") is not True]
    if eligible != sorted(HELDOUT_CASE_IDS) or excluded != ["slice-07", "slice-08"]:
        raise JudgeInputError("frozen eligibility split differs from the Week 10 contract")
    paths = SlicePaths.from_repo_root(repo_root)
    snapshot = load_slice(paths)
    if issues := validate_slice(snapshot, paths):
        raise JudgeInputError(f"production slice is invalid: {issues[0].path}: {issues[0].message}")
    drafts = {row["goldDraft"]["caseId"]: row for row in snapshot.rows}
    rendered: dict[str, str] = {}
    for row in rows:
        case_id = row["case_id"]
        if case_id not in HELDOUT_CASE_IDS:
            continue
        draft = drafts.get(case_id)
        prompt = draft.get("prompt") if isinstance(draft, Mapping) else None
        expected = row.get("expectation")
        _validate_dry_run_request(case_id, prompt, expected)
        request = _judge_prompt(
            case_id,
            expected,
            {"user_request": prompt, "observed_calls": []},
        )
        rendered[case_id] = sha256(request.encode("utf-8")).hexdigest()
    if list(rendered) != eligible:
        raise JudgeInputError("dry run did not render every eligible case")
    return {
        "eligibleCaseIds": eligible,
        "excludedCaseIds": excluded,
        "renderedCaseIds": list(rendered),
        "renderedRequestSha256": rendered,
        "providerTouched": False,
    }


def _validate_dry_run_request(case_id: str, prompt: Any, expected: Any) -> None:
    """Validate a model-visible request shape without inventing an observed trajectory."""

    if not isinstance(prompt, str) or not prompt.strip() or not isinstance(expected, Mapping):
        raise JudgeInputError(f"dry run {case_id} lacks prompt or expectation")
    sequence = expected.get("orderedToolSequence")
    tools = expected.get("toolIds")
    constraints = expected.get("argConstraints")
    if (
        not isinstance(sequence, list)
        or not all(isinstance(tool, str) for tool in sequence)
        or not isinstance(tools, list)
        or not all(isinstance(tool, str) for tool in tools)
        or not isinstance(constraints, list)
        or any(tool not in tools for tool in sequence)
    ):
        raise JudgeInputError(f"dry run {case_id} has invalid normalized expectation")


def run_calibration(repo_root: Path, provider: Callable[[str], Mapping[str, Any]] = bedrock_provider) -> dict[str, Any]:
    """Run the single candidate judge over the fixed calibration pack."""

    vectors = load_calibration_vectors(repo_root / CALIBRATION_RELATIVE)
    outcomes = []
    for vector in vectors:
        verdict = judge_evidence(
            case_id=vector.vector_id,
            expected=vector.document["expected"],
            evidence={"user_request": vector.document["user_request"], "observed_calls": vector.document["observed_calls"]},
            provider=provider,
        )
        outcomes.append({"vectorId": vector.vector_id, "expectedLabel": vector.expected_label, "actualLabel": verdict.label, "match": verdict.label == vector.expected_label, "label": f"{verdict.selection_verdict}/{verdict.parameter_verdict}"})
    return {"rubricVersion": JUDGE_RUBRIC_VERSION, "promptSha256": prompt_digest(), "modelId": JUDGE_MODEL_ID, "outcomes": outcomes}


def load_frozen_calibration_receipt(path: Path) -> dict[str, Any]:
    """Accept only a passed receipt for the current pinned judge configuration."""

    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise JudgeInputError(f"cannot load calibration receipt: {error}") from error
    outcomes = receipt.get("outcomes") if isinstance(receipt, dict) else None
    if (
        not isinstance(outcomes, list)
        or len(outcomes) != 6
        or receipt.get("modelId") != JUDGE_MODEL_ID
        or receipt.get("promptSha256") != prompt_digest()
        or any(not isinstance(outcome, dict) or outcome.get("match") is not True for outcome in outcomes)
        or [outcome.get("vectorId") for outcome in outcomes] != [f"cal-{index:02}" for index in range(1, 7)]
    ):
        raise JudgeInputError("calibration receipt is not a passed freeze for the current judge")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--calibrate", action="store_true")
    parser.add_argument("--confirm-live-bedrock", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.calibrate and not arguments.confirm_live_bedrock:
        parser.error("--confirm-live-bedrock is required for calibration")
    receipt = run_dry_run(REPO_ROOT) if arguments.dry_run else run_calibration(REPO_ROOT)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
