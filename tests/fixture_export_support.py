"""Synthetic private-run builder for public fixture export tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.dataset_projection import load_projection


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"
RUN_MANIFEST_FIXTURE = (
    REPO_ROOT / "tests/fixtures/run-manifests/valid/weather-only.json"
)
TRACE_FIXTURE = REPO_ROOT / "tests/fixtures/telemetry/canonical/weather-success.json"
INSTRUMENT_ERROR_IDS = {"tc-0090", "tc-0093"}


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_synthetic_private_run(root: Path) -> Path:
    """Create 60 valid traces and two bounded instrument errors for tests."""

    projection = load_projection(PROJECTION_PATH, repo_root=REPO_ROOT)
    manifest = json.loads(RUN_MANIFEST_FIXTURE.read_text(encoding="utf-8"))
    manifest["outputs"] = {
        "status": "completed",
        "runDirectory": "datasets/runs/synthetic-fixture-export",
        "canonicalTracePath": (
            "datasets/runs/synthetic-fixture-export/canonical-traces.jsonl"
        ),
        "error": None,
    }
    _write_json(root / "run-manifest.json", manifest)

    source_trace = json.loads(TRACE_FIXTURE.read_text(encoding="utf-8"))
    for row in projection.rows:
        example_id = row["exampleId"]
        case_root = root / "cases" / example_id
        if example_id in INSTRUMENT_ERROR_IDS:
            outcome = {
                "schemaVersion": "1.0.0",
                "exampleId": example_id,
                "scenarioFamily": "synthetic",
                "status": "instrument-error",
                "errorKind": "TelemetryNormalizationError",
            }
            _write_json(
                case_root / "instrument-error.json",
                {
                    "kind": "TelemetryNormalizationError",
                    "message": "synthetic normalization failure",
                },
            )
        else:
            outcome = {
                "schemaVersion": "1.0.0",
                "exampleId": example_id,
                "scenarioFamily": "synthetic",
                "status": "completed",
                "errorKind": None,
            }
            trace = copy.deepcopy(source_trace)
            trace["prompt"] = row["prompt"]
            trace["sessionId"] = f"{manifest['runId']}:{example_id}"
            for span in trace["spans"]:
                if span["operationName"] == "execute_tool":
                    span["selectionReasoning"] = (
                        "Synthetic model-emitted tool-selection reasoning."
                    )
            _write_json(case_root / "canonical-trace.json", trace)
        _write_json(case_root / "outcome.json", outcome)
    return root
