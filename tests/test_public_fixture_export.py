"""Tests for deterministic public-safe Week 8 fixture export."""

from __future__ import annotations

import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from evals.fixtures.manifest import (
    ExactFixtureSafetyError,
    validate_exact_fixture_safety,
)
from evals.fixtures.public_export import export_fixture_set
from scripts.export_week_08_fixtures import parse_args
from tests.fixture_export_support import build_synthetic_private_run


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_TRACE = REPO_ROOT / "tests/fixtures/telemetry/canonical/weather-success.json"
PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"
class PublicFixtureExportTests(unittest.TestCase):
    def test_safety_scanner_does_not_treat_hex_span_ids_as_account_ids(self) -> None:
        validate_exact_fixture_safety(
            '{"spanId":"a534368870991ffa"}',
            label="synthetic span",
        )

    def test_export_cli_accepts_staging_output(self) -> None:
        args = parse_args(
            ["synthetic-run", "--output-directory", "staging-fixtures"]
        )

        self.assertEqual(Path("synthetic-run"), args.run_directory)
        self.assertEqual(Path("staging-fixtures"), args.output_directory)

    def test_export_rejects_automated_safety_findings(self) -> None:
        forbidden_values = {
            "home path": "/home/example/.aws/credentials",
            "AWS ARN": "arn:aws:iam::000000000000:role/example",
            "email": "person@example.com",
            "private IP": "192.168.1.25",
        }
        for label, forbidden in forbidden_values.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                private_run = build_synthetic_private_run(root / "private-run")
                trace_path = private_run / "cases/tc-0001/canonical-trace.json"
                trace = json.loads(trace_path.read_text(encoding="utf-8"))
                trace["response"] = f"Synthetic unsafe value: {forbidden}"
                trace_path.write_text(
                    json.dumps(trace, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )

                with self.assertRaises(ExactFixtureSafetyError):
                    export_fixture_set(
                        private_run,
                        PROJECTION_PATH,
                        root / "public",
                        artifact_prefix="evals/fixtures/weather-only-62",
                        repo_root=REPO_ROOT,
                    )

    def test_exporter_preserves_every_source_artifact_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_run = build_synthetic_private_run(root / "private-run")
            output_root = root / "public"
            manifest = export_fixture_set(
                private_run,
                PROJECTION_PATH,
                output_root,
                artifact_prefix="evals/fixtures/weather-only-62",
                repo_root=REPO_ROOT,
            )

            for entry in manifest["fixtures"]:
                example_id = entry["exampleId"]
                source_name = (
                    "canonical-trace.json"
                    if entry["status"] == "canonical-trace"
                    else "instrument-error.json"
                )
                source = private_run / "cases" / example_id / source_name
                relative = entry["path"].removeprefix(
                    "evals/fixtures/weather-only-62/"
                )
                exported = output_root / relative
                self.assertEqual(source.read_bytes(), exported.read_bytes())

    def test_exporter_builds_a_deterministic_62_case_public_fixture_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_run = build_synthetic_private_run(root / "private-run")
            source_trace = json.loads(
                (private_run / "cases/tc-0001/canonical-trace.json").read_text(
                    encoding="utf-8"
                )
            )
            selection_reasoning = next(
                span["selectionReasoning"]
                for span in source_trace["spans"]
                if span["selectionReasoning"] is not None
            )
            first_root = root / "first"
            second_root = root / "second"
            first = export_fixture_set(
                private_run,
                PROJECTION_PATH,
                first_root,
                artifact_prefix="evals/fixtures/weather-only-62",
                repo_root=REPO_ROOT,
            )
            second = export_fixture_set(
                private_run,
                PROJECTION_PATH,
                second_root,
                artifact_prefix="evals/fixtures/weather-only-62",
                repo_root=REPO_ROOT,
            )

            self.assertEqual(first, second)
            self.assertEqual(
                {"expected": 62, "canonicalTrace": 60, "instrumentError": 2},
                first["counts"],
            )
            self.assertEqual(62, len(first["expectedCaseIds"]))
            self.assertEqual(62, len(first["fixtures"]))
            first_files = {
                path.relative_to(first_root).as_posix(): path.read_bytes()
                for path in first_root.rglob("*.json")
            }
            second_files = {
                path.relative_to(second_root).as_posix(): path.read_bytes()
                for path in second_root.rglob("*.json")
            }
            self.assertEqual(first_files, second_files)
            self.assertEqual(63, len(first_files))
            exported_text = b"\n".join(first_files.values()).decode("utf-8")
            self.assertIn(source_trace["prompt"], exported_text)
            self.assertIn(source_trace["response"], exported_text)
            self.assertIn(selection_reasoning, exported_text)
            for fixture in first["fixtures"]:
                relative = fixture["path"].removeprefix(
                    "evals/fixtures/weather-only-62/"
                )
                self.assertEqual(
                    fixture["sha256"],
                    sha256((first_root / relative).read_bytes()).hexdigest(),
                )


if __name__ == "__main__":
    unittest.main()
