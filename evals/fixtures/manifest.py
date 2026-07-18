"""Independent validation for provenance-linked public evaluation fixtures."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.dataset_projection import load_projection
from src.execution_trace_validation import validate_execution_trace_semantics


class FixtureManifestError(ValueError):
    """A fixture manifest or one of its artifacts violates provenance."""


class ExactFixtureSafetyError(ValueError):
    """An exact synthetic artifact contains data forbidden from publication."""


_FORBIDDEN_EXACT_FIXTURE_PATTERNS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "AWS access key"),
    (
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
        "bearer token",
    ),
    (
        re.compile(r"(?:^|[\"'\s])/home/[^\s\"']+"),
        "private home path",
    ),
    (re.compile(r"\barn:aws(?:-[a-z]+)?:"), "AWS ARN"),
    (
        re.compile(r"(?<![A-Za-z0-9])[0-9]{12}(?![A-Za-z0-9])"),
        "AWS account ID",
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "email address",
    ),
    (
        re.compile(
            r"\+?[1-9][0-9]{0,2}[ .-]\(?[2-9][0-9]{2}\)?"
            r"[ .-][0-9]{3}[ .-][0-9]{4}\b"
        ),
        "phone number",
    ),
    (
        re.compile(
            r"\b(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|"
            r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})\b"
        ),
        "private IPv4 address",
    ),
)


def validate_exact_fixture_safety(text: str, *, label: str) -> None:
    """Reject concrete secrets and private identifiers without transforming text."""

    for pattern, description in _FORBIDDEN_EXACT_FIXTURE_PATTERNS:
        if pattern.search(text):
            raise ExactFixtureSafetyError(
                f"{label}: exact fixture contains forbidden {description}"
            )


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FixtureManifestError(
            f"cannot load {path}: {error.__class__.__name__}"
        ) from error
    if not isinstance(value, dict):
        raise FixtureManifestError(f"{path} must contain a JSON object")
    return value


def _schema_errors(
    document: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> list[str]:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def _validate_public_trace(
    trace: Mapping[str, Any],
    *,
    example_id: str,
    expected_prompt: str,
    source_run_id: str,
    trace_contract: Mapping[str, Any],
    trace_schema: Mapping[str, Any],
    repo_root: Path,
) -> None:
    errors = _schema_errors(trace, trace_schema)
    if errors:
        raise FixtureManifestError(f"{example_id}: trace schema error at {errors[0]}")
    validate_execution_trace_semantics(trace, repo_root=repo_root)
    if trace.get("schemaVersion") != trace_contract["schemaVersion"]:
        raise FixtureManifestError(f"{example_id}: trace schemaVersion mismatch")
    if trace.get("canonicalizerVersion") != trace_contract["canonicalizerVersion"]:
        raise FixtureManifestError(f"{example_id}: canonicalizerVersion mismatch")
    source_profile = trace.get("sourceProfile")
    if not isinstance(source_profile, Mapping) or (
        source_profile.get("name")
        != trace_contract["sourceProfile"]["profileId"]
    ):
        raise FixtureManifestError(f"{example_id}: source profile mismatch")
    if trace.get("sessionId") != f"{source_run_id}:{example_id}":
        raise FixtureManifestError(
            f"{example_id}: sessionId does not match source run"
        )
    if trace.get("prompt") != expected_prompt:
        raise FixtureManifestError(f"{example_id}: prompt does not match dataset")
    response = trace.get("response")
    if not isinstance(response, str) or not response.strip():
        raise FixtureManifestError(f"{example_id}: response must be non-empty")


def validate_fixture_manifest(
    manifest_path: Path,
    *,
    projection_path: Path,
    artifact_root: Path,
    artifact_prefix: str,
    expected_experiment_id: str,
    repo_root: Path,
) -> dict[str, Any]:
    """Validate a fixture set without consulting its private source run."""

    root = repo_root.resolve()
    manifest = _load_object(manifest_path)
    fixture_schema = _load_object(root / "schemas/eval-fixture-manifest.schema.json")
    errors = _schema_errors(manifest, fixture_schema)
    if errors:
        raise FixtureManifestError(f"fixture manifest schema error at {errors[0]}")
    if manifest["experimentId"] != expected_experiment_id:
        raise FixtureManifestError("fixture manifest belongs to a different experiment")

    projection = load_projection(projection_path, repo_root=root)
    expected_projection = {
        "projectionId": projection.document["projectionId"],
        "version": projection.document["version"],
        "artifactSha256": sha256(projection_path.read_bytes()).hexdigest(),
    }
    if manifest["projection"] != expected_projection:
        raise FixtureManifestError("fixture manifest projection identity is stale")
    expected_ids = list(projection.document["selectedExampleIds"])
    expected_prompts = {
        row["exampleId"]: row["prompt"]
        for row in projection.rows
    }
    if manifest["expectedCaseIds"] != expected_ids:
        raise FixtureManifestError("fixture manifest expected case IDs do not match projection")

    fixtures = manifest["fixtures"]
    fixture_ids = [entry["exampleId"] for entry in fixtures]
    if fixture_ids != expected_ids:
        raise FixtureManifestError("fixture entries must match projection IDs in source order")
    if len(set(fixture_ids)) != len(fixture_ids):
        raise FixtureManifestError("fixture entries contain duplicate example IDs")
    observed_counts = {
        "expected": len(expected_ids),
        "canonicalTrace": sum(
            entry["status"] == "canonical-trace" for entry in fixtures
        ),
        "instrumentError": sum(
            entry["status"] == "instrument-error" for entry in fixtures
        ),
    }
    if manifest["counts"] != observed_counts:
        raise FixtureManifestError("fixture manifest counts do not match entries")

    trace_schema = _load_object(root / "schemas/execution-trace.schema.json")
    if manifest["traceContract"]["schemaId"] != trace_schema["$id"]:
        raise FixtureManifestError("trace schema identity is stale")
    expected_paths: set[Path] = set()
    validate_exact_fixture_safety(
        manifest_path.read_text(encoding="utf-8"),
        label="fixture manifest",
    )
    prefix = f"{artifact_prefix}/"
    for entry in fixtures:
        path_value = entry["path"]
        if not path_value.startswith(prefix):
            raise FixtureManifestError(
                f"{entry['exampleId']}: fixture path escapes artifact prefix"
            )
        relative = Path(path_value.removeprefix(prefix))
        resolved_artifact_root = artifact_root.resolve()
        resolved_path = (artifact_root / relative).resolve()
        if (
            relative.is_absolute()
            or any(part in {".", ".."} for part in relative.parts)
            or not resolved_path.is_relative_to(resolved_artifact_root)
        ):
            raise FixtureManifestError(
                f"{entry['exampleId']}: fixture path escapes artifact root"
            )
        path = artifact_root / relative
        expected_paths.add(relative)
        if not path.is_file():
            raise FixtureManifestError(f"{entry['exampleId']}: fixture file is missing")
        payload = path.read_bytes()
        if sha256(payload).hexdigest() != entry["sha256"]:
            raise FixtureManifestError(f"{entry['exampleId']}: fixture hash mismatch")
        validate_exact_fixture_safety(
            payload.decode("utf-8"),
            label=f"{entry['exampleId']} fixture artifact",
        )
        document = _load_object(path)
        if entry["status"] == "canonical-trace":
            _validate_public_trace(
                document,
                example_id=entry["exampleId"],
                expected_prompt=expected_prompts[entry["exampleId"]],
                source_run_id=manifest["sourceRun"]["runId"],
                trace_contract=manifest["traceContract"],
                trace_schema=trace_schema,
                repo_root=root,
            )
        else:
            if (
                set(document) != {"kind", "message"}
                or document.get("kind") != entry["errorKind"]
                or not isinstance(document.get("message"), str)
                or not document["message"]
            ):
                raise FixtureManifestError(
                    f"{entry['exampleId']}: instrument error artifact mismatch"
                )

    actual_paths = {
        path.relative_to(artifact_root)
        for path in artifact_root.rglob("*.json")
        if path != manifest_path
    }
    if actual_paths != expected_paths:
        missing = sorted(str(path) for path in expected_paths - actual_paths)
        extra = sorted(str(path) for path in actual_paths - expected_paths)
        raise FixtureManifestError(
            f"fixture directory membership mismatch: missing={missing}, extra={extra}"
        )
    return manifest
