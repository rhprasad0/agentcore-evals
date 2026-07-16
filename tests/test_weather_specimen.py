"""Offline tests for the Week 7 weather-only specimen."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agents.weather_specimen import (
    MODEL_ID,
    build_behavior_pins,
    build_mock_weather_tool,
    build_specimen,
    build_specimen_model,
)
from src.deterministic_mocks import MockRegistry
from src.run_manifest import derive_experiment_id
from src.tools.weather import get_current_weather
from weatheragent.app.weather_agent.weather_contract import SYSTEM_PROMPT


REPO_ROOT = Path(__file__).resolve().parents[1]


class WeatherSpecimenTests(unittest.TestCase):
    @staticmethod
    def _versions(package: str) -> str:
        return {
            "strands-agents": "1.46.0",
            "botocore": "1.43.44",
            "bedrock-agentcore": "1.17.0",
            "aws-opentelemetry-distro": "0.18.0",
        }[package]

    @patch("src.agents.weather_specimen.Agent")
    def test_build_specimen_registers_only_weather(self, agent_class) -> None:
        model = object()
        registry = MockRegistry.from_repo_root(REPO_ROOT)

        build_specimen(model=model, registry=registry, example_id="tc-0001")

        agent_class.assert_called_once()
        arguments = agent_class.call_args.kwargs
        self.assertIs(model, arguments["model"])
        self.assertEqual(SYSTEM_PROMPT, arguments["system_prompt"])
        self.assertEqual(get_current_weather.tool_spec, arguments["tools"][0].tool_spec)
        self.assertIsNone(arguments["callback_handler"])

    def test_mock_weather_tool_preserves_exact_surface_and_uses_row_scoped_fixture(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)

        mock_tool = build_mock_weather_tool(registry, "tc-0001")

        self.assertEqual(get_current_weather.tool_spec, mock_tool.tool_spec)
        self.assertEqual(
            {
                "ok": True,
                "city": "Oslo",
                "temp": 12.5,
                "units": "metric",
                "conditions": "clear",
            },
            mock_tool(city="Oslo", units="metric"),
        )

    def test_mock_weather_tool_preserves_absent_optional_units_in_fixture_identity(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)

        mock_tool = build_mock_weather_tool(registry, "tc-0004")
        result = mock_tool(city="Reykjavík")

        self.assertFalse(result["ok"])
        self.assertEqual("timeout", result["error"]["kind"])

    @patch("src.agents.weather_specimen.BedrockModel")
    def test_build_specimen_model_pins_supported_sampling_controls(self, model_class) -> None:
        build_specimen_model()

        model_class.assert_called_once_with(
            model_id=MODEL_ID,
            temperature=0.0,
            top_p=1.0,
            max_tokens=1024,
        )

    def test_behavior_pins_use_exact_runtime_values_and_one_tool_binding(self) -> None:
        pins = build_behavior_pins(REPO_ROOT, version_provider=self._versions)

        self.assertEqual({"manifestId": "agents.weather", "version": "4.0.0"}, pins["capabilityManifest"])
        self.assertEqual(["weather.get_current_weather"], [tool["toolId"] for tool in pins["tools"]])
        self.assertEqual(len(SYSTEM_PROMPT.encode("utf-8")), pins["systemPrompt"]["utf8ByteLength"])
        self.assertEqual("strands-inline", pins["sourceProfile"]["profileId"])
        self.assertEqual("1.46.0", pins["sdkVersions"]["strands-agents"])

    def test_prompt_or_description_byte_change_changes_experiment_identity(self) -> None:
        pins = build_behavior_pins(REPO_ROOT, version_provider=self._versions)
        changed_prompt = json.loads(json.dumps(pins))
        changed_prompt["systemPrompt"]["sha256"] = "0" * 64
        changed_description = json.loads(json.dumps(pins))
        changed_description["tools"][0]["descriptionSha256"] = "f" * 64

        baseline = derive_experiment_id(pins)
        self.assertNotEqual(baseline, derive_experiment_id(changed_prompt))
        self.assertNotEqual(baseline, derive_experiment_id(changed_description))


if __name__ == "__main__":
    unittest.main()
