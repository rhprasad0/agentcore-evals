"""HTTP tests for the editable Week 9 production-slice draft workbench."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.production_slice_workbench import create_server
from src.production_slice_dataset import SlicePaths


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProductionSliceWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temporary_directory.name)
        for relative_path in ("contracts", "datasets", "schemas"):
            shutil.copytree(REPO_ROOT / relative_path, self.repo_root / relative_path)
        self.paths = SlicePaths.from_repo_root(self.repo_root)
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

    def test_draft_workbench_round_trip(self) -> None:
        source_path = self.repo_root / "datasets" / "synthetic" / "tool-calling-100.jsonl"
        source_before = source_path.read_bytes()

        status, dataset = self.request("GET", "/api/dataset")
        self.assertEqual(200, status)
        self.assertEqual(8, len(dataset["rows"]))
        self.assertFalse(dataset["capabilities"]["canFinalize"])
        self.assertIn("placeholder", dataset["notice"].lower())

        updated_row = copy.deepcopy(dataset["rows"][0])
        updated_row["prompt"] = "What is the current weather in Arlington, Virginia?"
        status, updated = self.request(
            "PUT",
            "/api/rows/tc-0001",
            {"revision": dataset["revision"], "row": updated_row},
        )
        self.assertEqual(200, status)
        self.assertEqual(updated_row, updated["row"])

        status, error = self.request(
            "POST",
            "/api/finalize",
            {"revision": updated["revision"]},
        )
        self.assertEqual(409, status)
        self.assertEqual("draft_not_finalizable", error["error"]["code"])
        self.assertEqual(source_before, source_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
