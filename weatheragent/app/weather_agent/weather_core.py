"""Transport-independent current-weather contract shared by direct and Lambda seams."""

from __future__ import annotations

from typing import Any

FAILURE_KINDS = (
    "bad_input",
    "auth",
    "upstream_4xx",
    "upstream_5xx",
    "timeout",
    "network",
)
VALID_UNITS = ("metric", "imperial", "standard")
UPSTREAM_TIMEOUT_SECONDS = 10


def failure(kind: str, message: str, *, retryable: bool) -> dict[str, Any]:
    """Build the stable typed failure envelope."""
    if kind not in FAILURE_KINDS:
        raise ValueError(f"unknown failure kind: {kind}")
    if not message:
        raise ValueError("failure message must be non-empty")
    return {"ok": False, "error": {"kind": kind, "message": message, "retryable": retryable}}


def normalize_arguments(city: Any, units: Any) -> tuple[str, str, dict[str, Any] | None]:
    """Normalize and validate model-provided weather arguments."""
    normalized_city = city.strip() if isinstance(city, str) else ""
    normalized_units = units.strip().lower() if isinstance(units, str) else ""
    if not normalized_city:
        return normalized_city, normalized_units, failure("bad_input", "city must be non-empty", retryable=False)
    if normalized_units not in VALID_UNITS:
        return (
            normalized_city,
            normalized_units,
            failure(
                "bad_input",
                f"units must be one of: {', '.join(VALID_UNITS)}",
                retryable=False,
            ),
        )
    return normalized_city, normalized_units, None


def status_failure(status_code: int) -> dict[str, Any]:
    """Map upstream HTTP status into the stable failure taxonomy."""
    if status_code in (401, 403):
        return failure("auth", f"weather API rejected credentials with status {status_code}", retryable=False)
    if status_code == 429:
        return failure("upstream_4xx", "weather API rate limited the request", retryable=True)
    if status_code >= 500:
        return failure("upstream_5xx", f"weather API returned status {status_code}", retryable=True)
    return failure("upstream_4xx", f"weather API returned status {status_code}", retryable=False)


def result_from_payload(payload: Any, city: str, units: str) -> dict[str, Any]:
    """Map an upstream payload into the stable success or shape-failure envelope."""
    try:
        temp = payload["main"]["temp"]
        conditions = payload["weather"][0]["description"]
    except (KeyError, IndexError, TypeError):
        return failure("upstream_5xx", "weather API returned an unexpected response shape", retryable=True)
    return {
        "ok": True,
        "city": payload.get("name") or city,
        "temp": temp,
        "units": units,
        "conditions": conditions,
    }
