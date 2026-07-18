"""Deterministic tool-contract gates over prevalidated Week 8 trace evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from typing import Any, Mapping

from strands_evals.evaluators import Evaluator
from strands_evals.types.evaluation import EvaluationData, EvaluationOutput


class GateEvidenceError(ValueError):
    """The harness supplied malformed or inconsistent deterministic evidence."""


@dataclass(frozen=True)
class GateEvidence:
    """The subset of a replayed evaluation case consumed by deterministic gates."""

    expected: Mapping[str, Any]
    spans: tuple[Mapping[str, Any], ...]
    response: str | None
    failure_injection: Mapping[str, Any] | None

    @property
    def tool_spans(self) -> tuple[Mapping[str, Any], ...]:
        """Return normalized spans that represent an executed tool call."""

        return tuple(
            span for span in self.spans if span.get("operationName") == "execute_tool"
        )


def read_gate_evidence(case: EvaluationData[Any, Any]) -> GateEvidence:
    """Read the prevalidated evidence tuple supplied by the Stage B harness."""

    metadata = case.metadata
    if not isinstance(metadata, Mapping) or not isinstance(metadata.get("expected"), Mapping):
        raise GateEvidenceError("metadata.expected must be a mapping")
    if not isinstance(case.actual_trajectory, list):
        raise GateEvidenceError("actual_trajectory must be a list of normalized spans")
    if any(not isinstance(span, Mapping) for span in case.actual_trajectory):
        raise GateEvidenceError("actual_trajectory must contain only mapping spans")
    if case.actual_output is not None and not isinstance(case.actual_output, str):
        raise GateEvidenceError("actual_output must be a string or null")
    failure_injection = metadata.get("failureInjection")
    if failure_injection is not None and not isinstance(failure_injection, Mapping):
        raise GateEvidenceError("metadata.failureInjection must be a mapping or null")
    return GateEvidence(
        expected=metadata["expected"],
        spans=tuple(case.actual_trajectory),
        response=case.actual_output,
        failure_injection=failure_injection,
    )


def _output(*, passed: bool, label: str, reason: str) -> EvaluationOutput:
    return EvaluationOutput(
        score=1.0 if passed else 0.0,
        test_pass=passed,
        label=label,
        reason=reason,
    )


def _tool_id(span: Mapping[str, Any]) -> str:
    tool = span.get("tool")
    if not isinstance(tool, Mapping) or not isinstance(tool.get("toolId"), str):
        raise GateEvidenceError("execute_tool span requires tool.toolId")
    return tool["toolId"]


def _arguments(span: Mapping[str, Any]) -> Mapping[str, Any]:
    arguments = span.get("arguments")
    if not isinstance(arguments, Mapping):
        raise GateEvidenceError("execute_tool span requires mapping arguments")
    return arguments


def _root_property(path: Any) -> str:
    if (
        not isinstance(path, str)
        or not path.startswith("$.")
        or not path[2:]
        or any(marker in path[2:] for marker in (".", "[", "]"))
    ):
        raise GateEvidenceError("argument constraint path must name one root property")
    return path[2:]


def _constraint_values(
    constraint: Mapping[str, Any],
    tool_spans: tuple[Mapping[str, Any], ...],
) -> tuple[str, tuple[Mapping[str, Any], ...]]:
    tool_id = constraint.get("toolId")
    if not isinstance(tool_id, str):
        raise GateEvidenceError("argument constraint requires toolId")
    return tool_id, tuple(span for span in tool_spans if _tool_id(span) == tool_id)


def _canonical_value(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise GateEvidenceError("argument constraint value is not JSON-compatible") from error


class DeterministicGate(Evaluator):
    """Base evaluator preserving a labeled neutral result for non-applicable gates."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name)
        self.aggregator = self._aggregate

    @staticmethod
    def _aggregate(outputs: list[EvaluationOutput]) -> tuple[float, bool, str]:
        if outputs and all(output.label == "not_applicable" for output in outputs):
            reasons = " | ".join(
                output.reason for output in outputs if output.reason
            )
            return 1.0, True, reasons or "not applicable"
        return Evaluator._default_aggregator(outputs)


