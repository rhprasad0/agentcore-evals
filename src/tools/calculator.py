"""Contract-owned arithmetic wrapper around the Strands calculator tool."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from typing import Any

from strands import tool
from strands_tools.calculator import calculator as strands_calculator


CalculatorBackend = Callable[..., dict[str, Any]]
_NON_FINITE_RESULT = re.compile(r"(?<![a-z])(nan|inf|oo|zoo)(?![a-z])", re.IGNORECASE)
_ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.UAdd,
    ast.USub,
)


def _bad_input(message: str) -> dict[str, Any]:
    """Build the calculator's normalized non-retryable failure envelope."""
    return {
        "ok": False,
        "error": {
            "kind": "bad_input",
            "message": message,
            "retryable": False,
        },
    }


def _is_arithmetic_expression(expression: str) -> bool:
    """Return whether an expression contains only numeric arithmetic syntax."""
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, TypeError, ValueError):
        return False

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            return False
        if isinstance(node, ast.Constant) and (
            isinstance(node.value, bool) or not isinstance(node.value, (int, float))
        ):
            return False
    return True


def _result_text(result: Any) -> str | None:
    """Extract the single text item from a Strands calculator result."""
    if not isinstance(result, dict):
        return None
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
        return None
    text = content[0].get("text")
    return text if isinstance(text, str) and text else None


def calculate_expression(
    expression: str,
    *,
    backend: CalculatorBackend = strands_calculator,
) -> dict[str, Any]:
    """Evaluate numeric arithmetic and normalize the dependency's result envelope."""
    normalized_expression = expression.strip() if isinstance(expression, str) else ""
    if not normalized_expression or not _is_arithmetic_expression(normalized_expression):
        return _bad_input("expression must contain only numeric arithmetic")

    try:
        raw_result = backend(expression=normalized_expression, mode="evaluate")
    except Exception:
        return _bad_input("calculator could not evaluate the expression")

    if not isinstance(raw_result, dict):
        return _bad_input("calculator returned an invalid result")
    text = _result_text(raw_result)
    if raw_result.get("status") != "success" or text is None:
        return _bad_input("calculator could not evaluate the expression")

    prefix = "Result: "
    if not text.startswith(prefix):
        return _bad_input("calculator returned an invalid result")
    value = text.removeprefix(prefix).strip()
    if not value or _NON_FINITE_RESULT.search(value):
        return _bad_input("calculator result must be finite")
    return {"ok": True, "value": value}


@tool
def calculator(expression: str) -> dict[str, Any]:
    """Calculate arithmetic over supplied numeric values.

    Accepts numeric literals with arithmetic operators and parentheses. It does
    not retrieve current or external facts, solve symbolic equations, perform
    calculus, or mutate external state. Returns {ok: True, value} on success or
    {ok: False, error: {kind, message, retryable}} on failure.
    """
    return calculate_expression(expression)
