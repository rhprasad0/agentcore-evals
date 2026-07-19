"""Validation and persistence primitives for the Week 9 draft projection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.tool_calling_dataset import (
    DatasetPaths,
    ValidationIssue,
    load_contract_metadata,
    schema_issues,
    serialize_rows,
)
from src.version_bindings import VersionBindingError, resolve_exact_version_bindings


SOURCE_EXAMPLE_IDS = (
    "tc-0001",
    "tc-0021",
    "tc-0006",
    "tc-0097",
    "tc-0098",
    "tc-0073",
    "tc-0065",
    "tc-0092",
)


@dataclass(frozen=True)
class SlicePaths:
    repo_root: Path
    draft_path: Path
    example_schema_path: Path
    source_manifest_path: Path

    @classmethod
    def from_repo_root(
        cls,
        repo_root: Path,
        *,
        draft_path: Path | None = None,
    ) -> SlicePaths:
        root = repo_root.resolve()
        return cls(
            repo_root=root,
            draft_path=(draft_path or root / "datasets" / "synthetic" / "production-slice-8.jsonl").resolve(),
            example_schema_path=root / "schemas" / "tool-calling-example.schema.json",
            source_manifest_path=root / "datasets" / "synthetic" / "tool-calling-100.manifest.json",
        )


@dataclass
class SliceSnapshot:
    rows: list[dict[str, Any]]
    corpus_path: Path
    source_manifest: dict[str, Any]


def load_slice(paths: SlicePaths) -> SliceSnapshot:
    rows = []
    for line_number, line in enumerate(paths.draft_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        document = json.loads(line)
        if not isinstance(document, dict):
            raise ValueError(f"{paths.draft_path}:{line_number} must contain a JSON object")
        rows.append(document)
    source_manifest = _load_object(paths.source_manifest_path)
    return SliceSnapshot(rows=rows, corpus_path=paths.draft_path, source_manifest=source_manifest)


def slice_revision(snapshot: SliceSnapshot) -> str:
    payload = json.dumps(
        {
            "sourceDataset": {
                "datasetId": snapshot.source_manifest.get("datasetId"),
                "version": snapshot.source_manifest.get("version"),
            },
            "rows": snapshot.rows,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_slice(snapshot: SliceSnapshot, paths: SlicePaths) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    schema = _load_object(paths.example_schema_path)
    validator = Draft202012Validator(schema)
    issues.extend(
        issue
        for index, row in enumerate(snapshot.rows, start=1)
        for issue in schema_issues(validator, row, str(row.get("exampleId", f"row-{index}")))
    )

    if len(snapshot.rows) != len(SOURCE_EXAMPLE_IDS):
        issues.append(ValidationIssue("slice.rowCount", f"expected exactly {len(SOURCE_EXAMPLE_IDS)} rows"))

    example_ids = [row.get("exampleId") for row in snapshot.rows]
    string_example_ids = [value for value in example_ids if isinstance(value, str)]
    if len(string_example_ids) != len(set(string_example_ids)):
        issues.append(ValidationIssue("slice.exampleId", "example IDs must be unique"))
    if set(string_example_ids) != set(SOURCE_EXAMPLE_IDS):
        issues.append(ValidationIssue("slice.exampleId", "rows must match the confirmed source ID set"))

    prompts = [row.get("prompt") for row in snapshot.rows]
    string_prompts = [value for value in prompts if isinstance(value, str)]
    if len(string_prompts) != len(set(string_prompts)):
        issues.append(ValidationIssue("slice.prompt", "prompts must be unique"))

    try:
        resolve_exact_version_bindings(
            snapshot.source_manifest["agentManifest"],
            snapshot.source_manifest["toolContracts"],
            manifests_root=paths.repo_root / "contracts" / "manifests",
            tool_contracts_root=paths.repo_root / "contracts" / "tools",
        )
    except (KeyError, TypeError, VersionBindingError) as error:
        issues.append(ValidationIssue("sourceManifest.bindings", str(error)))

    metadata, metadata_issues = load_contract_metadata(
        snapshot.source_manifest,
        DatasetPaths.from_repo_root(paths.repo_root),
    )
    issues.extend(
        ValidationIssue("sourceManifest.toolContracts", issue.message)
        for issue in metadata_issues
    )
    input_fields = metadata.input_fields
    granted_tool_ids = {
        reference["toolId"]
        for reference in snapshot.source_manifest.get("toolContracts", [])
        if isinstance(reference, dict) and isinstance(reference.get("toolId"), str)
    }
    for row in snapshot.rows:
        example_id = str(row.get("exampleId", "row"))
        expected = row.get("expected")
        if not isinstance(expected, dict):
            continue
        for field in ("toolIds", "mustNotCall"):
            values = expected.get(field, [])
            if isinstance(values, list):
                unknown = sorted(
                    value for value in values
                    if isinstance(value, str) and value not in granted_tool_ids
                )
                if unknown:
                    issues.append(ValidationIssue(f"{example_id}.expected.{field}", f"unknown tool IDs: {', '.join(unknown)}"))
        minimum = expected.get("minCalls")
        maximum = expected.get("maxCalls")
        if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
            issues.append(ValidationIssue(f"{example_id}.expected.minCalls", "must be less than or equal to maxCalls"))
        constraints = expected.get("argConstraints", [])
        if isinstance(constraints, list):
            for index, constraint in enumerate(constraints):
                if not isinstance(constraint, dict):
                    continue
                tool_id = constraint.get("toolId")
                path = constraint.get("path")
                if tool_id not in granted_tool_ids:
                    issues.append(ValidationIssue(f"{example_id}.expected.argConstraints[{index}].toolId", f"unknown tool ID: {tool_id}"))
                if isinstance(tool_id, str) and isinstance(path, str):
                    field = path[2:] if path.startswith("$.") else path
                    if field not in input_fields.get(tool_id, set()):
                        issues.append(ValidationIssue(f"{example_id}.expected.argConstraints[{index}].path", f"{path} is not an input of {tool_id}"))
        failure = row.get("failureInjection")
        if isinstance(failure, dict) and failure.get("toolId") not in granted_tool_ids:
            issues.append(ValidationIssue(f"{example_id}.failureInjection.toolId", f"unknown tool ID: {failure.get('toolId')}"))
    return issues


def _load_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document
