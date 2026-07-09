"""Offline tests for the Week 2 temperature conversion tool."""

from __future__ import annotations

import unittest

from src.tools.temperature import convert_temperature, convert_temperature_value


class TemperatureToolTests(unittest.TestCase):
    def assert_failure(self, result: dict, message_fragment: str) -> None:
        self.assertEqual(result["ok"], False)
        self.assertEqual(result["error"]["kind"], "bad_input")
        self.assertEqual(result["error"]["retryable"], False)
        self.assertIn(message_fragment, result["error"]["message"])

    def test_celsius_to_fahrenheit(self) -> None:
        result = convert_temperature_value(0, "celsius", "fahrenheit")

        self.assertEqual(
            result,
            {
                "ok": True,
                "input": {"value": 0.0, "unit": "celsius"},
                "output": {"value": 32.0, "unit": "fahrenheit"},
            },
        )

    def test_fahrenheit_to_celsius(self) -> None:
        result = convert_temperature_value(212, "fahrenheit", "celsius")

        self.assertEqual(result["output"], {"value": 100.0, "unit": "celsius"})

    def test_kelvin_to_celsius(self) -> None:
        result = convert_temperature_value(273.15, "kelvin", "celsius")

        self.assertEqual(result["output"], {"value": 0.0, "unit": "celsius"})

    def test_invalid_value(self) -> None:
        result = convert_temperature_value("hot", "celsius", "fahrenheit")

        self.assert_failure(result, "value must be numeric")

    def test_invalid_from_unit(self) -> None:
        result = convert_temperature_value(10, "rankine", "celsius")

        self.assert_failure(result, "from_unit must be one of")

    def test_invalid_to_unit(self) -> None:
        result = convert_temperature_value(10, "celsius", "rankine")

        self.assert_failure(result, "to_unit must be one of")

    def test_literal_type_hints_emit_model_visible_enums(self) -> None:
        schema = convert_temperature.tool_spec["inputSchema"]["json"]

        self.assertEqual(schema["properties"]["from_unit"]["enum"], ["celsius", "fahrenheit", "kelvin"])
        self.assertEqual(schema["properties"]["to_unit"]["enum"], ["celsius", "fahrenheit", "kelvin"])
        self.assertEqual(schema["properties"]["value"]["type"], "number")
        self.assertEqual(set(schema["required"]), {"value", "from_unit", "to_unit"})


if __name__ == "__main__":
    unittest.main()
