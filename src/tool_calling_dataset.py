"""Source-derived validation for the checked-in Week 6 tool-calling dataset."""

from __future__ import annotations

import json
from hashlib import sha256
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from src.version_bindings import VersionBindingError, resolve_exact_version_bindings


@dataclass(frozen=True)
class DatasetPaths:
    """Locations of one repository's versioned tool-calling dataset artifacts."""

    repo_root: Path
    manifest_path: Path
    example_schema_path: Path
    manifest_schema_path: Path

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> DatasetPaths:
        root = repo_root.resolve()
        return cls(
            repo_root=root,
            manifest_path=root / "datasets" / "synthetic" / "tool-calling-100.manifest.json",
            example_schema_path=root / "schemas" / "tool-calling-example.schema.json",
            manifest_schema_path=root / "schemas" / "tool-calling-dataset-manifest.schema.json",
        )


@dataclass(frozen=True)
class ValidationIssue:
    """One human-actionable validation failure."""

    path: str
    message: str


@dataclass
class DatasetSnapshot:
    """The manifest and corpus rows loaded from the authoritative source files."""

    manifest: dict[str, Any]
    rows: list[dict[str, Any]]
    corpus_path: Path


@dataclass(frozen=True)
class ContractMetadata:
    input_fields: dict[str, set[str]]
    failure_kinds: set[str]
    untrusted_tool_ids: set[str]


def load_dataset(paths: DatasetPaths) -> DatasetSnapshot:
    """Load the manifest-directed JSONL corpus without modifying it."""

    manifest = _load_object(paths.manifest_path)
    corpus_path = _resolve_repo_path(paths.repo_root, manifest["corpusPath"])
    rows = [
        json.loads(line)
        for line in corpus_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return DatasetSnapshot(manifest=manifest, rows=rows, corpus_path=corpus_path)


def serialize_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    """Serialize rows as deterministic UTF-8 JSONL text."""

    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )


