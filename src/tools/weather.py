"""Compatibility import for the deployable weather tool implementation."""

from weatheragent.app.weather_agent.weather_tool import (
    FAILURE_KINDS,
    OWM_URL,
    VALID_UNITS,
    fetch_current_weather,
    get_current_weather,
)

__all__ = [
    "FAILURE_KINDS",
    "OWM_URL",
    "VALID_UNITS",
    "fetch_current_weather",
    "get_current_weather",
]
