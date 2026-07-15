"""Tests for shared Week 6 tool-calling dataset validation."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.tool_calling_dataset import (
    DatasetPaths,
    dataset_revision,
    load_dataset,
    serialize_rows,
    validate_dataset,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ToolCallingDatasetTests(unittest.TestCase):
    def test_checked_in_dataset_has_no_validation_issues(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)

        issues = validate_dataset(load_dataset(paths), paths)

        self.assertEqual([], issues)

    def test_validation_rejects_a_duplicate_prompt(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)
        snapshot = load_dataset(paths)
        snapshot.rows[1]["prompt"] = snapshot.rows[0]["prompt"]

        issues = validate_dataset(snapshot, paths)

        self.assertTrue(
            any(issue.path == "tc-0002.prompt" for issue in issues),
            issues,
        )

    def test_validation_rejects_more_minimum_than_maximum_calls(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)
        snapshot = load_dataset(paths)
        snapshot.rows[0]["expected"]["minCalls"] = 2
        snapshot.rows[0]["expected"]["maxCalls"] = 1

        issues = validate_dataset(snapshot, paths)

        self.assertTrue(
            any(issue.path == "tc-0001.expected.minCalls" for issue in issues),
            issues,
        )

    def test_validation_rejects_tool_references_not_granted_by_the_manifest(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)
        cases = [
            (
                "expected tool",
                lambda row: row["expected"]["toolIds"].__setitem__(0, "time.now"),
                "tc-0001.expected.toolIds[0]",
            ),
            (
                "forbidden tool",
                lambda row: row["expected"]["mustNotCall"].__setitem__(0, "time.now"),
                "tc-0001.expected.mustNotCall[0]",
            ),
            (
                "constraint tool",
                lambda row: row["expected"]["argConstraints"][0].__setitem__("toolId", "time.now"),
                "tc-0001.expected.argConstraints[0].toolId",
            ),
            (
                "failure tool",
                lambda row: row["failureInjection"].__setitem__("toolId", "time.now"),
                "tc-0004.failureInjection.toolId",
            ),
        ]

        for name, mutate, expected_path in cases:
            with self.subTest(name=name):
                snapshot = load_dataset(paths)
                mutate(snapshot.rows[3] if name == "failure tool" else snapshot.rows[0])

                issues = validate_dataset(snapshot, paths)

                self.assertTrue(any(issue.path == expected_path for issue in issues), issues)

    def test_validation_rejects_a_constraint_path_missing_from_the_exact_contract(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)
        snapshot = load_dataset(paths)
        snapshot.rows[0]["expected"]["argConstraints"][0]["path"] = "$.unknown"

        issues = validate_dataset(snapshot, paths)

        self.assertTrue(
            any(issue.path == "tc-0001.expected.argConstraints[0].path" for issue in issues),
            issues,
        )

    def test_validation_rejects_a_corpus_with_the_wrong_row_count(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)
        snapshot = load_dataset(paths)
        snapshot.rows.pop()

        issues = validate_dataset(snapshot, paths)

        self.assertTrue(any(issue.path == "corpus.rowCount" for issue in issues), issues)

    def test_validation_rejects_a_non_sequential_example_id(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)
        snapshot = load_dataset(paths)
        snapshot.rows[1]["exampleId"] = "tc-0101"

        issues = validate_dataset(snapshot, paths)

        self.assertTrue(any(issue.path == "corpus.exampleIds[1]" for issue in issues), issues)

    def test_validation_rejects_a_distribution_that_does_not_match_the_manifest(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)
        snapshot = load_dataset(paths)
        snapshot.rows[0]["scenarioFamily"] = "no-tool"

        issues = validate_dataset(snapshot, paths)

        self.assertTrue(any(issue.path == "corpus.distribution" for issue in issues), issues)

    def test_serialize_rows_uses_sorted_utf8_jsonl(self) -> None:
        serialized = serialize_rows([{"z": 1, "a": "café"}])

        self.assertEqual('{"a": "café", "z": 1}\n', serialized)

    def test_dataset_revision_changes_when_a_row_changes(self) -> None:
        paths = DatasetPaths.from_repo_root(REPO_ROOT)
        snapshot = load_dataset(paths)
        original_revision = dataset_revision(snapshot)
        snapshot.rows[0]["prompt"] = "A changed prompt"

        self.assertNotEqual(original_revision, dataset_revision(snapshot))


if __name__ == "__main__":
    unittest.main()
