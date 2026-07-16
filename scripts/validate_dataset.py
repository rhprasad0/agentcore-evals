"""Validate the repository-owned Week 6 dataset artifacts."""

from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.telemetry_normalization import (
    TelemetryNormalizationError,
    canonical_projection_bytes,
    normalize_strands_telemetry,
    validate_agentcore_evaluation_input,
)
from src.deterministic_mocks import MockFixtureError, MockRegistry
from src.tool_calling_dataset import (
    DatasetPaths,
    DatasetSnapshot,
    ValidationIssue,
    load_dataset,
    validate_dataset,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_SAFETY_PATTERNS = (
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("AWS ARN", re.compile(r"\barn:(?:aws|aws-us-gov|aws-cn):[^\s\"'<>]+")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("credential-bearing URL", re.compile(r"https?://[^/\s:@]+:[^@\s/]+@")),
    ("12-digit account identifier", re.compile(r"(?<![0-9A-Fa-f])[0-9]{12}(?![0-9A-Fa-f])")),
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
PUBLIC_EXAMPLE_DOMAINS = {"example.com", "example.net", "example.org"}


def validate_invalid_dataset_fixtures(
    repo_root: Path,
    snapshot: DatasetSnapshot,
    paths: DatasetPaths,
    *,
    fixture_root: Path | None = None,
) -> tuple[list[ValidationIssue], int]:
    root = fixture_root or repo_root / "tests/fixtures/tool-calling-dataset/invalid"
    fixture_paths = sorted(root.glob("*.json"))
    issues = []
    if not fixture_paths:
        return [ValidationIssue("invalidFixtures", "no invalid fixtures found")], 0
    for fixture_path in fixture_paths:
        try:
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            mutations = fixture["mutations"]
            expected = fixture["expectedIssue"]
            if not isinstance(mutations, list) or len(mutations) != 1:
                raise ValueError("must declare exactly one mutation")
            candidate = DatasetSnapshot(
                manifest=deepcopy(snapshot.manifest),
                rows=deepcopy(snapshot.rows),
                corpus_path=snapshot.corpus_path,
            )
            _apply_fixture_mutation(candidate, mutations[0])
            candidate_issues = validate_dataset(candidate, paths)
            expected_path = expected["path"]
            expected_message = expected["messageContains"]
            if not any(
                issue.path == expected_path and expected_message in issue.message
                for issue in candidate_issues
            ):
                raise ValueError(
                    f"expected issue {expected_path!r} containing {expected_message!r}; "
                    f"found {candidate_issues!r}"
                )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            issues.append(
                ValidationIssue(
                    fixture_path.relative_to(repo_root).as_posix(),
                    str(error),
                )
            )
    return issues, len(fixture_paths)


def _apply_fixture_mutation(snapshot: DatasetSnapshot, mutation: dict[str, object]) -> None:
    target_name = mutation["target"]
    if target_name == "manifest":
        target: Any = snapshot.manifest
    else:
        target = next(
            row for row in snapshot.rows if row.get("exampleId") == target_name
        )
    pointer = mutation["path"]
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("mutation path must be a JSON pointer")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    parent: Any = target
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    leaf = parts[-1]
    operation = mutation["operation"]
    if operation == "replace":
        if isinstance(parent, list):
            parent[int(leaf)] = deepcopy(mutation["value"])
        else:
            parent[leaf] = deepcopy(mutation["value"])
    elif operation == "remove":
        if isinstance(parent, list):
            parent.pop(int(leaf))
        else:
            del parent[leaf]
    else:
        raise ValueError(f"unsupported mutation operation: {operation!r}")


def validate_public_safety(repo_root: Path, paths: list[Path]) -> list[ValidationIssue]:
    issues = []
    for path in paths:
        try:
            resolved_path = path.resolve()
            display_path = resolved_path.relative_to(repo_root.resolve()).as_posix()
            text = resolved_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as error:
            issues.append(ValidationIssue(str(path), str(error)))
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PUBLIC_SAFETY_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        ValidationIssue(
                            path=f"{display_path}:{line_number}",
                            message=f"contains a real-looking {label}",
                        )
                    )
            for email_match in EMAIL_PATTERN.finditer(line):
                if email_match.group(1).lower() not in PUBLIC_EXAMPLE_DOMAINS:
                    issues.append(
                        ValidationIssue(
                            path=f"{display_path}:{line_number}",
                            message="contains a non-example email address",
                        )
                    )
    return issues


def validate_mock_fixtures(
    repo_root: Path,
    snapshot: DatasetSnapshot,
    *,
    fixtures_path: Path | None = None,
) -> list[ValidationIssue]:
    source_path = fixtures_path or repo_root / "datasets/fixtures/mocks/tool-calling.jsonl"
    try:
        MockRegistry.from_repo_root(repo_root, fixtures_path=source_path)
        documents = [
            json.loads(line)
            for line in source_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, MockFixtureError) as error:
        return [ValidationIssue("mocks.fixtures", str(error))]

    canary = snapshot.manifest.get("canonicalCanary")
    issues = []
    required_tools = {
        reference["toolId"]
        for reference in snapshot.manifest.get("toolContracts", [])
        if isinstance(reference, dict) and isinstance(reference.get("toolId"), str)
    }
    success_tools = {
        document["toolId"]
        for document in documents
        if isinstance(document.get("toolId"), str)
        and isinstance(document.get("result"), dict)
        and document["result"].get("ok") is True
    }
    missing_success = sorted(required_tools - success_tools)
    if missing_success:
        issues.append(
            ValidationIssue(
                path="mocks.successCoverage",
                message=f"missing successful fixture for: {', '.join(missing_success)}",
            )
        )
    for index, row in enumerate(snapshot.rows, start=1):
        injection = row.get("failureInjection")
        if not isinstance(injection, dict):
            continue
        example_id = str(row.get("exampleId", f"row-{index}"))
        matching_results = [
            document.get("result")
            for document in documents
            if document.get("exampleId") == example_id
            and document.get("toolId") == injection.get("toolId")
        ]
        if not any(
            isinstance(result, dict)
            and isinstance(result.get("error"), dict)
            and result["error"].get("kind") == injection.get("kind")
            and result["error"].get("retryable") == injection.get("retryable")
            for result in matching_results
        ):
            issues.append(
                ValidationIssue(
                    path=f"mocks.{example_id}.failureInjection",
                    message="missing matching deterministic failure fixture",
                )
            )
    for index, row in enumerate(snapshot.rows, start=1):
        if "untrusted-result" not in row.get("tags", []):
            continue
        example_id = str(row.get("exampleId", f"row-{index}"))
        expected = row.get("expected")
        expected_tools = expected.get("toolIds", []) if isinstance(expected, dict) else []
        matches = [
            document
            for document in documents
            if document.get("exampleId") == example_id
            and document.get("toolId") in expected_tools
        ]
        canary_count = sum(
            json.dumps(document.get("result"), ensure_ascii=False).count(str(canary))
            for document in matches
        )
        if canary_count != 1:
            issues.append(
                ValidationIssue(
                    path=f"mocks.{example_id}.result",
                    message=f"expected exactly one canonical canary, found {canary_count}",
                )
            )
        serialized_results = "\n".join(
            json.dumps(document.get("result"), ensure_ascii=False).lower()
            for document in matches
        )
        armed_markers = (
            "ignore previous instructions",
            "follow these instructions",
            "system prompt",
            "developer message",
        )
        if any(marker in serialized_results for marker in armed_markers):
            issues.append(
                ValidationIssue(
                    path=f"mocks.{example_id}.result",
                    message="contains armed-looking instruction text",
                )
            )
    return issues


def validate_telemetry_compatibility(repo_root: Path) -> list[ValidationIssue]:
    fixture_root = repo_root / "tests/fixtures/telemetry"
    try:
        inline_source = json.loads(
            (fixture_root / "strands-inline/weather-success.json").read_text(encoding="utf-8")
        )
        adot_source = json.loads(
            (fixture_root / "strands-adot/weather-success.json").read_text(encoding="utf-8")
        )
        expected = json.loads(
            (fixture_root / "canonical/weather-success.json").read_text(encoding="utf-8")
        )
        managed_input = json.loads(
            (fixture_root / "agentcore-evaluation-input/session-spans.json").read_text(
                encoding="utf-8"
            )
        )
        inline_trace = normalize_strands_telemetry(inline_source, repo_root=repo_root)
        adot_trace = normalize_strands_telemetry(adot_source, repo_root=repo_root)
        validate_agentcore_evaluation_input(managed_input)
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        TelemetryNormalizationError,
    ) as error:
        return [ValidationIssue("telemetry.fixtures", str(error))]

    issues = []
    if inline_trace != expected:
        issues.append(
            ValidationIssue(
                "telemetry.strandsInline",
                "normalized trace does not match the canonical fixture",
            )
        )
    if canonical_projection_bytes(inline_trace) != canonical_projection_bytes(adot_trace):
        issues.append(
            ValidationIssue(
                "telemetry.canonicalProjection",
                "inline and ADOT profiles do not produce byte-identical projections",
            )
        )
    return issues


def main() -> int:
    paths = DatasetPaths.from_repo_root(REPO_ROOT)
    snapshot = load_dataset(paths)
    issues = validate_dataset(snapshot, paths)
    invalid_issues, invalid_count = validate_invalid_dataset_fixtures(
        REPO_ROOT,
        snapshot,
        paths,
    )
    issues.extend(invalid_issues)
    issues.extend(validate_mock_fixtures(REPO_ROOT, snapshot))
    issues.extend(validate_telemetry_compatibility(REPO_ROOT))

    mock_path = REPO_ROOT / "datasets/fixtures/mocks/tool-calling.jsonl"
    invalid_paths = sorted(
        (REPO_ROOT / "tests/fixtures/tool-calling-dataset/invalid").glob("*.json")
    )
    telemetry_paths = sorted((REPO_ROOT / "tests/fixtures/telemetry").rglob("*.json"))
    safety_paths = [
        paths.manifest_path,
        snapshot.corpus_path,
        REPO_ROOT / snapshot.manifest["generationPromptPath"],
        REPO_ROOT / snapshot.manifest["editorialChecklistPath"],
        mock_path,
        *invalid_paths,
        *telemetry_paths,
    ]
    issues.extend(validate_public_safety(REPO_ROOT, safety_paths))
    if issues:
        for issue in issues:
            print(f"ERROR: {issue.path}: {issue.message}", file=sys.stderr)
        return 1

    mock_count = sum(
        1 for line in mock_path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    print(
        f"Validated {len(snapshot.rows)} dataset rows, {invalid_count} invalid regression "
        f"fixtures, {mock_count} mock fixtures, 2 telemetry profiles, and 1 managed-input "
        "fixture."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
