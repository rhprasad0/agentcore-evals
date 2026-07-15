"""Tests for the generated Week 6 tool-calling corpus."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "datasets" / "synthetic" / "tool-calling-100.manifest.json"
SCHEMA_PATH = REPO_ROOT / "schemas" / "tool-calling-example.schema.json"


class ToolCallingCorpusTests(unittest.TestCase):
    def _load_manifest(self) -> dict[str, Any]:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def _load_rows(self) -> list[dict[str, Any]]:
        manifest = self._load_manifest()
        corpus_path = REPO_ROOT / manifest["corpusPath"]
        self.assertTrue(
            corpus_path.is_file(),
            f"missing corpus: {corpus_path.relative_to(REPO_ROOT)}",
        )
        return [
            json.loads(line)
            for line in corpus_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_corpus_has_manifest_distribution_and_schema_valid_rows(self) -> None:
        manifest = self._load_manifest()
        rows = self._load_rows()
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)

        self.assertEqual(manifest["expectedRowCount"], len(rows))
        self.assertEqual(
            manifest["distribution"],
            dict(Counter(row["scenarioFamily"] for row in rows)),
        )
        self.assertEqual(
            [f"tc-{index:04d}" for index in range(1, 101)],
            [row["exampleId"] for row in rows],
        )
        self.assertEqual(len(rows), len({row["prompt"] for row in rows}))

        for row in rows:
            with self.subTest(example_id=row["exampleId"]):
                errors = list(validator.iter_errors(row))
                self.assertEqual([], [error.message for error in errors])

    def test_six_quality_bar_rows_precede_generated_drafts(self) -> None:
        rows = self._load_rows()
        expected_families = [
            "straightforward",
            "multi-call",
            "no-tool",
            "failure-injection",
            "adversarial-ambiguous",
            "dependency-stop",
        ]

        self.assertEqual(expected_families, [row["scenarioFamily"] for row in rows[:6]])
        self.assertTrue(
            all(row["provenance"]["authoringMethod"] == "hand-authored" for row in rows[:6])
        )
        self.assertTrue(
            all(row["provenance"]["authoringMethod"] == "generated" for row in rows[6:])
        )
        self.assertTrue(all(row["provenance"]["reviewStatus"] == "pending" for row in rows))


if __name__ == "__main__":
    unittest.main()
