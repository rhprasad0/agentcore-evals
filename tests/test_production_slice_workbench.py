"""HTTP tests for the editable Week 9 production-slice draft workbench."""

from __future__ import annotations

import copy
import hashlib
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
        self.paths.gold_path.unlink(missing_ok=True)
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
        self.assertTrue(dataset["capabilities"]["canEditGoldDraft"])
        self.assertTrue(dataset["capabilities"]["canFinalize"])
        self.assertIn("prefilled", dataset["notice"].lower())
        first = dataset["rows"][0]
        self.assertEqual("slice-01", first["goldDraft"]["caseId"])
        self.assertEqual("behavior", first["goldDraft"]["evaluationKind"])
        self.assertTrue(first["goldDraft"]["automatedJudgeEligible"])
        self.assertEqual(
            ["weather.get_current_weather"],
            first["goldDraft"]["orderedToolSequence"],
        )
        self.assertIsInstance(first["goldDraft"]["rationale"], str)

        boundary = dataset["rows"][6]["goldDraft"]
        self.assertEqual("slice-07", boundary["caseId"])
        self.assertEqual("boundary", boundary["evaluationKind"])
        self.assertFalse(boundary["automatedJudgeEligible"])
        self.assertEqual("week_11", boundary["boundaryExpectation"]["observationOwner"])

        guardrail_row = dataset["rows"][7]
        self.assertEqual("tc-0101", guardrail_row["exampleId"])
        self.assertNotIn("search.web_search", json.dumps(guardrail_row))

        reviewed_without_rationale = copy.deepcopy(first)
        reviewed_without_rationale["goldDraft"]["rationale"] = ""
        reviewed_without_rationale["provenance"]["reviewStatus"] = "reviewed"
        status, error = self.request(
            "PUT",
            "/api/rows/tc-0001",
            {"revision": dataset["revision"], "row": reviewed_without_rationale},
        )
        self.assertEqual(422, status)
        self.assertEqual("validation_failed", error["error"]["code"])
        self.assertTrue(
            any("rationale" in detail["path"] for detail in error["error"]["details"])
        )

        revision = dataset["revision"]
        for row in dataset["rows"]:
            reviewed = copy.deepcopy(row)
            reviewed["goldDraft"]["rationale"] = f"Reviewed expectation for {reviewed['goldDraft']['caseId']}."
            reviewed["provenance"]["reviewStatus"] = "reviewed"
            status, updated = self.request(
                "PUT",
                f"/api/rows/{reviewed['exampleId']}",
                {"revision": revision, "row": reviewed},
            )
            self.assertEqual(200, status)
            revision = updated["revision"]

        status, finalized = self.request("POST", "/api/finalize", {"revision": revision})
        self.assertEqual(200, status)
        self.assertEqual("human-reviewed", finalized["manifest"]["reviewStatus"])

        gold_path = self.repo_root / "datasets" / "labels" / "production-slice-8-human.jsonl"
        report_path = self.repo_root / "docs" / "reports" / "week-09-human-labels.md"
        gold_rows = [json.loads(line) for line in gold_path.read_text().splitlines()]
        self.assertEqual(8, len(gold_rows))
        self.assertEqual(6, sum(row["automated_judge_eligible"] for row in gold_rows))
        self.assertEqual(2, sum(row["evaluation_kind"] == "boundary" for row in gold_rows))
        digest_payload = {
            "case_id": gold_rows[0]["case_id"],
            "expectation": gold_rows[0]["expectation"],
            "expectation_version": gold_rows[0]["expectation_version"],
        }
        digest = hashlib.sha256(
            json.dumps(digest_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        self.assertEqual(digest, gold_rows[0]["expectation_sha256"])
        report = report_path.read_text()
        self.assertIn("Input SHA-256", report)
        self.assertIn("Gold SHA-256", report)

        status, error = self.request(
            "PUT",
            "/api/rows/tc-0001",
            {"revision": finalized["revision"], "row": finalized["rows"][0]},
        )
        self.assertEqual(409, status)
        self.assertEqual("dataset_finalized", error["error"]["code"])
        self.assertEqual(source_before, source_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
