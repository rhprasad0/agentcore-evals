"""Tests for the generated Week 6 tool-calling corpus."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts import generate_tool_calling_corpus


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
        rows = generate_tool_calling_corpus.build_rows()
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

    def test_write_rows_refuses_to_replace_an_existing_corpus_without_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "tool-calling-100.jsonl"
            output_path.write_text("preserve me\n", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "--overwrite-existing"):
                generate_tool_calling_corpus.write_rows([], output_path, overwrite=False)

            self.assertEqual("preserve me\n", output_path.read_text(encoding="utf-8"))

    def test_write_rows_replaces_an_existing_corpus_with_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "tool-calling-100.jsonl"
            output_path.write_text("old data\n", encoding="utf-8")

            generate_tool_calling_corpus.write_rows(
                [{"exampleId": "tc-0001", "prompt": "replacement"}],
                output_path,
                overwrite=True,
            )

            self.assertEqual(
                '{"exampleId": "tc-0001", "prompt": "replacement"}\n',
                output_path.read_text(encoding="utf-8"),
            )

    def test_main_refuses_an_existing_output_without_overwrite_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "tool-calling-100.jsonl"
            output_path.write_text("preserve me\n", encoding="utf-8")
            stderr = StringIO()

            with redirect_stderr(stderr):
                exit_code = generate_tool_calling_corpus.main([], output_path=output_path)

            self.assertEqual(2, exit_code)
            self.assertIn("--overwrite-existing", stderr.getvalue())
            self.assertEqual("preserve me\n", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
