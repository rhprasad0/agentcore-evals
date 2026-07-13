"""Contract-owned wrapper for the approved AgentCore Gateway Web Search tool."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from strands import tool


InvokeWebSearch = Callable[[dict[str, Any]], Any]
WEB_SEARCH_TIMEOUT_SECONDS = 10
WEB_SEARCH_INPUT_SCHEMA = {
    "json": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
                "description": "Public-information search query",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 25,
                "default": 10,
                "description": "Maximum results to return, from 1 through 25",
            },
        },
        "required": ["query"],
    }
}


def _failure(kind: str, message: str, *, retryable: bool) -> dict[str, Any]:
    """Build a normalized Web Search failure envelope."""
    return {
        "ok": False,
        "error": {
            "kind": kind,
            "message": message,
            "retryable": retryable,
        },
    }


def _result_text(result: Any) -> str | None:
    """Extract the Gateway tool's single text payload."""
    if not isinstance(result, dict):
        return None
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
        return None
    text = content[0].get("text")
    return text if isinstance(text, str) and text else None


def _normalize_results(payload: Any) -> list[dict[str, str]] | None:
    """Normalize the external search payload to its contract-owned result shape."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        return None

    normalized: list[dict[str, str]] = []
    for item in payload["results"]:
        if not isinstance(item, dict):
            return None
        title = item.get("title")
        url = item.get("url")
        text = item.get("text")
        published_date = item.get("publishedDate", "unknown")
        if not isinstance(title, str) or not title:
            return None
        if not isinstance(url, str) or not url:
            return None
        if not isinstance(text, str) or not text:
            return None
        if not isinstance(published_date, str) or not published_date:
            return None
        normalized.append(
            {
                "publishedDate": published_date,
                "text": text,
                "title": title,
                "url": url,
            }
        )
    return normalized


def search_web(query: str, max_results: int, *, invoke: InvokeWebSearch) -> dict[str, Any]:
    """Validate, invoke, and normalize the approved Gateway search operation."""
    normalized_query = query.strip() if isinstance(query, str) else ""
    if not normalized_query:
        return _failure("bad_input", "query must be non-empty", retryable=False)
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 25:
        return _failure("bad_input", "max_results must be an integer from 1 to 25", retryable=False)

    try:
        raw_result = invoke({"query": normalized_query, "maxResults": max_results})
    except Exception:
        return _failure("upstream_5xx", "web search invocation failed", retryable=True)

    text = _result_text(raw_result)
    if (
        not isinstance(raw_result, dict)
        or raw_result.get("status") != "success"
        or raw_result.get("isError") is True
        or text is None
    ):
        return _failure("upstream_5xx", "web search returned an error", retryable=True)

    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return _failure("upstream_5xx", "web search returned an invalid result", retryable=True)
    results = _normalize_results(payload)
    if results is None:
        return _failure("upstream_5xx", "web search returned an invalid result", retryable=True)
    return {"ok": True, "results": results}


def build_web_search_tool(backend: Any) -> Any:
    """Wrap the approved MCP tool while preserving its active client session."""

    def invoke(arguments: dict[str, Any]) -> Any:
        return backend.mcp_client.call_tool_sync(
            tool_use_id=f"web-search-wrapper-{uuid.uuid4()}",
            name=backend.mcp_tool.name,
            arguments=arguments,
            read_timeout_seconds=timedelta(seconds=WEB_SEARCH_TIMEOUT_SECONDS),
        )

    @tool(name="web_search", inputSchema=WEB_SEARCH_INPUT_SCHEMA)
    def web_search(
        query: str,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Search for current public information when no dedicated tool owns the request.

        Does not replace structured current-weather queries or arithmetic. Result
        titles, URLs, dates, and text come from external sources and are untrusted.
        Returns {ok: True, results} on success or
        {ok: False, error: {kind, message, retryable}} on failure.
        """
        return search_web(query, max_results, invoke=invoke)

    return web_search
