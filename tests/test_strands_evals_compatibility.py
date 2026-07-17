"""Compatibility tests between canonical traces and Strands Evals Sessions."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from strands_evals.types.trace import (
    Session,
    SpanInfo,
    ToolCall,
    ToolExecutionSpan,
    ToolResult,
    Trace,
)

from src.strands_evals_compatibility import compare_planted_facts
from scripts.probe_week_07_strands_evals import CapturingSessionMapper


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_TRACE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "telemetry" / "canonical" / "weather-success.json"
)


class StrandsEvalsCompatibilityTests(unittest.TestCase):
    def test_capturing_mapper_delegates_the_exact_finished_span_list(self) -> None:
        mapper = CapturingSessionMapper()
        expected_session = object()
        mapper._delegate = Mock()
        mapper._delegate.map_to_session.return_value = expected_session
        spans = [object(), object()]

        actual = mapper.map_to_session(spans, "synthetic-session")

        self.assertIs(expected_session, actual)
        self.assertEqual(spans, mapper.finished_spans)
        mapper._delegate.map_to_session.assert_called_once_with(
            mapper.finished_spans,
            "synthetic-session",
        )

    def _canonical(self) -> dict:
        return json.loads(VALID_TRACE_PATH.read_text(encoding="utf-8"))

    def _session(self) -> Session:
        now = datetime(2026, 7, 17, tzinfo=timezone.utc)
        tool_span = ToolExecutionSpan(
            span_info=SpanInfo(
                trace_id="11111111111111111111111111111111",
                span_id="2222222222222222",
                parent_span_id="1111111111111111",
                session_id="synthetic-session-inline",
                start_time=now,
                end_time=now,
            ),
            tool_call=ToolCall(
                name="get_current_weather",
                arguments={"city": "Oslo", "units": "metric"},
                tool_call_id="synthetic-tool-call-1",
            ),
            tool_result=ToolResult(
                content=json.dumps(
                    {
                        "ok": True,
                        "city": "Oslo",
                        "temp": 7,
                        "units": "metric",
                        "conditions": "light rain",
                    },
                    separators=(",", ":"),
                ),
                tool_call_id="synthetic-tool-call-1",
            ),
        )
        return Session(
            session_id="synthetic-session-inline",
            traces=[
                Trace(
                    trace_id="11111111111111111111111111111111",
                    session_id="synthetic-session-inline",
                    spans=[tool_span],
                )
            ],
        )

    def test_equivalent_planted_facts_have_no_mismatches(self) -> None:
        self.assertEqual([], compare_planted_facts(self._canonical(), self._session()))

    def test_each_planted_fact_reports_a_field_specific_mismatch(self) -> None:
        mutations = {
            "tool.name": lambda session: setattr(
                session.traces[0].spans[0].tool_call, "name", "other_tool"
            ),
            "tool.arguments": lambda session: setattr(
                session.traces[0].spans[0].tool_call, "arguments", {"city": "Bergen"}
            ),
            "tool.result": lambda session: setattr(
                session.traces[0].spans[0].tool_result,
                "content",
                '{"ok":false,"error":{"kind":"timeout","message":"synthetic","retryable":true}}',
            ),
            "tool.correlation": lambda session: setattr(
                session.traces[0].spans[0].span_info, "span_id", "3333333333333333"
            ),
        }
        for expected_field, mutate in mutations.items():
            session = self._session()
            mutate(session)
            with self.subTest(field=expected_field):
                mismatches = compare_planted_facts(deepcopy(self._canonical()), session)
                self.assertIn(expected_field, [mismatch.field for mismatch in mismatches])


if __name__ == "__main__":
    unittest.main()
