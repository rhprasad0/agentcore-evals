#!/usr/bin/env python3
"""Compare direct and Gateway-backed current-weather seams without an LLM."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client  # pyright: ignore[reportMissingImports]
from strands.tools.mcp.mcp_client import MCPClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.weather import DEPLOYED_STATE_PATH, load_gateway_url
from src.tools.weather import fetch_current_weather, get_current_weather

GATEWAY_WEATHER_TOOL = "weather-lambda___get_current_weather"
INVALID_CITY = "NoSuchCityWeek4"


def _timed_call(call: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter()
    result = call()
    return round((time.perf_counter() - started) * 1000, 1), result


def _parse_gateway_result(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content", [])
    if not content or not isinstance(content[0], dict) or not isinstance(content[0].get("text"), str):
        raise RuntimeError("Gateway weather tool returned no JSON text content.")
    payload = json.loads(content[0]["text"])
    return {
        "mcpStatus": result.get("status"),
        "mcpIsError": result.get("isError"),
        "payload": payload,
    }


def _summarize_latencies(samples: list[float]) -> dict[str, Any]:
    return {
        "samplesMs": samples,
        "medianMs": round(statistics.median(samples), 1),
        "minMs": min(samples),
        "maxMs": max(samples),
    }


def compare(city: str, units: str, samples: int) -> dict[str, Any]:
    endpoint = load_gateway_url(os.environ, DEPLOYED_STATE_PATH)
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=endpoint,
            aws_region=region,
            aws_service="bedrock-agentcore",
        )
    )

    direct_spec = get_current_weather.tool_spec
    direct_latencies: list[float] = []
    direct_results: list[dict[str, Any]] = []
    gateway_latencies: list[float] = []
    gateway_results: list[dict[str, Any]] = []

    with client:
        advertised = [tool for tool in client.list_tools_sync() if tool.tool_name == GATEWAY_WEATHER_TOOL]
        if len(advertised) != 1:
            raise RuntimeError(f"Expected exactly one {GATEWAY_WEATHER_TOOL}; found {len(advertised)}.")
        gateway_tool = advertised[0]

        for index in range(samples):
            direct_ms, direct_result = _timed_call(lambda: fetch_current_weather(city, units))
            gateway_ms, gateway_result = _timed_call(
                lambda index=index: client.call_tool_sync(
                    f"week4-success-{index}",
                    GATEWAY_WEATHER_TOOL,
                    {"city": city, "units": units},
                )
            )
            direct_latencies.append(direct_ms)
            direct_results.append(direct_result)
            gateway_latencies.append(gateway_ms)
            gateway_results.append(_parse_gateway_result(gateway_result))

        direct_failure_ms, direct_failure = _timed_call(lambda: fetch_current_weather(INVALID_CITY, units))
        gateway_failure_ms, gateway_failure = _timed_call(
            lambda: client.call_tool_sync(
                "week4-invalid-city",
                GATEWAY_WEATHER_TOOL,
                {"city": INVALID_CITY, "units": units},
            )
        )

        gateway_spec = gateway_tool.tool_spec

    direct_input = direct_spec["inputSchema"]["json"]
    gateway_input = gateway_spec["inputSchema"]["json"]
    return {
        "schema": {
            "directToolName": direct_spec["name"],
            "gatewayToolName": gateway_spec["name"],
            "descriptionsEqual": direct_spec["description"] == gateway_spec["description"],
            "directDescription": direct_spec["description"],
            "gatewayDescription": gateway_spec["description"],
            "directRequired": direct_input.get("required", []),
            "gatewayRequired": gateway_input.get("required", []),
            "directUnitsHasDefault": "default" in direct_input["properties"]["units"],
            "gatewayUnitsHasDefault": "default" in gateway_input["properties"]["units"],
        },
        "success": {
            "city": city,
            "units": units,
            "directLatency": _summarize_latencies(direct_latencies),
            "gatewayLatency": _summarize_latencies(gateway_latencies),
            "medianGatewayOverheadMs": round(
                statistics.median(gateway_latencies) - statistics.median(direct_latencies),
                1,
            ),
            "directResults": direct_results,
            "gatewayResults": gateway_results,
        },
        "invalidCity": {
            "directLatencyMs": direct_failure_ms,
            "gatewayLatencyMs": gateway_failure_ms,
            "directResult": direct_failure,
            "gatewayResult": _parse_gateway_result(gateway_failure),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="Oslo")
    parser.add_argument("--units", choices=("metric", "imperial", "standard"), default="metric")
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    if args.samples < 1:
        raise SystemExit("--samples must be at least 1")
    print(json.dumps(compare(args.city, args.units, args.samples), indent=2))


if __name__ == "__main__":
    main()
