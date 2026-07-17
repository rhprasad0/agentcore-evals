"""Semantic invariants for repository canonical execution traces."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class ExecutionTraceSemanticError(ValueError):
    """A schema-shaped execution trace violates repository semantics."""


def validate_execution_trace_semantics(
    trace: Mapping[str, Any],
    *,
    repo_root: Path,
) -> None:
    """Validate exact capability, payload, ordering, and parentage invariants."""

    spans = trace.get("spans")
    if not isinstance(spans, list) or not spans:
        raise ExecutionTraceSemanticError("spans must be a non-empty array")
    _validate_sequences(spans)
    _validate_parentage(spans)
    contracts = _resolve_contracts(trace, repo_root)
    for index, span in enumerate(spans):
        if not isinstance(span, dict):
            raise ExecutionTraceSemanticError(f"spans[{index}] must be an object")
        if span.get("operationName") == "execute_tool":
            _validate_tool_span(span, index, contracts)
        else:
            for field in ("observedToolName", "tool", "arguments", "result"):
                if span.get(field) is not None:
                    raise ExecutionTraceSemanticError(
                        f"spans[{index}].{field} must be null for a non-tool span"
                    )


def _validate_sequences(spans: list[Any]) -> None:
    sequences = [span.get("sequence") if isinstance(span, dict) else None for span in spans]
    if sequences != list(range(len(spans))):
        raise ExecutionTraceSemanticError(
            "spans.sequence values must be contiguous and unique from zero in array order"
        )


def _validate_parentage(spans: list[Any]) -> None:
    typed = [span for span in spans if isinstance(span, dict)]
    roots = [
        span
        for span in typed
        if span.get("operationName") == "invoke_agent" and span.get("parentSpanId") is None
    ]
    if len(roots) != 1:
        raise ExecutionTraceSemanticError(
            f"spans must contain exactly one root invoke_agent span, found {len(roots)}"
        )
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, span in enumerate(typed):
        span_id = span.get("spanId")
        if not isinstance(span_id, str) or not span_id:
            raise ExecutionTraceSemanticError(f"spans[{index}].spanId must be non-empty")
        if span_id in by_id:
            raise ExecutionTraceSemanticError(f"spans[{index}].spanId duplicates {span_id}")
        by_id[span_id] = span
    root_id = roots[0]["spanId"]
    for index, span in enumerate(typed):
        span_id = span["spanId"]
        parent_id = span.get("parentSpanId")
        if span_id == root_id:
            continue
        if not isinstance(parent_id, str) or parent_id not in by_id:
            raise ExecutionTraceSemanticError(
                f"spans[{index}].parentSpanId does not reference a trace span"
            )
        if parent_id == span_id:
            raise ExecutionTraceSemanticError(
                f"spans[{index}].parentSpanId cannot reference itself"
            )
        visited = {span_id}
        cursor: str | None = parent_id
        while cursor is not None:
            if cursor in visited:
                raise ExecutionTraceSemanticError(
                    f"spans[{index}].parentSpanId participates in a cycle"
                )
            visited.add(cursor)
            parent = by_id.get(cursor)
            if parent is None:
                break
            cursor = parent.get("parentSpanId")


def _resolve_contracts(
    trace: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, tuple[str, str, Mapping[str, Any]]]:
    manifest_ref = trace.get("agentManifest")
    if not isinstance(manifest_ref, dict):
        raise ExecutionTraceSemanticError("agentManifest must be an object")
    manifest_id = manifest_ref.get("manifestId")
    version = manifest_ref.get("version")
    manifest_path = repo_root / "contracts" / "manifests" / str(manifest_id) / f"{version}.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExecutionTraceSemanticError(
            f"agentManifest {manifest_id}@{version} cannot be loaded: {error}"
        ) from error
    contracts: dict[str, tuple[str, str, Mapping[str, Any]]] = {}
    for tool_id, contract_version in manifest["toolGrants"].items():
        contract_path = (
            repo_root / "contracts" / "tools" / tool_id / f"{contract_version}.json"
        )
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        name = contract["name"]
        if name in contracts:
            raise ExecutionTraceSemanticError(
                f"runtime tool name {name!r} resolves to multiple exact contracts"
            )
        contracts[name] = (tool_id, contract_version, contract)
    return contracts


def _validate_tool_span(
    span: Mapping[str, Any],
    index: int,
    contracts: Mapping[str, tuple[str, str, Mapping[str, Any]]],
) -> None:
    observed_name = span.get("observedToolName")
    resolved = contracts.get(observed_name) if isinstance(observed_name, str) else None
    if resolved is None:
        raise ExecutionTraceSemanticError(
            f"spans[{index}].observedToolName does not resolve to one granted exact contract"
        )
    tool_id, version, contract = resolved
    identity = f"{tool_id}@{version}"
    if span.get("tool") != {"toolId": tool_id, "contractVersion": version}:
        raise ExecutionTraceSemanticError(
            f"spans[{index}].tool must match exact contract {identity}"
        )
    _validate_instance(
        span.get("arguments"),
        contract["inputSchema"],
        f"spans[{index}].arguments",
        identity,
    )
    result = span.get("result")
    if not isinstance(result, dict):
        raise ExecutionTraceSemanticError(f"spans[{index}].result must be an object")
    output = result.get("output")
    _validate_instance(
        output,
        contract["outputSchema"],
        f"spans[{index}].result.output",
        identity,
    )
    if not isinstance(output, dict) or not isinstance(output.get("ok"), bool):
        raise ExecutionTraceSemanticError(
            f"spans[{index}].result.output must expose boolean ok for {identity}"
        )
    if result.get("ok") is not output["ok"]:
        raise ExecutionTraceSemanticError(
            f"spans[{index}].result.ok must agree with result.output.ok for {identity}"
        )
    if output["ok"]:
        if result.get("failureKind") is not None or result.get("retryable") is not None:
            raise ExecutionTraceSemanticError(
                f"spans[{index}].result failure fields must be null for successful {identity}"
            )
        return
    error = output.get("error")
    if not isinstance(error, dict):
        raise ExecutionTraceSemanticError(
            f"spans[{index}].result.output.error must be an object for failed {identity}"
        )
    if result.get("failureKind") != error.get("kind"):
        raise ExecutionTraceSemanticError(
            f"spans[{index}].result.failureKind must agree with output.error.kind for {identity}"
        )
    if result.get("retryable") is not error.get("retryable"):
        raise ExecutionTraceSemanticError(
            f"spans[{index}].result.retryable must agree with output.error.retryable for {identity}"
        )


def _validate_instance(
    instance: Any,
    schema: Mapping[str, Any],
    field: str,
    identity: str,
) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if not errors:
        return
    error = errors[0]
    suffix = "".join(f"[{part!r}]" for part in error.absolute_path)
    raise ExecutionTraceSemanticError(
        f"{field}{suffix} violates {identity}: {error.message}"
    )
