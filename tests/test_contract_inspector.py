"""Tests for the generated contract-inspector artifact."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "spikes" / "001-contract-inspector" / "build.py"
OUTPUT_PATH = BUILD_SCRIPT.with_name("contract-inspector.html")


class ContractInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(["python3", str(BUILD_SCRIPT)], cwd=REPO_ROOT, check=True)
        cls.html = OUTPUT_PATH.read_text(encoding="utf-8")

    def test_contract_vocabulary_uses_field_tooltips(self) -> None:
        self.assertNotIn('data-tab="glossary"', self.html)
        self.assertNotIn("Contract field guide", self.html)
        self.assertIn('class="field-help"', self.html)
        self.assertIn('role="tooltip"', self.html)
        self.assertIn('aria-describedby="', self.html)
        self.assertIn(".field-help:hover .field-tooltip", self.html)
        self.assertIn(".field-help:focus-visible .field-tooltip", self.html)

    def test_schema_property_descriptions_remain_inline(self) -> None:
        self.assertIn('class="field-description"', self.html)
        self.assertIn("Public-information search query", self.html)

    def test_removed_field_guide_hash_falls_back_to_overview(self) -> None:
        self.assertIn(
            'activeTab = validTabs.includes(match[3]) ? match[3] : "overview";',
            self.html,
        )


if __name__ == "__main__":
    unittest.main()
