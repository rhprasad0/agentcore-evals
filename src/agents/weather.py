"""Week 4 Strands multi-tool agent runner.

This script explicitly registers direct weather and calculator tools plus the
approved AgentCore Gateway Web Search tool. Inspection opens the Gateway MCP
session but does not invoke a model, weather provider, or search tool.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYED_STATE_PATH = REPO_ROOT / "weatheragent" / "agentcore" / ".cli" / "deployed-state.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.contracts import validate_tool_portfolio
from src.tools.calculator import calculator
from src.tools.web_search import build_web_search_tool
from src.tools.weather import get_current_weather
from weatheragent.app.weather_agent.weather_contract import PORTFOLIO_SYSTEM_PROMPT

APPID_RE = re.compile(r"([?&]appid=)[^&\s]+")
OWM_KEY_RE = re.compile(r"\b[a-f0-9]{32}\b", re.IGNORECASE)
EXPECTED_WEB_SEARCH_TOOL = "web-search___WebSearch"
GATEWAY_URL_ENV = "AGENTCORE_GATEWAY_URL"


def load_gateway_url(environ: Mapping[str, str], state_path: Path) -> str:
    """Load the Gateway endpoint without exposing it in tracked configuration."""
    if gateway_url := environ.get(GATEWAY_URL_ENV):
        return gateway_url
    try:
        state = json.loads(state_path.read_text())
        gateway_url = state["targets"]["default"]["resources"]["mcp"]["gateways"]["eval-gateway"][
            "gatewayUrl"
        ]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Set {GATEWAY_URL_ENV} or deploy eval-gateway so local AgentCore state is available."
        ) from error
    if not isinstance(gateway_url, str) or not gateway_url:
        raise RuntimeError("The local eval-gateway deployment state has no Gateway URL.")
    return gateway_url


def select_web_search_tool(advertised_tools: list[Any]) -> Any:
    """Select the single explicitly approved Gateway Web Search tool."""
    approved = [tool for tool in advertised_tools if tool.tool_name == EXPECTED_WEB_SEARCH_TOOL]
    if len(approved) != 1:
        raise RuntimeError(
            f"Expected exactly one {EXPECTED_WEB_SEARCH_TOOL!r} tool; found {len(approved)}."
        )
    return approved[0]


def registered_tool_specs(tools: list[Any]) -> list[dict[str, Any]]:
    """Return each registered tool specification in model-visible order."""
    return [tool.tool_spec for tool in tools]


def build_registered_tools(advertised_tools: list[Any]) -> list[Any]:
    """Build the fixed Week 4 portfolio from direct and approved MCP tools."""
    web_search = build_web_search_tool(select_web_search_tool(advertised_tools))
    return [get_current_weather, calculator, web_search]


def scrub(value: Any) -> Any:
    """Redact OpenWeatherMap keys before printing local receipts."""
    if isinstance(value, str):
        return OWM_KEY_RE.sub("<OWM_API_KEY>", APPID_RE.sub(r"\1<OWM_API_KEY>", value))
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    return value


def build_agent(tools: list[Any]) -> Agent:
    """Build the agent only after its fixed tool portfolio passes manifest enforcement."""
    validated_tools = validate_tool_portfolio(tools)
    return Agent(
        system_prompt=PORTFOLIO_SYSTEM_PROMPT,
        tools=validated_tools,
        callback_handler=None,
    )


def print_tool_specs(tools: list[Any]) -> None:
    """Print what Strands exposes to the model for all registered tools."""
    print(json.dumps(scrub(registered_tool_specs(tools)), indent=2, sort_keys=True))


def main() -> None:
    from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client  # pyright: ignore[reportMissingImports]

    parser = argparse.ArgumentParser(description="Run or inspect the Week 4 multi-tool agent.")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="What's the current weather in Seattle?",
        help="Prompt to send to the agent when not using --inspect-tool.",
    )
    parser.add_argument(
        "--inspect-tool",
        action="store_true",
        help="Print all registered Strands tool specs without invoking the model or tools.",
    )
    args = parser.parse_args()

    gateway_url = load_gateway_url(os.environ, DEPLOYED_STATE_PATH)
    aws_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    gateway_client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=gateway_url,
            aws_region=aws_region,
            aws_service="bedrock-agentcore",
        )
    )

    with gateway_client:
        tools = build_registered_tools(list(gateway_client.list_tools_sync()))
        if args.inspect_tool:
            print_tool_specs(tools)
            return

        agent = build_agent(tools)
        result = agent(args.prompt)
        print("=== Final answer (scrubbed) ===")
        print(json.dumps(scrub(str(result)), indent=2))
        print("\n=== Agent messages (scrubbed) ===")
        print(json.dumps(scrub(agent.messages), indent=2))


if __name__ == "__main__":
    main()
