"""Run one explicitly confirmed Week 7 live telemetry calibration case."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from strands_evals.telemetry import StrandsEvalsTelemetry

from src.agents.weather_specimen import (
    MODEL_ID,
    REPO_ROOT,
    build_behavior_pins,
    build_specimen,
    build_specimen_model,
)
from src.dataset_projection import load_projection
from src.deterministic_mocks import MockRegistry
from src.run_manifest import create_run_manifest
from src.telemetry_capture import (
    capture_finished_spans,
    serialize_strands_inline_spans,
)
from src.telemetry_normalization import normalize_strands_telemetry


def _telemetry_factory() -> StrandsEvalsTelemetry:
    return StrandsEvalsTelemetry().setup_in_memory_exporter()


def _environment() -> dict[str, str | None]:
    return {
        "pythonVersion": platform.python_version(),
        "platform": sys.platform,
        "architecture": platform.machine(),
        "region": os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1",
    }


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_capture_probe(
    *,
    example_id: str,
    prompt: str,
    run_store: Path,
    telemetry_factory: Callable[[], Any] = _telemetry_factory,
) -> dict[str, Any]:
    """Capture and normalize one case, recording instrument failures separately."""

    behavior_pins = build_behavior_pins(REPO_ROOT)
    manifest = create_run_manifest(
        behavior_pins,
        _environment(),
        run_store,
    )
    run_id = manifest["runId"]
    run_directory = run_store / run_id
    raw_path = run_directory / "raw" / "strands-inline.json"
    canonical_path = run_directory / "canonical-trace.json"
    manifest_path = run_directory / "run-manifest.json"
    run_directory.mkdir(parents=True, exist_ok=False)
    telemetry = telemetry_factory()
    try:
        telemetry.in_memory_exporter.clear()
        agent = build_specimen(
            model=build_specimen_model(),
            registry=MockRegistry.from_repo_root(REPO_ROOT),
            example_id=example_id,
            trace_attributes={
                "session.id": run_id,
                "gen_ai.conversation.id": run_id,
            },
        )
        agent(prompt)
        spans = capture_finished_spans(telemetry)
        source = serialize_strands_inline_spans(
            spans,
            agent_manifest={"manifestId": "agents.weather", "version": "4.0.0"},
            producer_version=behavior_pins["sdkVersions"]["strands-agents"],
        )
        _write_json_atomic(raw_path, source)
        canonical = normalize_strands_telemetry(source, repo_root=REPO_ROOT)
        _write_json_atomic(canonical_path, canonical)
        manifest["outputs"] = {
            "status": "completed",
            "runDirectory": f"datasets/runs/{run_id}",
            "canonicalTracePath": f"datasets/runs/{run_id}/canonical-trace.json",
            "error": None,
        }
    except Exception as error:
        manifest["outputs"] = {
            "status": "instrument-error",
            "runDirectory": f"datasets/runs/{run_id}",
            "canonicalTracePath": None,
            "error": {
                "kind": error.__class__.__name__,
                "message": str(error)[:500] or error.__class__.__name__,
            },
        }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _row_prompt(example_id: str) -> str:
    projection = load_projection(
        REPO_ROOT / "datasets" / "projections" / "weather-only-62.json",
        repo_root=REPO_ROOT,
    )
    matches = [row for row in projection.rows if row["exampleId"] == example_id]
    if len(matches) != 1:
        raise ValueError(f"exampleId {example_id!r} is not unique in weather-only-62@1.0.0")
    return matches[0]["prompt"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example-id", default="tc-0001")
    parser.add_argument("--confirm-live-bedrock", action="store_true")
    arguments = parser.parse_args()
    if not arguments.confirm_live_bedrock:
        parser.error("--confirm-live-bedrock is required for the metered model invocation")
    manifest = run_capture_probe(
        example_id=arguments.example_id,
        prompt=_row_prompt(arguments.example_id),
        run_store=REPO_ROOT / "datasets" / "runs",
    )
    output = manifest["outputs"]
    print(
        json.dumps(
            {
                "runId": manifest["runId"],
                "experimentId": manifest["experimentId"],
                "modelId": MODEL_ID,
                "status": output["status"],
                "runDirectory": output["runDirectory"],
                "canonicalTracePath": output["canonicalTracePath"],
                "errorKind": None if output["error"] is None else output["error"]["kind"],
            },
            sort_keys=True,
        )
    )
    return 0 if output["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
