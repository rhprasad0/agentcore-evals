"""Deterministic source-derived dataset projection loading."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.version_bindings import VersionBindingError, resolve_exact_version_bindings


class DatasetProjectionError(ValueError):
    """A projection cannot be reproduced from its exact source artifacts."""


@dataclass(frozen=True)
class DatasetProjection:
    """A validated projection document and its unchanged source rows."""

    document: dict[str, Any]
    rows: tuple[dict[str, Any], ...]


def _load_object(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetProjectionError(f"cannot load {path}: {error.__class__.__name__}") from error
    if not isinstance(document, dict):
        raise DatasetProjectionError(f"{path} must contain a JSON object")
    return document


def _repo_path(repo_root: Path, relative_path: str) -> Path:
    path = (repo_root / relative_path).resolve()
    if repo_root != path and repo_root not in path.parents:
        raise DatasetProjectionError(f"projection source path escapes repository root: {relative_path}")
    return path


def _sha256_file(path: Path) -> str:
    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise DatasetProjectionError(f"cannot read projection source {path}") from error


def _required_tools(row: Mapping[str, Any]) -> set[str]:
    expected = row.get("expected")
    if not isinstance(expected, dict) or not isinstance(expected.get("toolIds"), list):
        raise DatasetProjectionError(f"{row.get('exampleId', '<unknown>')}: expected.toolIds is invalid")
    return {tool_id for tool_id in expected["toolIds"] if isinstance(tool_id, str)}


def _failure_tools(row: Mapping[str, Any]) -> set[str]:
    injection = row.get("failureInjection")
    if injection is None:
        return set()
    if not isinstance(injection, dict) or not isinstance(injection.get("toolId"), str):
        raise DatasetProjectionError(f"{row.get('exampleId', '<unknown>')}: failureInjection is invalid")
    return {injection["toolId"]}


def load_projection(path: Path, *, repo_root: Path) -> DatasetProjection:
    """Validate and reproduce a projection from exact source bytes."""

    root = repo_root.resolve()
    document = _load_object(path)
    schema = _load_object(root / "schemas/dataset-projection.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        raise DatasetProjectionError(f"projection schema error at {location}: {error.message}")

    source = document["source"]
    manifest_path = _repo_path(root, source["manifestPath"])
    corpus_path = _repo_path(root, source["corpusPath"])
    for label, source_path, expected_hash in (
        ("manifest", manifest_path, source["manifestSha256"]),
        ("corpus", corpus_path, source["corpusSha256"]),
    ):
        observed_hash = _sha256_file(source_path)
        if observed_hash != expected_hash:
            raise DatasetProjectionError(
                f"{label} sha256 mismatch: expected {expected_hash}, observed {observed_hash}"
            )

    source_manifest = _load_object(manifest_path)
    if (source_manifest.get("datasetId"), source_manifest.get("version")) != (
        source["datasetId"],
        source["version"],
    ):
        raise DatasetProjectionError("source dataset identity does not match its pinned manifest")

    bindings = document["specimenBindings"]
    try:
        resolve_exact_version_bindings(
            bindings["agentManifest"],
            bindings["toolContracts"],
            manifests_root=root / "contracts/manifests",
            tool_contracts_root=root / "contracts/tools",
        )
    except VersionBindingError as error:
        raise DatasetProjectionError(f"specimen bindings: {error}") from error

    try:
        rows = [
            json.loads(line)
            for line in corpus_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetProjectionError(f"cannot load source corpus: {error.__class__.__name__}") from error
    if not all(isinstance(row, dict) for row in rows):
        raise DatasetProjectionError("source corpus rows must be JSON objects")

    rule = document["selectionRule"]
    required_allowed = set(rule["requiredToolIdsSubsetOf"])
    failure_allowed = set(rule["failureToolIdsSubsetOf"])
    excluded = {item["exampleId"] for item in document["semanticExclusions"]}
    selected = tuple(
        row
        for row in rows
        if _required_tools(row) <= required_allowed
        and _failure_tools(row) <= failure_allowed
        and row["exampleId"] not in excluded
    )
    observed_ids = [row["exampleId"] for row in selected]
    expected_ids = document["selectedExampleIds"]
    if observed_ids != expected_ids:
        missing = sorted(set(observed_ids) - set(expected_ids))
        extra = sorted(set(expected_ids) - set(observed_ids))
        raise DatasetProjectionError(
            f"selectedExampleIds drift: missing from artifact={missing}; extra in artifact={extra}"
        )
    if len(selected) != document["expectedRowCount"]:
        raise DatasetProjectionError(
            f"expectedRowCount {document['expectedRowCount']} does not match {len(selected)} rows"
        )
    distribution = dict(Counter(row["scenarioFamily"] for row in selected))
    if distribution != document["distribution"]:
        raise DatasetProjectionError(
            f"distribution drift: expected {document['distribution']}, observed {distribution}"
        )
    return DatasetProjection(document=document, rows=selected)
