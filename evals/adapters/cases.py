"""Map validated source-derived dataset projections into Strands Evals cases."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from strands_evals import Case, Experiment

from src.dataset_projection import load_projection
from src.tool_calling_dataset import DatasetPaths, load_dataset, validate_dataset


class CaseAdapterError(ValueError):
    """Source dataset evidence is not valid enough to construct SDK cases."""


def _case_metadata(
    row: Mapping[str, Any],
    projection_document: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    source = projection_document["source"]
    bindings = projection_document["specimenBindings"]
    return deepcopy(
        {
            "expected": row["expected"],
            "tags": row["tags"],
            "scenarioFamily": row["scenarioFamily"],
            "failureInjection": row["failureInjection"],
            "rowProvenance": row["provenance"],
            "versionBindings": {
                "dataset": {
                    "datasetId": source["datasetId"],
                    "version": source["version"],
                    "schemaVersion": source_manifest["schemaVersion"],
                    "taxonomyVersion": source_manifest["taxonomyVersion"],
                },
                "projection": {
                    "projectionId": projection_document["projectionId"],
                    "version": projection_document["version"],
                },
                "agentManifest": bindings["agentManifest"],
                "toolContracts": bindings["toolContracts"],
            },
        }
    )


def build_projection_cases(
    projection_path: Path,
    *,
    repo_root: Path,
) -> list[Case]:
    """Build ordered SDK cases after validating source and projection contracts."""

    root = repo_root.resolve()
    dataset_paths = DatasetPaths.from_repo_root(root)
    source_snapshot = load_dataset(dataset_paths)
    source_issues = validate_dataset(source_snapshot, dataset_paths)
    if source_issues:
        first = source_issues[0]
        raise CaseAdapterError(
            f"source dataset validation failed at {first.path}: {first.message}"
        )

    projection = load_projection(projection_path, repo_root=root)
    projection_identity = (
        f"{projection.document['projectionId']}@{projection.document['version']}"
    )
    return [
        Case(
            name=row["exampleId"],
            session_id=f"{projection_identity}:{row['exampleId']}",
            input=row["prompt"],
            metadata=_case_metadata(row, projection.document, source_snapshot.manifest),
        )
        for row in projection.rows
    ]


def build_projection_experiment(
    projection_path: Path,
    *,
    repo_root: Path,
    evaluators: Sequence[Any],
) -> Experiment:
    """Build a runnable Experiment without the SDK's empty-evaluator fallback."""

    if not evaluators:
        raise CaseAdapterError("at least one evaluator is required")
    cases = build_projection_cases(projection_path, repo_root=repo_root)
    return Experiment(cases=cases, evaluators=list(evaluators))
