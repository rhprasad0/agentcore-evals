"""Tests for the contract-owned calculator wrapper."""

from __future__ import annotations

import unittest
from typing import Any

from src.tools.calculator import calculate_expression, calculator


class FakeCalculatorBackend:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


class CalculatorToolTests(unittest.TestCase):
    def test_model_visible_spec_is_narrow_and_contract_owned(self) -> None:
        spec = calculator.tool_spec
        normalized_description = " ".join(spec["description"].split()).lower()

        self.assertEqual("calculator", spec["name"])
        self.assertIn("required arithmetic expression supplied as a string", normalized_description)
        self.assertIn("finite result string", normalized_description)
        self.assertNotIn("supplied numeric values", normalized_description)
        self.assertIn("does not retrieve", normalized_description)
        self.assertEqual(
            {"expression"},
            set(spec["inputSchema"]["json"]["properties"]),
        )
        self.assertEqual(["expression"], spec["inputSchema"]["json"]["required"])

    def test_model_visible_expression_description_matches_string_input(self) -> None:
        expression_schema = calculator.tool_spec["inputSchema"]["json"]["properties"]["expression"]

        self.assertEqual(
            "Required arithmetic expression string containing only supported numeric arithmetic syntax.",
            expression_schema["description"],
        )

    def test_success_is_normalized(self) -> None:
        backend = FakeCalculatorBackend(
            {"status": "success", "content": [{"text": "Result: 21.6"}]}
        )

        result = calculate_expression("0.30 * 72", backend=backend)

        self.assertEqual({"ok": True, "value": "21.6"}, result)
        self.assertEqual([{"expression": "0.30 * 72", "mode": "evaluate"}], backend.calls)

    def test_invalid_or_out_of_scope_expressions_fail_before_backend(self) -> None:
        for expression in ("", "x + 1", "sin(1)", "[1, 2]", "'2' + '3'"):
            with self.subTest(expression=expression):
                backend = FakeCalculatorBackend(
                    {"status": "success", "content": [{"text": "Result: unused"}]}
                )

                result = calculate_expression(expression, backend=backend)

                self.assertEqual(False, result["ok"])
                self.assertEqual("bad_input", result["error"]["kind"])
                self.assertEqual(False, result["error"]["retryable"])
                self.assertEqual([], backend.calls)

    def test_backend_error_is_normalized(self) -> None:
        backend = FakeCalculatorBackend(
            {"status": "error", "content": [{"text": "Error: invalid syntax"}]}
        )

        result = calculate_expression("2 + 3", backend=backend)

        self.assertEqual(False, result["ok"])
        self.assertEqual("bad_input", result["error"]["kind"])
        self.assertEqual(False, result["error"]["retryable"])
        self.assertEqual([{"expression": "2 + 3", "mode": "evaluate"}], backend.calls)

    def test_non_finite_backend_result_is_rejected(self) -> None:
        backend = FakeCalculatorBackend(
            {"status": "success", "content": [{"text": "Result: nan-nanj"}]}
        )

        result = calculate_expression("1 / 0", backend=backend)

        self.assertEqual(False, result["ok"])
        self.assertEqual("bad_input", result["error"]["kind"])
        self.assertEqual(False, result["error"]["retryable"])

    def test_malformed_backend_result_is_normalized(self) -> None:
        backend = FakeCalculatorBackend("not-a-result-envelope")

        result = calculate_expression("2 + 3", backend=backend)

        self.assertEqual(False, result["ok"])
        self.assertEqual("bad_input", result["error"]["kind"])
        self.assertEqual(False, result["error"]["retryable"])


if __name__ == "__main__":
    unittest.main()
