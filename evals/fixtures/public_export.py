"""Export exact synthetic evaluation evidence with provenance."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from evals.fixtures.manifest import validate_exact_fixture_safety
from src.dataset_projection import load_projection
from src.execution_trace_validation import validate_execution_trace_semantics
from src.run_manifest import derive_experiment_id


class PublicFixtureExportError(ValueError):
    """Private run evidence cannot be exported without weakening the contract."""



def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PublicFixtureExportError(
            f"cannot load {path}: {error.__class__.__name__}"
        ) from error
    if not isinstance(value, dict):
        raise PublicFixtureExportError(f"{path} must contain a JSON object")
    return value


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _validate_schema(
    document: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    label: str,
) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise PublicFixtureExportError(
            f"{label} schema error at {location}: {error.message}"
        )


def export_fixture_set(
    run_directory: Path,
    projection_path: Path,
    output_directory: Path,
    *,
    artifact_prefix: str,
    repo_root: Path,
) -> dict[str, Any]:
    """Export one completed synthetic run without altering source artifacts."""

    root = repo_root.resolve()
    run = run_directory.resolve()
    if output_directory.exists():
        raise PublicFixtureExportError(
            f"output directory already exists: {output_directory}"
        )
    manifest = _load_object(run / "run-manifest.json")
    run_schema = _load_object(root / "schemas/run-manifest.schema.json")
    _validate_schema(manifest, run_schema, label="run manifest")
    if derive_experiment_id(manifest["behaviorPins"]) != manifest["experimentId"]:
        raise PublicFixtureExportError("run manifest experimentId does not match behavior pins")
    if manifest["outputs"] is None or manifest["outputs"]["status"] != "completed":
        raise PublicFixtureExportError("run manifest must describe a completed run")

    projection = load_projection(projection_path, repo_root=root)
    projection_hash = sha256(projection_path.read_bytes()).hexdigest()
    expected_projection = {
        "projectionId": projection.document["projectionId"],
        "version": projection.document["version"],
        "artifactSha256": projection_hash,
    }
    if manifest["behaviorPins"]["datasetProjection"] != expected_projection:
        raise PublicFixtureExportError("run projection identity does not match export projection")

    trace_schema = _load_object(root / "schemas/execution-trace.schema.json")
    documents: list[tuple[Path, bytes]] = []
    fixture_entries: list[dict[str, Any]] = []
    canonical_count = 0
    error_count = 0
    canonicalizer_version: str | None = None
    source_profile = manifest["behaviorPins"]["sourceProfile"]
    producer_version = manifest["behaviorPins"]["sdkVersions"]["strands-agents"]

    for row in projection.rows:
        example_id = row["exampleId"]
        case_directory = run / "cases" / example_id
        outcome = _load_object(case_directory / "outcome.json")
        if outcome.get("exampleId") != example_id:
            raise PublicFixtureExportError(f"{example_id}: outcome identity mismatch")
        status = outcome.get("status")
        if status == "completed":
            source_path = case_directory / "canonical-trace.json"
            payload = source_path.read_bytes()
            source_trace = _load_object(source_path)
            _validate_schema(source_trace, trace_schema, label=f"{example_id} source trace")
            validate_execution_trace_semantics(source_trace, repo_root=root)
            if source_trace["sourceProfile"]["name"] != source_profile["profileId"]:
                raise PublicFixtureExportError(f"{example_id}: source profile mismatch")
            if source_trace["sourceProfile"]["producer"]["version"] != producer_version:
                raise PublicFixtureExportError(f"{example_id}: producer version mismatch")
            observed_canonicalizer = source_trace["canonicalizerVersion"]
            if canonicalizer_version is None:
                canonicalizer_version = observed_canonicalizer
            elif canonicalizer_version != observed_canonicalizer:
                raise PublicFixtureExportError(
                    f"{example_id}: canonicalizer version mismatch"
                )
            relative = Path("traces") / f"{example_id}.json"
            entry: dict[str, Any] = {
                "exampleId": example_id,
                "status": "canonical-trace",
                "path": f"{artifact_prefix}/{relative.as_posix()}",
            }
            canonical_count += 1
        elif status == "instrument-error":
            source_path = case_directory / "instrument-error.json"
            payload = source_path.read_bytes()
            source_error = _load_object(source_path)
            error_kind = outcome.get("errorKind")
            if not isinstance(error_kind, str) or source_error.get("kind") != error_kind:
                raise PublicFixtureExportError(f"{example_id}: instrument error mismatch")
            relative = Path("errors") / f"{example_id}.json"
            entry = {
                "exampleId": example_id,
                "status": "instrument-error",
                "path": f"{artifact_prefix}/{relative.as_posix()}",
                "errorKind": error_kind,
            }
            error_count += 1
        else:
            raise PublicFixtureExportError(
                f"{example_id}: unsupported outcome status {status!r}"
            )
        validate_exact_fixture_safety(
            payload.decode("utf-8"),
            label=f"{example_id} source artifact",
        )
        entry["sha256"] = sha256(payload).hexdigest()
        fixture_entries.append(entry)
        documents.append((relative, payload))

    if canonicalizer_version is None:
        raise PublicFixtureExportError("fixture set contains no canonical traces")
    expected_ids = list(projection.document["selectedExampleIds"])
    public_manifest = {
        "schemaVersion": "1.0.0",
        "fixtureSetId": "evals.weather_only_regression",
        "version": "1.0.0",
        "experimentId": manifest["experimentId"],
        "sourceRun": {
            "runId": manifest["runId"],
            "executedAt": manifest["executedAt"],
        },
        "projection": expected_projection,
        "traceContract": {
            "schemaId": trace_schema["$id"],
            "schemaVersion": "1.0.0",
            "canonicalizerVersion": canonicalizer_version,
            "sourceProfile": source_profile,
        },
        "expectedCaseIds": expected_ids,
        "fixtures": fixture_entries,
        "counts": {
            "expected": len(expected_ids),
            "canonicalTrace": canonical_count,
            "instrumentError": error_count,
        },
        "publicSafety": {
            "policyId": "safety.exact_synthetic_fixture",
            "version": "1.0.0",
            "publicationMode": "exact-source-artifacts",
            "automatedChecks": [
                "schema",
                "semantics",
                "provenance",
                "secrets",
                "privatePaths",
                "awsIdentifiers",
                "contactIdentifiers",
            ],
        },
    }
    fixture_schema = _load_object(root / "schemas/eval-fixture-manifest.schema.json")
    _validate_schema(public_manifest, fixture_schema, label="fixture manifest")
    manifest_payload = _json_bytes(public_manifest)
    validate_exact_fixture_safety(
        manifest_payload.decode("utf-8"),
        label="fixture manifest",
    )

    output_directory.mkdir(parents=True)
    for relative, payload in documents:
        path = output_directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (output_directory / "manifest.json").write_bytes(manifest_payload)
    return public_manifest
