"""Fail-closed capability-manifest enforcement for agent tool portfolios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
WEATHER_MANIFEST_PATH = REPO_ROOT / "contracts" / "manifests" / "agents.weather" / "3.0.0.json"
CONTRACTS_ROOT = REPO_ROOT / "contracts" / "tools"
CAPABILITY_MANIFEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "capability-manifest.schema.json"
TOOL_CONTRACT_SCHEMA_PATH = REPO_ROOT / "schemas" / "tool-contract.schema.json"
SIDE_EFFECT_LEVELS = {"none": 0, "read_external": 1, "write_external": 2}


def validate_tool_portfolio(tools: list[Any], manifest_path: Path = WEATHER_MANIFEST_PATH) -> list[Any]:
    """Reject tools that do not resolve to an exact contract granted by the manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest_errors = list(Draft202012Validator(manifest_schema).iter_errors(manifest))
    if manifest_errors:
        details = "; ".join(error.message for error in manifest_errors)
        raise RuntimeError(f"Capability manifest {manifest_path} is invalid: {details}")
    contract_schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    contract_validator = Draft202012Validator(contract_schema)
    contracts_by_name = {}
    for tool_id, version in manifest["toolGrants"].items():
        contract_path = CONTRACTS_ROOT / tool_id / f"{version}.json"
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Manifest grant {tool_id}@{version} in {manifest_path} cannot load exact "
                f"contract {contract_path}: {error.__class__.__name__}."
            ) from error
        contract_errors = list(contract_validator.iter_errors(contract))
        if contract_errors:
            details = "; ".join(error.message for error in contract_errors)
            raise RuntimeError(
                f"Manifest grant {tool_id}@{version} resolved to an invalid contract: {details}"
            )
        actual_identity = f"{contract.get('toolId')}@{contract.get('version')}"
        expected_identity = f"{tool_id}@{version}"
        if actual_identity != expected_identity:
            raise RuntimeError(
                f"Manifest grant {expected_identity} resolved to contract identity {actual_identity} "
                f"at {contract_path}. Fix the contract identity or grant the matching exact version."
            )
        contracts_by_name[contract["name"]] = contract

    seen_tool_ids: set[str] = set()
    for tool in tools:
        runtime_name = tool.tool_spec["name"]
        if runtime_name not in contracts_by_name:
            relative_manifest = manifest_path.relative_to(REPO_ROOT)
            raise RuntimeError(
                f"Tool {runtime_name!r} is not granted by capability manifest {relative_manifest}. "
                "Add an exact tool contract grant or remove the tool before constructing Agent(...)."
            )
        contract = contracts_by_name[runtime_name]
        tool_id = contract["toolId"]
        if tool_id in seen_tool_ids:
            relative_manifest = manifest_path.relative_to(REPO_ROOT)
            raise RuntimeError(
                f"Duplicate toolId {tool_id!r} violates capability manifest {relative_manifest}. "
                "Register each granted capability exactly once before constructing Agent(...)."
            )
        seen_tool_ids.add(tool_id)
        side_effects = contracts_by_name[runtime_name]["sideEffects"]
        ceiling = manifest["sideEffectCeiling"]
        if SIDE_EFFECT_LEVELS[side_effects] > SIDE_EFFECT_LEVELS[ceiling]:
            raise RuntimeError(
                f"Tool {tool_id!r} declares sideEffects {side_effects!r}, above manifest ceiling "
                f"{ceiling!r}. Raise the reviewed ceiling or remove the tool before constructing "
                "Agent(...)."
            )
        contract_input = dict(contract["inputSchema"])
        contract_input.pop("$schema", None)
        expected_spec = {
            "name": contract["name"],
            "description": contract["description"],
            "inputSchema": {"json": contract_input},
        }
        drifted_fields = [
            field for field, expected in expected_spec.items() if tool.tool_spec.get(field) != expected
        ]
        if drifted_fields:
            raise RuntimeError(
                f"Tool {tool_id!r} final model-visible spec drifts in "
                f"{', '.join(drifted_fields)}. Update the runtime tool or grant a new exact contract "
                "version before constructing Agent(...)."
            )

    return tools
