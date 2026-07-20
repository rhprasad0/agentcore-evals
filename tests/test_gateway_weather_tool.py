"""Offline checks for the narrow governed-weather Runtime wrapper."""

from __future__ import annotations

import json
import unittest
from typing import Any

from weatheragent.app.weather_agent.gateway_weather import (
    GATEWAY_TOOL_NAME,
    build_gateway_weather_tool,
    fetch_current_weather,
)
from scripts.verify_gateway_weather_boundary import run_trace, select_current_weather_tool


SUCCESS = {
    "status": "success",
    "isError": False,
    "content": [
        {
            "text": json.dumps(
                {
                    "name": "Oslo",
                    "main": {"temp": 12.5},
                    "weather": [{"description": "clear sky"}],
                }
            )
        }
    ],
}


class FakeMCPClient:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def call_tool_sync(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


class FakeTool:
    name = GATEWAY_TOOL_NAME


class FakeBackend:
    def __init__(self, result: Any, *, tool_name: str = GATEWAY_TOOL_NAME) -> None:
        self.mcp_client = FakeMCPClient(result)
        self.mcp_tool = FakeTool()
        self.mcp_tool.name = tool_name


class AdvertisedGatewayTool:
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name


class GatewayWeatherToolTests(unittest.TestCase):
    def test_success_normalizes_gateway_payload(self) -> None:
        calls: list[dict[str, Any]] = []
        result = fetch_current_weather(" Oslo ", "metric", invoke=lambda arguments: calls.append(arguments) or SUCCESS)

        self.assertEqual(
            {"ok": True, "city": "Oslo", "temp": 12.5, "units": "metric", "conditions": "clear sky"}, result
        )
        self.assertEqual([{"q": "Oslo", "units": "metric"}], calls)

    def test_invalid_input_never_reaches_gateway(self) -> None:
        calls: list[dict[str, Any]] = []
        result = fetch_current_weather("", invoke=lambda arguments: calls.append(arguments))

        self.assertEqual(False, result["ok"])
        self.assertEqual("bad_input", result["error"]["kind"])
        self.assertEqual([], calls)

    def test_model_contract_excludes_credential_and_forecast(self) -> None:
        backend = FakeBackend(SUCCESS)
        wrapper = build_gateway_weather_tool(backend)
        properties = wrapper.tool_spec["inputSchema"]["json"]["properties"]

        self.assertEqual("get_current_weather", wrapper.tool_spec["name"])
        self.assertEqual({"city", "units"}, set(properties))
        self.assertNotIn("appid", properties)

        self.assertTrue(wrapper(city="Oslo")["ok"])
        self.assertEqual(GATEWAY_TOOL_NAME, backend.mcp_client.calls[0]["name"])
        self.assertEqual({"q": "Oslo", "units": "metric"}, backend.mcp_client.calls[0]["arguments"])

    def test_wrong_gateway_tool_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_gateway_weather_tool(FakeBackend(SUCCESS, tool_name="openweather___get_forecast"))

    def test_trace_uses_the_weather_value_as_the_calculator_input(self) -> None:
        receipt = run_trace(
            lambda *, city: {"ok": True, "city": city, "temp": 12.5, "units": "metric", "conditions": "clear sky"},
            "Oslo",
            2.0,
        )

        self.assertEqual(12.5, receipt["intermediate_temperature"])
        self.assertEqual({"ok": True, "value": "25"}, receipt["calculator"])

    def test_trace_selects_only_the_approved_gateway_operation(self) -> None:
        approved = AdvertisedGatewayTool(GATEWAY_TOOL_NAME)

        self.assertIs(approved, select_current_weather_tool([AdvertisedGatewayTool("openweather___get_forecast"), approved]))
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            select_current_weather_tool([AdvertisedGatewayTool("openweather___get_forecast")])


if __name__ == "__main__":
    unittest.main()