class ExpectedToolsGate(DeterministicGate):
    """Score required and forbidden tool selection with inclusive call bounds."""

    def evaluate(
        self, evaluation_case: EvaluationData[Any, Any]
    ) -> list[EvaluationOutput]:
        evidence = read_gate_evidence(evaluation_case)
        expected_ids = evidence.expected.get("toolIds")
        if not isinstance(expected_ids, list) or not all(
            isinstance(tool_id, str) for tool_id in expected_ids
        ):
            raise GateEvidenceError("expected.toolIds must be an array of strings")
        if not expected_ids:
            return [_output(passed=True, label="not_applicable", reason="no expected tools")]

        observed_ids = [_tool_id(span) for span in evidence.tool_spans]
        forbidden = evidence.expected.get("mustNotCall", [])
        if not isinstance(forbidden, list) or not all(
            isinstance(tool_id, str) for tool_id in forbidden
        ):
            raise GateEvidenceError("expected.mustNotCall must be an array of strings")
        forbidden_hits = sorted(set(observed_ids).intersection(forbidden))
        if forbidden_hits:
            return [
                _output(
                    passed=False,
                    label="fail",
                    reason=f"forbidden tools called: {', '.join(forbidden_hits)}",
                )
            ]

        unexpected = sorted(set(observed_ids) - set(expected_ids))
        if unexpected:
            return [
                _output(
                    passed=False,
                    label="fail",
                    reason=f"unexpected tools called: {', '.join(unexpected)}",
                )
            ]

        missing = sorted(set(expected_ids) - set(observed_ids))
        if missing:
            return [
                _output(
                    passed=False,
                    label="fail",
                    reason=f"required tools missing: {', '.join(missing)}",
                )
            ]

        minimum = evidence.expected.get("minCalls")
        maximum = evidence.expected.get("maxCalls")
        if not isinstance(minimum, int) or not isinstance(maximum, int):
            raise GateEvidenceError("expected minCalls and maxCalls must be integers")
        if not minimum <= len(observed_ids) <= maximum:
            return [
                _output(
                    passed=False,
                    label="fail",
                    reason=(
                        f"tool call count {len(observed_ids)} outside "
                        f"inclusive bounds [{minimum}, {maximum}]"
                    ),
                )
            ]

        return [
            _output(
                passed=True,
                label="pass",
                reason=f"required tools selected in {len(observed_ids)} calls",
            )
        ]


class ArgConstraintGate(DeterministicGate):
    """Score the frozen root-level argument-constraint vocabulary."""

    _PREDICATES = frozenset(
        {"equals", "inSet", "coversExactlyOnce", "absent", "notContains"}
    )

    def evaluate(
        self, evaluation_case: EvaluationData[Any, Any]
    ) -> list[EvaluationOutput]:
        evidence = read_gate_evidence(evaluation_case)
        constraints = evidence.expected.get("argConstraints")
        if not isinstance(constraints, list):
            raise GateEvidenceError("expected.argConstraints must be an array")
        if not constraints:
            return [
                _output(
                    passed=True,
                    label="not_applicable",
                    reason="no argument constraints",
                )
            ]

        matched_any = False
        for index, value in enumerate(constraints):
            if not isinstance(value, Mapping):
                raise GateEvidenceError("argument constraint must be a mapping")
            predicates = self._PREDICATES.intersection(value)
            if len(predicates) != 1:
                raise GateEvidenceError(
                    "argument constraint must declare exactly one supported predicate"
                )
            predicate = next(iter(predicates))
            property_name = _root_property(value.get("path"))
            tool_id, matching_spans = _constraint_values(value, evidence.tool_spans)
            if not matching_spans:
                continue
            matched_any = True
            if not self._constraint_passes(
                predicate,
                value[predicate],
                property_name,
                matching_spans,
            ):
                return [
                    _output(
                        passed=False,
                        label="fail",
                        reason=(
                            f"constraint {index} ({predicate}) failed for "
                            f"{tool_id} at $.{property_name}"
                        ),
                    )
                ]

        if not matched_any:
            return [
                _output(
                    passed=True,
                    label="not_applicable",
                    reason="no constrained tool call was observed",
                )
            ]
        return [
            _output(
                passed=True,
                label="pass",
                reason="all applicable argument constraints passed",
            )
        ]

    @staticmethod
    def _constraint_passes(
        predicate: str,
        expected_value: Any,
        property_name: str,
        spans: tuple[Mapping[str, Any], ...],
    ) -> bool:
        observed = [
            (property_name in _arguments(span), _arguments(span).get(property_name))
            for span in spans
        ]
        if predicate == "absent":
            if expected_value is not True:
                raise GateEvidenceError("absent constraint must be true")
            return all(not present for present, _ in observed)
        if predicate == "equals":
            return all(present and value == expected_value for present, value in observed)
        if predicate == "inSet":
            if not isinstance(expected_value, list):
                raise GateEvidenceError("inSet constraint must be an array")
            return all(present and value in expected_value for present, value in observed)
        if predicate == "coversExactlyOnce":
            if not isinstance(expected_value, list):
                raise GateEvidenceError("coversExactlyOnce constraint must be an array")
            if not all(present for present, _ in observed):
                return False
            return Counter(_canonical_value(value) for _, value in observed) == Counter(
                _canonical_value(value) for value in expected_value
            )
        if predicate == "notContains":
            if not isinstance(expected_value, str):
                raise GateEvidenceError("notContains constraint must be a string")
            for present, value in observed:
                if not present:
                    continue
                if not isinstance(value, str):
                    raise GateEvidenceError(
                        "notContains constraint requires string argument values"
                    )
                if expected_value in value:
                    return False
            return True
        raise GateEvidenceError(f"unsupported argument predicate: {predicate}")


