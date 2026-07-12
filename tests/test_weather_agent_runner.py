"""Offline tests for the Week 4 multi-tool runner."""

from __future__ import annotations

import json
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.agents.weather import (
    build_agent,
    build_registered_tools,
    load_gateway_url,
    main,
    print_tool_specs,
    registered_tool_specs,
    select_web_search_tool,
)
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
            ["get_current_weather", "calculator", "web-search___WebSearch"],
        )

    @patch("src.agents.weather.Agent")
    def test_build_agent_registers_the_supplied_portfolio(self, agent_class) -> None:
        tools = [FakeTool("weather"), FakeTool("calculator"), FakeTool("web-search")]

        build_agent(tools)

        agent_class.assert_called_once_with(
            system_prompt=PORTFOLIO_SYSTEM_PROMPT,
            tools=tools,
            callback_handler=None,
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
            ["get_current_weather", "calculator", "web-search___WebSearch"],
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
