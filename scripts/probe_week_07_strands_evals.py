"""Run one bounded Strands Evals mapping compatibility probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from strands_evals import Case, TracedHandler, eval_task
from strands_evals.mappers import StrandsInMemorySessionMapper

from scripts.probe_week_07_telemetry import (
    REPO_ROOT,
    _environment,
    _row_prompt,
    _write_json_atomic,
)
from src.agents.weather_specimen import (
    MODEL_ID,
    build_behavior_pins,
    build_specimen,
    build_specimen_model,
)
from src.deterministic_mocks import MockRegistry
from src.run_manifest import create_run_manifest
from src.strands_evals_compatibility import compare_planted_facts
from src.telemetry_capture import serialize_strands_inline_spans
from src.telemetry_normalization import normalize_strands_telemetry


class CapturingSessionMapper:
    """Delegate native Session mapping while retaining the exact public span inputs."""

    def __init__(self) -> None:
        self._delegate = StrandsInMemorySessionMapper()
        self.finished_spans: list[Any] = []

    def map_to_session(self, data: list[Any], session_id: str):
        self.finished_spans = list(data)
        return self._delegate.map_to_session(self.finished_spans, session_id)


def run_native_compatibility_probe(
    *,
    example_id: str,
    prompt: str,
    run_store: Path,
) -> dict[str, Any]:
    """Map one span set through both native and repository representations."""

    behavior_pins = build_behavior_pins(REPO_ROOT)
    manifest = create_run_manifest(behavior_pins, _environment(), run_store)
    run_id = manifest["runId"]
    run_directory = run_store / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    manifest_path = run_directory / "run-manifest.json"
    raw_path = run_directory / "raw" / "strands-inline.json"
    canonical_path = run_directory / "canonical-trace.json"
    compatibility_path = run_directory / "native-compatibility.json"
    mapper = CapturingSessionMapper()
    handler = TracedHandler(mapper=mapper)

    @eval_task(handler)
    def native_task(case: Case):
        return build_specimen(
            model=build_specimen_model(),
            registry=MockRegistry.from_repo_root(REPO_ROOT),
            example_id=example_id,
            trace_attributes={
                "session.id": case.session_id,
                "gen_ai.conversation.id": case.session_id,
            },
        )

    try:
        case = Case(
            name=f"week-07-{example_id}",
            session_id=run_id,
            input=prompt,
        )
        native_result = native_task(case)
        session = native_result["trajectory"]
        source = serialize_strands_inline_spans(
            mapper.finished_spans,
            agent_manifest={"manifestId": "agents.weather", "version": "4.0.0"},
            producer_version=behavior_pins["sdkVersions"]["strands-agents"],
        )
        _write_json_atomic(raw_path, source)
        canonical = normalize_strands_telemetry(source, repo_root=REPO_ROOT)
        _write_json_atomic(canonical_path, canonical)
        mismatches = compare_planted_facts(canonical, session)
        _write_json_atomic(
            compatibility_path,
            {
                "schemaVersion": "1.0.0",
                "mismatchFields": [mismatch.field for mismatch in mismatches],
                "representationOnlyFields": [
                    "native typed span classes",
                    "native Session and Trace containers",
                    "timestamps and token usage",
                ],
            },
        )
        if mismatches:
            raise ValueError(
                "native compatibility mismatches: "
                + ", ".join(mismatch.field for mismatch in mismatches)
            )
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example-id", default="tc-0004")
    parser.add_argument("--confirm-live-bedrock", action="store_true")
    arguments = parser.parse_args()
    if not arguments.confirm_live_bedrock:
        parser.error("--confirm-live-bedrock is required for the metered model invocation")
    manifest = run_native_compatibility_probe(
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
                "errorKind": None if output["error"] is None else output["error"]["kind"],
            },
            sort_keys=True,
        )
    )
    return 0 if output["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
