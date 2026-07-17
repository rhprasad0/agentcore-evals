"""Normalize pinned Strands telemetry profiles into repository execution traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.execution_trace_validation import validate_execution_trace_semantics


SCHEMA_VERSION = "1.0.0"
CANONICALIZER_VERSION = "1.0.0"
SUPPORTED_SCOPE = "strands.telemetry.tracer"


class TelemetryNormalizationError(ValueError):
    """Source telemetry cannot be mapped to the canonical trace contract."""


def selection_reasoning_by_call_id(messages: list[Any]) -> dict[str, str | None]:
    """Return exact contiguous assistant text immediately preceding each tool call."""

    reasoning: dict[str, str | None] = {}
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise TelemetryNormalizationError(
                f"messages[{message_index}] must be an object"
            )
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            raise TelemetryNormalizationError(
                f"messages[{message_index}].content must be an array"
            )
        for block_index, block in enumerate(content):
            if not isinstance(block, dict) or "toolUse" not in block:
                continue
            tool_use = block.get("toolUse")
            if not isinstance(tool_use, dict):
                raise TelemetryNormalizationError(
                    f"messages[{message_index}].content[{block_index}].toolUse must be an object"
                )
            call_id = tool_use.get("toolUseId")
            if not isinstance(call_id, str) or not call_id:
                raise TelemetryNormalizationError(
                    f"messages[{message_index}].content[{block_index}].toolUseId must be non-empty"
                )
            if call_id in reasoning:
                raise TelemetryNormalizationError(f"duplicate toolUseId {call_id!r}")
            text_parts: list[str] = []
            cursor = block_index - 1
            while cursor >= 0:
                previous = content[cursor]
                if not isinstance(previous, dict) or set(previous) != {"text"}:
                    break
                text = previous["text"]
                if not isinstance(text, str) or not text:
                    break
                text_parts.append(text)
                cursor -= 1
            observed = "".join(reversed(text_parts))
            reasoning[call_id] = observed or None
    return reasoning


def normalize_strands_telemetry(
    document: Mapping[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    """Normalize one synthetic pinned Strands source-profile document."""

    profile = _require_mapping(document, "sourceProfile")
    profile_name = profile.get("name")
    if profile_name not in {"strands-inline", "strands-adot-split"}:
        raise TelemetryNormalizationError(
            f"unsupported Strands source profile: {profile_name!r}"
        )
    scope = _require_mapping(profile, "instrumentationScope")
    if scope.get("name") != SUPPORTED_SCOPE:
        raise TelemetryNormalizationError(
            f"instrumentation scope must be {SUPPORTED_SCOPE!r}"
        )

    raw_spans = document.get("spans")
    if not isinstance(raw_spans, list) or not raw_spans:
        raise TelemetryNormalizationError("spans must be a non-empty array")
    _validate_source_profile(profile, raw_spans)
    spans = sorted(raw_spans, key=_span_order_key)
    invoke_spans = [span for span in spans if _operation(span) == "invoke_agent"]
    if len(invoke_spans) != 1:
        raise TelemetryNormalizationError(
            f"expected exactly one invoke_agent span, found {len(invoke_spans)}"
        )
    invoke = invoke_spans[0]
    contracts = _runtime_contracts(repo_root, document)
    supported_spans = [
        span for span in spans if _operation(span) in {"invoke_agent", "execute_tool", "chat"}
    ]
    if profile_name == "strands-inline":
        selection_reasoning = _inline_selection_reasoning(supported_spans)
        normalized_spans = [
            _normalize_inline_span(span, sequence, contracts, selection_reasoning)
            for sequence, span in enumerate(supported_spans)
        ]
        prompt, response = _inline_prompt_and_response(invoke)
    else:
        event_records = _event_record_map(document, supported_spans)
        normalized_spans = [
            _normalize_adot_span(
                span,
                sequence,
                contracts,
                event_records[(_require_string(span, "traceId"), _require_string(span, "spanId"))],
            )
            for sequence, span in enumerate(supported_spans)
        ]
        invoke_record = event_records[
            (_require_string(invoke, "traceId"), _require_string(invoke, "spanId"))
        ]
        prompt, response = _adot_prompt_and_response(invoke_record)
    attributes = _require_mapping(invoke, "attributes")
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "canonicalizerVersion": CANONICALIZER_VERSION,
        "sourceProfile": dict(profile),
        "sessionId": _require_string(attributes, "session.id"),
        "traceId": _require_string(invoke, "traceId"),
        "agentManifest": dict(_require_mapping(document, "agentManifest")),
        "prompt": prompt,
        "response": response,
        "spans": normalized_spans,
    }
    schema = json.loads(
        (repo_root / "schemas/execution-trace.schema.json").read_text(encoding="utf-8")
    )
    errors = sorted(
        Draft202012Validator(schema).iter_errors(result),
        key=lambda error: list(error.path),
    )
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.path) or "<root>"
        raise TelemetryNormalizationError(f"canonical trace {path}: {error.message}")
    validate_execution_trace_semantics(result, repo_root=repo_root)
    return result


def canonical_projection_bytes(trace: Mapping[str, Any]) -> bytes:
    """Serialize stable semantic fields while excluding volatile source metadata."""

    spans = trace.get("spans")
    if not isinstance(spans, list):
        raise TelemetryNormalizationError("canonical trace spans must be an array")
    ordered_spans = sorted(spans, key=lambda item: item["sequence"])
    if [span["sequence"] for span in ordered_spans] != list(range(len(ordered_spans))):
        raise TelemetryNormalizationError(
            "canonical span sequence values must be contiguous and unique from zero"
        )
    projected_spans = [
        {
            "sequence": span["sequence"],
            "operationName": span["operationName"],
            "observedToolName": span["observedToolName"],
            "tool": span["tool"],
            "arguments": span["arguments"],
            "result": span["result"],
            "selectionReasoning": span["selectionReasoning"],
        }
        for span in ordered_spans
    ]
    projection = {
        "schemaVersion": trace["schemaVersion"],
        "canonicalizerVersion": trace["canonicalizerVersion"],
        "agentManifest": trace["agentManifest"],
        "prompt": trace["prompt"],
        "response": trace["response"],
        "spans": projected_spans,
    }
    return json.dumps(
        projection,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def validate_agentcore_evaluation_input(document: Mapping[str, Any]) -> None:
    """Validate the documented offline EvaluationInput.sessionSpans boundary."""

    if set(document) != {"sessionSpans"}:
        raise TelemetryNormalizationError(
            "EvaluationInput must specify exactly one union member: sessionSpans"
        )
    spans = document.get("sessionSpans")
    if not isinstance(spans, list) or not 1 <= len(spans) <= 1000:
        raise TelemetryNormalizationError(
            "EvaluationInput.sessionSpans must contain between 1 and 1000 items"
        )
    try:
        json.dumps(spans, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise TelemetryNormalizationError(
            f"EvaluationInput.sessionSpans must contain JSON values: {error}"
        ) from error


def _validate_source_profile(
    profile: Mapping[str, Any],
    spans: list[Mapping[str, Any]],
) -> None:
    producer = _require_mapping(profile, "producer")
    if producer.get("name") != "strands-agents" or producer.get("version") != "1.46.0":
        raise TelemetryNormalizationError(
            "source profile must pin strands-agents==1.46.0"
        )
    if profile.get("name") == "strands-inline":
        if profile.get("collector") is not None:
            raise TelemetryNormalizationError("strands-inline collector must be null")
    else:
        collector = _require_mapping(profile, "collector")
        if (
            collector.get("name") != "aws-opentelemetry-distro"
            or collector.get("version") != "0.18.0"
        ):
            raise TelemetryNormalizationError(
                "strands-adot-split must pin aws-opentelemetry-distro==0.18.0"
            )
    for span in spans:
        scope = _require_mapping(span, "scope")
        if scope.get("name") != SUPPORTED_SCOPE:
            raise TelemetryNormalizationError(
                f"span scope must be {SUPPORTED_SCOPE!r}"
            )


def _inline_selection_reasoning(
    spans: list[Mapping[str, Any]],
) -> dict[str, str | None]:
    reasoning: dict[str, str | None] = {}
    for span in spans:
        if _operation(span) != "chat":
            continue
        choice = _unique_event(span, "gen_ai.choice")
        message = _parse_json_layers(
            _require_mapping(choice, "attributes").get("message")
        )
        if isinstance(message, list):
            messages = [{"role": "assistant", "content": message}]
        elif isinstance(message, dict) and message.get("role") == "assistant":
            messages = [message]
        else:
            raise TelemetryNormalizationError(
                f"chat span {_require_string(span, 'spanId')} choice must preserve assistant content blocks"
            )
        for call_id, observed in selection_reasoning_by_call_id(messages).items():
            if call_id in reasoning:
                raise TelemetryNormalizationError(
                    f"duplicate toolUseId {call_id!r} across chat spans"
                )
            reasoning[call_id] = observed
    return reasoning


def _normalize_inline_span(
    span: Mapping[str, Any],
    sequence: int,
    contracts: Mapping[str, tuple[str, str]],
    selection_reasoning: Mapping[str, str | None],
) -> dict[str, Any]:
    operation = _operation(span)
    attributes = _require_mapping(span, "attributes")
    start = _require_int(span, "startTimeUnixNano")
    end = _require_int(span, "endTimeUnixNano")
    if end < start:
        raise TelemetryNormalizationError(
            f"span {_require_string(span, 'spanId')} ends before it starts"
        )
    token_usage = _token_usage(attributes)
    normalized: dict[str, Any] = {
        "sequence": sequence,
        "spanId": _require_string(span, "spanId"),
        "parentSpanId": span.get("parentSpanId"),
        "operationName": operation,
        "observedToolName": None,
        "tool": None,
        "arguments": None,
        "result": None,
        "selectionReasoning": None,
        "startTimeUnixNano": start,
        "endTimeUnixNano": end,
        "latencyMs": (end - start) / 1_000_000,
        "tokenUsage": token_usage,
    }
    if operation != "execute_tool":
        return normalized

    observed_name = _require_string(attributes, "gen_ai.tool.name")
    reference = contracts.get(observed_name)
    if reference is None:
        raise TelemetryNormalizationError(
            f"observed tool name {observed_name!r} does not resolve to one exact contract"
        )
    arguments_event = _unique_event(span, "gen_ai.tool.message")
    result_event = _unique_event(span, "gen_ai.choice")
    call_id = _require_string(attributes, "gen_ai.tool.call.id")
    arguments = _unwrap_tool_payload(
        _require_mapping(arguments_event, "attributes").get("content")
    )
    output = _unwrap_tool_payload(
        _require_mapping(result_event, "attributes").get("message")
    )
    if not isinstance(arguments, dict):
        raise TelemetryNormalizationError("tool arguments must decode to an object")
    if not isinstance(output, dict) or not isinstance(output.get("ok"), bool):
        raise TelemetryNormalizationError(
            "tool result must decode to a normalized object with boolean ok"
        )
    diagnostic = _diagnostic(attributes)
    error = output.get("error") if output["ok"] is False else None
    if error is not None and not isinstance(error, dict):
        raise TelemetryNormalizationError("failed tool result error must be an object")
    normalized.update(
        {
            "observedToolName": observed_name,
            "tool": {"toolId": reference[0], "contractVersion": reference[1]},
            "arguments": arguments,
            "result": {
                "ok": output["ok"],
                "output": output,
                "failureKind": None if error is None else error.get("kind"),
                "retryable": None if error is None else error.get("retryable"),
                "diagnostic": diagnostic,
            },
            "selectionReasoning": selection_reasoning.get(call_id),
        }
    )
    return normalized


def _normalize_adot_span(
    span: Mapping[str, Any],
    sequence: int,
    contracts: Mapping[str, tuple[str, str]],
    event_record: Mapping[str, Any],
) -> dict[str, Any]:
    operation = _operation(span)
    attributes = _require_mapping(span, "attributes")
    start = _require_int(span, "startTimeUnixNano")
    end = _require_int(span, "endTimeUnixNano")
    if end < start:
        raise TelemetryNormalizationError(
            f"span {_require_string(span, 'spanId')} ends before it starts"
        )
    normalized: dict[str, Any] = {
        "sequence": sequence,
        "spanId": _require_string(span, "spanId"),
        "parentSpanId": span.get("parentSpanId"),
        "operationName": operation,
        "observedToolName": None,
        "tool": None,
        "arguments": None,
        "result": None,
        "selectionReasoning": None,
        "startTimeUnixNano": start,
        "endTimeUnixNano": end,
        "latencyMs": (end - start) / 1_000_000,
        "tokenUsage": _token_usage(attributes),
    }
    if operation != "execute_tool":
        return normalized

    observed_name = _require_string(attributes, "gen_ai.tool.name")
    reference = contracts.get(observed_name)
    if reference is None:
        raise TelemetryNormalizationError(
            f"observed tool name {observed_name!r} does not resolve to one exact contract"
        )
    body = _require_mapping(event_record, "body")
    input_message = _message_with_role(_require_mapping(body, "input"), "tool")
    output_message = _message_with_role(_require_mapping(body, "output"), "assistant")
    input_content = _require_mapping(input_message, "content")
    output_content = _require_mapping(output_message, "content")
    arguments = _unwrap_tool_payload(input_content.get("content"))
    output = _unwrap_tool_payload(output_content.get("message"))
    if not isinstance(arguments, dict):
        raise TelemetryNormalizationError("tool arguments must decode to an object")
    if not isinstance(output, dict) or not isinstance(output.get("ok"), bool):
        raise TelemetryNormalizationError(
            "tool result must decode to a normalized object with boolean ok"
        )
    error = output.get("error") if output["ok"] is False else None
    if error is not None and not isinstance(error, dict):
        raise TelemetryNormalizationError("failed tool result error must be an object")
    normalized.update(
        {
            "observedToolName": observed_name,
            "tool": {"toolId": reference[0], "contractVersion": reference[1]},
            "arguments": arguments,
            "result": {
                "ok": output["ok"],
                "output": output,
                "failureKind": None if error is None else error.get("kind"),
                "retryable": None if error is None else error.get("retryable"),
                "diagnostic": _diagnostic(attributes),
            },
        }
    )
    return normalized


def _inline_prompt_and_response(span: Mapping[str, Any]) -> tuple[str, str]:
    prompt_event = _unique_event(span, "gen_ai.user.message")
    response_event = _unique_event(span, "gen_ai.choice")
    prompt_value = _require_mapping(prompt_event, "attributes").get("content")
    response_value = _require_mapping(response_event, "attributes").get("message")
    prompt = _message_text(_parse_json_layers(prompt_value))
    response = _message_text(_parse_json_layers(response_value))
    if not prompt or not response:
        raise TelemetryNormalizationError("invoke_agent prompt and response must be non-empty")
    return prompt, response


def _adot_prompt_and_response(event_record: Mapping[str, Any]) -> tuple[str, str]:
    body = _require_mapping(event_record, "body")
    user = _message_with_role(_require_mapping(body, "input"), "user")
    assistant = _message_with_role(_require_mapping(body, "output"), "assistant")
    prompt = _message_text(user.get("content"))
    response = _message_text(assistant.get("content"))
    if not prompt or not response:
        raise TelemetryNormalizationError("invoke_agent prompt and response must be non-empty")
    return prompt, response


def _event_record_map(
    document: Mapping[str, Any],
    spans: list[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    records = document.get("eventRecords")
    if not isinstance(records, list):
        raise TelemetryNormalizationError("ADOT source profile requires eventRecords array")
    expected = {
        (_require_string(span, "traceId"), _require_string(span, "spanId"))
        for span in spans
    }
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise TelemetryNormalizationError("event record must be an object")
        key = (_require_string(record, "traceId"), _require_string(record, "spanId"))
        if key in indexed:
            raise TelemetryNormalizationError(
                f"duplicate event record correlation traceId={key[0]} spanId={key[1]}"
            )
        indexed[key] = record
    missing = expected - indexed.keys()
    orphaned = indexed.keys() - expected
    if missing:
        trace_id, span_id = sorted(missing)[0]
        raise TelemetryNormalizationError(
            f"missing event record correlation traceId={trace_id} spanId={span_id}"
        )
    if orphaned:
        trace_id, span_id = sorted(orphaned)[0]
        raise TelemetryNormalizationError(
            f"orphaned event record correlation traceId={trace_id} spanId={span_id}"
        )
    return indexed


def _message_with_role(container: Mapping[str, Any], role: str) -> Mapping[str, Any]:
    messages = container.get("messages")
    if not isinstance(messages, list):
        raise TelemetryNormalizationError("event record input/output messages must be an array")
    matches = [
        message
        for message in messages
        if isinstance(message, dict) and message.get("role") == role
    ]
    if len(matches) != 1:
        raise TelemetryNormalizationError(
            f"expected one event-record message with role {role!r}, found {len(matches)}"
        )
    return matches[0]


def _runtime_contracts(
    repo_root: Path,
    document: Mapping[str, Any],
) -> dict[str, tuple[str, str]]:
    manifest_ref = _require_mapping(document, "agentManifest")
    manifest_path = (
        repo_root
        / "contracts/manifests"
        / _require_string(manifest_ref, "manifestId")
        / f"{_require_string(manifest_ref, 'version')}.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    resolved: dict[str, tuple[str, str]] = {}
    for tool_id, version in manifest["toolGrants"].items():
        contract_path = repo_root / "contracts/tools" / tool_id / f"{version}.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        name = contract["name"]
        if name in resolved:
            raise TelemetryNormalizationError(
                f"runtime tool name {name!r} resolves to multiple contracts"
            )
        resolved[name] = (tool_id, version)
    return resolved


def _operation(span: Mapping[str, Any]) -> str:
    return _require_string(_require_mapping(span, "attributes"), "gen_ai.operation.name")


def _span_order_key(span: Mapping[str, Any]) -> tuple[int, int, str]:
    return (
        _require_int(span, "startTimeUnixNano"),
        _require_int(span, "endTimeUnixNano"),
        _require_string(span, "spanId"),
    )


def _unique_event(span: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    events = span.get("events")
    if not isinstance(events, list):
        raise TelemetryNormalizationError(
            f"span {_require_string(span, 'spanId')} has no inline events"
        )
    matches = [event for event in events if isinstance(event, dict) and event.get("name") == name]
    if len(matches) != 1:
        raise TelemetryNormalizationError(
            f"span {_require_string(span, 'spanId')} expected one {name!r} event, found {len(matches)}"
        )
    return matches[0]


def _unwrap_tool_payload(value: Any) -> Any:
    parsed = _parse_json_layers(value)
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        if "text" in parsed[0]:
            return _parse_json_layers(parsed[0]["text"])
    return parsed


def _parse_json_layers(value: Any) -> Any:
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
    return parsed


def _message_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("message", "text", "content"):
            if key in value:
                return _message_text(value[key])
    if isinstance(value, list):
        parts = [_message_text(item) for item in value]
        return "".join(part for part in parts if part)
    return ""


def _token_usage(attributes: Mapping[str, Any]) -> dict[str, int] | None:
    keys = (
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.total_tokens",
    )
    if not any(key in attributes for key in keys):
        return None
    if not all(isinstance(attributes.get(key), int) for key in keys):
        raise TelemetryNormalizationError("token usage must include integer input/output/total")
    return {
        "input": attributes[keys[0]],
        "output": attributes[keys[1]],
        "total": attributes[keys[2]],
    }


def _diagnostic(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    source = attributes.get("agentcore_evals.failure.source")
    code = attributes.get("agentcore_evals.failure.code")
    if source is None and code is None:
        return None
    return {"source": source, "code": code}


def _require_mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise TelemetryNormalizationError(f"{key} must be an object")
    return value


def _require_string(container: Mapping[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise TelemetryNormalizationError(f"{key} must be a non-empty string")
    return value


def _require_int(container: Mapping[str, Any], key: str) -> int:
    value = container.get(key)
    if not isinstance(value, int):
        raise TelemetryNormalizationError(f"{key} must be an integer")
    return value
