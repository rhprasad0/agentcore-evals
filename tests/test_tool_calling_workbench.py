"""HTTP tests for the loopback-only tool-calling corpus review workbench."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.tool_calling_workbench import create_server
from src.tool_calling_dataset import DatasetPaths, load_dataset, serialize_rows


REPO_ROOT = Path(__file__).resolve().parents[1]


class ToolCallingWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temporary_directory.name)
        for relative_path in ("contracts", "datasets", "schemas"):
            shutil.copytree(REPO_ROOT / relative_path, self.repo_root / relative_path)
        self.paths = DatasetPaths.from_repo_root(self.repo_root)
        manifest = json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))
        manifest["reviewStatus"] = "draft"
        self.paths.manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        self.server = create_server(self.paths)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.temporary_directory.cleanup()

    def request(self, method: str, route: str, payload: object | None = None) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.base_url}{route}",
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def request_text(self, route: str) -> tuple[int, str, str]:
        request = Request(f"{self.base_url}{route}", method="GET")
        try:
            with urlopen(request, timeout=5) as response:
                return (
                    response.status,
                    response.headers["Content-Type"],
                    response.read().decode("utf-8"),
                )
        except HTTPError as error:
            return error.code, error.headers["Content-Type"], error.read().decode("utf-8")

    def test_dataset_endpoint_returns_authoritative_rows_and_revision(self) -> None:
        status, payload = self.request("GET", "/api/dataset")

        self.assertEqual(200, status)
        self.assertEqual("tool-calling-100", payload["manifest"]["datasetId"])
        self.assertEqual(100, len(payload["rows"]))
        self.assertEqual(100, payload["summary"]["rowCount"])
        self.assertEqual(100, payload["summary"]["reviewCounts"]["reviewed"])
        self.assertRegex(payload["revision"], r"^[0-9a-f]{64}$")
        self.assertIn("failure-injection", payload["editorMetadata"]["scenarioFamilies"])
        self.assertIn("weather.get_current_weather", payload["editorMetadata"]["contractInputs"])
        self.assertIn("city", payload["editorMetadata"]["contractInputs"]["weather.get_current_weather"])
        self.assertNotIn("checklist", payload["editorMetadata"])

    def test_static_workbench_surface_and_assets_are_served_from_fixed_routes(self) -> None:
        status, content_type, document = self.request_text("/")
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("text/html"))
        self.assertIn('id="workbench"', document)
        self.assertIn('rel="icon" href="data:,"', document)

        status, content_type, script = self.request_text("/assets/app.js")
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("application/javascript"))
        self.assertIn("saveRow", script)
        self.assertIn("refreshFilteredView", script)
        self.assertNotIn("readChecklistItems", script)
        self.assertNotIn("renderChecklist", script)
        self.assertNotIn("Blind-review checklist", script)
        self.assertNotIn("allChecklistItemsComplete", script)

        status, content_type, stylesheet = self.request_text("/assets/styles.css")
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("text/css"))
        self.assertIn("--surface", stylesheet)
        self.assertNotIn(".checklist", stylesheet)
        self.assertNotIn(".local-note", stylesheet)

        status, _, _ = self.request_text("/assets/not-a-file.js")
        self.assertEqual(404, status)

    def test_valid_put_updates_only_the_requested_row(self) -> None:
        _, dataset = self.request("GET", "/api/dataset")
        updated_row = json.loads(json.dumps(dataset["rows"][0]))
        updated_row["prompt"] = "What is the current weather in Arlington, Virginia?"

        status, payload = self.request(
            "PUT",
            "/api/rows/tc-0001",
            {"revision": dataset["revision"], "row": updated_row},
        )

        self.assertEqual(200, status)
        self.assertNotEqual(dataset["revision"], payload["revision"])
        self.assertEqual(updated_row, payload["row"])
        _, reloaded = self.request("GET", "/api/dataset")
        self.assertEqual(updated_row, reloaded["rows"][0])
        self.assertEqual(dataset["rows"][1], reloaded["rows"][1])

    def test_invalid_put_never_writes_partial_jsonl(self) -> None:
        _, dataset = self.request("GET", "/api/dataset")
        corpus_path = self.repo_root / dataset["manifest"]["corpusPath"]
        original_contents = corpus_path.read_bytes()

        status, payload = self.request(
            "PUT",
            "/api/rows/tc-0001",
            {"revision": dataset["revision"], "row": {"exampleId": "tc-0001"}},
        )

        self.assertEqual(422, status)
        self.assertEqual("validation_failed", payload["error"]["code"])
        self.assertEqual(original_contents, corpus_path.read_bytes())

    def test_stale_put_returns_conflict_without_writing(self) -> None:
        _, dataset = self.request("GET", "/api/dataset")
        corpus_path = self.repo_root / dataset["manifest"]["corpusPath"]
        original_contents = corpus_path.read_bytes()

        status, payload = self.request(
            "PUT",
            "/api/rows/tc-0001",
            {"revision": "0" * 64, "row": dataset["rows"][0]},
        )

        self.assertEqual(409, status)
        self.assertEqual("stale_revision", payload["error"]["code"])
        self.assertEqual(original_contents, corpus_path.read_bytes())

    def test_put_rejects_a_route_and_body_example_id_mismatch(self) -> None:
        _, dataset = self.request("GET", "/api/dataset")

        status, payload = self.request(
            "PUT",
            "/api/rows/tc-0001",
            {"revision": dataset["revision"], "row": dataset["rows"][1]},
        )

        self.assertEqual(400, status)
        self.assertEqual("example_id_mismatch", payload["error"]["code"])

    def test_finalize_requires_reviews_then_makes_the_dataset_read_only(self) -> None:
        snapshot = load_dataset(self.paths)
        snapshot.rows[0]["provenance"]["reviewStatus"] = "pending"
        snapshot.corpus_path.write_text(serialize_rows(snapshot.rows), encoding="utf-8")
        _, dataset = self.request("GET", "/api/dataset")

        status, payload = self.request(
            "POST",
            "/api/finalize",
            {"revision": dataset["revision"]},
        )

        self.assertEqual(409, status)
        self.assertEqual("reviews_pending", payload["error"]["code"])

        snapshot = load_dataset(self.paths)
        for row in snapshot.rows:
            row["provenance"]["reviewStatus"] = "reviewed"
        snapshot.corpus_path.write_text(serialize_rows(snapshot.rows), encoding="utf-8")
        _, reviewed_dataset = self.request("GET", "/api/dataset")

        status, finalized = self.request(
            "POST",
            "/api/finalize",
            {"revision": reviewed_dataset["revision"]},
        )

        self.assertEqual(200, status)
        self.assertEqual("human-reviewed", finalized["manifest"]["reviewStatus"])
        status, mutation = self.request(
            "PUT",
            "/api/rows/tc-0001",
            {"revision": finalized["revision"], "row": finalized["rows"][0]},
        )
        self.assertEqual(409, status)
        self.assertEqual("dataset_finalized", mutation["error"]["code"])


if __name__ == "__main__":
    unittest.main()
