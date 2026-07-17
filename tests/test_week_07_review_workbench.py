"""Tests for the private Week 7 frozen-row review workspace."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.week_07_review_workbench import create_server
from src.week07_review_workspace import (
    ReviewConflictError,
    ReviewValidationError,
    Week07ReviewWorkspace,
    load_week07_review_workspace,
)
from src.review_sample import load_frozen_review_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = REPO_ROOT / "tests/fixtures/telemetry/canonical/weather-success.json"


def synthetic_workspace(review_path: Path) -> Week07ReviewWorkspace:
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    second_trace = deepcopy(trace)
    second_trace["prompt"] = "Can this tool provide a forecast?"
    second_trace["response"] = "No. This tool only provides current weather."
    return Week07ReviewWorkspace(
        sample_id="week-07-human-review-10",
        experiment_id="sha256:" + "a" * 64,
        rows=(
            {
                "exampleId": "tc-0001",
                "scenarioFamily": "straightforward",
                "prompt": trace["prompt"],
                "expected": {
                    "minCalls": 1,
                    "maxCalls": 1,
                    "toolIds": ["weather.get_current_weather"],
                    "mustNotCall": [],
                    "argConstraints": [],
                    "responseMust": ["report current weather"],
                    "responseMustNot": [],
                },
                "tags": ["weather", "single-tool"],
                "failureInjection": None,
            },
            {
                "exampleId": "tc-0065",
                "scenarioFamily": "no-tool",
                "prompt": second_trace["prompt"],
                "expected": {
                    "minCalls": 0,
                    "maxCalls": 0,
                    "toolIds": [],
                    "mustNotCall": ["weather.get_current_weather"],
                    "argConstraints": [],
                    "responseMust": ["explain capability boundary"],
                    "responseMustNot": [],
                },
                "tags": ["near-boundary", "decline"],
                "failureInjection": None,
            },
        ),
        traces={"tc-0001": trace, "tc-0065": second_trace},
        review_path=review_path,
    )


class Week07ReviewWorkspaceTests(unittest.TestCase):
    def test_loader_binds_the_frozen_sample_to_one_run_without_raw_telemetry(self) -> None:
        sample = load_frozen_review_sample(
            REPO_ROOT / "datasets/reviews/week-07-ten-row-sample.json",
            projection_path=REPO_ROOT / "datasets/projections/weather-only-62.json",
            repo_root=REPO_ROOT,
        )
        template = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            run_directory = Path(directory) / "run"
            for row in sample.rows:
                trace = deepcopy(template)
                trace["prompt"] = row["prompt"]
                trace["response"] = "Synthetic review-workbench response."
                case_directory = run_directory / "cases" / row["exampleId"]
                case_directory.mkdir(parents=True)
                (case_directory / "canonical-trace.json").write_text(
                    json.dumps(trace), encoding="utf-8"
                )
            (run_directory / "run-manifest.json").write_text(
                json.dumps({"experimentId": "sha256:" + "a" * 64}),
                encoding="utf-8",
            )

            workspace = load_week07_review_workspace(
                REPO_ROOT,
                run_directory,
                review_path=Path(directory) / "review.json",
            )

            payload = workspace.payload()
            self.assertEqual(10, payload["summary"]["total"])
            self.assertEqual(sample.document["selectedExampleIds"], [
                row["exampleId"] for row in payload["rows"]
            ])

    def test_payload_is_source_ordered_and_contains_no_preloaded_verdicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = synthetic_workspace(Path(directory) / "human-review.json")

            payload = workspace.payload()

        self.assertEqual(["tc-0001", "tc-0065"], [row["exampleId"] for row in payload["rows"]])
        self.assertEqual(0, payload["summary"]["reviewed"])
        self.assertEqual(2, payload["summary"]["remaining"])
        self.assertRegex(payload["revision"], r"^[0-9a-f]{64}$")
        self.assertIsNone(payload["rows"][0]["review"])
        self.assertEqual(1, len(payload["rows"][0]["observed"]["toolCalls"]))
        self.assertNotIn("suggestedVerdict", json.dumps(payload))

    def test_save_is_atomic_revisioned_and_rejects_stale_or_invalid_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            review_path = Path(directory) / "human-review.json"
            workspace = synthetic_workspace(review_path)
            revision = workspace.payload()["revision"]
            review = {
                "exampleId": "tc-0001",
                "verdict": "pass",
                "confidence": "high",
                "checks": {
                    "expectationDefensible": True,
                    "toolChoiceAndCount": True,
                    "arguments": True,
                    "resultHandling": True,
                    "responseRequirements": True,
                    "noForbiddenBehavior": True,
                },
                "notes": "The trace matches the declared expectation.",
            }

            saved = workspace.save_review("tc-0001", review, revision=revision)

            self.assertNotEqual(revision, saved["revision"])
            self.assertEqual(1, saved["summary"]["reviewed"])
            persisted = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertEqual("pass", persisted["reviews"]["tc-0001"]["verdict"])
            with self.assertRaises(ReviewConflictError):
                workspace.save_review("tc-0001", review, revision=revision)
            invalid = deepcopy(review)
            invalid["verdict"] = "looks-good"
            with self.assertRaises(ReviewValidationError):
                workspace.save_review(
                    "tc-0001",
                    invalid,
                    revision=saved["revision"],
                )


class Week07ReviewWorkbenchHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = synthetic_workspace(
            Path(self.temporary_directory.name) / "human-review.json"
        )
        self.server = create_server(self.workspace)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.temporary_directory.cleanup()

    def request_json(
        self, method: str, route: str, payload: object | None = None
    ) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + route,
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
        try:
            with urlopen(self.base_url + route, timeout=5) as response:
                return (
                    response.status,
                    response.headers["Content-Type"],
                    response.read().decode("utf-8"),
                )
        except HTTPError as error:
            return error.code, error.headers["Content-Type"], error.read().decode("utf-8")

    def test_api_loads_saves_and_exports_private_review_state(self) -> None:
        status, payload = self.request_json("GET", "/api/review")
        review = {
            "exampleId": "tc-0001",
            "verdict": "pass",
            "confidence": "high",
            "checks": {field: True for field in payload["reviewMetadata"]["checkFields"]},
            "notes": "Reviewed in the local GUI.",
        }

        status, saved = self.request_json(
            "PUT",
            "/api/reviews/tc-0001",
            {"revision": payload["revision"], "review": review},
        )

        self.assertEqual(200, status)
        self.assertEqual(1, saved["summary"]["reviewed"])
        status, exported = self.request_json("GET", "/api/export")
        self.assertEqual(200, status)
        self.assertEqual("pass", exported["reviews"]["tc-0001"]["verdict"])

    def test_server_is_loopback_only_and_serves_allowlisted_assets(self) -> None:
        self.assertEqual("127.0.0.1", self.server.server_address[0])
        status, content_type, document = self.request_text("/")
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("text/html"))
        self.assertIn('id="review-app"', document)
        status, content_type, script = self.request_text("/assets/app.js")
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("application/javascript"))
        self.assertIn("saveAndNext", script)
        self.assertIn("renderWorkspace", script)
        self.assertIn("toggleRubric", script)
        self.assertIn("downloadReview", script)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)
        status, content_type, stylesheet = self.request_text("/assets/styles.css")
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("text/css"))
        self.assertIn("--accent", stylesheet)
        self.assertIn("@media (max-width: 900px)", stylesheet)
        status, _, _ = self.request_text("/assets/not-allowed.js")
        self.assertEqual(404, status)


if __name__ == "__main__":
    unittest.main()
