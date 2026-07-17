"""Offline-configurable one-tool weather specimen for Week 7 evaluation."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from hashlib import sha256
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from src.contracts import validate_tool_portfolio
from src.deterministic_mocks import CANONICALIZER_VERSION, MockRegistry
from src.run_manifest import canonical_json_bytes
from src.tools.weather import get_current_weather
from src.version_bindings import resolve_exact_version_bindings
from weatheragent.app.weather_agent.weather_contract import SYSTEM_PROMPT


REPO_ROOT = Path(__file__).resolve().parents[2]
WEATHER_SPECIMEN_MANIFEST_PATH = (
    REPO_ROOT / "contracts/manifests/agents.weather/4.0.0.json"
)
PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"
MOCK_FIXTURES_PATH = REPO_ROOT / "datasets/fixtures/mocks/tool-calling.jsonl"
MODEL_ID = "us.amazon.nova-micro-v1:0"


def build_specimen_model() -> BedrockModel:
    """Build the exact Bedrock model configuration pinned by the run manifest."""

    return BedrockModel(
        model_id=MODEL_ID,
        temperature=0.0,
        top_p=1.0,
        max_tokens=1024,
    )


def build_mock_weather_tool(registry: MockRegistry, example_id: str) -> Any:
    """Bind the exact weather surface to one row-scoped deterministic fixture world."""

    spec = get_current_weather.tool_spec

    @tool(
        name=spec["name"],
        description=spec["description"],
        inputSchema=spec["inputSchema"],
    )
    def mock_weather(city: str, units: str | None = None) -> dict[str, Any]:
        arguments = {"city": city}
        if units is not None:
            arguments["units"] = units
        return registry.invoke(
            example_id,
            "weather.get_current_weather",
            arguments,
        )

    return mock_weather


def build_specimen(
    *,
    model: Any,
    registry: MockRegistry,
    example_id: str,
    trace_attributes: Mapping[str, str] | None = None,
) -> Agent:
    """Construct the agent only after its one-tool surface passes exact validation."""

    mock_weather = build_mock_weather_tool(registry, example_id)
    tools = validate_tool_portfolio(
        [mock_weather],
        manifest_path=WEATHER_SPECIMEN_MANIFEST_PATH,
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        callback_handler=None,
        trace_attributes=trace_attributes,
    )


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _utf8_pin(value: str) -> dict[str, Any]:
    encoded = value.encode("utf-8")
    return {"sha256": sha256(encoded).hexdigest(), "utf8ByteLength": len(encoded)}


def build_behavior_pins(
    repo_root: Path = REPO_ROOT,
    *,
    version_provider: Callable[[str], str] = package_version,
) -> dict[str, Any]:
    """Derive behavior pins from exact checked-in and final model-visible values."""

    root = repo_root.resolve()
    projection_path = root / "datasets/projections/weather-only-62.json"
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    bindings_document = projection["specimenBindings"]
    bindings = resolve_exact_version_bindings(
        bindings_document["agentManifest"],
        bindings_document["toolContracts"],
        manifests_root=root / "contracts/manifests",
        tool_contracts_root=root / "contracts/tools",
    )
    manifest_path = (
        root
        / "contracts/manifests"
        / bindings.agent_manifest.artifact_id
        / f"{bindings.agent_manifest.version}.json"
    )
    validated_tools = validate_tool_portfolio([get_current_weather], manifest_path=manifest_path)
    tool = validated_tools[0]
    tool_ref = bindings.tool_contracts[0]
    tool_spec = tool.tool_spec
    description = tool_spec["description"]
    return {
        "model": {"provider": "bedrock", "modelId": MODEL_ID},
        "systemPrompt": _utf8_pin(SYSTEM_PROMPT),
        "capabilityManifest": {
            "manifestId": bindings.agent_manifest.artifact_id,
            "version": bindings.agent_manifest.version,
        },
        "tools": [
            {
                "toolId": tool_ref.artifact_id,
                "version": tool_ref.version,
                "runtimeName": tool_spec["name"],
                "descriptionSha256": sha256(description.encode("utf-8")).hexdigest(),
                "registeredSpecSha256": sha256(canonical_json_bytes(tool_spec)).hexdigest(),
            }
        ],
        "datasetProjection": {
            "projectionId": projection["projectionId"],
            "version": projection["version"],
            "artifactSha256": _file_sha256(projection_path),
        },
        "mockRegistry": {
            "fixtureId": "mocks.tool_calling",
            "version": "1.0.0",
            "canonicalizerVersion": CANONICALIZER_VERSION,
            "fixtureSha256": _file_sha256(root / "datasets/fixtures/mocks/tool-calling.jsonl"),
        },
        "sampling": {
            "temperature": {"status": "set", "value": 0.0},
            "topP": {"status": "set", "value": 1.0},
            "topK": {"status": "unsupported"},
            "seed": {"status": "unsupported"},
            "stopSequences": {"status": "omitted"},
            "maxTokens": {"status": "set", "value": 1024},
        },
        "sdkVersions": {
            package: version_provider(package)
            for package in (
                "strands-agents",
                "strands-agents-evals",
                "botocore",
                "bedrock-agentcore",
                "aws-opentelemetry-distro",
            )
        },
        "sourceProfile": {"profileId": "strands-inline", "version": "1.0.0"},
    }
