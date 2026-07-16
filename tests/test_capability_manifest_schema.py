"""Tests for the Week 5 capability-manifest schema."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_MANIFEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "capability-manifest.schema.json"
CAPABILITY_MANIFEST_FIXTURES_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "capability-manifests"
)


class CapabilityManifestSchemaTests(unittest.TestCase):
    def _load_fixture(self, category: str, name: str) -> Any:
        return json.loads(
            (CAPABILITY_MANIFEST_FIXTURES_PATH / category / name).read_text(encoding="utf-8")
        )

    def test_schema_declares_draft_2020_12(self) -> None:
        self.assertTrue(
            CAPABILITY_MANIFEST_SCHEMA_PATH.is_file(),
            f"missing schema: {CAPABILITY_MANIFEST_SCHEMA_PATH.relative_to(REPO_ROOT)}",
        )
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema.get("$schema"),
            "https://json-schema.org/draft/2020-12/schema",
        )

    def test_schema_has_versioned_identity(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema.get("$id"),
            "urn:agentcore-evals:schema:capability-manifest:1.0.0",
        )

    def test_schema_is_valid_draft_2020_12(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))

        Draft202012Validator.check_schema(schema)

    def test_all_valid_manifest_fixtures_are_accepted(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture_paths = sorted((CAPABILITY_MANIFEST_FIXTURES_PATH / "valid").glob("*.json"))

        self.assertTrue(fixture_paths, "expected at least one valid capability-manifest fixture")

        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                manifest = json.loads(fixture_path.read_text(encoding="utf-8"))
                errors = list(Draft202012Validator(schema).iter_errors(manifest))

                self.assertEqual([], [error.message for error in errors])

    def test_weather_portfolio_pins_current_tool_contracts(self) -> None:
        manifest = self._load_fixture("valid", "weather-portfolio.json")

        self.assertEqual("3.0.0", manifest["version"])
        self.assertEqual("2.0.0", manifest["toolGrants"]["weather.get_current_weather"])
        self.assertEqual("2.0.0", manifest["toolGrants"]["calculator.calculate"])
        self.assertEqual("2.0.0", manifest["toolGrants"]["search.web_search"])

    def test_weather_only_manifest_grants_exactly_one_tool(self) -> None:
        manifest = self._load_fixture("valid", "weather-only.json")

        self.assertEqual("agents.weather", manifest["manifestId"])
        self.assertEqual("4.0.0", manifest["version"])
        self.assertEqual(
            {"weather.get_current_weather": "2.0.0"},
            manifest["toolGrants"],
        )
        self.assertEqual("read_external", manifest["sideEffectCeiling"])

    def test_all_invalid_manifest_fixtures_are_rejected(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture_paths = sorted((CAPABILITY_MANIFEST_FIXTURES_PATH / "invalid").glob("*.json"))

        self.assertTrue(fixture_paths, "expected at least one invalid capability-manifest fixture")

        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                manifest = json.loads(fixture_path.read_text(encoding="utf-8"))
                errors = list(Draft202012Validator(schema).iter_errors(manifest))

                self.assertTrue(errors, f"expected {fixture_path.name} to fail validation")

    def test_manifest_fields_are_required(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = self._load_fixture("valid", "weather-portfolio.json")

        for field in (
            "manifestId",
            "version",
            "toolGrants",
            "sideEffectCeiling",
            "outOfScope",
        ):
            with self.subTest(field=field):
                candidate = {key: value for key, value in manifest.items() if key != field}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(error.validator == "required" and field in error.message for error in errors),
                    f"expected missing {field} error, got: {[error.message for error in errors]}",
                )

    def test_manifest_with_unknown_property_is_rejected(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = self._load_fixture("invalid", "unknown-property.json")

        errors = list(Draft202012Validator(schema).iter_errors(manifest))

        self.assertTrue(
            any(error.validator == "additionalProperties" and list(error.path) == [] for error in errors),
            f"expected additionalProperties error, got: {[error.message for error in errors]}",
        )

    def test_manifest_and_grant_versions_require_semver(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        expected_paths = {
            "malformed-version.json": ["version"],
            "malformed-tool-version.json": ["toolGrants", "weather.get_current_weather"],
        }

        for fixture_name, expected_path in expected_paths.items():
            with self.subTest(fixture=fixture_name):
                manifest = self._load_fixture("invalid", fixture_name)
                errors = list(Draft202012Validator(schema).iter_errors(manifest))

                self.assertTrue(
                    any(
                        error.validator == "pattern" and list(error.path) == expected_path
                        for error in errors
                    ),
                    f"expected SemVer pattern error, got: {[error.message for error in errors]}",
                )

    def test_semver_rejects_unicode_digits_newlines_and_leading_zeroes(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = self._load_fixture("valid", "weather-portfolio.json")

        for version in ("1.2٢.0", "1.2.3\n", "01.2.3", "1.2.3-01"):
            with self.subTest(version=version):
                candidate = {**manifest, "version": version}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(list(error.path) == ["version"] for error in errors),
                    f"expected invalid SemVer error, got: {[error.message for error in errors]}",
                )

    def test_manifest_and_tool_ids_must_be_namespaced(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = self._load_fixture("valid", "weather-portfolio.json")
        candidates = (
            ({**manifest, "manifestId": "weather"}, ["manifestId"]),
            (self._load_fixture("invalid", "invalid-tool-id.json"), ["toolGrants"]),
        )

        for candidate, expected_path in candidates:
            with self.subTest(path=expected_path):
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(
                        error.validator == "pattern" and list(error.path) == expected_path
                        for error in errors
                    ),
                    f"expected namespaced ID error, got: {[error.message for error in errors]}",
                )

    def test_side_effect_ceiling_is_closed(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = self._load_fixture("invalid", "unknown-side-effect-ceiling.json")

        errors = list(Draft202012Validator(schema).iter_errors(manifest))

        self.assertTrue(
            any(
                error.validator == "enum" and list(error.path) == ["sideEffectCeiling"]
                for error in errors
            ),
            f"expected sideEffectCeiling enum error, got: {[error.message for error in errors]}",
        )

    def test_exclusion_ids_and_descriptions_are_constrained(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = self._load_fixture("valid", "weather-portfolio.json")
        invalid_id = {
            **manifest,
            "outOfScope": {"External write actions": "Does not mutate external resources."},
        }
        empty_description = self._load_fixture("invalid", "empty-exclusion-description.json")
        candidates = (
            (invalid_id, "pattern", ["outOfScope"]),
            (empty_description, "minLength", ["outOfScope", "external_write_actions"]),
        )

        for candidate, expected_validator, expected_path in candidates:
            with self.subTest(validator=expected_validator):
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(
                        error.validator == expected_validator
                        and list(error.path) == expected_path
                        for error in errors
                    ),
                    f"expected exclusion error, got: {[error.message for error in errors]}",
                )

    def test_empty_grants_and_exclusions_are_explicitly_valid(self) -> None:
        schema = json.loads(CAPABILITY_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = self._load_fixture("valid", "weather-portfolio.json")
        candidate = {**manifest, "toolGrants": {}, "outOfScope": {}}

        errors = list(Draft202012Validator(schema).iter_errors(candidate))

        self.assertEqual([], [error.message for error in errors])

    def test_invalid_fixtures_each_contain_one_named_top_level_defect(self) -> None:
        valid_manifest = self._load_fixture("valid", "weather-portfolio.json")
        expected_changed_field = {
            "empty-exclusion-description.json": "outOfScope",
            "invalid-tool-id.json": "toolGrants",
            "malformed-tool-version.json": "toolGrants",
            "malformed-version.json": "version",
            "missing-manifest-id.json": "manifestId",
            "unknown-property.json": "owner",
            "unknown-side-effect-ceiling.json": "sideEffectCeiling",
        }
        invalid_fixture_names = {
            path.name for path in (CAPABILITY_MANIFEST_FIXTURES_PATH / "invalid").glob("*.json")
        }

        self.assertEqual(set(expected_changed_field), invalid_fixture_names)

        for fixture_name, expected_field in expected_changed_field.items():
            with self.subTest(fixture=fixture_name):
                invalid_manifest = self._load_fixture("invalid", fixture_name)
                changed_fields = {
                    key
                    for key in valid_manifest.keys() | invalid_manifest.keys()
                    if valid_manifest.get(key) != invalid_manifest.get(key)
                }

                self.assertEqual({expected_field}, changed_fields)


if __name__ == "__main__":
    unittest.main()