def dataset_revision(snapshot: DatasetSnapshot) -> str:
    """Return a deterministic content revision for stale-write protection."""

    payload = json.dumps(
        {"manifest": snapshot.manifest, "rows": snapshot.rows},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def validate_dataset(snapshot: DatasetSnapshot, paths: DatasetPaths) -> list[ValidationIssue]:
    """Return schema and exact-binding failures without mutating the snapshot."""

    issues: list[ValidationIssue] = []
    manifest_schema = _load_object(paths.manifest_schema_path)
    example_schema = _load_object(paths.example_schema_path)
    Draft202012Validator.check_schema(manifest_schema)
    Draft202012Validator.check_schema(example_schema)

    issues.extend(_schema_issues(Draft202012Validator(manifest_schema), snapshot.manifest, "manifest"))
    try:
        resolve_exact_version_bindings(
            snapshot.manifest["agentManifest"],
            snapshot.manifest["toolContracts"],
            manifests_root=paths.repo_root / "contracts" / "manifests",
            tool_contracts_root=paths.repo_root / "contracts" / "tools",
        )
    except (KeyError, TypeError, VersionBindingError) as error:
        issues.append(ValidationIssue("manifest.bindings", str(error)))

    validator = Draft202012Validator(example_schema)
    for index, row in enumerate(snapshot.rows, start=1):
        example_id = row.get("exampleId", f"row-{index}") if isinstance(row, dict) else f"row-{index}"
        issues.extend(_schema_issues(validator, row, str(example_id)))
    issues.extend(_duplicate_prompt_issues(snapshot.rows))
    issues.extend(_call_bound_issues(snapshot.rows))
    granted_tool_ids = {
        reference["toolId"]
        for reference in snapshot.manifest.get("toolContracts", [])
        if isinstance(reference, dict) and isinstance(reference.get("toolId"), str)
    }
    issues.extend(_tool_reference_issues(snapshot.rows, granted_tool_ids))
    contract_metadata, contract_issues = _contract_metadata(snapshot.manifest, paths)
    issues.extend(contract_issues)
    issues.extend(_constraint_path_issues(snapshot.rows, contract_metadata.input_fields))
    issues.extend(
        _failure_kind_coverage_issues(snapshot.rows, contract_metadata.failure_kinds)
    )
    issues.extend(
        _untrusted_result_coverage_issues(
            snapshot.rows,
            contract_metadata.untrusted_tool_ids,
        )
    )
    issues.extend(
        _canary_assertion_issues(
            snapshot.rows,
            snapshot.manifest,
            granted_tool_ids,
        )
    )
    issues.extend(_row_count_issues(snapshot.rows, snapshot.manifest))
    issues.extend(_example_id_issues(snapshot.rows))
    issues.extend(_distribution_issues(snapshot.rows, snapshot.manifest))
    issues.extend(_review_status_issues(snapshot.rows, snapshot.manifest))
    return issues


def _load_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def _resolve_repo_path(repo_root: Path, relative_path: str) -> Path:
    candidate = (repo_root / relative_path).resolve()
    if repo_root not in candidate.parents:
        raise ValueError(f"dataset path escapes repository root: {relative_path}")
    return candidate


def _schema_issues(
    validator: Draft202012Validator,
    document: Any,
    prefix: str,
) -> list[ValidationIssue]:
    issues = []
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        suffix = "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.path)
        issues.append(ValidationIssue(path=f"{prefix}{suffix}", message=error.message))
    return issues


def _duplicate_prompt_issues(rows: list[dict[str, Any]]) -> list[ValidationIssue]:
    first_by_prompt: dict[str, str] = {}
    issues = []
    for index, row in enumerate(rows, start=1):
        prompt = row.get("prompt")
        if not isinstance(prompt, str):
            continue
        example_id = row.get("exampleId", f"row-{index}")
        if prompt in first_by_prompt:
            issues.append(
                ValidationIssue(
                    path=f"{example_id}.prompt",
                    message=f"duplicates prompt from {first_by_prompt[prompt]}",
                )
            )
        else:
            first_by_prompt[prompt] = str(example_id)
    return issues


def _call_bound_issues(rows: list[dict[str, Any]]) -> list[ValidationIssue]:
    issues = []
    for index, row in enumerate(rows, start=1):
        expected = row.get("expected")
        if not isinstance(expected, dict):
            continue
        minimum = expected.get("minCalls")
        maximum = expected.get("maxCalls")
        if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
            example_id = row.get("exampleId", f"row-{index}")
            issues.append(
                ValidationIssue(
                    path=f"{example_id}.expected.minCalls",
                    message="must be less than or equal to expected.maxCalls",
                )
            )
    return issues


def _tool_reference_issues(
    rows: list[dict[str, Any]],
    granted_tool_ids: set[str],
) -> list[ValidationIssue]:
    issues = []
    for index, row in enumerate(rows, start=1):
        example_id = str(row.get("exampleId", f"row-{index}"))
        expected = row.get("expected")
        if isinstance(expected, dict):
            for field in ("toolIds", "mustNotCall"):
                values = expected.get(field)
                if isinstance(values, list):
                    for value_index, tool_id in enumerate(values):
                        if isinstance(tool_id, str) and tool_id not in granted_tool_ids:
                            issues.append(
                                ValidationIssue(
                                    path=f"{example_id}.expected.{field}[{value_index}]",
                                    message=f"{tool_id} is not granted by the dataset manifest",
                                )
                            )
            constraints = expected.get("argConstraints")
            if isinstance(constraints, list):
                for constraint_index, constraint in enumerate(constraints):
                    if not isinstance(constraint, dict):
                        continue
                    tool_id = constraint.get("toolId")
                    if isinstance(tool_id, str) and tool_id not in granted_tool_ids:
                        issues.append(
                            ValidationIssue(
                                path=f"{example_id}.expected.argConstraints[{constraint_index}].toolId",
                                message=f"{tool_id} is not granted by the dataset manifest",
                            )
                        )
        failure_injection = row.get("failureInjection")
        if isinstance(failure_injection, dict):
            tool_id = failure_injection.get("toolId")
            if isinstance(tool_id, str) and tool_id not in granted_tool_ids:
                issues.append(
                    ValidationIssue(
                        path=f"{example_id}.failureInjection.toolId",
                        message=f"{tool_id} is not granted by the dataset manifest",
                    )
                )
    return issues


def _contract_metadata(
    manifest: dict[str, Any],
    paths: DatasetPaths,
) -> tuple[ContractMetadata, list[ValidationIssue]]:
    fields_by_tool_id: dict[str, set[str]] = {}
    failure_kinds: set[str] = set()
    untrusted_tool_ids: set[str] = set()
    issues = []
    for reference in manifest.get("toolContracts", []):
        if not isinstance(reference, dict):
            continue
        tool_id = reference.get("toolId")
        version = reference.get("version")
        if not isinstance(tool_id, str) or not isinstance(version, str):
            continue
        contract_path = paths.repo_root / "contracts" / "tools" / tool_id / f"{version}.json"
        try:
            contract = _load_object(contract_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            issues.append(ValidationIssue("manifest.toolContracts", str(error)))
            continue
        input_schema = contract.get("inputSchema")
        properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
        fields_by_tool_id[tool_id] = set(properties) if isinstance(properties, dict) else set()
        failure_modes = contract.get("failureModes")
        if isinstance(failure_modes, list):
            failure_kinds.update(kind for kind in failure_modes if isinstance(kind, str))
        if contract.get("resultTrust") == "untrusted_external":
            untrusted_tool_ids.add(tool_id)
    return (
        ContractMetadata(
            input_fields=fields_by_tool_id,
            failure_kinds=failure_kinds,
            untrusted_tool_ids=untrusted_tool_ids,
        ),
        issues,
    )


def _failure_kind_coverage_issues(
    rows: list[dict[str, Any]],
    required_failure_kinds: set[str],
) -> list[ValidationIssue]:
    covered = {
        injection["kind"]
        for row in rows
        if isinstance((injection := row.get("failureInjection")), dict)
        and isinstance(injection.get("kind"), str)
    }
    missing = sorted(required_failure_kinds - covered)
    if missing:
        return [
            ValidationIssue(
                path="corpus.failureKinds",
                message=f"missing failure-injection coverage for: {', '.join(missing)}",
            )
        ]
    return []


def _untrusted_result_coverage_issues(
    rows: list[dict[str, Any]],
    required_tool_ids: set[str],
) -> list[ValidationIssue]:
    covered = set()
    for row in rows:
        tags = row.get("tags")
        expected = row.get("expected")
        tool_ids = expected.get("toolIds") if isinstance(expected, dict) else None
        if isinstance(tags, list) and "untrusted-result" in tags and isinstance(tool_ids, list):
            covered.update(tool_id for tool_id in tool_ids if isinstance(tool_id, str))
    missing = sorted(required_tool_ids - covered)
    if missing:
        return [
            ValidationIssue(
                path="corpus.untrustedResults",
                message=f"missing untrusted-result coverage for: {', '.join(missing)}",
            )
        ]
    return []


def _canary_assertion_issues(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    granted_tool_ids: set[str],
) -> list[ValidationIssue]:
    canary = manifest.get("canonicalCanary")
    if not isinstance(canary, str):
        return []
    issues = []
    for index, row in enumerate(rows, start=1):
        tags = row.get("tags")
        if not isinstance(tags, list) or "untrusted-result" not in tags:
            continue
        example_id = str(row.get("exampleId", f"row-{index}"))
        expected = row.get("expected")
        response_must_not = expected.get("responseMustNot") if isinstance(expected, dict) else None
        if not isinstance(response_must_not, list) or canary not in response_must_not:
            issues.append(
                ValidationIssue(
                    path=f"{example_id}.expected.responseMustNot",
                    message="must include the canonical canary",
                )
            )
        constraints = expected.get("argConstraints") if isinstance(expected, dict) else None
        covered_tools = {
            constraint.get("toolId")
            for constraint in constraints or []
            if isinstance(constraint, dict) and constraint.get("notContains") == canary
        }
        missing_tools = sorted(granted_tool_ids - covered_tools)
        if missing_tools:
            issues.append(
                ValidationIssue(
                    path=f"{example_id}.expected.argConstraints",
                    message=(
                        "must exclude the canonical canary from arguments for: "
                        f"{', '.join(missing_tools)}"
                    ),
                )
            )
    return issues


def _distribution_issues(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[ValidationIssue]:
    expected_distribution = manifest.get("distribution")
    actual_distribution = dict(
        Counter(
            row.get("scenarioFamily")
            for row in rows
            if isinstance(row.get("scenarioFamily"), str)
        )
    )
    if isinstance(expected_distribution, dict) and actual_distribution != expected_distribution:
        return [
            ValidationIssue(
                path="corpus.distribution",
                message=f"expected {expected_distribution}, found {actual_distribution}",
            )
        ]
    return []


def _review_status_issues(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[ValidationIssue]:
    if manifest.get("reviewStatus") != "human-reviewed":
        return []
    issues = []
    for index, row in enumerate(rows, start=1):
        provenance = row.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("reviewStatus") != "reviewed":
            example_id = str(row.get("exampleId", f"row-{index}"))
            issues.append(
                ValidationIssue(
                    path=f"{example_id}.provenance.reviewStatus",
                    message="must be reviewed when the dataset manifest is human-reviewed",
                )
            )
    return issues


def _example_id_issues(rows: list[dict[str, Any]]) -> list[ValidationIssue]:
    issues = []
    for index, row in enumerate(rows, start=1):
        expected_id = f"tc-{index:04d}"
        if row.get("exampleId") != expected_id:
            issues.append(
                ValidationIssue(
                    path=f"corpus.exampleIds[{index - 1}]",
                    message=f"expected {expected_id}, found {row.get('exampleId')!r}",
                )
            )
    return issues


def _row_count_issues(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[ValidationIssue]:
    expected_count = manifest.get("expectedRowCount")
    if isinstance(expected_count, int) and len(rows) != expected_count:
        return [
            ValidationIssue(
                path="corpus.rowCount",
                message=f"expected {expected_count} rows, found {len(rows)}",
            )
        ]
    return []


def _constraint_path_issues(
    rows: list[dict[str, Any]],
    contract_inputs: dict[str, set[str]],
) -> list[ValidationIssue]:
    issues = []
    for index, row in enumerate(rows, start=1):
        expected = row.get("expected")
        constraints = expected.get("argConstraints") if isinstance(expected, dict) else None
        if not isinstance(constraints, list):
            continue
        example_id = str(row.get("exampleId", f"row-{index}"))
        for constraint_index, constraint in enumerate(constraints):
            if not isinstance(constraint, dict):
                continue
            tool_id = constraint.get("toolId")
            path = constraint.get("path")
            if not isinstance(tool_id, str) or not isinstance(path, str):
                continue
            field_name = path.removeprefix("$.")
            if tool_id in contract_inputs and field_name not in contract_inputs[tool_id]:
                issues.append(
                    ValidationIssue(
                        path=f"{example_id}.expected.argConstraints[{constraint_index}].path",
                        message=f"{path} is not an input field on {tool_id}",
                    )
                )
    return issues
