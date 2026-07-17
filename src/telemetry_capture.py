"""Capture finished Strands OpenTelemetry spans as the pinned inline profile."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


SUPPORTED_SCOPE = "strands.telemetry.tracer"
SUPPORTED_OPERATIONS = {"invoke_agent", "chat", "execute_tool"}
IGNORED_OPERATIONS = {"execute_event_loop_cycle"}


class TelemetryCaptureError(ValueError):
    """Finished telemetry cannot be represented by the pinned source profile."""


def serialize_strands_inline_spans(
    spans: Sequence[Any],
    *,
    agent_manifest: Mapping[str, str],
    producer_version: str,
) -> dict[str, Any]:
    """Serialize one trace of finished spans into `strands-inline@1.0.0`."""

    if not spans:
        raise TelemetryCaptureError("finished spans must be non-empty")
    serialized = [_serialize_span(span) for span in spans]
    trace_ids = {span["traceId"] for span in serialized}
    if len(trace_ids) != 1:
        raise TelemetryCaptureError("finished spans must belong to exactly one traceId")
    span_ids = [span["spanId"] for span in serialized]
    if len(span_ids) != len(set(span_ids)):
        raise TelemetryCaptureError("finished spans contain duplicate spanId values")
    scope_metadata = {
        (span["scope"]["name"], span["scope"]["version"], span["scope"]["schemaUrl"])
        for span in serialized
    }
    if len(scope_metadata) != 1:
        raise TelemetryCaptureError("finished spans must share one instrumentation scope")
    scope_name, scope_version, scope_schema_url = next(iter(scope_metadata))
    by_span_id = {span["spanId"]: span for span in serialized}
    serialized = [
        span
        for span in serialized
        if span["attributes"]["gen_ai.operation.name"] in SUPPORTED_OPERATIONS
    ]
    if not serialized:
        raise TelemetryCaptureError("finished spans contain no supported operations")
    supported_span_ids = {span["spanId"] for span in serialized}
    for span in serialized:
        parent_id = span["parentSpanId"]
        visited = {span["spanId"]}
        while parent_id is not None and parent_id not in supported_span_ids:
            if parent_id in visited:
                raise TelemetryCaptureError(
                    f"span {span['spanId']} parent chain contains a cycle"
                )
            visited.add(parent_id)
            omitted_parent = by_span_id.get(parent_id)
            if omitted_parent is None:
                raise TelemetryCaptureError(
                    f"span {span['spanId']} parent {parent_id} was not captured"
                )
            parent_id = omitted_parent["parentSpanId"]
        span["parentSpanId"] = parent_id
    serialized.sort(
        key=lambda span: (
            span["startTimeUnixNano"],
            span["endTimeUnixNano"],
            span["spanId"],
        )
    )
    return {
        "sourceProfile": {
            "name": "strands-inline",
            "producer": {"name": "strands-agents", "version": producer_version},
            "instrumentationScope": {
                "name": scope_name,
                "version": scope_version,
                "schemaUrl": scope_schema_url,
            },
            "collector": None,
        },
        "agentManifest": dict(agent_manifest),
        "spans": serialized,
    }


def capture_finished_spans(telemetry: Any) -> list[Any]:
    """Return a stable list of finished spans from Strands Evals telemetry."""

    exporter = getattr(telemetry, "in_memory_exporter", None)
    if exporter is None:
        exporter = getattr(telemetry, "memory_exporter", None)
    if exporter is None or not hasattr(exporter, "get_finished_spans"):
        raise TelemetryCaptureError("telemetry has no in-memory finished-span exporter")
    spans = list(exporter.get_finished_spans())
    if not spans:
        raise TelemetryCaptureError("in-memory exporter returned no finished spans")
    return spans


def _serialize_span(span: Any) -> dict[str, Any]:
    context = getattr(span, "context", None)
    trace_id = _hex_id(getattr(context, "trace_id", None), 32, "traceId")
    span_id = _hex_id(getattr(context, "span_id", None), 16, "spanId")
    parent = getattr(span, "parent", None)
    parent_span_id = (
        None
        if parent is None
        else _hex_id(getattr(parent, "span_id", None), 16, "parentSpanId")
    )
    scope = getattr(span, "instrumentation_scope", None)
    if getattr(scope, "name", None) != SUPPORTED_SCOPE:
        raise TelemetryCaptureError(
            f"span {span_id} instrumentation scope must be {SUPPORTED_SCOPE!r}"
        )
    attributes = _json_mapping(getattr(span, "attributes", None), f"span {span_id} attributes")
    operation = attributes.get("gen_ai.operation.name")
    if operation not in SUPPORTED_OPERATIONS | IGNORED_OPERATIONS:
        raise TelemetryCaptureError(
            f"span {span_id} has unsupported gen_ai.operation.name {operation!r}"
        )
    start = getattr(span, "start_time", None)
    end = getattr(span, "end_time", None)
    if not isinstance(start, int) or not isinstance(end, int):
        raise TelemetryCaptureError(f"span {span_id} timestamps must be integers")
    events = []
    for index, event in enumerate(getattr(span, "events", ())):
        name = getattr(event, "name", None)
        if not isinstance(name, str) or not name:
            raise TelemetryCaptureError(f"span {span_id} event[{index}].name must be non-empty")
        serialized_event = {
            "name": name,
            "attributes": _json_mapping(
                getattr(event, "attributes", None),
                f"span {span_id} event[{index}].attributes",
            ),
        }
        timestamp = getattr(event, "timestamp", None)
        if timestamp is not None:
            if not isinstance(timestamp, int):
                raise TelemetryCaptureError(
                    f"span {span_id} event[{index}].timestamp must be an integer"
                )
            serialized_event["timeUnixNano"] = timestamp
        events.append(serialized_event)
    return {
        "traceId": trace_id,
        "spanId": span_id,
        "parentSpanId": parent_span_id,
        "name": str(getattr(span, "name", "")),
        "scope": {
            "name": SUPPORTED_SCOPE,
            "version": getattr(scope, "version", None),
            "schemaUrl": getattr(scope, "schema_url", None),
        },
        "startTimeUnixNano": start,
        "endTimeUnixNano": end,
        "attributes": attributes,
        "events": events,
    }


def _hex_id(value: Any, width: int, field: str) -> str:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise TelemetryCaptureError(f"{field} must be a positive integer")
    encoded = f"{value:0{width}x}"
    if len(encoded) != width:
        raise TelemetryCaptureError(f"{field} must fit exactly {width} hexadecimal characters")
    return encoded


def _json_mapping(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TelemetryCaptureError(f"{field} must be a mapping")
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TelemetryCaptureError(f"{field} keys must be strings")
        result[key] = _json_value(item, f"{field}.{key}")
    return result


def _json_value(value: Any, field: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TelemetryCaptureError(f"{field} must be a finite JSON number")
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item, f"{field}[]") for item in value]
    raise TelemetryCaptureError(f"{field} has unsupported telemetry value {type(value).__name__}")
