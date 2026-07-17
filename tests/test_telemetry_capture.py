"""Tests for converting finished Strands spans into the pinned inline profile."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from src.telemetry_capture import serialize_strands_inline_spans


def _span(
    *,
    operation: str,
    span_id: int,
    parent_id: int | None,
    start: int,
    end: int,
    events: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    context = SimpleNamespace(trace_id=int("1" * 32, 16), span_id=span_id)
    parent = None if parent_id is None else SimpleNamespace(span_id=parent_id)
    return SimpleNamespace(
        context=context,
        parent=parent,
        name=operation,
        instrumentation_scope=SimpleNamespace(
            name="strands.telemetry.tracer",
            version=None,
            schema_url=None,
        ),
        start_time=start,
        end_time=end,
        attributes={
            "gen_ai.operation.name": operation,
            "session.id": "synthetic-session",
        },
        events=events or [],
    )


class TelemetryCaptureTests(unittest.TestCase):
    def test_finished_spans_serialize_to_the_pinned_inline_profile(self) -> None:
        spans = [
            _span(
                operation="execute_tool",
                span_id=int("2" * 16, 16),
                parent_id=int("1" * 16, 16),
                start=20,
                end=30,
                events=[
                    SimpleNamespace(
                        name="gen_ai.tool.message",
                        attributes={"content": '{"city":"Oslo"}'},
                        timestamp=21,
                    )
                ],
            ),
            _span(
                operation="invoke_agent",
                span_id=int("1" * 16, 16),
                parent_id=None,
                start=10,
                end=40,
            ),
        ]

        source = serialize_strands_inline_spans(
            spans,
            agent_manifest={"manifestId": "agents.weather", "version": "4.0.0"},
            producer_version="1.46.0",
        )

        self.assertEqual("strands-inline", source["sourceProfile"]["name"])
        self.assertEqual(
            "strands.telemetry.tracer",
            source["sourceProfile"]["instrumentationScope"]["name"],
        )
        self.assertEqual(
            ["invoke_agent", "execute_tool"],
            [span["attributes"]["gen_ai.operation.name"] for span in source["spans"]],
        )
        self.assertEqual("11111111111111111111111111111111", source["spans"][0]["traceId"])
        self.assertEqual("1111111111111111", source["spans"][0]["spanId"])
        self.assertIsNone(source["spans"][0]["parentSpanId"])
        self.assertEqual("1111111111111111", source["spans"][1]["parentSpanId"])
        json.dumps(source, allow_nan=False)

    def test_profile_preserves_scope_metadata_from_finished_spans(self) -> None:
        span = _span(
            operation="invoke_agent",
            span_id=int("1" * 16, 16),
            parent_id=None,
            start=10,
            end=20,
        )
        span.instrumentation_scope.version = "synthetic-scope-version"
        span.instrumentation_scope.schema_url = "https://example.com/synthetic-schema"

        source = serialize_strands_inline_spans(
            [span],
            agent_manifest={"manifestId": "agents.weather", "version": "4.0.0"},
            producer_version="1.46.0",
        )

        self.assertEqual(
            {
                "name": "strands.telemetry.tracer",
                "version": "synthetic-scope-version",
                "schemaUrl": "https://example.com/synthetic-schema",
            },
            source["sourceProfile"]["instrumentationScope"],
        )

    def test_explicit_event_loop_scaffolding_is_omitted_from_the_source_profile(self) -> None:
        invoke = _span(
            operation="invoke_agent",
            span_id=int("1" * 16, 16),
            parent_id=None,
            start=1_000,
            end=2_000,
        )
        cycle = _span(
            operation="execute_event_loop_cycle",
            span_id=int("2" * 16, 16),
            parent_id=int("1" * 16, 16),
            start=1_100,
            end=1_900,
        )
        tool = _span(
            operation="execute_tool",
            span_id=int("3" * 16, 16),
            parent_id=int("2" * 16, 16),
            start=1_200,
            end=1_800,
        )

        source = serialize_strands_inline_spans(
            [cycle, tool, invoke],
            agent_manifest={"manifestId": "agents.weather", "version": "4.0.0"},
            producer_version="1.46.0",
        )

        self.assertEqual(
            ["invoke_agent", "execute_tool"],
            [span["attributes"]["gen_ai.operation.name"] for span in source["spans"]],
        )
        self.assertEqual("1111111111111111", source["spans"][1]["parentSpanId"])


if __name__ == "__main__":
    unittest.main()
