"""Execute or resume the complete metered Week 7 weather projection."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from strands_evals.telemetry import StrandsEvalsTelemetry

from scripts.probe_week_07_telemetry import REPO_ROOT, _environment
from src.agents.weather_specimen import (
    MODEL_ID,
    build_behavior_pins,
    build_specimen,
    build_specimen_model,
)
from src.dataset_projection import load_projection
from src.deterministic_mocks import MockRegistry
from src.projection_runner import run_projection_batch
from src.run_manifest import create_run_manifest, derive_experiment_id
from src.telemetry_capture import capture_finished_spans, serialize_strands_inline_spans
from src.telemetry_normalization import normalize_strands_telemetry


PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"
RUN_STORE = REPO_ROOT / "datasets/runs"


def _load_or_create_manifest(
    *,
    behavior_pins: Mapping[str, Any],
    resume_run_id: str | None,
) -> dict[str, Any]:
    if resume_run_id is None:
        return create_run_manifest(behavior_pins, _environment(), RUN_STORE)
    manifest_path = RUN_STORE / resume_run_id / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_experiment_id = derive_experiment_id(behavior_pins)
    if manifest.get("runId") != resume_run_id:
        raise ValueError("resume runId does not match stored manifest")
    if manifest.get("experimentId") != expected_experiment_id:
        raise ValueError("resume behavior pins do not match the current experiment")
    if manifest.get("behaviorPins") != dict(behavior_pins):
        raise ValueError("resume manifest behaviorPins differ from current exact pins")
    manifest["outputs"] = None
    return manifest


def _case_executor(telemetry: Any, model: Any, *, producer_version: str):
    registry = MockRegistry.from_repo_root(REPO_ROOT)

    def execute(row: Mapping[str, Any], session_id: str) -> dict[str, Any]:
        example_id = str(row["exampleId"])
        print(json.dumps({"event": "case-start", "exampleId": example_id}, sort_keys=True))
        telemetry.in_memory_exporter.clear()
        source = None
        try:
            agent = build_specimen(
                model=model,
                registry=registry,
                example_id=example_id,
                trace_attributes={
                    "session.id": session_id,
                    "gen_ai.conversation.id": session_id,
                },
            )
            agent(str(row["prompt"]))
            spans = capture_finished_spans(telemetry)
            source = serialize_strands_inline_spans(
                spans,
                agent_manifest={"manifestId": "agents.weather", "version": "4.0.0"},
                producer_version=producer_version,
            )
            trace = normalize_strands_telemetry(source, repo_root=REPO_ROOT)
            print(json.dumps({"event": "case-complete", "exampleId": example_id}, sort_keys=True))
            return {
                "status": "completed",
                "trace": trace,
                "source": source,
                "error": None,
            }
        except Exception as error:
            print(
                json.dumps(
                    {
                        "event": "case-instrument-error",
                        "exampleId": example_id,
                        "errorKind": error.__class__.__name__,
                    },
                    sort_keys=True,
                )
            )
            return {
                "status": "instrument-error",
                "trace": None,
                "source": source,
                "error": {
                    "kind": error.__class__.__name__,
                    "message": str(error)[:500] or error.__class__.__name__,
                },
            }

    return execute


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-live-bedrock", action="store_true")
    parser.add_argument("--resume-run-id")
    arguments = parser.parse_args()
    if not arguments.confirm_live_bedrock:
        parser.error("--confirm-live-bedrock is required for 62 metered model invocations")
    projection = load_projection(PROJECTION_PATH, repo_root=REPO_ROOT)
    if len(projection.rows) != 62:
        raise ValueError(f"weather projection must resolve to 62 rows, got {len(projection.rows)}")
    behavior_pins = build_behavior_pins(REPO_ROOT)
    manifest = _load_or_create_manifest(
        behavior_pins=behavior_pins,
        resume_run_id=arguments.resume_run_id,
    )
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    model = build_specimen_model()
    result = run_projection_batch(
        projection.rows,
        manifest=manifest,
        run_store=RUN_STORE,
        projection={
            "projectionId": projection.document["projectionId"],
            "version": projection.document["version"],
            "artifactSha256": sha256(PROJECTION_PATH.read_bytes()).hexdigest(),
        },
        execute_case=_case_executor(
            telemetry,
            model,
            producer_version=behavior_pins["sdkVersions"]["strands-agents"],
        ),
    )
    manifest_schema = json.loads(
        (REPO_ROOT / "schemas/run-manifest.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(manifest_schema).validate(result)
    summary = json.loads(
        (RUN_STORE / result["runId"] / "summary.json").read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "runId": result["runId"],
                "experimentId": result["experimentId"],
                "modelId": MODEL_ID,
                "status": result["outputs"]["status"],
                "counts": summary["counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
