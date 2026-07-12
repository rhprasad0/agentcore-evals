"""Gateway-backed current-weather Lambda with the Week 2 failure envelope."""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from weather_core import (  # pyright: ignore[reportMissingImports]
        failure,
        normalize_arguments,
        result_from_payload,
        status_failure,
    )
except ModuleNotFoundError:
    from weatheragent.app.weather_agent.weather_core import (
        failure,
        normalize_arguments,
        result_from_payload,
        status_failure,
    )
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"
HTTP_OPEN = urlopen


def fetch_current_weather(
    city: str,
    units: str = "metric",
    *,
    api_key: str | None = None,
    http_open: Callable[..., Any] = HTTP_OPEN,
) -> dict[str, Any]:
    """Fetch current weather through the Lambda transport boundary."""
    city, units, validation_failure = normalize_arguments(city, units)
    if validation_failure is not None:
        return validation_failure

    resolved_api_key = api_key if api_key is not None else os.environ.get("OWM_API_KEY")
    if not resolved_api_key:
        return failure("auth", "OWM_API_KEY is not set", retryable=False)

    query = urlencode({"q": city, "units": units, "appid": resolved_api_key})
    request = Request(f"{OWM_URL}?{query}", headers={"User-Agent": "weatheragent-week4/1.0"})

    try:
        with http_open(request, timeout=5) as response:
            status_code = getattr(response, "status", 200)
            if status_code >= 400:
                return status_failure(status_code)
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return status_failure(error.code)
    except (TimeoutError, socket.timeout):
        return failure("timeout", "upstream exceeded 5s", retryable=True)
    except URLError as error:
        reason = getattr(error, "reason", error)
        return failure("network", reason.__class__.__name__, retryable=True)
    except OSError as error:
        return failure("network", error.__class__.__name__, retryable=True)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        return failure("upstream_5xx", "weather API returned an unexpected response shape", retryable=True)
    return result_from_payload(payload, city, units)


def lambda_handler(event: Any, context: Any) -> dict[str, Any]:
    """Adapt AgentCore Gateway's argument-map event to the weather contract."""
    arguments = event if isinstance(event, dict) else {}
    return fetch_current_weather(
        arguments.get("city", ""),
        arguments.get("units", "metric"),
        http_open=HTTP_OPEN,
    )
