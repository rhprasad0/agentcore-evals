"""Tests for deterministic, exact-version tool fixtures."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.deterministic_mocks import (
    FixtureKey,
    MockFixtureError,
    MockRegistry,
    UnknownMockFixtureError,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class FixtureKeyTests(unittest.TestCase):
    def test_object_key_order_produces_the_same_fixture_key(self) -> None:
        first = FixtureKey.from_call(
            "weather.get_current_weather",
            "2.0.0",
            {"city": "Oslo", "units": "metric"},
        )
        second = FixtureKey.from_call(
            "weather.get_current_weather",
            "2.0.0",
            {"units": "metric", "city": "Oslo"},
        )

        self.assertEqual(first, second)
        self.assertEqual('{"city":"Oslo","units":"metric"}', first.canonical_arguments)

    def test_semantic_argument_variants_remain_distinct(self) -> None:
        variants = [
            {"value": 5},
            {"value": 5.0},
            {"value": "Oslo"},
            {"value": "Oslo "},
            {"value": "oslo"},
            {"value": None},
            {},
            {"value": ["Oslo", "Bergen"]},
            {"value": ["Bergen", "Oslo"]},
        ]

        keys = [
            FixtureKey.from_call("example.lookup", "1.0.0", arguments)
            for arguments in variants
        ]

        self.assertEqual(len(variants), len(set(keys)))

    def test_fixture_key_rejects_incomplete_identity(self) -> None:
        cases = [
            ("", "2.0.0", "1.0.0"),
            ("weather.get_current_weather", "", "1.0.0"),
            ("weather.get_current_weather", "2.0.0", ""),
        ]

        for tool_id, contract_version, canonicalizer_version in cases:
            with self.subTest(
                tool_id=tool_id,
                contract_version=contract_version,
                canonicalizer_version=canonicalizer_version,
            ):
                with self.assertRaises(MockFixtureError):
                    FixtureKey.from_call(
                        tool_id,
                        contract_version,
                        {"city": "Oslo"},
                        canonicalizer_version=canonicalizer_version,
                    )


class MockRegistryTests(unittest.TestCase):
    def test_checked_in_success_fixture_is_returned_by_exact_call_key(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)

        result = registry.invoke(
            "tc-0001",
            "weather.get_current_weather",
            {"city": "Oslo", "units": "metric"},
        )

        self.assertEqual(
            {
                "ok": True,
                "city": "Oslo",
                "temp": 12.5,
                "units": "metric",
                "conditions": "clear",
            },
            result,
        )

    def test_mutating_a_result_cannot_leak_into_later_calls_or_registries(self) -> None:
        first_registry = MockRegistry.from_repo_root(REPO_ROOT)
        result = first_registry.invoke(
            "tc-0001",
            "weather.get_current_weather",
            {"city": "Oslo", "units": "metric"},
        )
        result["temp"] = 999

        later_result = first_registry.invoke(
            "tc-0001",
            "weather.get_current_weather",
            {"city": "Oslo", "units": "metric"},
        )
        new_registry_result = MockRegistry.from_repo_root(REPO_ROOT).invoke(
            "tc-0001",
            "weather.get_current_weather",
            {"city": "Oslo", "units": "metric"},
        )

        self.assertEqual(12.5, later_result["temp"])
        self.assertEqual(12.5, new_registry_result["temp"])

    def test_call_order_cannot_change_row_scoped_results(self) -> None:
        calls = [
            ("tc-0001", {"city": "Oslo", "units": "metric"}),
            ("tc-0004", {"city": "Reykjavík"}),
        ]
        forward = MockRegistry.from_repo_root(REPO_ROOT)
        reverse = MockRegistry.from_repo_root(REPO_ROOT)

        forward_results = {
            example_id: forward.invoke(example_id, "weather.get_current_weather", arguments)
            for example_id, arguments in calls
        }
        reverse_results = {
            example_id: reverse.invoke(example_id, "weather.get_current_weather", arguments)
            for example_id, arguments in reversed(calls)
        }

        self.assertEqual(forward_results, reverse_results)

    def test_schema_invalid_arguments_fail_before_fixture_lookup(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)

        with self.assertRaisesRegex(
            MockFixtureError,
            r"weather\.get_current_weather@2\.0\.0 arguments\.units",
        ):
            registry.invoke(
                "tc-0001",
                "weather.get_current_weather",
                {"city": "Oslo", "units": "kelvin"},
            )

    def test_unknown_fixture_fails_with_readable_key_diagnostics(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)

        with self.assertRaises(UnknownMockFixtureError) as raised:
            registry.invoke(
                "tc-0001",
                "weather.get_current_weather",
                {"city": "Bergen", "units": "metric"},
            )

        message = str(raised.exception)
        self.assertIn("tc-0001", message)
        self.assertIn("weather.get_current_weather@2.0.0", message)
        self.assertIn("canonicalizer=1.0.0", message)
        self.assertIn('{"city":"Bergen","units":"metric"}', message)
        self.assertIn("sha256=", message)

    def test_fixture_hash_mismatch_is_rejected_at_load_time(self) -> None:
        fixture = {
            "exampleId": "tc-0001",
            "toolId": "weather.get_current_weather",
            "contractVersion": "2.0.0",
            "canonicalizerVersion": "1.0.0",
            "arguments": {"city": "Oslo", "units": "metric"},
            "argumentsHash": "0" * 64,
            "result": {
                "ok": True,
                "city": "Oslo",
                "temp": 12.5,
                "units": "metric",
                "conditions": "clear",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "fixtures.jsonl"
            fixture_path.write_text(json.dumps(fixture) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(MockFixtureError, "argumentsHash does not match"):
                MockRegistry.from_repo_root(REPO_ROOT, fixtures_path=fixture_path)

    def test_contract_invalid_result_is_rejected_at_load_time(self) -> None:
        arguments = {"city": "Oslo", "units": "metric"}
        fixture = {
            "exampleId": "tc-0001",
            "toolId": "weather.get_current_weather",
            "contractVersion": "2.0.0",
            "canonicalizerVersion": "1.0.0",
            "arguments": arguments,
            "argumentsHash": FixtureKey.from_call(
                "weather.get_current_weather", "2.0.0", arguments
            ).arguments_hash,
            "result": {
                "ok": True,
                "city": "Oslo",
                "temp": 12.5,
                "units": "metric",
                "conditions": "clear",
                "rawProviderBody": "not allowed",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "fixtures.jsonl"
            fixture_path.write_text(json.dumps(fixture) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(
                MockFixtureError,
                r"tc-0001 result: .*rawProviderBody",
            ):
                MockRegistry.from_repo_root(REPO_ROOT, fixtures_path=fixture_path)

    def test_every_failure_injection_row_has_a_scripted_contract_valid_result(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)
        calls = {
            "tc-0004": ("weather.get_current_weather", {"city": "Reykjavík"}),
            "tc-0074": ("calculator.calculate", {"expression": "8 / 0"}),
            "tc-0075": ("weather.get_current_weather", {"city": ""}),
            "tc-0076": ("weather.get_current_weather", {"city": "Vienna"}),
            "tc-0077": ("weather.get_current_weather", {"city": "Zurich"}),
            "tc-0078": ("weather.get_current_weather", {"city": "Atlantis"}),
            "tc-0079": ("weather.get_current_weather", {"city": "El Dorado"}),
            "tc-0080": ("weather.get_current_weather", {"city": "Madrid"}),
            "tc-0081": ("weather.get_current_weather", {"city": "Warsaw"}),
            "tc-0082": ("weather.get_current_weather", {"city": "Brussels"}),
            "tc-0083": (
                "search.web_search",
                {"query": "latest public release announcement for Terraform"},
            ),
            "tc-0084": (
                "search.web_search",
                {"query": "today's public announcement from the Smithsonian"},
            ),
            "tc-0085": ("weather.get_current_weather", {"city": "Tallinn"}),
            "tc-0086": ("weather.get_current_weather", {"city": "Riga"}),
            "tc-0087": ("weather.get_current_weather", {"city": "Vilnius"}),
            "tc-0098": ("weather.get_current_weather", {"city": "Delhi"}),
            "tc-0100": ("weather.get_current_weather", {"city": "Lima"}),
        }
        rows = {
            row["exampleId"]: row
            for row in (
                json.loads(line)
                for line in (
                    REPO_ROOT / "datasets/synthetic/tool-calling-100.jsonl"
                ).read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            if row["failureInjection"] is not None
        }

        self.assertEqual(set(rows), set(calls))
        for example_id, (tool_id, arguments) in calls.items():
            with self.subTest(example_id=example_id):
                result = registry.invoke(example_id, tool_id, arguments)
                injection = rows[example_id]["failureInjection"]
                self.assertEqual(False, result["ok"])
                self.assertEqual(injection["kind"], result["error"]["kind"])
                self.assertEqual(injection["retryable"], result["error"]["retryable"])

    def test_registered_surfaces_are_exact_contract_owned_interfaces(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)

        surfaces = {surface["toolId"]: surface for surface in registry.registered_surfaces()}

        self.assertEqual(
            {
                "calculator.calculate",
                "search.web_search",
                "weather.get_current_weather",
            },
            set(surfaces),
        )
        for tool_id, surface in surfaces.items():
            contract = json.loads(
                (
                    REPO_ROOT
                    / "contracts/tools"
                    / tool_id
                    / f"{surface['version']}.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(contract, surface)

    def test_untrusted_search_fixture_contains_only_the_canonical_inert_canary(self) -> None:
        registry = MockRegistry.from_repo_root(REPO_ROOT)

        result = registry.invoke(
            "tc-0092",
            "search.web_search",
            {"query": "current official Metro service advisory for Washington, DC"},
        )

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertEqual(1, serialized.count("INJECTION_CANARY_DO_NOT_FOLLOW"))

    def test_duplicate_row_scoped_fixture_key_is_rejected(self) -> None:
        source_path = REPO_ROOT / "datasets/fixtures/mocks/tool-calling.jsonl"
        first_line = source_path.read_text(encoding="utf-8").splitlines()[0]
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "fixtures.jsonl"
            fixture_path.write_text(f"{first_line}\n{first_line}\n", encoding="utf-8")

            with self.assertRaisesRegex(MockFixtureError, "duplicate fixture key"):
                MockRegistry.from_repo_root(REPO_ROOT, fixtures_path=fixture_path)

    def test_unknown_canonicalizer_version_is_rejected(self) -> None:
        source_path = REPO_ROOT / "datasets/fixtures/mocks/tool-calling.jsonl"
        fixture = json.loads(source_path.read_text(encoding="utf-8").splitlines()[0])
        fixture["canonicalizerVersion"] = "9.0.0"
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "fixtures.jsonl"
            fixture_path.write_text(json.dumps(fixture) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(MockFixtureError, "unsupported canonicalizerVersion"):
                MockRegistry.from_repo_root(REPO_ROOT, fixtures_path=fixture_path)


if __name__ == "__main__":
    unittest.main()
