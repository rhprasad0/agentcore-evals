"""Tests for the Week 5 tool-contract schema."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_CONTRACT_SCHEMA_PATH = REPO_ROOT / "schemas" / "tool-contract.schema.json"
TOOL_CONTRACT_FIXTURES_PATH = REPO_ROOT / "tests" / "fixtures" / "tool-contracts"


class ToolContractSchemaTests(unittest.TestCase):
    def _load_fixture(self, category: str, name: str) -> Any:
        return json.loads(
            (TOOL_CONTRACT_FIXTURES_PATH / category / name).read_text(encoding="utf-8")
        )

    def test_schema_declares_draft_2020_12(self) -> None:
        self.assertTrue(
            TOOL_CONTRACT_SCHEMA_PATH.is_file(),
            f"missing schema: {TOOL_CONTRACT_SCHEMA_PATH.relative_to(REPO_ROOT)}",
        )
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema.get("$schema"),
            "https://json-schema.org/draft/2020-12/schema",
        )

    def test_schema_has_versioned_identity(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema.get("$id"),
            "urn:agentcore-evals:schema:tool-contract:1.0.0",
        )

    def test_schema_is_valid_draft_2020_12(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))

        Draft202012Validator.check_schema(schema)

    def test_contract_missing_tool_id_is_rejected(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("invalid", "missing-tool-id.json")

        errors = list(Draft202012Validator(schema).iter_errors(contract))

        self.assertTrue(
            any(error.validator == "required" and "toolId" in error.message for error in errors),
            f"expected missing toolId error, got: {[error.message for error in errors]}",
        )

    def test_all_valid_contract_fixtures_are_accepted(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture_paths = sorted((TOOL_CONTRACT_FIXTURES_PATH / "valid").glob("*.json"))

        self.assertTrue(fixture_paths, "expected at least one valid contract fixture")

        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                contract = json.loads(fixture_path.read_text(encoding="utf-8"))
                errors = list(Draft202012Validator(schema).iter_errors(contract))

                self.assertEqual([], [error.message for error in errors])

    def test_contract_with_unknown_property_is_rejected(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("invalid", "unknown-property.json")

        errors = list(Draft202012Validator(schema).iter_errors(contract))

        self.assertTrue(
            any(error.validator == "additionalProperties" for error in errors),
            f"expected additionalProperties error, got: {[error.message for error in errors]}",
        )

    def test_contract_fields_except_auth_scope_are_required(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        required_fields = (
            "toolId",
            "version",
            "description",
            "inputSchema",
            "outputSchema",
            "failureModes",
            "sideEffects",
            "resultTrust",
            "latencyBudgetMs",
        )

        for field in required_fields:
            with self.subTest(field=field):
                candidate = {key: value for key, value in contract.items() if key != field}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(error.validator == "required" and field in error.message for error in errors),
                    f"expected missing {field} error, got: {[error.message for error in errors]}",
                )

    def test_contract_with_malformed_version_is_rejected(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("invalid", "malformed-version.json")

        errors = list(Draft202012Validator(schema).iter_errors(contract))

        self.assertTrue(
            any(error.validator == "pattern" and list(error.path) == ["version"] for error in errors),
            f"expected version pattern error, got: {[error.message for error in errors]}",
        )

    def test_contract_with_non_ascii_semver_digit_is_rejected(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        contract["version"] = "1.2٢.0"

        errors = list(Draft202012Validator(schema).iter_errors(contract))

        self.assertTrue(
            any(error.validator == "pattern" and list(error.path) == ["version"] for error in errors),
            f"expected ASCII-only version pattern error, got: {[error.message for error in errors]}",
        )

    def test_contract_with_trailing_newline_in_version_is_rejected(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        contract["version"] = "1.2.3\n"

        errors = list(Draft202012Validator(schema).iter_errors(contract))

        self.assertTrue(
            any(list(error.path) == ["version"] for error in errors),
            f"expected trailing-newline version error, got: {[error.message for error in errors]}",
        )

    def test_contract_accepts_core_and_extended_semver(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")

        for version in ("0.0.0", "1.2.3-alpha.1+build.5"):
            with self.subTest(version=version):
                candidate = {**contract, "version": version}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertEqual([], [error.message for error in errors])

    def test_contract_rejects_semver_numeric_leading_zeroes(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")

        for version in ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01"):
            with self.subTest(version=version):
                candidate = {**contract, "version": version}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(
                        error.validator == "pattern" and list(error.path) == ["version"]
                        for error in errors
                    ),
                    f"expected leading-zero version error, got: {[error.message for error in errors]}",
                )

    def test_contract_with_unknown_failure_mode_is_rejected(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("invalid", "unknown-failure-mode.json")

        errors = list(Draft202012Validator(schema).iter_errors(contract))

        self.assertTrue(
            any(error.validator == "enum" and list(error.path) == ["failureModes", 0] for error in errors),
            f"expected failureModes enum error, got: {[error.message for error in errors]}",
        )

    def test_failure_modes_must_be_non_empty_and_unique(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        invalid_values = (
            ([], "minItems"),
            (["bad_input", "bad_input"], "uniqueItems"),
        )

        for value, expected_validator in invalid_values:
            with self.subTest(value=value):
                candidate = {**contract, "failureModes": value}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(
                        error.validator == expected_validator
                        and list(error.path) == ["failureModes"]
                        for error in errors
                    ),
                    f"expected {expected_validator} error, got: {[error.message for error in errors]}",
                )

    def test_contract_with_unknown_classification_is_rejected(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        invalid_values = {
            "sideEffects": "filesystem",
            "resultTrust": "trusted_external",
        }

        for field, value in invalid_values.items():
            with self.subTest(field=field):
                candidate = {**contract, field: value}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(error.validator == "enum" and list(error.path) == [field] for error in errors),
                    f"expected {field} enum error, got: {[error.message for error in errors]}",
                )

    def test_tool_id_must_be_namespaced(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        contract["toolId"] = "lookup"

        errors = list(Draft202012Validator(schema).iter_errors(contract))

        self.assertTrue(
            any(error.validator == "pattern" and list(error.path) == ["toolId"] for error in errors),
            f"expected toolId pattern error, got: {[error.message for error in errors]}",
        )

    def test_text_metadata_must_be_non_empty_when_present(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")

        for field in ("description", "authScope"):
            with self.subTest(field=field):
                candidate = {**contract, field: ""}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(error.validator == "minLength" and list(error.path) == [field] for error in errors),
                    f"expected {field} minLength error, got: {[error.message for error in errors]}",
                )

    def test_latency_budget_must_be_a_positive_integer(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")

        for value in (0, 1.5, "100"):
            with self.subTest(value=value):
                candidate = {**contract, "latencyBudgetMs": value}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(
                        error.validator in {"minimum", "type"}
                        and list(error.path) == ["latencyBudgetMs"]
                        for error in errors
                    ),
                    f"expected latencyBudgetMs error, got: {[error.message for error in errors]}",
                )

    def test_embedded_input_and_output_schemas_must_be_valid(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        invalid_embedded_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "not-a-json-schema-type",
        }

        for field in ("inputSchema", "outputSchema"):
            with self.subTest(field=field):
                candidate = {**contract, field: invalid_embedded_schema}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(
                        error.validator == "anyOf" and list(error.path) == [field, "type"]
                        for error in errors
                    ),
                    f"expected invalid {field} error, got: {[error.message for error in errors]}",
                )

    def test_embedded_schemas_must_declare_draft_2020_12(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        schema_without_dialect = {"type": "object"}

        for field in ("inputSchema", "outputSchema"):
            with self.subTest(field=field):
                candidate = {**contract, field: schema_without_dialect}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(error.path and error.path[0] == field for error in errors),
                    f"expected missing embedded dialect error, got: {[error.message for error in errors]}",
                )

    def test_embedded_schemas_reject_a_different_declared_dialect(self) -> None:
        schema = json.loads(TOOL_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = self._load_fixture("valid", "example-lookup.json")
        wrong_dialect_schema = {
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "type": "object",
        }

        for field in ("inputSchema", "outputSchema"):
            with self.subTest(field=field):
                candidate = {**contract, field: wrong_dialect_schema}
                errors = list(Draft202012Validator(schema).iter_errors(candidate))

                self.assertTrue(
                    any(
                        error.validator == "const"
                        and list(error.path) == [field, "$schema"]
                        for error in errors
                    ),
                    f"expected wrong embedded dialect error, got: {[error.message for error in errors]}",
                )

    def test_invalid_fixtures_each_contain_one_named_top_level_defect(self) -> None:
        valid_contract = self._load_fixture("valid", "example-lookup.json")
        expected_changed_field = {
            "missing-tool-id.json": "toolId",
            "malformed-version.json": "version",
            "unknown-failure-mode.json": "failureModes",
            "unknown-property.json": "owner",
        }
        invalid_fixture_names = {
            path.name for path in (TOOL_CONTRACT_FIXTURES_PATH / "invalid").glob("*.json")
        }

        self.assertEqual(set(expected_changed_field), invalid_fixture_names)

        for fixture_name, expected_field in expected_changed_field.items():
            with self.subTest(fixture=fixture_name):
                invalid_contract = self._load_fixture("invalid", fixture_name)
                changed_fields = {
                    key
                    for key in valid_contract.keys() | invalid_contract.keys()
                    if valid_contract.get(key) != invalid_contract.get(key)
                }

                self.assertEqual({expected_field}, changed_fields)


if __name__ == "__main__":
    unittest.main()
