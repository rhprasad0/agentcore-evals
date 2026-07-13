"""Deployable Week 2 weather tool with typed failure envelopes.

The Strands-facing tool never raises raw HTTP/auth exceptions across the
agent boundary. It returns a closed, labelable envelope instead.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Literal

import requests
from strands import tool

from .weather_core import (
    FAILURE_KINDS,
    VALID_UNITS,
    failure,
    normalize_arguments,
    result_from_payload,
    status_failure,
)
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"
WeatherUnits = Literal["metric", "imperial", "standard"]


def fetch_current_weather(
    city: str,
    units: str = "metric",
    *,
    api_key: str | None = None,
    http_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Fetch current weather and return either a success or failure envelope."""
    city, units, validation_failure = normalize_arguments(city, units)
    if validation_failure is not None:
        return validation_failure

    resolved_api_key = api_key if api_key is not None else os.environ.get("OWM_API_KEY")
    if not resolved_api_key:
        return failure("auth", "OWM_API_KEY is not set", retryable=False)

    try:
        response = http_get(
            OWM_URL,
            params={"q": city, "units": units, "appid": resolved_api_key},
            timeout=5,
        )
    except requests.Timeout:
        return failure("timeout", "upstream exceeded 5s", retryable=True)
    except requests.RequestException as exc:
        return failure("network", exc.__class__.__name__, retryable=True)

    status_code = getattr(response, "status_code", None)
    if status_code is not None and status_code >= 400:
        return status_failure(status_code)

    try:
        data = response.json()
    except (TypeError, ValueError):
        return failure("upstream_5xx", "weather API returned an unexpected response shape", retryable=True)
    return result_from_payload(data, city, units)


@tool
def get_current_weather(city: str, units: WeatherUnits = "metric") -> dict[str, Any]:
    """Get current weather for a city. Not forecasts, history, or climate averages.

    units must be 'metric', 'imperial', or 'standard'. Returns {ok, city, temp,
    units, conditions} on success or {ok: False, error: {kind, message,
    retryable}} on failure.
    """
    return fetch_current_weather(city, units)
