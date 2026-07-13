"""Tests for checked-in Week 5 tool-contract instances."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator

from src.tools.calculator import calculate_expression, calculator
from src.tools.web_search import build_web_search_tool, search_web
from src.tools.weather import get_current_weather
from weatheragent.app.weather_agent.weather_core import failure, result_from_payload


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_CONTRACT_SCHEMA_PATH = REPO_ROOT / "schemas" / "tool-contract.schema.json"
CONTRACT_PATHS = {
    "calculator.calculate": REPO_ROOT
    / "contracts"
    / "tools"
    / "calculator.calculate"
    / "1.0.0.json",
    "search.web_search": REPO_ROOT
    / "contracts"
    / "tools"
    / "search.web_search"
    / "1.0.0.json",
    "weather.get_current_weather": REPO_ROOT
    / "contracts"
    / "tools"
    / "weather.get_current_weather"
    / "1.2.0.json",
}
WEB_SEARCH_TOOL = build_web_search_tool(
    SimpleNamespace(
        mcp_client=None,
        mcp_tool=SimpleNamespace(name="web-search___WebSearch"),
    )
)
RUNTIME_TOOLS = {
    "calculator.calculate": calculator,
    "search.web_search": WEB_SEARCH_TOOL,
    "weather.get_current_weather": get_current_weather,
}


class ToolContractInstanceTests(unittest.TestCase):
    def _load_schema(self) -> dict[str, Any]:
        return json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))

    def _load_contract(self, tool_id: str) -> dict[str, Any]:
        path = CONTRACT_PATHS[tool_id]
        self.assertTrue(path.is_file(), f"missing contract: {path.relative_to(REPO_ROOT)}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_contract_instances_validate_against_tool_contract_schema(self) -> None:
        validator = Draft202012Validator(self._load_schema())

        for tool_id in sorted(CONTRACT_PATHS):
            with self.subTest(tool_id=tool_id):
                contract = self._load_contract(tool_id)
                errors = list(validator.iter_errors(contract))

                self.assertEqual([], [error.message for error in errors])
                self.assertEqual(tool_id, contract["toolId"])

    def test_contracts_match_final_model_visible_specs(self) -> None:
        for tool_id, runtime_tool in RUNTIME_TOOLS.items():
            with self.subTest(tool_id=tool_id):
                contract = self._load_contract(tool_id)
                runtime_spec = runtime_tool.tool_spec
                contract_input = dict(contract["inputSchema"])
                contract_input.pop("$schema")

                self.assertEqual(runtime_spec["name"], contract["name"])
                self.assertEqual(runtime_spec["description"], contract["description"])
                self.assertEqual(runtime_spec["inputSchema"]["json"], contract_input)

    def test_weather_outputs_satisfy_contract(self) -> None:
        contract = self._load_contract("weather.get_current_weather")
        validator = Draft202012Validator(contract["outputSchema"])
        success = result_from_payload(
            {"name": "Example City", "main": {"temp": 21.5}, "weather": [{"description": "clear"}]},
            "Example City",
            "metric",
        )
        failed = failure("timeout", "upstream exceeded 5s", retryable=True)

        for result in (success, failed):
            with self.subTest(result=result):
                self.assertEqual([], [error.message for error in validator.iter_errors(result)])

    def test_calculator_outputs_satisfy_contract(self) -> None:
        contract = self._load_contract("calculator.calculate")
        validator = Draft202012Validator(contract["outputSchema"])
        success = calculate_expression(
            "2 + 3",
            backend=lambda **_: {"status": "success", "content": [{"text": "Result: 5"}]},
        )
        failed = calculate_expression("sin(1)")

        for result in (success, failed):
            with self.subTest(result=result):
                self.assertEqual([], [error.message for error in validator.iter_errors(result)])

    def test_web_search_outputs_satisfy_contract(self) -> None:
        contract = self._load_contract("search.web_search")
        validator = Draft202012Validator(contract["outputSchema"])
        success = search_web(
            "AgentCore Gateway",
            1,
            invoke=lambda _: {
                "status": "success",
                "content": [
                    {
                        "text": json.dumps(
                            {
                                "results": [
                                    {
                                        "publishedDate": "unknown",
                                        "text": "External result text",
                                        "title": "Example result",
                                        "url": "https://example.com/result",
                                    }
                                ]
                            }
                        )
                    }
                ],
            },
        )
        failed = search_web("", 1, invoke=lambda _: None)

        for result in (success, failed):
            with self.subTest(result=result):
                self.assertEqual([], [error.message for error in validator.iter_errors(result)])


if __name__ == "__main__":
    unittest.main()
