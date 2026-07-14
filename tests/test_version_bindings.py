"""Tests for exact contract/manifest bindings shared by dataset and run consumers."""

from __future__ import annotations

import unittest

from src.version_bindings import (
    ExactVersionBindings,
    VersionBindingError,
    resolve_exact_version_bindings,
)


MANIFEST_REF = {"manifestId": "agents.weather", "version": "3.0.0"}
TOOL_REFS = [
    {"toolId": "weather.get_current_weather", "version": "2.0.0"},
    {"toolId": "calculator.calculate", "version": "2.0.0"},
    {"toolId": "search.web_search", "version": "2.0.0"},
]


class ExactVersionBindingsTests(unittest.TestCase):
    def test_identity_is_readable_and_independent_of_tool_order(self) -> None:
        forward = ExactVersionBindings.from_refs(MANIFEST_REF, TOOL_REFS)
        reversed_order = ExactVersionBindings.from_refs(MANIFEST_REF, reversed(TOOL_REFS))

        self.assertEqual(forward, reversed_order)
        self.assertEqual(
            "manifest=agents.weather@3.0.0;"
            "tools=calculator.calculate@2.0.0,search.web_search@2.0.0,"
            "weather.get_current_weather@2.0.0",
            forward.identity,
        )

    def test_version_changes_create_different_binding_identities(self) -> None:
        baseline = ExactVersionBindings.from_refs(MANIFEST_REF, TOOL_REFS)
        changed_manifest = ExactVersionBindings.from_refs(
            {"manifestId": "agents.weather", "version": "4.0.0"},
            TOOL_REFS,
        )
        changed_contract = ExactVersionBindings.from_refs(
            MANIFEST_REF,
            [
                {"toolId": "weather.get_current_weather", "version": "3.0.0"},
                *TOOL_REFS[1:],
            ],
        )

        self.assertEqual(
            3,
            len({baseline.identity, changed_manifest.identity, changed_contract.identity}),
        )

    def test_checked_in_exact_bindings_resolve(self) -> None:
        bindings = resolve_exact_version_bindings(MANIFEST_REF, TOOL_REFS)

        self.assertEqual(
            ExactVersionBindings.from_refs(MANIFEST_REF, TOOL_REFS),
            bindings,
        )

    def test_consumer_cannot_silently_retarget_one_contract_version(self) -> None:
        changed_refs = [
            {"toolId": "weather.get_current_weather", "version": "1.2.0"},
            *TOOL_REFS[1:],
        ]

        with self.assertRaisesRegex(
            VersionBindingError,
            r"weather\.get_current_weather expected 2\.0\.0, got 1\.2\.0",
        ):
            resolve_exact_version_bindings(MANIFEST_REF, changed_refs)


if __name__ == "__main__":
    unittest.main()
