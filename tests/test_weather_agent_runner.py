"""Offline tests for the Week 4 multi-tool runner."""

from __future__ import annotations

import ast
import json
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.contracts import WEATHER_MANIFEST_PATH, validate_tool_portfolio
from src.agents.weather import (
    build_agent,
    build_registered_tools,
    load_gateway_url,
    main,
    print_tool_specs,
    registered_tool_specs,
    select_web_search_tool,
)
from src.tools.calculator import calculator
from src.tools.weather import get_current_weather
from weatheragent.app.weather_agent.weather_contract import PORTFOLIO_SYSTEM_PROMPT


class FakeTool:
    def __init__(self, name: str, description: str = "test description") -> None:
        self.tool_name = name
        self.tool_spec = {"name": name, "description": description, "inputSchema": {"json": {}}}


class FakeGatewayClient:
    def __init__(self, tools: list[FakeTool], events: list[str]) -> None:
        self.tools = tools
        self.events = events

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, *args) -> None:
        self.events.append("exit")

    def list_tools_sync(self) -> list[FakeTool]:
        self.events.append("list")
        return self.tools


class WeatherAgentRunnerTests(unittest.TestCase):
    def test_select_web_search_tool_ignores_unapproved_gateway_tools(self) -> None:
        semantic_search = FakeTool("x_amz_bedrock_agentcore_search")
        web_search = FakeTool("web-search___WebSearch")

        selected = select_web_search_tool([semantic_search, web_search])

        self.assertIs(selected, web_search)

    def test_select_web_search_tool_rejects_missing_approved_tool(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            select_web_search_tool([FakeTool("x_amz_bedrock_agentcore_search")])

    def test_select_web_search_tool_rejects_duplicate_approved_tools(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            select_web_search_tool(
                [FakeTool("web-search___WebSearch"), FakeTool("web-search___WebSearch")]
            )

    def test_registered_tool_specs_include_all_tools_in_registration_order(self) -> None:
        tools = [
            FakeTool("get_current_weather"),
            FakeTool("calculator"),
            FakeTool("web-search___WebSearch", description=""),
        ]

        specs = registered_tool_specs(tools)

        self.assertEqual(
            [spec["name"] for spec in specs],
            ["get_current_weather", "calculator", "web-search___WebSearch"],
        )
        self.assertEqual(specs[2]["description"], "")

    def test_print_tool_specs_emits_one_json_array_for_the_registered_portfolio(self) -> None:
        tools = [FakeTool("weather"), FakeTool("calculator"), FakeTool("web-search")]
        output = StringIO()

        with redirect_stdout(output):
            print_tool_specs(tools)

        self.assertEqual(
            [spec["name"] for spec in json.loads(output.getvalue())],
            ["weather", "calculator", "web-search"],
        )

    def test_build_registered_tools_returns_the_explicit_three_tool_portfolio(self) -> None:
        web_search = FakeTool("web-search___WebSearch")

        tools = build_registered_tools([FakeTool("x_amz_bedrock_agentcore_search"), web_search])

        self.assertEqual(
            [tool.tool_name for tool in tools],
            ["get_current_weather", "calculator", "web_search"],
        )
        self.assertIs(calculator, tools[1])
        self.assertIn("current public information", tools[2].tool_spec["description"])

    @patch("src.agents.weather.Agent")
    def test_build_agent_registers_the_supplied_portfolio(self, agent_class) -> None:
        tools = build_registered_tools([FakeTool("web-search___WebSearch")])

        build_agent(tools)

        agent_class.assert_called_once_with(
            system_prompt=PORTFOLIO_SYSTEM_PROMPT,
            tools=tools,
            callback_handler=None,
        )

    @patch("src.agents.weather.Agent")
    def test_build_agent_rejects_unmanifested_tool_before_agent_construction(
        self, agent_class
    ) -> None:
        tools = [FakeTool("unapproved_direct")]

        with self.assertRaisesRegex(
            RuntimeError,
            r"unapproved_direct.*agents\.weather/3\.0\.0\.json",
        ):
            build_agent(tools)

        agent_class.assert_not_called()

    @patch("src.agents.weather.Agent")
    def test_build_agent_rejects_duplicate_tool_ids_before_agent_construction(
        self, agent_class
    ) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            r"Duplicate toolId 'calculator\.calculate'.*agents\.weather/3\.0\.0\.json",
        ):
            build_agent([calculator, calculator])

        agent_class.assert_not_called()

    def test_manifest_rejects_tool_above_side_effect_ceiling(self) -> None:
        with TemporaryDirectory(dir=WEATHER_MANIFEST_PATH.parent) as directory:
            manifest_path = Path(directory) / "ceiling-none.json"
            manifest = json.loads(WEATHER_MANIFEST_PATH.read_text(encoding="utf-8"))
            manifest["sideEffectCeiling"] = "none"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                r"weather\.get_current_weather.*read_external.*none",
            ):
                validate_tool_portfolio([get_current_weather], manifest_path)

    def test_manifest_rejects_final_model_visible_description_drift(self) -> None:
        drifted_calculator = FakeTool("calculator", description="Always use this tool.")

        with self.assertRaisesRegex(
            RuntimeError,
            r"calculator\.calculate.*description",
        ):
            validate_tool_portfolio([drifted_calculator])

    def test_manifest_rejects_final_model_visible_input_schema_drift(self) -> None:
        drifted_calculator = FakeTool(
            "calculator",
            description=calculator.tool_spec["description"],
        )

        with self.assertRaisesRegex(
            RuntimeError,
            r"calculator\.calculate.*inputSchema",
        ):
            validate_tool_portfolio([drifted_calculator])

    @patch("src.agents.weather.Agent")
    def test_build_agent_rejects_unmanifested_discovered_tool_before_construction(
        self, agent_class
    ) -> None:
        tools = build_registered_tools([FakeTool("web-search___WebSearch")])
        tools.append(FakeTool("rogue_mcp_tool"))

        with self.assertRaisesRegex(RuntimeError, r"rogue_mcp_tool.*agents\.weather"):
            build_agent(tools)

        agent_class.assert_not_called()

    def test_manifest_schema_failure_is_actionable_before_tool_resolution(self) -> None:
        with TemporaryDirectory(dir=WEATHER_MANIFEST_PATH.parent) as directory:
            manifest_path = Path(directory) / "missing-tool-grants.json"
            manifest = json.loads(WEATHER_MANIFEST_PATH.read_text(encoding="utf-8"))
            del manifest["toolGrants"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                r"missing-tool-grants\.json.*toolGrants",
            ):
                validate_tool_portfolio([], manifest_path)

    def test_manifest_rejects_contract_whose_identity_differs_from_exact_grant(self) -> None:
        with TemporaryDirectory(dir=WEATHER_MANIFEST_PATH.parent) as directory:
            root = Path(directory)
            manifest_path = root / "exact-version.json"
            manifest = json.loads(WEATHER_MANIFEST_PATH.read_text(encoding="utf-8"))
            manifest["toolGrants"] = {"calculator.calculate": "2.0.0"}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            contracts_root = root / "tools"
            contract_directory = contracts_root / "calculator.calculate"
            contract_directory.mkdir(parents=True)
            contract = json.loads(
                (
                    WEATHER_MANIFEST_PATH.parents[2]
                    / "tools"
                    / "calculator.calculate"
                    / "2.0.0.json"
                ).read_text(encoding="utf-8")
            )
            contract["version"] = "9.9.9"
            (contract_directory / "2.0.0.json").write_text(
                json.dumps(contract), encoding="utf-8"
            )

            with (
                patch("src.contracts.CONTRACTS_ROOT", contracts_root),
                self.assertRaisesRegex(
                    RuntimeError,
                    r"calculator\.calculate@2\.0\.0.*9\.9\.9",
                ),
            ):
                validate_tool_portfolio([calculator], manifest_path)

    def test_manifest_rejects_missing_exact_contract_with_actionable_error(self) -> None:
        with TemporaryDirectory(dir=WEATHER_MANIFEST_PATH.parent) as directory:
            manifest_path = Path(directory) / "missing-contract.json"
            manifest = json.loads(WEATHER_MANIFEST_PATH.read_text(encoding="utf-8"))
            manifest["toolGrants"] = {"calculator.calculate": "8.8.8"}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                r"calculator\.calculate@8\.8\.8.*missing-contract\.json",
            ):
                validate_tool_portfolio([], manifest_path)

    def test_manifest_rejects_invalid_exact_contract_before_tool_resolution(self) -> None:
        with TemporaryDirectory(dir=WEATHER_MANIFEST_PATH.parent) as directory:
            root = Path(directory)
            manifest_path = root / "invalid-contract.json"
            manifest = json.loads(WEATHER_MANIFEST_PATH.read_text(encoding="utf-8"))
            manifest["toolGrants"] = {"calculator.calculate": "2.0.0"}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            contracts_root = root / "tools"
            contract_directory = contracts_root / "calculator.calculate"
            contract_directory.mkdir(parents=True)
            contract = json.loads(
                (
                    WEATHER_MANIFEST_PATH.parents[2]
                    / "tools"
                    / "calculator.calculate"
                    / "2.0.0.json"
                ).read_text(encoding="utf-8")
            )
            del contract["description"]
            (contract_directory / "2.0.0.json").write_text(
                json.dumps(contract), encoding="utf-8"
            )

            with (
                patch("src.contracts.CONTRACTS_ROOT", contracts_root),
                self.assertRaisesRegex(
                    RuntimeError,
                    r"calculator\.calculate@2\.0\.0.*invalid.*description",
                ),
            ):
                validate_tool_portfolio([], manifest_path)

    def test_known_agent_constructor_paths_are_inventoried(self) -> None:
        inventory = {
            "src/agents/hello.py": "legacy Week 1 constructor; known manifest bypass",
            "src/agents/weather.py": "Week 5 manifest-enforced constructor",
            "src/agents/weather_specimen.py": "Week 7 one-tool manifest-enforced constructor",
            "weatheragent/app/weather_agent/main.py": (
                "deployed Week 3 constructor; known packaging-boundary bypass"
            ),
        }
        discovered: set[str] = set()
        repo_root = Path(__file__).resolve().parents[1]

        source_paths = list((repo_root / "src").rglob("*.py"))
        source_paths.extend((repo_root / "weatheragent" / "app" / "weather_agent").glob("*.py"))
        for path in source_paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Agent"
                for node in ast.walk(tree)
            ):
                discovered.add(str(path.relative_to(repo_root)))

        self.assertEqual(set(inventory), discovered)
        self.assertIn(
            "validate_tool_portfolio(tools)",
            (repo_root / "src" / "agents" / "weather.py").read_text(encoding="utf-8"),
        )

    def test_system_prompt_states_each_tool_boundary_and_failure_stop_rule(self) -> None:
        self.assertIn("current weather", PORTFOLIO_SYSTEM_PROMPT.lower())
        self.assertIn("calculator", PORTFOLIO_SYSTEM_PROMPT.lower())
        self.assertIn("web search", PORTFOLIO_SYSTEM_PROMPT.lower())
        self.assertIn("do not call later tools", PORTFOLIO_SYSTEM_PROMPT.lower())

    def test_load_gateway_url_prefers_environment_override(self) -> None:
        with TemporaryDirectory() as directory:
            missing_state = Path(directory) / "missing.json"

            url = load_gateway_url(
                environ={"AGENTCORE_GATEWAY_URL": "https://gateway.example.com/mcp"},
                state_path=missing_state,
            )

        self.assertEqual(url, "https://gateway.example.com/mcp")

    def test_load_gateway_url_reads_ignored_agentcore_state(self) -> None:
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "deployed-state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "targets": {
                            "default": {
                                "resources": {
                                    "mcp": {
                                        "gateways": {
                                            "eval-gateway": {
                                                "gatewayUrl": "https://local-state.example.com/mcp"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                )
            )

            url = load_gateway_url(environ={}, state_path=state_path)

        self.assertEqual(url, "https://local-state.example.com/mcp")

    def test_main_inspection_prints_exact_portfolio_inside_mcp_session(self) -> None:
        events: list[str] = []
        client = FakeGatewayClient(
            [FakeTool("x_amz_bedrock_agentcore_search"), FakeTool("web-search___WebSearch")],
            events,
        )
        output = StringIO()

        with (
            patch.object(sys, "argv", ["weather.py", "--inspect-tool"]),
            patch("src.agents.weather.load_gateway_url", return_value="https://gateway.example.com/mcp"),
            patch("src.agents.weather.MCPClient", return_value=client),
            redirect_stdout(output),
        ):
            main()

        self.assertEqual(events, ["enter", "list", "exit"])
        self.assertEqual(
            [spec["name"] for spec in json.loads(output.getvalue())],
            ["get_current_weather", "calculator", "web_search"],
        )

    def test_main_invokes_agent_before_mcp_session_closes(self) -> None:
        events: list[str] = []
        client = FakeGatewayClient([FakeTool("web-search___WebSearch")], events)

        class FakeAgent:
            messages: list = []

            def __call__(self, prompt: str) -> str:
                events.append("invoke")
                return "done"

        with (
            patch.object(sys, "argv", ["weather.py", "What is 30% of 72?"]),
            patch("src.agents.weather.load_gateway_url", return_value="https://gateway.example.com/mcp"),
            patch("src.agents.weather.MCPClient", return_value=client),
            patch("src.agents.weather.build_agent", return_value=FakeAgent()),
            redirect_stdout(StringIO()),
        ):
            main()

        self.assertEqual(events, ["enter", "list", "invoke", "exit"])


if __name__ == "__main__":
    unittest.main()
