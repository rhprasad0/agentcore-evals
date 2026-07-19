"""Loopback-only browser workbench for the Week 9 production-slice draft."""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Sequence

from scripts.tool_calling_workbench import (
    HOST,
    STATIC_ASSETS,
    atomic_write_text,
    editor_metadata,
    read_json_body,
    send_error,
    send_json,
    serve_static_asset,
)
from src.production_slice_dataset import (
    SlicePaths,
    load_slice,
    serialize_rows,
    slice_revision,
    validate_slice,
)
from src.tool_calling_dataset import DatasetPaths, load_dataset


DEFAULT_PORT = 8766


def create_server(paths: SlicePaths, *, port: int = 0) -> ThreadingHTTPServer:
    """Create an unstarted HTTP server bound only to the loopback interface."""

    class WorkbenchHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path in STATIC_ASSETS:
                serve_static_asset(self, self.path)
                return
            if self.path == "/api/dataset":
                send_json(self, HTTPStatus.OK, dataset_payload(paths))
                return
            send_error(self, HTTPStatus.NOT_FOUND, "route_not_found", "No such workbench route.")

        def do_PUT(self) -> None:  # noqa: N802
            prefix = "/api/rows/"
            if not self.path.startswith(prefix) or "/" in self.path[len(prefix) :]:
                send_error(self, HTTPStatus.NOT_FOUND, "route_not_found", "No such workbench route.")
                return
            handle_row_update(self, paths, self.path[len(prefix) :])

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/api/finalize":
                send_error(
                    self,
                    HTTPStatus.CONFLICT,
                    "draft_not_finalizable",
                    "This incomplete draft cannot be finalized; freeze human gold in the later Week 9 step.",
                )
                return
            send_error(self, HTTPStatus.NOT_FOUND, "route_not_found", "No such workbench route.")

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((HOST, port), WorkbenchHandler)


def dataset_payload(paths: SlicePaths) -> dict[str, Any]:
    snapshot = load_slice(paths)
    issues = validate_slice(snapshot, paths)
    if issues:
        raise ValueError("draft validation failed: " + "; ".join(f"{issue.path}: {issue.message}" for issue in issues))
    source_manifest = snapshot.source_manifest
    source_paths = DatasetPaths.from_repo_root(paths.repo_root)
    family_counts = Counter(row["scenarioFamily"] for row in snapshot.rows)
    review_counts = Counter(row["provenance"]["reviewStatus"] for row in snapshot.rows)
    return {
        "manifest": {
            "datasetId": "production-slice-8-draft",
            "version": "0.1.0",
            "workbenchTitle": "Production-slice draft workbench",
            "reviewStatus": "draft",
            "agentManifest": source_manifest["agentManifest"],
            "toolContracts": source_manifest["toolContracts"],
            "corpusPath": str(paths.draft_path.relative_to(paths.repo_root)),
        },
        "rows": snapshot.rows,
        "revision": slice_revision(snapshot),
        "editorMetadata": editor_metadata(source_paths, load_dataset(source_paths)),
        "capabilities": {"canFinalize": False},
        "notice": (
            "Draft projection only. tc-0065 and tc-0092 are placeholders for later Policy/Guardrail work; "
            "they are not infrastructure evidence."
        ),
        "summary": {
            "rowCount": len(snapshot.rows),
            "familyCounts": dict(family_counts),
            "reviewCounts": {
                "pending": review_counts["pending"],
                "reviewed": review_counts["reviewed"],
            },
        },
    }


def handle_row_update(
    handler: BaseHTTPRequestHandler,
    paths: SlicePaths,
    route_example_id: str,
) -> None:
    request_payload = read_json_body(handler)
    if request_payload is None:
        return
    revision = request_payload.get("revision")
    row = request_payload.get("row")
    if not isinstance(revision, str) or not isinstance(row, dict):
        send_error(
            handler,
            HTTPStatus.BAD_REQUEST,
            "invalid_request",
            "A row object and revision string are required.",
        )
        return
    if row.get("exampleId") != route_example_id:
        send_error(
            handler,
            HTTPStatus.BAD_REQUEST,
            "example_id_mismatch",
            "The route exampleId must match row.exampleId.",
        )
        return

    snapshot = load_slice(paths)
    current_revision = slice_revision(snapshot)
    if revision != current_revision:
        send_error(
            handler,
            HTTPStatus.CONFLICT,
            "stale_revision",
            "Reload the draft before saving this row.",
        )
        return

    replacement_index = next(
        (index for index, existing_row in enumerate(snapshot.rows) if existing_row["exampleId"] == route_example_id),
        None,
    )
    if replacement_index is None:
        send_error(
            handler,
            HTTPStatus.NOT_FOUND,
            "example_not_found",
            f"No row named {route_example_id} exists in this draft.",
        )
        return

    candidate_rows = copy.deepcopy(snapshot.rows)
    candidate_rows[replacement_index] = row
    candidate = copy.deepcopy(snapshot)
    candidate.rows = candidate_rows
    issues = validate_slice(candidate, paths)
    if issues:
        send_error(
            handler,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "validation_failed",
            "The proposed row would make the draft invalid.",
            [asdict(issue) for issue in issues],
        )
        return

    atomic_write_text(snapshot.corpus_path, serialize_rows(candidate.rows))
    updated_snapshot = load_slice(paths)
    send_json(
        handler,
        HTTPStatus.OK,
        {
            "row": updated_snapshot.rows[replacement_index],
            "revision": slice_revision(updated_snapshot),
        },
    )


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args(argv)
    paths = SlicePaths.from_repo_root(Path(__file__).resolve().parents[1])
    server = create_server(paths, port=arguments.port)
    print(f"Production-slice draft workbench: http://{HOST}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
