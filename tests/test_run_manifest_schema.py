"""Schema tests for Week 7 run manifests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas/run-manifest.schema.json"
FIXTURES_PATH = REPO_ROOT / "tests/fixtures/run-manifests"


class RunManifestSchemaTests(unittest.TestCase):
    def test_schema_header(self) -> None:
        self.assertTrue(SCHEMA_PATH.is_file(), f"missing schema: {SCHEMA_PATH}")
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertEqual("urn:agentcore-evals:schema:run-manifest:1.0.0", schema["$id"])
        Draft202012Validator.check_schema(schema)

    def test_valid_fixture_is_accepted(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        paths = sorted((FIXTURES_PATH / "valid").glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual([], [error.message for error in validator.iter_errors(document)])

    def test_invalid_fixtures_are_rejected_for_named_defects(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        expected = {
            "missing-experiment-id.json": "required",
            "environment-inside-pins.json": "additionalProperties",
            "non-uuid4-run-id.json": "pattern",
            "unknown-sampling-status.json": "oneOf",
            "unknown-property.json": "additionalProperties",
        }
        paths = sorted((FIXTURES_PATH / "invalid").glob("*.json"))
        self.assertEqual(set(expected), {path.name for path in paths})
        for path in paths:
            with self.subTest(path=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                errors = list(validator.iter_errors(document))
                self.assertTrue(any(error.validator == expected[path.name] for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
