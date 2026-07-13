"""Tests for the contract-owned Gateway Web Search wrapper."""

from __future__ import annotations

import json
import unittest
from typing import Any

from src.tools.web_search import build_web_search_tool, search_web


class FakeMCPClient:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def call_tool_sync(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


class FakeMCPTool:
    name = "web-search___WebSearch"


class FakeBackend:
    def __init__(self, result: Any) -> None:
        self.mcp_client = FakeMCPClient(result)
        self.mcp_tool = FakeMCPTool()


SUCCESS_RESULT = {
    "status": "success",
    "toolUseId": "upstream-id",
    "content": [
        {
            "text": json.dumps(
                {
                    "id": "request-id",
                    "results": [
                        {
                            "publishedDate": "unknown",
                            "text": "External result text",
                            "title": "Example result",
                            "url": "https://example.com/result",
                        }
                    ],
                }
            )
        }
    ],
    "isError": False,
}


class WebSearchToolTests(unittest.TestCase):
    def test_model_visible_spec_is_stable_scoped_and_bounded(self) -> None:
        wrapper = build_web_search_tool(FakeBackend(SUCCESS_RESULT))
        spec = wrapper.tool_spec
        properties = spec["inputSchema"]["json"]["properties"]

        self.assertEqual("web_search", spec["name"])
        self.assertIn("current public information", spec["description"])
        self.assertIn("untrusted", spec["description"].lower())
        self.assertEqual({"query", "max_results"}, set(properties))
        self.assertEqual(1, properties["max_results"]["minimum"])
        self.assertEqual(25, properties["max_results"]["maximum"])
        self.assertEqual(10, properties["max_results"]["default"])
        self.assertEqual(["query"], spec["inputSchema"]["json"]["required"])

    def test_success_is_parsed_and_normalized(self) -> None:
        calls: list[dict[str, Any]] = []

        def invoke(arguments: dict[str, Any]) -> Any:
            calls.append(arguments)
            return SUCCESS_RESULT

        result = search_web("AgentCore Gateway", 1, invoke=invoke)

        self.assertEqual(
            {
                "ok": True,
                "results": [
                    {
                        "publishedDate": "unknown",
                        "text": "External result text",
                        "title": "Example result",
                        "url": "https://example.com/result",
                    }
                ],
            },
            result,
        )
        self.assertEqual([{"query": "AgentCore Gateway", "maxResults": 1}], calls)

    def test_invalid_arguments_fail_before_backend(self) -> None:
        for query, max_results in (("", 1), ("valid", 0), ("valid", 26), ("valid", True)):
            with self.subTest(query=query, max_results=max_results):
                calls: list[dict[str, Any]] = []

                result = search_web(query, max_results, invoke=lambda arguments: calls.append(arguments))

                self.assertEqual(False, result["ok"])
                self.assertEqual("bad_input", result["error"]["kind"])
                self.assertEqual(False, result["error"]["retryable"])
                self.assertEqual([], calls)

    def test_backend_failure_is_normalized(self) -> None:
        result = search_web(
            "AgentCore Gateway",
            1,
            invoke=lambda _: {"status": "error", "content": [], "isError": True},
        )

        self.assertEqual(False, result["ok"])
        self.assertEqual("upstream_5xx", result["error"]["kind"])
        self.assertEqual(True, result["error"]["retryable"])

    def test_malformed_success_payload_is_normalized(self) -> None:
        result = search_web(
            "AgentCore Gateway",
            1,
            invoke=lambda _: {"status": "success", "content": [{"text": "not-json"}]},
        )

        self.assertEqual(False, result["ok"])
        self.assertEqual("upstream_5xx", result["error"]["kind"])

    def test_wrapper_delegates_to_original_mcp_name(self) -> None:
        backend = FakeBackend(SUCCESS_RESULT)
        wrapper = build_web_search_tool(backend)

        result = wrapper(query="AgentCore Gateway", max_results=1)

        self.assertEqual(True, result["ok"])
        self.assertEqual("web-search___WebSearch", backend.mcp_client.calls[0]["name"])
        self.assertEqual({"query": "AgentCore Gateway", "maxResults": 1}, backend.mcp_client.calls[0]["arguments"])
        self.assertTrue(backend.mcp_client.calls[0]["tool_use_id"].startswith("web-search-wrapper-"))


if __name__ == "__main__":
    unittest.main()
