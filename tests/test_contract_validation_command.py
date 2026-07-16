"""Tests for the canonical Week 5 contract-validation command."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SCRIPT = REPO_ROOT / "scripts" / "validate_contracts.py"
VALIDATION_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "contract-validation.yml"


class ContractValidationCommandTests(unittest.TestCase):
    def test_command_validates_all_contract_artifact_classes(self) -> None:
        self.assertTrue(
            VALIDATION_SCRIPT.is_file(),
            f"missing validator: {VALIDATION_SCRIPT.relative_to(REPO_ROOT)}",
        )
        result = subprocess.run(
            [sys.executable, "-m", "scripts.validate_contracts"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "Validated 4 schemas, 5 valid fixtures, 19 invalid fixtures, "
            "6 tool contracts, and 2 capability manifests.\n",
            result.stdout,
        )

    def test_ci_runs_the_canonical_validation_command(self) -> None:
        self.assertTrue(
            VALIDATION_WORKFLOW.is_file(),
            f"missing workflow: {VALIDATION_WORKFLOW.relative_to(REPO_ROOT)}",
        )
        workflow = VALIDATION_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "uv run --locked python -m scripts.validate_contracts",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
