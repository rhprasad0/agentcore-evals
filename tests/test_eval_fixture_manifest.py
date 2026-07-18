"""Tests for provenance-linked public evaluation fixture manifests."""

from __future__ import annotations

import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from jsonschema import Draft202012Validator

from evals.fixtures.manifest import (
    ExactFixtureSafetyError,
    FixtureManifestError,
    validate_fixture_manifest,
)
from evals.fixtures.public_export import export_fixture_set
from tests.fixture_export_support import build_synthetic_private_run


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas/eval-fixture-manifest.schema.json"
VALID_FIXTURE = (
    REPO_ROOT / "tests/fixtures/eval-fixture-manifests/valid/weather-only-minimal.json"
)
INVALID_FIXTURES = (
    REPO_ROOT / "tests/fixtures/eval-fixture-manifests/invalid"
)
PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"
COMMITTED_FIXTURE_ROOT = REPO_ROOT / "evals/fixtures/weather-only-62"
EXPECTED_EXPERIMENT_ID = (
    "sha256:44a9f913a720759748d57647f002b0e924d39b38b65a2fdfbe713774bfc2cca5"
)


class EvalFixtureManifestTests(unittest.TestCase):
    def _export(self, directory: Path) -> tuple[Path, dict]:
        private_run = build_synthetic_private_run(directory / "private-run")
        artifact_root = directory / "weather-only-62"
        manifest = export_fixture_set(
            private_run,
            PROJECTION_PATH,
            artifact_root,
            artifact_prefix="evals/fixtures/weather-only-62",
            repo_root=REPO_ROOT,
        )
        return artifact_root, manifest

    def _validate(
        self,
        artifact_root: Path,
        expected_experiment_id: str,
    ) -> dict:
        return validate_fixture_manifest(
            artifact_root / "manifest.json",
            projection_path=PROJECTION_PATH,
            artifact_root=artifact_root,
            artifact_prefix="evals/fixtures/weather-only-62",
            expected_experiment_id=expected_experiment_id,
            repo_root=REPO_ROOT,
        )

    @staticmethod
    def _write_manifest(artifact_root: Path, manifest: dict) -> None:
        (artifact_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _rewrite_fixture_and_hash(
        artifact_root: Path,
        manifest: dict,
        fixture_index: int,
        document: dict,
    ) -> None:
        entry = manifest["fixtures"][fixture_index]
        relative = entry["path"].removeprefix(
            "evals/fixtures/weather-only-62/"
        )
        payload = (
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        (artifact_root / relative).write_bytes(payload)
        entry["sha256"] = sha256(payload).hexdigest()

    def test_schema_pins_dialect_and_versioned_identity(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            schema["$schema"],
        )
        self.assertEqual(
            "urn:agentcore-evals:schema:eval-fixture-manifest:1.0.0",
            schema["$id"],
        )

    def test_schema_is_valid_and_accepts_the_minimal_manifest(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(VALID_FIXTURE.read_text(encoding="utf-8"))

        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(manifest),
            key=lambda error: list(error.path),
        )
        self.assertEqual([], [error.message for error in errors])
        self.assertEqual(
            "exact-source-artifacts",
            manifest["publicSafety"]["publicationMode"],
        )
        self.assertEqual(
            [
                "schema",
                "semantics",
                "provenance",
                "secrets",
                "privatePaths",
                "awsIdentifiers",
                "contactIdentifiers",
            ],
            manifest["publicSafety"]["automatedChecks"],
        )
        self.assertEqual(
            "12345678-1234-4abc-8def-1234567890ab",
            manifest["sourceRun"]["runId"],
        )

    def test_schema_rejects_every_checked_invalid_manifest(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        fixtures = sorted(INVALID_FIXTURES.glob("*.json"))

        self.assertTrue(fixtures)
        for path in fixtures:
            with self.subTest(path=path.name):
                manifest = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(list(validator.iter_errors(manifest)))

    def test_committed_fixture_set_passes_independent_validation(self) -> None:
        manifest = self._validate(
            COMMITTED_FIXTURE_ROOT,
            EXPECTED_EXPERIMENT_ID,
        )

        self.assertEqual(
            {"expected": 62, "canonicalTrace": 60, "instrumentError": 2},
            manifest["counts"],
        )

    def test_validator_accepts_the_exported_fixture_set_without_private_run_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact_root, exported = self._export(Path(directory))
            validated = self._validate(artifact_root, exported["experimentId"])

        self.assertEqual(exported, validated)

    def test_validator_rejects_cross_experiment_and_manifest_drift(self) -> None:
        mutations = {
            "cross-experiment": lambda manifest: manifest.__setitem__(
                "experimentId", "sha256:" + "f" * 64
            ),
            "count drift": lambda manifest: manifest["counts"].__setitem__(
                "canonicalTrace", 59
            ),
            "case-set drift": lambda manifest: manifest["expectedCaseIds"].__setitem__(
                0, "tc-9999"
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                artifact_root, manifest = self._export(Path(directory))
                expected_experiment_id = manifest["experimentId"]
                mutate(manifest)
                self._write_manifest(artifact_root, manifest)

                with self.assertRaises(FixtureManifestError):
                    self._validate(artifact_root, expected_experiment_id)

    def test_validator_rejects_stale_missing_and_extra_fixture_files(self) -> None:
        for label in ("stale hash", "missing file", "extra file"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                artifact_root, manifest = self._export(Path(directory))
                first_relative = manifest["fixtures"][0]["path"].removeprefix(
                    "evals/fixtures/weather-only-62/"
                )
                first_path = artifact_root / first_relative
                if label == "stale hash":
                    first_path.write_text("{}\n", encoding="utf-8")
                elif label == "missing file":
                    first_path.unlink()
                else:
                    (artifact_root / "traces/extra.json").write_text(
                        "{}\n", encoding="utf-8"
                    )

                with self.assertRaises(FixtureManifestError):
                    self._validate(artifact_root, manifest["experimentId"])

    def test_validator_rejects_path_traversal_before_reading_the_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact_root, manifest = self._export(root)
            source_path = artifact_root / "traces/tc-0001.json"
            outside_path = artifact_root.parent / "outside.json"
            outside_path.write_bytes(source_path.read_bytes())
            manifest["fixtures"][0]["path"] = (
                "evals/fixtures/weather-only-62/../outside.json"
            )
            self._write_manifest(artifact_root, manifest)

            with self.assertRaisesRegex(FixtureManifestError, "escapes artifact root"):
                self._validate(artifact_root, manifest["experimentId"])

    def test_validator_rejects_prompt_and_source_run_drift_with_matching_hashes(self) -> None:
        mutations = {
            "prompt": (
                lambda trace: trace.__setitem__(
                    "prompt", "Synthetic but not the selected dataset prompt"
                ),
                "prompt does not match dataset",
            ),
            "session": (
                lambda trace: trace.__setitem__(
                    "sessionId", "87654321-4321-4abc-8def-1234567890ab:tc-0001"
                ),
                "sessionId does not match source run",
            ),
        }
        for label, (mutate, expected_message) in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                artifact_root, manifest = self._export(Path(directory))
                trace_path = artifact_root / "traces/tc-0001.json"
                trace = json.loads(trace_path.read_text(encoding="utf-8"))
                mutate(trace)
                self._rewrite_fixture_and_hash(artifact_root, manifest, 0, trace)
                self._write_manifest(artifact_root, manifest)

                with self.assertRaisesRegex(FixtureManifestError, expected_message):
                    self._validate(artifact_root, manifest["experimentId"])

    def test_validator_rejects_unsafe_exact_content_with_a_matching_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact_root, manifest = self._export(Path(directory))
            trace_path = artifact_root / "traces/tc-0001.json"
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            trace["response"] = "Synthetic unsafe path: /home/example/private.txt"
            self._rewrite_fixture_and_hash(artifact_root, manifest, 0, trace)
            self._write_manifest(artifact_root, manifest)

            with self.assertRaisesRegex(
                ExactFixtureSafetyError,
                "forbidden private home path",
            ):
                self._validate(artifact_root, manifest["experimentId"])


if __name__ == "__main__":
    unittest.main()
