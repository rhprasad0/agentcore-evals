"""Loopback-only GUI for reviewing the frozen Week 7 ten-row trace sample."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

from src.week07_review_workspace import (
    ReviewConflictError,
    ReviewValidationError,
    Week07ReviewWorkspace,
    load_week07_review_workspace,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
DEFAULT_PORT = 8777
STATIC_ROOT = Path(__file__).with_name("week_07_review_workbench_static")
STATIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def create_server(
    workspace: Week07ReviewWorkspace,
    *,
    port: int = 0,
) -> ThreadingHTTPServer:
    """Create an unstarted HTTP server bound only to loopback."""

    class ReviewHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path in STATIC_ASSETS:
                _serve_static(self, self.path)
                return
            if self.path == "/api/review":
                _send_json(self, HTTPStatus.OK, workspace.payload())
                return
            if self.path == "/api/export":
                _send_json(self, HTTPStatus.OK, workspace.export_document())
                return
            _send_error(self, HTTPStatus.NOT_FOUND, "route_not_found", "No such route.")

        def do_PUT(self) -> None:  # noqa: N802
            prefix = "/api/reviews/"
            if not self.path.startswith(prefix) or "/" in self.path[len(prefix) :]:
                _send_error(self, HTTPStatus.NOT_FOUND, "route_not_found", "No such route.")
                return
            example_id = self.path[len(prefix) :]
            body = _read_json_body(self)
            if body is None:
                return
            revision = body.get("revision")
            review = body.get("review")
            if not isinstance(revision, str) or not isinstance(review, dict):
                _send_error(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    "invalid_request",
                    "revision and review are required.",
                )
                return
            try:
                payload = workspace.save_review(example_id, review, revision=revision)
            except ReviewConflictError as error:
                _send_error(self, HTTPStatus.CONFLICT, "stale_revision", str(error))
                return
            except ReviewValidationError as error:
                _send_error(self, HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_review", str(error))
                return
            _send_json(self, HTTPStatus.OK, payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((HOST, port), ReviewHandler)


def _serve_static(handler: BaseHTTPRequestHandler, route: str) -> None:
    filename, content_type = STATIC_ASSETS[route]
    body = (STATIC_ROOT / filename).read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    raw_length = handler.headers.get("Content-Length")
    try:
        length = int(raw_length) if raw_length is not None else -1
    except ValueError:
        length = -1
    if length < 0 or length > 100_000:
        _send_error(
            handler,
            HTTPStatus.BAD_REQUEST,
            "invalid_request",
            "Provide a JSON body smaller than 100 KB.",
        )
        return None
    try:
        body = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _send_error(handler, HTTPStatus.BAD_REQUEST, "invalid_json", "Body must be JSON.")
        return None
    if not isinstance(body, dict):
        _send_error(handler, HTTPStatus.BAD_REQUEST, "invalid_request", "Body must be an object.")
        return None
    return body


def _send_json(
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


def _send_error(
    handler: BaseHTTPRequestHandler,
    status: HTTPStatus | int,
    code: str,
    message: str,
) -> None:
    _send_json(handler, status, {"error": {"code": code, "message": message}})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args()
    run_directory = REPO_ROOT / "datasets/runs" / arguments.run_id
    workspace = load_week07_review_workspace(REPO_ROOT, run_directory)
    server = create_server(workspace, port=arguments.port)
    address = server.server_address
    host, port = str(address[0]), int(address[1])
    print(f"Week 7 review workbench: http://{host}:{port}")
    print(f"Private review state: {workspace.review_path.relative_to(REPO_ROOT)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
