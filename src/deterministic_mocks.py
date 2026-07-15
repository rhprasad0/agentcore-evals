"""Deterministic tool fixtures pinned to exact reviewed contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.version_bindings import ExactVersionBindings, resolve_exact_version_bindings


CANONICALIZER_VERSION = "1.0.0"


class MockFixtureError(ValueError):
    """A deterministic fixture or call identity violates the mock contract."""


class UnknownMockFixtureError(LookupError):
    """A schema-valid call has no exact deterministic fixture."""


@dataclass(frozen=True)
class FixtureKey:
    """Readable fixture identity plus a hash suitable for lookup."""

    tool_id: str
    contract_version: str
    canonicalizer_version: str
    canonical_arguments: str
    arguments_hash: str

    @classmethod
    def from_call(
        cls,
        tool_id: str,
        contract_version: str,
        arguments: Mapping[str, Any],
        *,
        canonicalizer_version: str = CANONICALIZER_VERSION,
    ) -> FixtureKey:
        identity = {
            "tool_id": tool_id,
            "contract_version": contract_version,
            "canonicalizer_version": canonicalizer_version,
        }
        for field, value in identity.items():
            if not isinstance(value, str) or not value:
                raise MockFixtureError(f"{field} must be a non-empty string")
        canonical_arguments = json.dumps(
            dict(arguments),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return cls(
            tool_id=tool_id,
            contract_version=contract_version,
            canonicalizer_version=canonicalizer_version,
            canonical_arguments=canonical_arguments,
            arguments_hash=sha256(canonical_arguments.encode("utf-8")).hexdigest(),
        )


class MockRegistry:
    """Row-scoped deterministic results for an exact reviewed tool portfolio."""

    def __init__(
        self,
        bindings: ExactVersionBindings,
        contracts: Mapping[str, Mapping[str, Any]],
        fixtures: Mapping[tuple[str, FixtureKey], Mapping[str, Any]],
    ) -> None:
        self.bindings = bindings
        self._contracts = {tool_id: dict(contract) for tool_id, contract in contracts.items()}
        self._fixtures = dict(fixtures)

    @classmethod
    def from_repo_root(
        cls,
        repo_root: Path,
        *,
        fixtures_path: Path | None = None,
    ) -> MockRegistry:
        root = repo_root.resolve()
        manifest = json.loads(
            (root / "datasets/synthetic/tool-calling-100.manifest.json").read_text(
                encoding="utf-8"
            )
        )
        bindings = resolve_exact_version_bindings(
            manifest["agentManifest"],
            manifest["toolContracts"],
            manifests_root=root / "contracts/manifests",
            tool_contracts_root=root / "contracts/tools",
        )
        contracts = {
            reference.artifact_id: json.loads(
                (
                    root
                    / "contracts/tools"
                    / reference.artifact_id
                    / f"{reference.version}.json"
                ).read_text(encoding="utf-8")
            )
            for reference in bindings.tool_contracts
        }
        fixtures = {}
        fixture_path = fixtures_path or root / "datasets/fixtures/mocks/tool-calling.jsonl"
        for line in fixture_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            document = json.loads(line)
            if document.get("canonicalizerVersion") != CANONICALIZER_VERSION:
                raise MockFixtureError(
                    f"{fixture_path}: {document.get('exampleId', '<unknown>')} has unsupported "
                    f"canonicalizerVersion {document.get('canonicalizerVersion')!r}; "
                    f"expected {CANONICALIZER_VERSION}"
                )
            key = FixtureKey.from_call(
                document["toolId"],
                document["contractVersion"],
                document["arguments"],
                canonicalizer_version=document["canonicalizerVersion"],
            )
            if document.get("argumentsHash") != key.arguments_hash:
                raise MockFixtureError(
                    f"{fixture_path}: {document.get('exampleId', '<unknown>')} "
                    "argumentsHash does not match canonical arguments"
                )
            contract = contracts.get(key.tool_id)
            if contract is None or contract.get("version") != key.contract_version:
                raise MockFixtureError(
                    f"{fixture_path}: {document.get('exampleId', '<unknown>')} references "
                    f"unbound contract {key.tool_id}@{key.contract_version}"
                )
            input_errors = _schema_error_messages(contract["inputSchema"], document["arguments"])
            if input_errors:
                raise MockFixtureError(
                    f"{document['exampleId']} arguments: {'; '.join(input_errors)}"
                )
            result_errors = _schema_error_messages(contract["outputSchema"], document["result"])
            if result_errors:
                raise MockFixtureError(
                    f"{document['exampleId']} result: {'; '.join(result_errors)}"
                )
            scoped_key = (document["exampleId"], key)
            if scoped_key in fixtures:
                raise MockFixtureError(
                    f"{fixture_path}: duplicate fixture key for {document['exampleId']} "
                    f"{key.tool_id}@{key.contract_version} sha256={key.arguments_hash}"
                )
            fixtures[scoped_key] = document["result"]
        return cls(bindings, contracts, fixtures)

    def invoke(
        self,
        example_id: str,
        tool_id: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        versions = {
            reference.artifact_id: reference.version
            for reference in self.bindings.tool_contracts
        }
        contract = self._contracts.get(tool_id)
        if contract is None:
            raise MockFixtureError(f"{tool_id} is not granted by {self.bindings.agent_manifest.label}")
        errors = sorted(
            Draft202012Validator(contract["inputSchema"]).iter_errors(arguments),
            key=lambda error: list(error.path),
        )
        if errors:
            error = errors[0]
            suffix = "".join(f".{part}" for part in error.path)
            raise MockFixtureError(
                f"{tool_id}@{versions[tool_id]} arguments{suffix}: {error.message}"
            )
        key = FixtureKey.from_call(tool_id, versions[tool_id], arguments)
        fixture = self._fixtures.get((example_id, key))
        if fixture is None:
            raise UnknownMockFixtureError(
                f"no deterministic fixture for example={example_id}; "
                f"tool={tool_id}@{key.contract_version}; "
                f"canonicalizer={key.canonicalizer_version}; "
                f"arguments={key.canonical_arguments}; sha256={key.arguments_hash}"
            )
        return deepcopy(dict(fixture))

    def registered_surfaces(self) -> tuple[dict[str, Any], ...]:
        """Return exact contract-owned interfaces in canonical binding order."""

        return tuple(
            deepcopy(self._contracts[reference.artifact_id])
            for reference in self.bindings.tool_contracts
        )


def _schema_error_messages(schema: Mapping[str, Any], value: Any) -> list[str]:
    messages = []
    pending = list(Draft202012Validator(schema).iter_errors(value))
    while pending:
        error = pending.pop(0)
        messages.append(error.message)
        pending.extend(error.context)
    return messages
