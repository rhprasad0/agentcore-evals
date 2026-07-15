"""Loopback-only browser workbench for the Week 6 tool-calling corpus."""

from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from collections import Counter
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.tool_calling_dataset import (
    DatasetPaths,
    DatasetSnapshot,
    dataset_revision,
    load_dataset,
    serialize_rows,
    validate_dataset,
)


HOST = "127.0.0.1"
DEFAULT_PORT = 8765
STATIC_ROOT = Path(__file__).with_name("tool_calling_workbench_static")
STATIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def create_server(paths: DatasetPaths, *, port: int = 0) -> ThreadingHTTPServer:
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
                handle_finalize(self, paths)
                return
            send_error(self, HTTPStatus.NOT_FOUND, "route_not_found", "No such workbench route.")

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((HOST, port), WorkbenchHandler)


def dataset_payload(paths: DatasetPaths) -> dict[str, Any]:
    """Load the source-derived data supplied to the local browser client."""

    snapshot = load_dataset(paths)
    family_counts = Counter(row["scenarioFamily"] for row in snapshot.rows)
    review_counts = Counter(row["provenance"]["reviewStatus"] for row in snapshot.rows)
    return {
        "manifest": snapshot.manifest,
        "rows": snapshot.rows,
        "revision": dataset_revision(snapshot),
        "editorMetadata": editor_metadata(paths, snapshot),
        "summary": {
            "rowCount": len(snapshot.rows),
            "familyCounts": dict(family_counts),
            "reviewCounts": {
                "pending": review_counts["pending"],
                "reviewed": review_counts["reviewed"],
            },
        },
    }


def serve_static_asset(handler: BaseHTTPRequestHandler, route: str) -> None:
    """Serve only the fixed local workbench assets, never arbitrary paths."""

    filename, content_type = STATIC_ASSETS[route]
    content = (STATIC_ROOT / filename).read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


def editor_metadata(paths: DatasetPaths, snapshot: DatasetSnapshot) -> dict[str, Any]:
    """Derive editor controls from the versioned schemas and exact pinned contracts."""

    example_schema = load_json_object(paths.example_schema_path)
    arg_constraint_properties = example_schema["$defs"]["argConstraint"]["properties"]
    failure_properties = example_schema["$defs"]["failureInjection"]["properties"]
    failure_kinds = example_schema["$defs"]["failureKind"]["enum"]
    contract_inputs = {}
    for reference in snapshot.manifest["toolContracts"]:
        tool_id = reference["toolId"]
        contract_path = paths.repo_root / "contracts" / "tools" / tool_id / f"{reference['version']}.json"
        contract = load_json_object(contract_path)
        contract_inputs[tool_id] = sorted(contract["inputSchema"].get("properties", {}))
    return {
        "scenarioFamilies": example_schema["properties"]["scenarioFamily"]["enum"],
        "tags": example_schema["properties"]["tags"]["items"]["enum"],
        "constraintPredicates": sorted(
            key for key in arg_constraint_properties if key not in {"toolId", "path"}
        ),
        "failureKinds": failure_kinds,
        "failureSources": failure_properties["source"]["enum"],
        "contractInputs": contract_inputs,
    }


