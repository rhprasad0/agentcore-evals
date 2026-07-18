"""Fail-closed fixture replay for the Week 8 offline Stage B evaluator lane."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from strands_evals import Case, Experiment

from evals.adapters.cases import CaseAdapterError, build_projection_cases
from evals.evaluators.gates import (
    ArgConstraintGate,
    ExpectedToolsGate,
    FailureBehaviorGate,
    NoToolGate,
)
from evals.fixtures.manifest import FixtureManifestError, validate_fixture_manifest


FIXTURE_ROOT_RELATIVE = Path("evals/fixtures/weather-only-62")
PROJECTION_RELATIVE = Path("datasets/projections/weather-only-62.json")
ARTIFACT_PREFIX = "evals/fixtures/weather-only-62"
EXPECTED_EXPERIMENT_ID = (
    "sha256:44a9f913a720759748d57647f002b0e924d39b38b65a2fdfbe713774bfc2cca5"
)


class HarnessEvidenceError(ValueError):
    """Committed Stage B evidence cannot safely be replayed."""


@dataclass(frozen=True)
class InstrumentErrorReceipt:
    """An explicitly recorded collection failure, never an agent verdict."""

    example_id: str
    kind: str
    message: str


@dataclass(frozen=True)
class StageBEvidence:
    """Validated fixture data split into replayable traces and instrument receipts."""

    eligible_cases: tuple[Case, ...]
    traces_by_case_name: Mapping[str, Mapping[str, Any]]
    instrument_errors: tuple[InstrumentErrorReceipt, ...]
    accounted_case_ids: tuple[str, ...]
    fixture_set_id: str
    experiment_id: str


@dataclass(frozen=True)
class StageBResult:
    """Mechanical gate results paired with the evidence they actually evaluated."""

    report: Any
    eligible_case_count: int
    instrument_errors: tuple[InstrumentErrorReceipt, ...]
    fixture_set_id: str
    experiment_id: str


def load_stage_b_evidence(
    repo_root: Path,
    *,
    fixture_root: Path | None = None,
) -> StageBEvidence:
    """Preflight committed evidence before creating any runnable evaluation case."""

    root = repo_root.resolve()
    selected_fixture_root = (fixture_root or root / FIXTURE_ROOT_RELATIVE).resolve()
    projection_path = root / PROJECTION_RELATIVE
    try:
        manifest = validate_fixture_manifest(
            selected_fixture_root / "manifest.json",
            projection_path=projection_path,
            artifact_root=selected_fixture_root,
            artifact_prefix=ARTIFACT_PREFIX,
            expected_experiment_id=EXPECTED_EXPERIMENT_ID,
            repo_root=root,
        )
        all_cases = build_projection_cases(projection_path, repo_root=root)
    except (CaseAdapterError, FixtureManifestError) as error:
        raise HarnessEvidenceError(str(error)) from error

    cases_by_name = {case.name: case for case in all_cases}
    expected_ids = tuple(manifest["expectedCaseIds"])
    if set(cases_by_name) != set(expected_ids) or len(cases_by_name) != len(expected_ids):
        raise HarnessEvidenceError("fixture case IDs do not exactly match projection cases")

    eligible_cases: list[Case] = []
    traces_by_case_name: dict[str, Mapping[str, Any]] = {}
    instrument_errors: list[InstrumentErrorReceipt] = []
    accounted_ids: list[str] = []
    for entry in manifest["fixtures"]:
        example_id = entry["exampleId"]
        case = cases_by_name.get(example_id)
        if case is None:
            raise HarnessEvidenceError(f"fixture {example_id} has no projection case")
        if not isinstance(case.name, str):
            raise HarnessEvidenceError(f"fixture {example_id} has an unnamed projection case")
        accounted_ids.append(example_id)
        relative_path = Path(entry["path"].removeprefix(f"{ARTIFACT_PREFIX}/"))
        try:
            document = json.loads(
                (selected_fixture_root / relative_path).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise HarnessEvidenceError(
                f"cannot load prevalidated fixture {example_id}: {error.__class__.__name__}"
            ) from error
        if entry["status"] == "canonical-trace":
            if not isinstance(document, Mapping):
                raise HarnessEvidenceError(f"fixture {example_id} trace must be a mapping")
            metadata = dict(case.metadata or {})
            metadata["fixture"] = {
                "exampleId": example_id,
                "fixtureSetId": manifest["fixtureSetId"],
                "sha256": entry["sha256"],
                "status": entry["status"],
            }
            eligible_cases.append(case.model_copy(update={"metadata": metadata}))
            traces_by_case_name[case.name] = document
        elif entry["status"] == "instrument-error":
            if not isinstance(document, Mapping):
                raise HarnessEvidenceError(f"fixture {example_id} error receipt must be a mapping")
            instrument_errors.append(
                InstrumentErrorReceipt(
                    example_id=example_id,
                    kind=document["kind"],
                    message=document["message"],
                )
            )
        else:
            raise HarnessEvidenceError(f"fixture {example_id} has unknown status")

    if tuple(accounted_ids) != expected_ids:
        raise HarnessEvidenceError("fixture replay order does not match manifest case IDs")
    return StageBEvidence(
        eligible_cases=tuple(eligible_cases),
        traces_by_case_name=traces_by_case_name,
        instrument_errors=tuple(instrument_errors),
        accounted_case_ids=tuple(accounted_ids),
        fixture_set_id=manifest["fixtureSetId"],
        experiment_id=manifest["experimentId"],
    )


def build_stage_b_experiment(evidence: StageBEvidence) -> Experiment:
    """Create the local deterministic evaluator bundle for canonical traces only."""

    if not evidence.eligible_cases:
        raise HarnessEvidenceError("Stage B requires at least one canonical trace")
    return Experiment(
        cases=list(evidence.eligible_cases),
        evaluators=[
            ExpectedToolsGate(),
            ArgConstraintGate(),
            FailureBehaviorGate(),
            NoToolGate(),
        ],
    )


def run_stage_b(
    repo_root: Path,
    *,
    fixture_root: Path | None = None,
) -> StageBResult:
    """Replay prevalidated fixture evidence through local deterministic gates."""

    evidence = load_stage_b_evidence(repo_root, fixture_root=fixture_root)
    experiment = build_stage_b_experiment(evidence)

    def replay_fixture(case: Case) -> dict[str, Any]:
        if not isinstance(case.name, str):
            raise HarnessEvidenceError("Stage B received an unnamed case")
        trace = evidence.traces_by_case_name.get(case.name)
        if trace is None:
            raise HarnessEvidenceError(f"Stage B has no fixture trace for {case.name}")
        response = trace.get("response")
        spans = trace.get("spans")
        if not isinstance(response, str) or not isinstance(spans, list):
            raise HarnessEvidenceError(f"Stage B fixture {case.name} lost validated trace fields")
        return {"output": response, "trajectory": spans}

    report = experiment.run_evaluations(replay_fixture)
    return StageBResult(
        report=report,
        eligible_case_count=len(evidence.eligible_cases),
        instrument_errors=evidence.instrument_errors,
        fixture_set_id=evidence.fixture_set_id,
        experiment_id=evidence.experiment_id,
    )
