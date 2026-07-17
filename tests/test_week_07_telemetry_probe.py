"""Offline orchestration tests for the bounded Week 7 telemetry probe."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.probe_week_07_telemetry import run_capture_probe


class Week07TelemetryProbeTests(unittest.TestCase):
    def _manifest(self) -> dict:
        return {
            "schemaVersion": "1.0.0",
            "experimentId": "sha256:" + "a" * 64,
            "runId": "12345678-1234-4abc-8def-1234567890ab",
            "executedAt": "2026-07-17T14:00:00Z",
            "behaviorPins": {
                "model": {
                    "provider": "bedrock",
                    "modelId": "us.amazon.nova-micro-v1:0",
                },
                "sdkVersions": {"strands-agents": "1.46.0"},
            },
            "environment": {
                "pythonVersion": "3.11.0",
                "platform": "linux",
                "architecture": "x86_64",
                "region": "us-east-1",
            },
            "outputs": None,
        }

    def _temporary_directory(self) -> str:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return temporary.name

    def test_probe_clears_invokes_normalizes_and_finalizes_in_order(self) -> None:
        calls: list[str] = []
        exporter = Mock()
        exporter.clear.side_effect = lambda: calls.append("clear")
        telemetry = Mock(in_memory_exporter=exporter)
        agent = Mock(side_effect=lambda prompt: calls.append("invoke"))
        source = {"sourceProfile": {}, "agentManifest": {}, "spans": []}
        canonical = {"schemaVersion": "1.0.0", "spans": []}
        directory = self._temporary_directory()

        with patch.multiple(
            "scripts.probe_week_07_telemetry",
            build_behavior_pins=Mock(return_value=self._manifest()["behaviorPins"]),
            create_run_manifest=Mock(return_value=self._manifest()),
            build_specimen_model=Mock(return_value=object()),
            build_specimen=Mock(return_value=agent),
            capture_finished_spans=Mock(side_effect=lambda value: calls.append("capture") or [object()]),
            serialize_strands_inline_spans=Mock(side_effect=lambda *args, **kwargs: calls.append("serialize") or source),
            normalize_strands_telemetry=Mock(side_effect=lambda *args, **kwargs: calls.append("normalize") or canonical),
        ):
            result = run_capture_probe(
                example_id="tc-0001",
                prompt="What is the current weather in Oslo?",
                run_store=Path(directory),
                telemetry_factory=lambda: telemetry,
            )

        self.assertEqual(["clear", "invoke", "capture", "serialize", "normalize"], calls)
        self.assertEqual("completed", result["outputs"]["status"])
        run_directory = Path(directory) / result["runId"]
        self.assertTrue((run_directory / "raw" / "strands-inline.json").is_file())
        self.assertTrue((run_directory / "canonical-trace.json").is_file())
        stored = json.loads((run_directory / "run-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("completed", stored["outputs"]["status"])

    def test_probe_records_instrument_error_without_canonical_trace(self) -> None:
        exporter = Mock()
        telemetry = Mock(in_memory_exporter=exporter)
        agent = Mock()
        directory = self._temporary_directory()

        with patch.multiple(
            "scripts.probe_week_07_telemetry",
            build_behavior_pins=Mock(return_value=self._manifest()["behaviorPins"]),
            create_run_manifest=Mock(return_value=self._manifest()),
            build_specimen_model=Mock(return_value=object()),
            build_specimen=Mock(return_value=agent),
            capture_finished_spans=Mock(return_value=[object()]),
            serialize_strands_inline_spans=Mock(return_value={"spans": []}),
            normalize_strands_telemetry=Mock(side_effect=ValueError("synthetic adapter failure")),
        ):
            result = run_capture_probe(
                example_id="tc-0001",
                prompt="What is the current weather in Oslo?",
                run_store=Path(directory),
                telemetry_factory=lambda: telemetry,
            )

        run_directory = Path(directory) / result["runId"]
        self.assertEqual("instrument-error", result["outputs"]["status"])
        self.assertFalse((run_directory / "canonical-trace.json").exists())
        self.assertEqual("ValueError", result["outputs"]["error"]["kind"])


if __name__ == "__main__":
    unittest.main()
