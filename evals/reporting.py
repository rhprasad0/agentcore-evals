"""Canonical public-safe aggregates for Week 8 Stage B replay."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from evals.harness import StageBEvidence


REPORT_SCHEMA_RELATIVE = Path("schemas/eval-report.schema.json")
HONESTY_FOOTER = (
    "Mechanical contract compliance only; response quality is out of scope until "
    "human labels exist (Week 9)."
)
METRIC_NAMES = (
    "selection",
    "parameter",
    "execution",
    "failureBehavior",
    "noTool",
    "instrumentValidity",
)
GATE_NAMES = {
    "ExpectedToolsGate",
    "ArgConstraintGate",
    "FailureBehaviorGate",
    "NoToolGate",
}


class ReportContractError(ValueError):
    """Stage B evidence or SDK rows cannot produce a safe aggregate."""


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _metric(
    *,
    unit: str,
    denominator: int,
    numerator: int,
    instrument_errors: int = 0,
    gate_errors: int = 0,
) -> dict[str, Any]:
    if min(denominator, numerator, instrument_errors, gate_errors) < 0:
        raise ReportContractError("metric counts must be non-negative")
    if numerator > denominator:
        raise ReportContractError("metric numerator cannot exceed denominator")
    return {
        "unit": unit,
        "eligible": denominator + gate_errors,
        "numerator": numerator,
        "denominator": denominator,
        "rate": _rate(numerator, denominator),
        "instrumentErrors": instrument_errors,
        "gateErrors": gate_errors,
    }


def _empty_metric_slice() -> dict[str, dict[str, Any]]:
    return {
        "selection": _metric(unit="case", denominator=0, numerator=0),
        "parameter": _metric(unit="tool-call", denominator=0, numerator=0),
        "execution": _metric(unit="tool-call", denominator=0, numerator=0),
        "failureBehavior": _metric(unit="case", denominator=0, numerator=0),
        "noTool": _metric(unit="case", denominator=0, numerator=0),
        "instrumentValidity": _metric(unit="case", denominator=0, numerator=0),
    }


def _report_rows(sdk_report: Any) -> dict[tuple[str, str], dict[str, Any]]:
    cases = getattr(sdk_report, "cases", None)
    scores = getattr(sdk_report, "scores", None)
    test_passes = getattr(sdk_report, "test_passes", None)
    reasons = getattr(sdk_report, "reasons", None)
    if not (
        isinstance(cases, list)
        and isinstance(scores, list)
        and isinstance(test_passes, list)
        and isinstance(reasons, list)
    ):
        raise ReportContractError("SDK report rows are not available as lists")
    if not len(cases) == len(scores) == len(test_passes) == len(reasons):
        raise ReportContractError("SDK report row arrays have different lengths")

    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for index, row in enumerate(cases):
        if not isinstance(row, Mapping):
            raise ReportContractError(f"SDK report row {index} is not a mapping")
        name = row.get("name")
        evaluator = row.get("evaluator")
        if not isinstance(name, str) or not isinstance(evaluator, str):
            raise ReportContractError(f"SDK report row {index} has invalid identity")
        if evaluator not in GATE_NAMES:
            raise ReportContractError(f"SDK report row {index} has unknown evaluator")
        key = (name, evaluator)
        if key in indexed:
            raise ReportContractError(f"duplicate SDK report row for {name}/{evaluator}")
        reason = reasons[index]
        if not isinstance(reason, str):
            raise ReportContractError(f"SDK report row {index} has no stable reason")
        indexed[key] = {
            "passed": test_passes[index] is True,
            "score": scores[index],
            "gateError": reason.startswith("Evaluator error:"),
        }
    return indexed


def _metadata(case: Any) -> Mapping[str, Any]:
    metadata = case.metadata
    if not isinstance(metadata, Mapping):
        raise ReportContractError(f"case {case.name!r} metadata is not a mapping")
    expected = metadata.get("expected")
    tags = metadata.get("tags")
    if not isinstance(expected, Mapping):
        raise ReportContractError(f"case {case.name!r} expected metadata is invalid")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ReportContractError(f"case {case.name!r} tags metadata is invalid")
    injection = metadata.get("failureInjection")
    if injection is not None and not isinstance(injection, Mapping):
        raise ReportContractError(f"case {case.name!r} failure injection metadata is invalid")
    return metadata


def _tool_spans(trace: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    spans = trace.get("spans")
    if not isinstance(spans, list):
        raise ReportContractError("validated trace spans are not a list")
    return [
        span
        for span in spans
        if isinstance(span, Mapping) and span.get("operationName") == "execute_tool"
    ]


def _tool_id(span: Mapping[str, Any]) -> str:
    tool = span.get("tool")
    if not isinstance(tool, Mapping) or not isinstance(tool.get("toolId"), str):
        raise ReportContractError("validated tool span has no tool ID")
    return tool["toolId"]


def _case_names_for_tag(evidence: StageBEvidence, tag: str) -> set[str]:
    names: set[str] = set()
    for case in evidence.projected_cases:
        metadata = _metadata(case)
        if tag in metadata["tags"]:
            if not isinstance(case.name, str):
                raise ReportContractError("projected case has no name")
            names.add(case.name)
    return names


def _case_names_for_failure_kind(evidence: StageBEvidence, kind: str) -> set[str]:
    names: set[str] = set()
    for case in evidence.projected_cases:
        metadata = _metadata(case)
        injection = metadata.get("failureInjection")
        if isinstance(injection, Mapping) and injection.get("kind") == kind:
            if not isinstance(case.name, str):
                raise ReportContractError("projected case has no name")
            names.add(case.name)
    return names


def _all_metric_slices(
    evidence: StageBEvidence,
    rows: Mapping[tuple[str, str], Mapping[str, Any]],
    case_names: set[str],
) -> dict[str, dict[str, Any]]:
    projected_cases = {
        case.name: case
        for case in evidence.projected_cases
        if isinstance(case.name, str) and case.name in case_names
    }
    eligible_cases = {
        case.name: case
        for case in evidence.eligible_cases
        if isinstance(case.name, str) and case.name in case_names
    }
    instrument_error_ids = {
        receipt.example_id
        for receipt in evidence.instrument_errors
        if receipt.example_id in case_names
    }
    selection_denominator = 0
    selection_numerator = 0
    selection_gate_errors = 0
    parameter_denominator = 0
    parameter_numerator = 0
    parameter_gate_errors = 0
    execution_denominator = 0
    execution_numerator = 0
    failure_denominator = 0
    failure_numerator = 0
    failure_gate_errors = 0
    no_tool_denominator = 0
    no_tool_numerator = 0
    no_tool_gate_errors = 0

    for name, case in eligible_cases.items():
        metadata = _metadata(case)
        expected = metadata["expected"]
        expected_tool_ids = expected.get("toolIds")
        if not isinstance(expected_tool_ids, list) or not all(
            isinstance(tool_id, str) for tool_id in expected_tool_ids
        ):
            raise ReportContractError(f"case {name} expected tool IDs are invalid")
        trace = evidence.traces_by_case_name.get(name)
        if not isinstance(trace, Mapping):
            raise ReportContractError(f"case {name} has no validated trace")
        tool_spans = _tool_spans(trace)
        gate_name = "ExpectedToolsGate" if expected_tool_ids else "NoToolGate"
        selection_row = rows.get((name, gate_name))
        if selection_row is None:
            raise ReportContractError(f"missing {gate_name} row for {name}")
        if selection_row["gateError"]:
            selection_gate_errors += 1
        else:
            selection_denominator += 1
            selection_numerator += int(selection_row["passed"])

        if expected_tool_ids:
            argument_constraints = expected.get("argConstraints")
            matching_spans = [
                span for span in tool_spans if _tool_id(span) in set(expected_tool_ids)
            ]
            argument_row = rows.get((name, "ArgConstraintGate"))
            if argument_row is None:
                raise ReportContractError(f"missing ArgConstraintGate row for {name}")
            if argument_row["gateError"]:
                parameter_gate_errors += 1
            elif isinstance(argument_constraints, list) and argument_constraints and matching_spans:
                parameter_denominator += len(matching_spans)
                parameter_numerator += len(matching_spans) * int(argument_row["passed"])

        for span in tool_spans:
            result = span.get("result")
            if not isinstance(result, Mapping) or not isinstance(result.get("ok"), bool):
                raise ReportContractError(f"case {name} has an invalid tool result")
            execution_denominator += 1
            execution_numerator += int(result["ok"] is True)

        injection = metadata.get("failureInjection")
        if isinstance(injection, Mapping):
            failure_row = rows.get((name, "FailureBehaviorGate"))
            if failure_row is None:
                raise ReportContractError(f"missing FailureBehaviorGate row for {name}")
            if failure_row["gateError"]:
                failure_gate_errors += 1
            else:
                failure_denominator += 1
                failure_numerator += int(failure_row["passed"])

        if not expected_tool_ids:
            no_tool_row = rows.get((name, "NoToolGate"))
            if no_tool_row is None:
                raise ReportContractError(f"missing NoToolGate row for {name}")
            if no_tool_row["gateError"]:
                no_tool_gate_errors += 1
            else:
                no_tool_denominator += 1
                no_tool_numerator += int(no_tool_row["passed"])

    instrument_validity_denominator = len(projected_cases)
    instrument_validity_numerator = instrument_validity_denominator - len(instrument_error_ids)
    instrument_validity_numerator = max(instrument_validity_numerator, 0)
    metrics = {
        "selection": _metric(
            unit="case",
            denominator=selection_denominator,
            numerator=selection_numerator,
            gate_errors=selection_gate_errors,
        ),
        "parameter": _metric(
            unit="tool-call",
            denominator=parameter_denominator,
            numerator=parameter_numerator,
            gate_errors=parameter_gate_errors,
        ),
        "execution": _metric(
            unit="tool-call",
            denominator=execution_denominator,
            numerator=execution_numerator,
        ),
        "failureBehavior": _metric(
            unit="case",
            denominator=failure_denominator,
            numerator=failure_numerator,
            gate_errors=failure_gate_errors,
        ),
        "noTool": _metric(
            unit="case",
            denominator=no_tool_denominator,
            numerator=no_tool_numerator,
            gate_errors=no_tool_gate_errors,
        ),
        "instrumentValidity": _metric(
            unit="case",
            denominator=instrument_validity_denominator,
            numerator=instrument_validity_numerator,
            instrument_errors=len(instrument_error_ids),
            gate_errors=0,
        ),
    }
    return metrics


def build_stage_b_aggregate(
    evidence: StageBEvidence,
    sdk_report: Any,
) -> dict[str, Any]:
    """Build one allowlisted aggregate from validated evidence and SDK rows."""

    rows = _report_rows(sdk_report)
    projected_ids = {
        case.name for case in evidence.projected_cases if isinstance(case.name, str)
    }
    if set(evidence.accounted_case_ids) != projected_ids:
        raise ReportContractError("evidence case IDs do not match projected cases")
    eligible_ids = {
        case.name for case in evidence.eligible_cases if isinstance(case.name, str)
    }
    if not eligible_ids.issubset(projected_ids):
        raise ReportContractError("eligible evidence is outside the projection")

    metrics = _all_metric_slices(evidence, rows, projected_ids)
    tags = sorted(
        {
            tag
            for case in evidence.projected_cases
            for tag in _metadata(case)["tags"]
        }
    )
    failure_kinds = sorted(
        {
            injection["kind"]
            for case in evidence.projected_cases
            for injection in [_metadata(case).get("failureInjection")]
            if isinstance(injection, Mapping) and isinstance(injection.get("kind"), str)
        }
    )
    return {
        "schemaVersion": "1.0.0",
        "experimentId": evidence.experiment_id,
        "fixtureSetId": evidence.fixture_set_id,
        "sourceRunId": evidence.source_run_id,
        "projection": dict(evidence.projection),
        "counts": {
            "projectedCases": len(projected_ids),
            "evidenceValidCases": len(eligible_ids),
            "instrumentErrors": len(evidence.instrument_errors),
            "gateErrors": sum(
                1
                for (case_name, _evaluator), row in rows.items()
                if case_name in eligible_ids and row["gateError"]
            ),
        },
        "metrics": metrics,
        "byTag": {
            tag: _all_metric_slices(evidence, rows, _case_names_for_tag(evidence, tag))
            for tag in tags
        },
        "byFailureKind": {
            kind: _all_metric_slices(
                evidence,
                rows,
                _case_names_for_failure_kind(evidence, kind),
            )
            for kind in failure_kinds
        },
        "honestyFooter": HONESTY_FOOTER,
    }


def validate_report(report: Mapping[str, Any], *, repo_root: Path) -> None:
    """Validate the closed report schema and its arithmetic/public-safety rules."""

    from jsonschema import Draft202012Validator

    schema_path = repo_root / REPORT_SCHEMA_RELATIVE
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReportContractError(f"cannot load report schema: {error.__class__.__name__}") from error
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ReportContractError(f"report schema error at {location}: {error.message}")
    _validate_report_arithmetic(report)


def _validate_report_arithmetic(report: Mapping[str, Any]) -> None:
    counts = report["counts"]
    if counts["evidenceValidCases"] + counts["instrumentErrors"] != counts["projectedCases"]:
        raise ReportContractError("evidence-valid and instrument-error counts do not account for projection")
    if counts["gateErrors"] < 0:
        raise ReportContractError("gateErrors cannot be negative")

    def check_slice(slice_value: Mapping[str, Any]) -> None:
        for metric in slice_value.values():
            if metric["numerator"] > metric["denominator"]:
                raise ReportContractError("metric numerator exceeds denominator")
            if metric["denominator"] == 0 and metric["rate"] is not None:
                raise ReportContractError("empty metric must have a null rate")
            if metric["denominator"] and metric["rate"] != metric["numerator"] / metric["denominator"]:
                raise ReportContractError("metric rate does not match numerator and denominator")

    check_slice(report["metrics"])
    for diagnostic_slice in report["byTag"].values():
        check_slice(diagnostic_slice)
    for diagnostic_slice in report["byFailureKind"].values():
        check_slice(diagnostic_slice)


def render_json(report: Mapping[str, Any]) -> str:
    """Render a validated aggregate as stable JSON."""

    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _render_metric(name: str, metric: Mapping[str, Any]) -> str:
    rate = "null" if metric["rate"] is None else f"{metric['rate']:.6f}"
    return (
        f"{name}: unit={metric['unit']} eligible={metric['eligible']} "
        f"numerator={metric['numerator']} denominator={metric['denominator']} "
        f"rate={rate} instrumentErrors={metric['instrumentErrors']} "
        f"gateErrors={metric['gateErrors']}"
    )


def render_text(report: Mapping[str, Any]) -> str:
    """Render a validated aggregate as deterministic console text."""

    lines = [
        "Week 8 Stage B evaluation report",
        f"experimentId: {report['experimentId']}",
        f"fixtureSetId: {report['fixtureSetId']}",
        f"sourceRunId: {report['sourceRunId']}",
        f"counts: {json.dumps(report['counts'], sort_keys=True)}",
        "",
        "Overall metrics:",
    ]
    lines.extend(_render_metric(name, report["metrics"][name]) for name in METRIC_NAMES)
    for dimension, slices in (("tag", report["byTag"]), ("failure kind", report["byFailureKind"])):
        lines.extend(["", f"By {dimension}:"])
        for key in sorted(slices):
            lines.append(f"[{key}]")
            lines.extend(_render_metric(name, slices[key][name]) for name in METRIC_NAMES)
    lines.extend(["", report["honestyFooter"], ""])
    return "\n".join(lines)


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a validated aggregate as deterministic public-safe Markdown."""

    lines = [
        "# Week 8 Stage B Evaluation Report",
        "",
        f"- Experiment: `{report['experimentId']}`",
        f"- Fixture set: `{report['fixtureSetId']}`",
        f"- Source run: `{report['sourceRunId']}`",
        f"- Counts: `{json.dumps(report['counts'], sort_keys=True)}`",
        "",
        "## Overall metrics",
        "",
        "| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    def add_metric_row(name: str, metric: Mapping[str, Any]) -> None:
        rate = "null" if metric["rate"] is None else f"{metric['rate']:.6f}"
        lines.append(
            f"| {name} | {metric['unit']} | {metric['eligible']} | "
            f"{metric['numerator']} | {metric['denominator']} | {rate} | "
            f"{metric['instrumentErrors']} | {metric['gateErrors']} |"
        )

    for name in METRIC_NAMES:
        add_metric_row(name, report["metrics"][name])
    for title, slices in (("By tag", report["byTag"]), ("By failure kind", report["byFailureKind"])):
        lines.extend(["", f"## {title}", ""])
        for key in sorted(slices):
            lines.extend(
                [
                    f"### `{key}`",
                    "",
                    "| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |",
                    "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for name in METRIC_NAMES:
                add_metric_row(name, slices[key][name])
    lines.extend(["", f"> {report['honestyFooter']}", ""])
    return "\n".join(lines)
