"""Regression tests for complete exact-key weather projection fixtures."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.deterministic_mocks import MockRegistry
from src.weather_fixture_generation import (
    generate_weather_projection_fixture_documents,
    required_weather_projection_calls,
    render_fixture_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class WeatherProjectionFixtureCoverageTests(unittest.TestCase):
    def test_checked_in_fixture_file_is_generator_idempotent(self) -> None:
        expected = render_fixture_jsonl(
            generate_weather_projection_fixture_documents(REPO_ROOT)
        )
        observed = (
            REPO_ROOT / "datasets/fixtures/mocks/tool-calling.jsonl"
        ).read_text(encoding="utf-8")

        self.assertEqual(expected, observed)

    def test_every_predeclared_contract_valid_projection_call_has_a_fixture(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)
        calls = required_weather_projection_calls(REPO_ROOT)

        self.assertGreater(len(calls), 62)
        tc_0055_arguments = [
            call["arguments"] for call in calls if call["exampleId"] == "tc-0055"
        ]
        self.assertTrue(any("units" not in arguments for arguments in tc_0055_arguments))
        self.assertTrue(
            any(arguments.get("units") == "metric" for arguments in tc_0055_arguments)
        )
        self.assertEqual(
            len(calls),
            len(
                {
                    (call["exampleId"], tuple(sorted(call["arguments"].items())))
                    for call in calls
                }
            ),
        )
        for call in calls:
            with self.subTest(example_id=call["exampleId"], arguments=call["arguments"]):
                result = registry.invoke(
                    call["exampleId"],
                    "weather.get_current_weather",
                    call["arguments"],
                )
                self.assertIsInstance(result["ok"], bool)


if __name__ == "__main__":
    unittest.main()
