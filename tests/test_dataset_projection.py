"""Tests for deterministic source-derived dataset projection loading."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from src.dataset_projection import DatasetProjectionError, load_projection


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"
SOURCE_PATH = REPO_ROOT / "datasets/synthetic/tool-calling-100.jsonl"


class DatasetProjectionTests(unittest.TestCase):
    def test_projection_selects_62_original_rows_in_source_order(self) -> None:
        projection = load_projection(PROJECTION_PATH, repo_root=REPO_ROOT)

        ids = [row["exampleId"] for row in projection.rows]
        self.assertEqual(62, len(ids))
        self.assertEqual(projection.document["selectedExampleIds"], ids)
        self.assertEqual("tc-0001", ids[0])
        self.assertEqual("tc-0100", ids[-1])
        self.assertNotIn("tc-0068", ids)
        self.assertNotIn("tc-0069", ids)
        self.assertEqual(
            projection.document["distribution"],
            dict(Counter(row["scenarioFamily"] for row in projection.rows)),
        )

    def test_selected_rows_equal_the_source_rows_without_rewriting(self) -> None:
        source_rows = {
            row["exampleId"]: row
            for row in (
                json.loads(line)
                for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
        projection = load_projection(PROJECTION_PATH, repo_root=REPO_ROOT)

        for row in projection.rows:
            self.assertEqual(source_rows[row["exampleId"]], row)

    def test_source_hash_mismatch_fails_loudly(self) -> None:
        document = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
        document["source"]["corpusSha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "projection.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(
                DatasetProjectionError,
                r"corpus sha256 mismatch.*expected 0000.*observed",
            ):
                load_projection(path, repo_root=REPO_ROOT)

    def test_selected_id_drift_fails_with_actionable_diagnostics(self) -> None:
        document = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
        document["selectedExampleIds"] = document["selectedExampleIds"][:-1]
        document["expectedRowCount"] = 61
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "projection.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(DatasetProjectionError, r"selectedExampleIds drift.*tc-0100"):
                load_projection(path, repo_root=REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
