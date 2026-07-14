"""Validate the repository-owned Week 5 contract artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from src.version_bindings import VersionBindingError, resolve_exact_version_bindings


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FIXTURE_GROUPS = (
    (
        REPO_ROOT / "schemas" / "tool-contract.schema.json",
        REPO_ROOT / "tests" / "fixtures" / "tool-contracts",
    ),
    (
        REPO_ROOT / "schemas" / "capability-manifest.schema.json",
        REPO_ROOT / "tests" / "fixtures" / "capability-manifests",
    ),
)
TOOL_CONTRACTS_ROOT = REPO_ROOT / "contracts" / "tools"
CAPABILITY_MANIFESTS_ROOT = REPO_ROOT / "contracts" / "manifests"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        relative_path = path.relative_to(REPO_ROOT)
        raise ValueError(f"{relative_path}: {error}") from error


def format_schema_errors(path: Path, errors: list[Any]) -> list[str]:
    relative_path = path.relative_to(REPO_ROOT)
    return [f"{relative_path}: {error.message}" for error in errors]


def validate() -> tuple[list[str], dict[str, int]]:
    failures: list[str] = []
    validators: dict[str, Draft202012Validator] = {}
    counts = {
        "schemas": 0,
        "valid_fixtures": 0,
        "invalid_fixtures": 0,
        "tool_contracts": 0,
        "capability_manifests": 0,
    }

    for schema_path, fixture_root in SCHEMA_FIXTURE_GROUPS:
        try:
            schema = load_json(schema_path)
            Draft202012Validator.check_schema(schema)
        except (ValueError, SchemaError) as error:
            failures.append(str(error))
            continue

        validator = Draft202012Validator(schema)
        validators[schema_path.name] = validator
        counts["schemas"] += 1

        valid_paths = sorted((fixture_root / "valid").glob("*.json"))
        invalid_paths = sorted((fixture_root / "invalid").glob("*.json"))
        if not valid_paths:
            failures.append(f"{fixture_root.relative_to(REPO_ROOT)}: no valid fixtures found")
        if not invalid_paths:
            failures.append(f"{fixture_root.relative_to(REPO_ROOT)}: no invalid fixtures found")

        for fixture_path in valid_paths:
            counts["valid_fixtures"] += 1
            try:
                fixture = load_json(fixture_path)
            except ValueError as error:
                failures.append(str(error))
                continue
            failures.extend(
                format_schema_errors(fixture_path, list(validator.iter_errors(fixture)))
            )

        for fixture_path in invalid_paths:
            counts["invalid_fixtures"] += 1
            try:
                fixture = load_json(fixture_path)
            except ValueError as error:
                failures.append(str(error))
                continue
            if not list(validator.iter_errors(fixture)):
                failures.append(
                    f"{fixture_path.relative_to(REPO_ROOT)}: expected schema rejection"
                )

    contract_validator = validators.get("tool-contract.schema.json")
    if contract_validator is not None:
        for contract_path in sorted(TOOL_CONTRACTS_ROOT.glob("*/*.json")):
            counts["tool_contracts"] += 1
            try:
                contract = load_json(contract_path)
            except ValueError as error:
                failures.append(str(error))
                continue
            failures.extend(
                format_schema_errors(
                    contract_path,
                    list(contract_validator.iter_errors(contract)),
                )
            )
            expected_identity = (contract_path.parent.name, contract_path.stem)
            actual_identity = (contract.get("toolId"), contract.get("version"))
            if actual_identity != expected_identity:
                failures.append(
                    f"{contract_path.relative_to(REPO_ROOT)}: path identifies "
                    f"{expected_identity[0]}@{expected_identity[1]}, document identifies "
                    f"{actual_identity[0]}@{actual_identity[1]}"
                )

    manifest_validator = validators.get("capability-manifest.schema.json")
    if manifest_validator is not None:
        for manifest_path in sorted(CAPABILITY_MANIFESTS_ROOT.glob("*/*.json")):
            counts["capability_manifests"] += 1
            try:
                manifest = load_json(manifest_path)
            except ValueError as error:
                failures.append(str(error))
                continue
            manifest_errors = list(manifest_validator.iter_errors(manifest))
            failures.extend(format_schema_errors(manifest_path, manifest_errors))
            if manifest_errors:
                continue
            try:
                resolve_exact_version_bindings(
                    {
                        "manifestId": manifest["manifestId"],
                        "version": manifest["version"],
                    },
                    [
                        {"toolId": tool_id, "version": version}
                        for tool_id, version in manifest["toolGrants"].items()
                    ],
                    manifests_root=CAPABILITY_MANIFESTS_ROOT,
                    tool_contracts_root=TOOL_CONTRACTS_ROOT,
                )
            except VersionBindingError as error:
                failures.append(str(error))

    return failures, counts


def main() -> int:
    failures, counts = validate()
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    print(
        f"Validated {counts['schemas']} schemas, {counts['valid_fixtures']} valid fixtures, "
        f"{counts['invalid_fixtures']} invalid fixtures, {counts['tool_contracts']} tool "
        f"contracts, and {counts['capability_manifests']} capability manifest."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
