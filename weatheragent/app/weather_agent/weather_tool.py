"""Deployable Week 2 weather tool with typed failure envelopes.

The Strands-facing tool never raises raw HTTP/auth exceptions across the
agent boundary. It returns a closed, labelable envelope instead.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import requests
from strands import tool

FAILURE_KINDS = (
    "bad_input",
    "auth",
    "upstream_4xx",
    "upstream_5xx",
    "timeout",
    "network",
)

VALID_UNITS = ("metric", "imperial", "standard")
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


def _fail(kind: str, message: str, *, retryable: bool) -> dict[str, Any]:
    """Build a validated failure envelope for the agent/tool boundary."""
    if kind not in FAILURE_KINDS:
        raise ValueError(f"unknown failure kind: {kind}")
    if not message:
        raise ValueError("failure message must be non-empty")
    return {"ok": False, "error": {"kind": kind, "message": message, "retryable": retryable}}


def fetch_current_weather(
    city: str,
    units: str = "metric",
    *,
    api_key: str | None = None,
    http_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Fetch current weather and return either a success or failure envelope."""
    city = city.strip() if isinstance(city, str) else ""
    units = units.strip().lower() if isinstance(units, str) else ""

    if not city:
        return _fail("bad_input", "city must be non-empty", retryable=False)
    if units not in VALID_UNITS:
        return _fail(
            "bad_input",
            f"units must be one of: {', '.join(VALID_UNITS)}",
            retryable=False,
        )

    resolved_api_key = api_key if api_key is not None else os.environ.get("OWM_API_KEY")
    if not resolved_api_key:
        return _fail("auth", "OWM_API_KEY is not set", retryable=False)

    try:
        response = http_get(
            OWM_URL,
            params={"q": city, "units": units, "appid": resolved_api_key},
            timeout=5,
        )
    except requests.Timeout:
        return _fail("timeout", "upstream exceeded 5s", retryable=True)
    except requests.RequestException as exc:
        return _fail("network", exc.__class__.__name__, retryable=True)

    status_code = getattr(response, "status_code", None)
    if status_code in (401, 403):
        return _fail("auth", f"weather API rejected credentials with status {status_code}", retryable=False)
    if status_code == 429:
        return _fail("upstream_4xx", "weather API rate limited the request", retryable=True)
    if status_code is not None and status_code >= 500:
        return _fail("upstream_5xx", f"weather API returned status {status_code}", retryable=True)
    if status_code is not None and status_code >= 400:
        return _fail("upstream_4xx", f"weather API returned status {status_code}", retryable=False)

    try:
        data = response.json()
        temp = data["main"]["temp"]
        conditions = data["weather"][0]["description"]
    except (KeyError, IndexError, TypeError, ValueError):
        return _fail("upstream_5xx", "weather API returned an unexpected response shape", retryable=True)

    return {
        "ok": True,
        "city": data.get("name") or city,
        "temp": temp,
        "units": units,
        "conditions": conditions,
    }


@tool
def get_current_weather(city: str, units: str = "metric") -> dict[str, Any]:
    """Get current weather for a city. Not forecasts, history, or climate averages.

    units must be 'metric', 'imperial', or 'standard'. Returns {ok, city, temp,
    units, conditions} on success or {ok: False, error: {kind, message,
    retryable}} on failure.
    """
    return fetch_current_weather(city, units)