class NoToolGate(DeterministicGate):
    """Score explicit no-tool cases without treating chat spans as tool calls."""

    def evaluate(
        self, evaluation_case: EvaluationData[Any, Any]
    ) -> list[EvaluationOutput]:
        evidence = read_gate_evidence(evaluation_case)
        expected_ids = evidence.expected.get("toolIds")
        if not isinstance(expected_ids, list) or not all(
            isinstance(tool_id, str) for tool_id in expected_ids
        ):
            raise GateEvidenceError("expected.toolIds must be an array of strings")
        if expected_ids:
            return [
                _output(
                    passed=True,
                    label="not_applicable",
                    reason="tools are expected",
                )
            ]
        observed = [_tool_id(span) for span in evidence.tool_spans]
        if observed:
            return [
                _output(
                    passed=False,
                    label="fail",
                    reason=f"no-tool case called: {', '.join(sorted(set(observed)))}",
                )
            ]
        return [_output(passed=True, label="pass", reason="no tool call observed")]


class FailureBehaviorGate(DeterministicGate):
    """Score normalized injected-failure envelopes without judging response prose."""

    def evaluate(
        self, evaluation_case: EvaluationData[Any, Any]
    ) -> list[EvaluationOutput]:
        evidence = read_gate_evidence(evaluation_case)
        injection = evidence.failure_injection
        if injection is None:
            return [
                _output(
                    passed=True,
                    label="not_applicable",
                    reason="no failure injection",
                )
            ]
        target_tool = injection.get("toolId")
        failure_kind = injection.get("kind")
        retryable = injection.get("retryable")
        if (
            not isinstance(target_tool, str)
            or not isinstance(failure_kind, str)
            or not isinstance(retryable, bool)
        ):
            raise GateEvidenceError(
                "failureInjection requires string toolId/kind and boolean retryable"
            )
        target_spans = tuple(
            span for span in evidence.tool_spans if _tool_id(span) == target_tool
        )
        occurrence = injection.get("occurrence")
        if occurrence is not None:
            if not isinstance(occurrence, int) or occurrence < 1:
                raise GateEvidenceError("failureInjection.occurrence must be a positive integer")
            candidates = target_spans[occurrence - 1 : occurrence]
        else:
            candidates = target_spans
        for span in candidates:
            result = span.get("result")
            if not isinstance(result, Mapping):
                raise GateEvidenceError("execute_tool span requires a mapping result")
            if (
                result.get("ok") is False
                and result.get("failureKind") == failure_kind
                and result.get("retryable") is retryable
            ):
                return [
                    _output(
                        passed=True,
                        label="pass",
                        reason=(
                            f"observed {failure_kind}/retryable={retryable} on "
                            f"{target_tool}"
                        ),
                    )
                ]
        return [
            _output(
                passed=False,
                label="fail",
                reason=(
                    f"missing {failure_kind}/retryable={retryable} failure envelope on "
                    f"{target_tool}"
                ),
            )
        ]
