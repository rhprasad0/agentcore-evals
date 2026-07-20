"""Run one governed current-weather to calculator trace without a model call."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from strands.tools.mcp.mcp_client import MCPClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.weather import DEPLOYED_STATE_PATH, load_gateway_url, scrub
from src.tools.calculator import calculator
from weatheragent.app.weather_agent.gateway_weather import GATEWAY_TOOL_NAME, build_gateway_weather_tool


def select_current_weather_tool(advertised_tools: list[Any]) -> Any:
    approved = [tool for tool in advertised_tools if tool.tool_name == GATEWAY_TOOL_NAME]
    if len(approved) != 1:
        raise RuntimeError(f"Expected exactly one {GATEWAY_TOOL_NAME!r} tool; found {len(approved)}.")
    return approved[0]


def run_trace(weather_tool: Callable[..., dict[str, Any]], city: str, multiplier: float) -> dict[str, Any]:
    weather = weather_tool(city=city)
    if weather.get("ok") is not True:
        return {"weather": weather, "calculator": None}
    calculation = calculator(expression=f"{weather['temp']} * {multiplier}")
    return {"weather": weather, "intermediate_temperature": weather["temp"], "calculator": calculation}


def main() -> int:
    from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client  # pyright: ignore[reportMissingImports]

    parser = argparse.ArgumentParser(description="Verify one governed weather-to-calculator trace.")
    parser.add_argument("city")
    parser.add_argument("--multiplier", type=float, default=2.0)
    args = parser.parse_args()
    gateway_url = load_gateway_url(os.environ, DEPLOYED_STATE_PATH)
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=gateway_url,
            aws_region=region,
            aws_service="bedrock-agentcore",
        )
    )
    with client:
        weather_tool = build_gateway_weather_tool(select_current_weather_tool(list(client.list_tools_sync())))
        receipt = run_trace(weather_tool, args.city, args.multiplier)
    print(json.dumps(scrub(receipt), indent=2, sort_keys=True))
    calculator = receipt.get("calculator")
    return 0 if isinstance(calculator, dict) and calculator.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
