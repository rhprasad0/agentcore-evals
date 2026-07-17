"""Bounded fact comparison for Strands Evals Session compatibility."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from strands_evals.types.trace import Session, ToolExecutionSpan


@dataclass(frozen=True)
class CompatibilityMismatch:
    """One planted fact that differs across the two representations."""

    field: str
    expected: Any
    actual: Any


def compare_planted_facts(
    canonical_trace: Mapping[str, Any],
    session: Session,
) -> list[CompatibilityMismatch]:
    """Compare independently represented tool facts without requiring schema identity."""

    canonical_spans = [
        span
        for span in canonical_trace.get("spans", [])
        if isinstance(span, dict) and span.get("operationName") == "execute_tool"
    ]
    native_spans = [
        span
        for trace in session.traces
        for span in trace.spans
        if isinstance(span, ToolExecutionSpan)
    ]
    mismatches: list[CompatibilityMismatch] = []
    if len(canonical_spans) != len(native_spans):
        return [
            CompatibilityMismatch(
                field="tool.count",
                expected=len(canonical_spans),
                actual=len(native_spans),
            )
        ]
    for canonical, native in zip(canonical_spans, native_spans, strict=True):
        facts = (
            (
                "tool.name",
                canonical.get("observedToolName"),
                native.tool_call.name,
            ),
            (
                "tool.arguments",
                canonical.get("arguments"),
                native.tool_call.arguments,
            ),
            (
                "tool.result",
                canonical.get("result", {}).get("output"),
                _parse_native_result(native.tool_result.content),
            ),
            (
                "tool.correlation",
                canonical.get("spanId"),
                native.span_info.span_id,
            ),
        )
        for field, expected, actual in facts:
            if expected != actual:
                mismatches.append(
                    CompatibilityMismatch(field=field, expected=expected, actual=actual)
                )
    return mismatches


def _parse_native_result(value: Any) -> Any:
    parsed = value
    for _ in range(4):
        if not isinstance(parsed, str):
            break
        try:
            candidate = json.loads(parsed)
        except json.JSONDecodeError:
            break
        if candidate == parsed:
            break
        parsed = candidate
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        if "text" in parsed[0]:
            return _parse_native_result(parsed[0]["text"])
    return parsed
