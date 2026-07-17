"""Resumable, case-isolated execution for one dataset projection run."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.run_summary import summarize_projection_run


class ProjectionRunnerError(ValueError):
    """A projection run cannot preserve case isolation or resumability."""


def run_projection_batch(
    rows: Sequence[Mapping[str, Any]],
    *,
    manifest: dict[str, Any],
    run_store: Path,
    projection: Mapping[str, str],
    execute_case: Callable[[Mapping[str, Any], str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Execute unfinished cases and rebuild aggregate artifacts in source order."""

    if not rows:
        raise ProjectionRunnerError("projection rows must be non-empty")
    run_id = manifest.get("runId")
    experiment_id = manifest.get("experimentId")
    if not isinstance(run_id, str) or not isinstance(experiment_id, str):
        raise ProjectionRunnerError("manifest must include runId and experimentId")
    run_directory = run_store / run_id
    run_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = run_directory / "run-manifest.json"
    _write_json_atomic(manifest_path, manifest)
    outcomes: list[dict[str, Any]] = []
    canonical_traces: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        example_id = row.get("exampleId")
        family = row.get("scenarioFamily")
        if not isinstance(example_id, str) or example_id in seen_ids:
            raise ProjectionRunnerError(f"rows[{index}].exampleId must be a unique string")
        if not isinstance(family, str) or not family:
            raise ProjectionRunnerError(f"rows[{index}].scenarioFamily must be non-empty")
        seen_ids.add(example_id)
        case_directory = run_directory / "cases" / example_id
        outcome_path = case_directory / "outcome.json"
        if outcome_path.exists():
            outcome = _load_case_outcome(outcome_path, case_directory, example_id, family)
        else:
            session_id = f"{run_id}:{example_id}"
            observed = dict(execute_case(row, session_id))
            outcome = _persist_case_outcome(
                observed,
                case_directory=case_directory,
                example_id=example_id,
                family=family,
            )
        outcomes.append(outcome)
        if outcome["trace"] is not None:
            canonical_traces.append(outcome["trace"])
    aggregate_path = run_directory / "canonical-traces.jsonl"
    _write_jsonl_atomic(aggregate_path, canonical_traces)
    summary = summarize_projection_run(
        outcomes,
        experiment_id=experiment_id,
        run_id=run_id,
        projection=projection,
    )
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "run-summary.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(summary),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ProjectionRunnerError(f"run summary schema error at {location}: {error.message}")
    _write_json_atomic(run_directory / "summary.json", summary)
    manifest["outputs"] = {
        "status": "completed",
        "runDirectory": f"datasets/runs/{run_id}",
        "canonicalTracePath": f"datasets/runs/{run_id}/canonical-traces.jsonl",
        "error": None,
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _persist_case_outcome(
    observed: Mapping[str, Any],
    *,
    case_directory: Path,
    example_id: str,
    family: str,
) -> dict[str, Any]:
    status = observed.get("status")
    trace = observed.get("trace")
    source = observed.get("source")
    error = observed.get("error")
    if status == "completed":
        if not isinstance(trace, dict) or not isinstance(source, dict) or error is not None:
            raise ProjectionRunnerError(
                f"completed case {example_id} requires source and trace without error"
            )
        _write_json_atomic(case_directory / "raw" / "strands-inline.json", source)
        _write_json_atomic(case_directory / "canonical-trace.json", trace)
        metadata = {
            "schemaVersion": "1.0.0",
            "exampleId": example_id,
            "scenarioFamily": family,
            "status": "completed",
            "errorKind": None,
        }
    elif status == "instrument-error":
        if trace is not None or not isinstance(error, Mapping):
            raise ProjectionRunnerError(
                f"instrument-error case {example_id} requires error and no trace"
            )
        kind = error.get("kind")
        message = error.get("message")
        if not isinstance(kind, str) or not kind or not isinstance(message, str) or not message:
            raise ProjectionRunnerError(f"instrument-error case {example_id} has invalid error")
        if isinstance(source, dict):
            _write_json_atomic(case_directory / "raw" / "strands-inline.json", source)
        _write_json_atomic(
            case_directory / "instrument-error.json",
            {"kind": kind, "message": message[:500]},
        )
        metadata = {
            "schemaVersion": "1.0.0",
            "exampleId": example_id,
            "scenarioFamily": family,
            "status": "instrument-error",
            "errorKind": kind,
        }
    else:
        raise ProjectionRunnerError(f"case {example_id} has unsupported status {status!r}")
    _write_json_atomic(case_directory / "outcome.json", metadata)
    return {
        "exampleId": example_id,
        "scenarioFamily": family,
        "status": metadata["status"],
        "trace": trace,
        "errorKind": metadata["errorKind"],
    }


def _load_case_outcome(
    outcome_path: Path,
    case_directory: Path,
    example_id: str,
    family: str,
) -> dict[str, Any]:
    metadata = json.loads(outcome_path.read_text(encoding="utf-8"))
    if metadata.get("exampleId") != example_id or metadata.get("scenarioFamily") != family:
        raise ProjectionRunnerError(f"resumed case identity drift for {example_id}")
    status = metadata.get("status")
    if status == "completed":
        trace_path = case_directory / "canonical-trace.json"
        if not trace_path.is_file():
            raise ProjectionRunnerError(f"resumed completed case {example_id} has no trace")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        error_kind = None
    elif status == "instrument-error":
        if not (case_directory / "instrument-error.json").is_file():
            raise ProjectionRunnerError(f"resumed instrument-error case {example_id} has no error")
        trace = None
        error_kind = metadata.get("errorKind")
        if not isinstance(error_kind, str) or not error_kind:
            raise ProjectionRunnerError(f"resumed instrument-error case {example_id} has no errorKind")
    else:
        raise ProjectionRunnerError(f"resumed case {example_id} has invalid status")
    return {
        "exampleId": example_id,
        "scenarioFamily": family,
        "status": status,
        "trace": trace,
        "errorKind": error_kind,
    }


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl_atomic(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
            for value in values
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
