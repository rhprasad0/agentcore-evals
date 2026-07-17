"""Public-safe summaries for metered projection runs."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


class RunSummaryError(ValueError):
    """Case outcomes cannot be summarized without leaking or ambiguity."""


def summarize_projection_run(
    outcomes: Sequence[Mapping[str, Any]],
    *,
    experiment_id: str,
    run_id: str,
    projection: Mapping[str, str],
) -> dict[str, Any]:
    """Aggregate trace mechanics while excluding prompts, arguments, and prose."""

    if not outcomes:
        raise RunSummaryError("outcomes must be non-empty")
    case_rows: list[dict[str, Any]] = []
    error_kinds: Counter[str] = Counter()
    result_kinds: Counter[str] = Counter()
    family_rows: dict[str, list[dict[str, Any]]] = {}
    total_tool_calls = 0
    reasoning_present = 0
    reasoning_null = 0
    completed = 0
    instrument_errors = 0
    seen_ids: set[str] = set()
    for index, outcome in enumerate(outcomes):
        example_id = outcome.get("exampleId")
        family = outcome.get("scenarioFamily")
        status = outcome.get("status")
        if not isinstance(example_id, str) or example_id in seen_ids:
            raise RunSummaryError(f"outcomes[{index}].exampleId must be a unique string")
        if not isinstance(family, str) or not family:
            raise RunSummaryError(f"outcomes[{index}].scenarioFamily must be non-empty")
        if status not in {"completed", "instrument-error"}:
            raise RunSummaryError(f"outcomes[{index}].status is unsupported: {status!r}")
        seen_ids.add(example_id)
        trace = outcome.get("trace")
        error_kind = outcome.get("errorKind")
        tool_calls = 0
        present = 0
        null = 0
        observed_result_kinds: Counter[str] = Counter()
        if status == "completed":
            completed += 1
            if not isinstance(trace, Mapping):
                raise RunSummaryError(f"completed outcome {example_id} must include a trace")
            if error_kind is not None:
                raise RunSummaryError(f"completed outcome {example_id} cannot include errorKind")
            spans = trace.get("spans")
            if not isinstance(spans, list):
                raise RunSummaryError(f"completed outcome {example_id} trace.spans must be an array")
            for span in spans:
                if not isinstance(span, Mapping) or span.get("operationName") != "execute_tool":
                    continue
                tool_calls += 1
                if span.get("selectionReasoning") is None:
                    null += 1
                else:
                    present += 1
                result = span.get("result")
                if not isinstance(result, Mapping) or not isinstance(result.get("ok"), bool):
                    raise RunSummaryError(f"completed outcome {example_id} has invalid tool result")
                kind = "success" if result["ok"] else result.get("failureKind")
                if not isinstance(kind, str) or not kind:
                    raise RunSummaryError(f"completed outcome {example_id} has no result kind")
                observed_result_kinds[kind] += 1
        else:
            instrument_errors += 1
            if trace is not None:
                raise RunSummaryError(f"instrument-error outcome {example_id} cannot include a trace")
            if not isinstance(error_kind, str) or not error_kind:
                raise RunSummaryError(f"instrument-error outcome {example_id} requires errorKind")
            error_kinds[error_kind] += 1
        total_tool_calls += tool_calls
        reasoning_present += present
        reasoning_null += null
        result_kinds.update(observed_result_kinds)
        row = {
            "exampleId": example_id,
            "scenarioFamily": family,
            "status": status,
            "toolCalls": tool_calls,
            "resultKinds": dict(sorted(observed_result_kinds.items())),
            "selectionReasoningPresent": present,
            "selectionReasoningNull": null,
            "errorKind": error_kind,
        }
        case_rows.append(row)
        family_rows.setdefault(family, []).append(row)
    by_family = {
        family: {
            "totalCases": len(rows),
            "completedCases": sum(row["status"] == "completed" for row in rows),
            "instrumentErrors": sum(row["status"] == "instrument-error" for row in rows),
            "toolCalls": sum(row["toolCalls"] for row in rows),
            "selectionReasoningPresent": sum(row["selectionReasoningPresent"] for row in rows),
            "selectionReasoningNull": sum(row["selectionReasoningNull"] for row in rows),
        }
        for family, rows in sorted(family_rows.items())
    }
    return {
        "schemaVersion": "1.0.0",
        "experimentId": experiment_id,
        "runId": run_id,
        "projection": dict(projection),
        "counts": {
            "totalCases": len(outcomes),
            "completedCases": completed,
            "instrumentErrors": instrument_errors,
            "toolCalls": total_tool_calls,
        },
        "selectionReasoning": {
            "present": reasoning_present,
            "null": reasoning_null,
            "totalToolCalls": total_tool_calls,
        },
        "resultKinds": dict(sorted(result_kinds.items())),
        "instrumentErrorKinds": dict(sorted(error_kinds.items())),
        "byScenarioFamily": by_family,
        "cases": case_rows,
    }
