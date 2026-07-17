"""Public-safe repeatability comparison for two Week 7 projection runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.telemetry_normalization import canonical_projection_bytes


class RunComparisonError(ValueError):
    """Two runs cannot be compared under the same experiment identity."""


def compare_projection_runs(left_directory: Path, right_directory: Path) -> dict[str, Any]:
    """Compare case status, exact tool sequence, and canonical projection separately."""

    left_manifest = _load_object(left_directory / "run-manifest.json")
    right_manifest = _load_object(right_directory / "run-manifest.json")
    experiment_id = left_manifest.get("experimentId")
    if experiment_id != right_manifest.get("experimentId"):
        raise RunComparisonError("runs must share one experimentId")
    left_run_id = left_manifest.get("runId")
    right_run_id = right_manifest.get("runId")
    if left_run_id == right_run_id:
        raise RunComparisonError("repeatability comparison requires distinct runId values")
    left_summary = _load_object(left_directory / "summary.json")
    right_summary = _load_object(right_directory / "summary.json")
    left_cases = left_summary.get("cases")
    right_cases = right_summary.get("cases")
    if not isinstance(left_cases, list) or not isinstance(right_cases, list):
        raise RunComparisonError("both summaries must contain case arrays")
    left_ids = [case.get("exampleId") for case in left_cases if isinstance(case, dict)]
    right_ids = [case.get("exampleId") for case in right_cases if isinstance(case, dict)]
    if left_ids != right_ids or len(left_ids) != len(left_cases) or len(right_ids) != len(right_cases):
        raise RunComparisonError("runs must contain the same cases in projection order")
    rows = []
    status_matches = 0
    compared = 0
    equal_sequences = 0
    equal_projections = 0
    for left_case, right_case in zip(left_cases, right_cases, strict=True):
        example_id = left_case["exampleId"]
        left_status = left_case.get("status")
        right_status = right_case.get("status")
        status_equal = left_status == right_status
        status_matches += int(status_equal)
        tool_sequence_equal: bool | None = None
        projection_equal: bool | None = None
        if left_status == right_status == "completed":
            compared += 1
            left_trace = _load_object(
                left_directory / "cases" / example_id / "canonical-trace.json"
            )
            right_trace = _load_object(
                right_directory / "cases" / example_id / "canonical-trace.json"
            )
            tool_sequence_equal = _tool_sequence(left_trace) == _tool_sequence(right_trace)
            projection_equal = canonical_projection_bytes(left_trace) == canonical_projection_bytes(
                right_trace
            )
            equal_sequences += int(tool_sequence_equal)
            equal_projections += int(projection_equal)
        rows.append(
            {
                "exampleId": example_id,
                "leftStatus": left_status,
                "rightStatus": right_status,
                "statusEqual": status_equal,
                "toolSequenceEqual": tool_sequence_equal,
                "canonicalProjectionEqual": projection_equal,
            }
        )
    return {
        "schemaVersion": "1.0.0",
        "experimentId": experiment_id,
        "leftRunId": left_run_id,
        "rightRunId": right_run_id,
        "counts": {
            "totalCases": len(rows),
            "statusMatches": status_matches,
            "comparedCases": compared,
            "equalToolSequences": equal_sequences,
            "equalCanonicalProjections": equal_projections,
        },
        "cases": rows,
    }


def _tool_sequence(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    spans = trace.get("spans")
    if not isinstance(spans, list):
        raise RunComparisonError("canonical trace spans must be an array")
    return [
        {
            "observedToolName": span.get("observedToolName"),
            "tool": span.get("tool"),
            "arguments": span.get("arguments"),
        }
        for span in sorted(spans, key=lambda item: item["sequence"])
        if isinstance(span, Mapping) and span.get("operationName") == "execute_tool"
    ]


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunComparisonError(f"cannot load {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise RunComparisonError(f"{path.name} must contain an object")
    return value
