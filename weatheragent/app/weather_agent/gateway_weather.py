"""Current-weather wrapper over the governed AgentCore Gateway target."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any, Literal

from strands import tool

from .weather_core import failure, normalize_arguments, result_from_payload

GatewayInvoke = Callable[[dict[str, Any]], Any]
WeatherUnits = Literal["metric", "imperial", "standard"]
GATEWAY_TOOL_NAME = "openweather___get_current_weather"
WEATHER_INPUT_SCHEMA = {
    "json": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "minLength": 1},
            "units": {"type": "string", "enum": ["metric", "imperial", "standard"], "default": "metric"},
        },
        "required": ["city"],
    }
}


def _failure(message: str) -> dict[str, Any]:
    return failure("upstream_5xx", message, retryable=True)


def _result_payload(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict) or result.get("status") != "success" or result.get("isError") is True:
        return None
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
        return None
    text = content[0].get("text")
    if not isinstance(text, str) or not text:
        return None
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def fetch_current_weather(city: str, units: str = "metric", *, invoke: GatewayInvoke) -> dict[str, Any]:
    """Call only current weather through Gateway and normalize its response."""
    city, units, validation_failure = normalize_arguments(city, units)
    if validation_failure is not None:
        return validation_failure
    try:
        result = invoke({"q": city, "units": units})
    except Exception:
        return _failure("current-weather Gateway invocation failed")
    payload = _result_payload(result)
    if payload is None:
        return _failure("current-weather Gateway returned an invalid result")
    return result_from_payload(payload, city, units)


def build_gateway_weather_tool(backend: Any) -> Any:
    """Expose only the approved current-weather Gateway operation to the model."""
    if backend.mcp_tool.name != GATEWAY_TOOL_NAME:
        raise ValueError(f"expected Gateway tool {GATEWAY_TOOL_NAME}")

    def invoke(arguments: dict[str, Any]) -> Any:
        return backend.mcp_client.call_tool_sync(
            tool_use_id=f"gateway-weather-wrapper-{uuid.uuid4()}",
            name=GATEWAY_TOOL_NAME,
            arguments=arguments,
        )

    @tool(name="get_current_weather", inputSchema=WEATHER_INPUT_SCHEMA)
    def get_current_weather(city: str, units: WeatherUnits = "metric") -> dict[str, Any]:
        """Get current weather for a city through the governed weather boundary.

        Does not provide forecasts, history, climate averages, URLs, or credentials.
        Returns the stable weather envelope or a typed failure envelope.
        """
        return fetch_current_weather(city, units, invoke=invoke)

    return get_current_weather
