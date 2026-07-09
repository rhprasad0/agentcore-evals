"""Week 2 temperature conversion tool for schema archaeology.

This deliberately small tool exists to compare Python-side constraints with the
JSON schema Strands exposes to the model.
"""

from __future__ import annotations

from typing import Any, Literal

from strands import tool

TemperatureUnit = Literal["celsius", "fahrenheit", "kelvin"]
VALID_TEMPERATURE_UNITS = ("celsius", "fahrenheit", "kelvin")


def _fail(message: str) -> dict[str, Any]:
    """Build a bad-input envelope for conversion failures."""
    if not message:
        raise ValueError("failure message must be non-empty")
    return {"ok": False, "error": {"kind": "bad_input", "message": message, "retryable": False}}


def _normalize_unit(unit: str) -> str | None:
    normalized = unit.strip().lower() if isinstance(unit, str) else ""
    if normalized in VALID_TEMPERATURE_UNITS:
        return normalized
    return None


def convert_temperature_value(value: Any, from_unit: str, to_unit: str) -> dict[str, Any]:
    """Convert a temperature and return either a success or failure envelope."""
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return _fail("value must be numeric")

    normalized_from = _normalize_unit(from_unit)
    normalized_to = _normalize_unit(to_unit)
    if normalized_from is None:
        return _fail(f"from_unit must be one of: {', '.join(VALID_TEMPERATURE_UNITS)}")
    if normalized_to is None:
        return _fail(f"to_unit must be one of: {', '.join(VALID_TEMPERATURE_UNITS)}")

    if normalized_from == "celsius":
        celsius = numeric_value
    elif normalized_from == "fahrenheit":
        celsius = (numeric_value - 32) * 5 / 9
    else:
        celsius = numeric_value - 273.15

    if normalized_to == "celsius":
        converted = celsius
    elif normalized_to == "fahrenheit":
        converted = celsius * 9 / 5 + 32
    else:
        converted = celsius + 273.15

    return {
        "ok": True,
        "input": {"value": numeric_value, "unit": normalized_from},
        "output": {"value": round(converted, 2), "unit": normalized_to},
    }


@tool
def convert_temperature(value: float, from_unit: TemperatureUnit, to_unit: TemperatureUnit) -> dict[str, Any]:
    """Convert a temperature between celsius, fahrenheit, and kelvin.

    from_unit and to_unit must each be one of: celsius, fahrenheit, kelvin.
    Returns {ok, input, output} on success or {ok: False, error: {kind,
    message, retryable}} on failure.
    """
    return convert_temperature_value(value, from_unit, to_unit)
