"""Frozen pre-output human-review sample loading for Week 7."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.dataset_projection import load_projection


class ReviewSampleError(ValueError):
    """A frozen review sample no longer resolves to its exact source."""


@dataclass(frozen=True)
class FrozenReviewSample:
    document: dict[str, Any]
    rows: tuple[dict[str, Any], ...]


def load_frozen_review_sample(
    path: Path,
    *,
    projection_path: Path,
    repo_root: Path,
) -> FrozenReviewSample:
    """Resolve a predeclared review sample against exact projection bytes."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewSampleError(f"cannot load frozen review sample: {error}") from error
    expected_keys = {
        "schemaVersion",
        "sampleId",
        "frozenAt",
        "freezeBoundary",
        "projection",
        "selectionRule",
        "selectedExampleIds",
        "triageRules",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise ReviewSampleError("frozen review sample fields do not match version 1.0.0")
    if document["schemaVersion"] != "1.0.0":
        raise ReviewSampleError("unsupported frozen review sample schemaVersion")
    if document["freezeBoundary"] != "before-full-projection-output":
        raise ReviewSampleError("review sample must be frozen before full projection output")
    projection_ref = document["projection"]
    if not isinstance(projection_ref, dict):
        raise ReviewSampleError("projection reference must be an object")
    observed_hash = sha256(projection_path.read_bytes()).hexdigest()
    if projection_ref.get("artifactSha256") != observed_hash:
        raise ReviewSampleError(
            f"projection hash mismatch: expected {projection_ref.get('artifactSha256')}, observed {observed_hash}"
        )
    projection = load_projection(projection_path, repo_root=repo_root)
    if (
        projection_ref.get("projectionId"),
        projection_ref.get("version"),
    ) != (
        projection.document["projectionId"],
        projection.document["version"],
    ):
        raise ReviewSampleError("projection identity does not match frozen review sample")
    selected_ids = document["selectedExampleIds"]
    if (
        not isinstance(selected_ids, list)
        or len(selected_ids) != 10
        or len(set(selected_ids)) != 10
        or not all(isinstance(example_id, str) for example_id in selected_ids)
    ):
        raise ReviewSampleError("selectedExampleIds must contain ten unique string IDs")
    rows_by_id = {row["exampleId"]: row for row in projection.rows}
    missing = [example_id for example_id in selected_ids if example_id not in rows_by_id]
    if missing:
        raise ReviewSampleError(f"sample IDs are absent from projection: {missing}")
    triage_rules = document["triageRules"]
    required_rules = {
        "dataset-bug",
        "agent-bug",
        "contract-ambiguity",
        "instrument-error",
    }
    if (
        not isinstance(triage_rules, dict)
        or set(triage_rules) != required_rules
        or not all(isinstance(value, str) and value.strip() for value in triage_rules.values())
    ):
        raise ReviewSampleError("triageRules must define four non-empty classifications")
    return FrozenReviewSample(
        document=document,
        rows=tuple(rows_by_id[example_id] for example_id in selected_ids),
    )