def load_json_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def handle_row_update(
    handler: BaseHTTPRequestHandler,
    paths: DatasetPaths,
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

    snapshot = load_dataset(paths)
    if snapshot.manifest.get("reviewStatus") == "human-reviewed":
        send_error(
            handler,
            HTTPStatus.CONFLICT,
            "dataset_finalized",
            "The human-reviewed dataset is read-only; create a versioned erratum instead.",
        )
        return
    if revision != dataset_revision(snapshot):
        send_error(
            handler,
            HTTPStatus.CONFLICT,
            "stale_revision",
            "Reload the dataset before saving this row.",
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
            f"No row named {route_example_id} exists in this dataset.",
        )
        return
    candidate_rows = copy.deepcopy(snapshot.rows)
    candidate_rows[replacement_index] = row
    candidate = DatasetSnapshot(
        manifest=copy.deepcopy(snapshot.manifest),
        rows=candidate_rows,
        corpus_path=snapshot.corpus_path,
    )
    issues = validate_dataset(candidate, paths)
    if issues:
        send_error(
            handler,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "validation_failed",
            "The proposed row would make the corpus invalid.",
            [asdict(issue) for issue in issues],
        )
        return

    atomic_write_text(snapshot.corpus_path, serialize_rows(candidate.rows))
    updated_snapshot = load_dataset(paths)
    send_json(
        handler,
        HTTPStatus.OK,
        {
            "row": updated_snapshot.rows[replacement_index],
            "revision": dataset_revision(updated_snapshot),
        },
    )


def handle_finalize(handler: BaseHTTPRequestHandler, paths: DatasetPaths) -> None:
    request_payload = read_json_body(handler)
    if request_payload is None:
        return
    revision = request_payload.get("revision")
    if not isinstance(revision, str):
        send_error(
            handler,
            HTTPStatus.BAD_REQUEST,
            "invalid_request",
            "A revision string is required to finalize the dataset.",
        )
        return
    snapshot = load_dataset(paths)
    if snapshot.manifest.get("reviewStatus") == "human-reviewed":
        send_error(
            handler,
            HTTPStatus.CONFLICT,
            "dataset_finalized",
            "The human-reviewed dataset is already frozen.",
        )
        return
    if revision != dataset_revision(snapshot):
        send_error(
            handler,
            HTTPStatus.CONFLICT,
            "stale_revision",
            "Reload the dataset before finalizing it.",
        )
        return
    issues = validate_dataset(snapshot, paths)
    if issues:
        send_error(
            handler,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "validation_failed",
            "The corpus must validate before finalization.",
            [asdict(issue) for issue in issues],
        )
        return
    pending_rows = [
        row["exampleId"]
        for row in snapshot.rows
        if row["provenance"]["reviewStatus"] != "reviewed"
    ]
    if pending_rows:
        send_error(
            handler,
            HTTPStatus.CONFLICT,
            "reviews_pending",
            "Every row must be marked reviewed before finalization.",
            [
                {
                    "path": f"{example_id}.provenance.reviewStatus",
                    "message": "must be reviewed before finalization",
                }
                for example_id in pending_rows
            ],
        )
        return
    finalized_manifest = copy.deepcopy(snapshot.manifest)
    finalized_manifest["reviewStatus"] = "human-reviewed"
    atomic_write_text(
        paths.manifest_path,
        json.dumps(finalized_manifest, ensure_ascii=False, indent=2) + "\n",
    )
    send_json(handler, HTTPStatus.OK, dataset_payload(paths))


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    raw_length = handler.headers.get("Content-Length")
    try:
        content_length = int(raw_length) if raw_length is not None else -1
    except ValueError:
        content_length = -1
    if content_length < 0 or content_length > 1_000_000:
        send_error(
            handler,
            HTTPStatus.BAD_REQUEST,
            "invalid_request",
            "Provide a JSON request body smaller than 1 MB.",
        )
        return None
    try:
        payload = json.loads(handler.rfile.read(content_length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        send_error(handler, HTTPStatus.BAD_REQUEST, "invalid_json", "Request body must be valid JSON.")
        return None
    if not isinstance(payload, dict):
        send_error(handler, HTTPStatus.BAD_REQUEST, "invalid_request", "Request body must be a JSON object.")
        return None
    return payload


def atomic_write_text(path: Path, text: str) -> None:
    """Durably replace one repository-owned text artifact without partial writes."""

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def send_json(
    handler: BaseHTTPRequestHandler,
    status: HTTPStatus | int,
    payload: Mapping[str, Any],
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_error(
    handler: BaseHTTPRequestHandler,
    status: HTTPStatus | int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
) -> None:
    send_json(
        handler,
        status,
        {
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
            }
        },
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args(argv)
    server = create_server(DatasetPaths.from_repo_root(Path(__file__).resolve().parents[1]), port=arguments.port)
    print(f"Tool-calling review workbench: http://{HOST}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
