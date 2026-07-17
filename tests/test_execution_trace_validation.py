"""Semantic validation tests for canonical execution traces."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from src.execution_trace_validation import (
    ExecutionTraceSemanticError,
    validate_execution_trace_semantics,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_TRACE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "telemetry" / "canonical" / "weather-success.json"
)


class ExecutionTraceSemanticTests(unittest.TestCase):
    def _trace(self) -> dict:
        return json.loads(VALID_TRACE_PATH.read_text(encoding="utf-8"))

    def test_rejects_arguments_that_violate_the_exact_tool_contract(self) -> None:
        trace = self._trace()
        trace["spans"][1]["arguments"] = {"city": "Oslo", "units": "kelvin"}

        with self.assertRaisesRegex(
            ExecutionTraceSemanticError,
            r"spans\[1\]\.arguments.*weather\.get_current_weather@2\.0\.0",
        ):
            validate_execution_trace_semantics(trace, repo_root=REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
