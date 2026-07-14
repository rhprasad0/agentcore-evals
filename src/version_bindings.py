"""Exact manifest and tool-contract bindings shared by future dataset/run consumers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFESTS_ROOT = REPO_ROOT / "contracts" / "manifests"
TOOL_CONTRACTS_ROOT = REPO_ROOT / "contracts" / "tools"


class VersionBindingError(ValueError):
    """An exact consumer binding cannot resolve to the reviewed registry."""


@dataclass(frozen=True, order=True)
class VersionRef:
    """One readable, exact artifact reference."""

    artifact_id: str
    version: str

    @property
    def label(self) -> str:
        return f"{self.artifact_id}@{self.version}"


@dataclass(frozen=True)
class ExactVersionBindings:
    """Canonical version bindings that become one component of dataset/run identity."""

    agent_manifest: VersionRef
    tool_contracts: tuple[VersionRef, ...]

    @classmethod
    def from_refs(
        cls,
        agent_manifest: Mapping[str, str],
        tool_contracts: Iterable[Mapping[str, str]],
    ) -> ExactVersionBindings:
        manifest_ref = _version_ref(agent_manifest, "manifestId")
        contract_refs = tuple(
            sorted(_version_ref(reference, "toolId") for reference in tool_contracts)
        )
        tool_ids = [reference.artifact_id for reference in contract_refs]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("tool contract bindings must contain each toolId exactly once")
        return cls(agent_manifest=manifest_ref, tool_contracts=contract_refs)

    @property
    def identity(self) -> str:
        tool_labels = ",".join(reference.label for reference in self.tool_contracts)
        return f"manifest={self.agent_manifest.label};tools={tool_labels}"


def resolve_exact_version_bindings(
    agent_manifest: Mapping[str, str],
    tool_contracts: Iterable[Mapping[str, str]],
    *,
    manifests_root: Path = MANIFESTS_ROOT,
    tool_contracts_root: Path = TOOL_CONTRACTS_ROOT,
) -> ExactVersionBindings:
    """Resolve consumer pins exactly; never retarget them to another reviewed version."""
    try:
        bindings = ExactVersionBindings.from_refs(agent_manifest, tool_contracts)
    except ValueError as error:
        raise VersionBindingError(str(error)) from error

    manifest_ref = bindings.agent_manifest
    manifest_path = manifests_root / manifest_ref.artifact_id / f"{manifest_ref.version}.json"
    manifest = _load_registry_document(manifest_path, "capability manifest")
    actual_manifest_ref = (manifest.get("manifestId"), manifest.get("version"))
    expected_manifest_ref = (manifest_ref.artifact_id, manifest_ref.version)
    if actual_manifest_ref != expected_manifest_ref:
        raise VersionBindingError(
            f"{manifest_path}: expected capability manifest {manifest_ref.label}, found "
            f"{actual_manifest_ref[0]}@{actual_manifest_ref[1]}"
        )

    grants = manifest.get("toolGrants")
    if not isinstance(grants, dict):
        raise VersionBindingError(f"{manifest_path}: toolGrants must be an object")
    consumer_grants = {
        reference.artifact_id: reference.version for reference in bindings.tool_contracts
    }
    mismatches = _grant_mismatches(grants, consumer_grants)
    if mismatches:
        raise VersionBindingError(
            f"consumer bindings do not match {manifest_ref.label} grants: "
            + "; ".join(mismatches)
        )

    for contract_ref in bindings.tool_contracts:
        contract_path = (
            tool_contracts_root
            / contract_ref.artifact_id
            / f"{contract_ref.version}.json"
        )
        contract = _load_registry_document(contract_path, "tool contract")
        actual_contract_ref = (contract.get("toolId"), contract.get("version"))
        expected_contract_ref = (contract_ref.artifact_id, contract_ref.version)
        if actual_contract_ref != expected_contract_ref:
            raise VersionBindingError(
                f"{contract_path}: expected tool contract {contract_ref.label}, found "
                f"{actual_contract_ref[0]}@{actual_contract_ref[1]}"
            )

    return bindings


def _version_ref(reference: Mapping[str, str], id_field: str) -> VersionRef:
    artifact_id = reference.get(id_field)
    version = reference.get("version")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise ValueError(f"exact version binding requires non-empty {id_field}")
    if not isinstance(version, str) or not version:
        raise ValueError("exact version binding requires non-empty version")
    return VersionRef(artifact_id=artifact_id, version=version)


def _load_registry_document(path: Path, artifact_kind: str) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VersionBindingError(
            f"cannot resolve exact {artifact_kind} at {path}: {error.__class__.__name__}"
        ) from error
    if not isinstance(document, dict):
        raise VersionBindingError(f"{path}: {artifact_kind} must be a JSON object")
    return document


def _grant_mismatches(
    expected: Mapping[str, object],
    actual: Mapping[str, str],
) -> list[str]:
    mismatches = []
    for tool_id in sorted(expected.keys() | actual.keys()):
        expected_version = expected.get(tool_id)
        actual_version = actual.get(tool_id)
        if expected_version != actual_version:
            mismatches.append(
                f"{tool_id} expected {expected_version or '<ungranted>'}, "
                f"got {actual_version or '<missing>'}"
            )
    return mismatches
