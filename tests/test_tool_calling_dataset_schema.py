"""Tests for the Week 6 tool-calling dataset contracts."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.version_bindings import resolve_exact_version_bindings


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SCHEMA_PATH = REPO_ROOT / "schemas" / "tool-calling-example.schema.json"
DATASET_MANIFEST_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "tool-calling-dataset-manifest.schema.json"
)
DATASET_MANIFEST_PATH = REPO_ROOT / "datasets" / "synthetic" / "tool-calling-100.manifest.json"
EXAMPLE_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "tool-calling-examples" / "valid" / "straightforward-weather.json"
)


class ToolCallingExampleSchemaTests(unittest.TestCase):
    def _load_valid_fixture(self) -> Any:
        return json.loads(EXAMPLE_FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_schema_declares_draft_2020_12(self) -> None:
        self.assertTrue(
            EXAMPLE_SCHEMA_PATH.is_file(),
            f"missing schema: {EXAMPLE_SCHEMA_PATH.relative_to(REPO_ROOT)}",
        )
        schema = json.loads(EXAMPLE_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            schema.get("$schema"),
        )

    def test_schema_has_versioned_identity(self) -> None:
        schema = json.loads(EXAMPLE_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            "urn:agentcore-evals:schema:tool-calling-example:1.0.0",
            schema.get("$id"),
        )

    def test_schema_is_valid_draft_2020_12(self) -> None:
        schema = json.loads(EXAMPLE_SCHEMA_PATH.read_text(encoding="utf-8"))

        Draft202012Validator.check_schema(schema)

    def test_straightforward_weather_fixture_is_valid(self) -> None:
        self.assertTrue(
            EXAMPLE_FIXTURE_PATH.is_file(),
            f"missing fixture: {EXAMPLE_FIXTURE_PATH.relative_to(REPO_ROOT)}",
        )
        schema = json.loads(EXAMPLE_SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(EXAMPLE_FIXTURE_PATH.read_text(encoding="utf-8"))

        errors = list(Draft202012Validator(schema).iter_errors(fixture))

        self.assertEqual([], [error.message for error in errors])

    def test_argument_constraint_requires_explicit_tool_id(self) -> None:
        schema = json.loads(EXAMPLE_SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = self._load_valid_fixture()
        del fixture["expected"]["argConstraints"][0]["toolId"]

        errors = list(Draft202012Validator(schema).iter_errors(fixture))

        self.assertTrue(
            any(
                error.validator == "required"
                and "toolId" in error.message
                and list(error.path) == ["expected", "argConstraints", 0]
                for error in errors
            ),
            f"expected missing constraint toolId error, got: {[error.message for error in errors]}",
        )

    def test_argument_constraint_requires_exactly_one_supported_predicate(self) -> None:
        schema = json.loads(EXAMPLE_SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = self._load_valid_fixture()
        constraint = fixture["expected"]["argConstraints"][0]

        missing_predicate = {key: value for key, value in constraint.items() if key != "equals"}
        multiple_predicates = {**constraint, "inSet": ["Oslo", "Bergen"]}

        for candidate in (missing_predicate, multiple_predicates):
            with self.subTest(candidate=candidate):
                fixture["expected"]["argConstraints"][0] = candidate
                errors = list(Draft202012Validator(schema).iter_errors(fixture))

                self.assertTrue(
                    any(
                        error.validator == "oneOf"
                        and list(error.path) == ["expected", "argConstraints", 0]
                        for error in errors
                    ),
                    f"expected oneOf predicate error, got: {[error.message for error in errors]}",
                )

    def test_row_requires_core_fields_and_rejects_unknown_properties(self) -> None:
        schema = json.loads(EXAMPLE_SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = self._load_valid_fixture()

        for field in (
            "exampleId",
            "prompt",
            "scenarioFamily",
            "expected",
            "failureInjection",
            "tags",
            "provenance",
        ):
            with self.subTest(field=field):
                candidate = {key: value for key, value in fixture.items() if key != field}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))
                self.assertTrue(
                    any(error.validator == "required" and field in error.message for error in errors),
                    f"expected missing {field} error, got: {[error.message for error in errors]}",
                )

        errors = list(
            Draft202012Validator(schema).iter_errors({**fixture, "reviewerNotes": "extra"})
        )
        self.assertTrue(
            any(error.validator == "additionalProperties" and list(error.path) == [] for error in errors),
            f"expected unknown-property error, got: {[error.message for error in errors]}",
        )


class ToolCallingDatasetManifestSchemaTests(unittest.TestCase):
    def test_schema_declares_draft_2020_12(self) -> None:
        self.assertTrue(
            DATASET_MANIFEST_SCHEMA_PATH.is_file(),
            f"missing schema: {DATASET_MANIFEST_SCHEMA_PATH.relative_to(REPO_ROOT)}",
        )
        schema = json.loads(DATASET_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            schema.get("$schema"),
        )

    def test_schema_has_versioned_identity(self) -> None:
        schema = json.loads(DATASET_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            "urn:agentcore-evals:schema:tool-calling-dataset-manifest:1.0.0",
            schema.get("$id"),
        )

    def test_checked_in_dataset_manifest_is_valid_and_resolves_exact_bindings(self) -> None:
        self.assertTrue(
            DATASET_MANIFEST_PATH.is_file(),
            f"missing manifest: {DATASET_MANIFEST_PATH.relative_to(REPO_ROOT)}",
        )
        schema = json.loads(DATASET_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))

        errors = list(Draft202012Validator(schema).iter_errors(manifest))
        self.assertEqual([], [error.message for error in errors])

        bindings = resolve_exact_version_bindings(
            manifest["agentManifest"],
            manifest["toolContracts"],
        )
        self.assertEqual(
            "manifest=agents.weather@3.0.0;"
            "tools=calculator.calculate@2.0.0,search.web_search@2.0.0,"
            "weather.get_current_weather@2.0.0",
            bindings.identity,
        )

    def test_manifest_requires_identity_bindings_and_distribution(self) -> None:
        schema = json.loads(DATASET_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))

        for field in (
            "datasetId",
            "version",
            "schemaVersion",
            "taxonomyVersion",
            "agentManifest",
            "toolContracts",
            "corpusPath",
            "expectedRowCount",
            "distribution",
            "canonicalCanary",
            "generationPromptPath",
            "editorialChecklistPath",
            "reviewStatus",
        ):
            with self.subTest(field=field):
                candidate = {key: value for key, value in manifest.items() if key != field}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))
                self.assertTrue(
                    any(error.validator == "required" and field in error.message for error in errors),
                    f"expected missing {field} error, got: {[error.message for error in errors]}",
                )


if __name__ == "__main__":
    unittest.main()
