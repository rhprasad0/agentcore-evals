"""Tests for canonical experiment and per-execution run identity."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator

from src.run_manifest import (
    RunIdentityError,
    canonical_json_bytes,
    create_run_manifest,
    derive_experiment_id,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_FIXTURE = REPO_ROOT / "tests/fixtures/run-manifests/valid/weather-only.json"
SCHEMA_PATH = REPO_ROOT / "schemas/run-manifest.schema.json"


class RunManifestIdentityTests(unittest.TestCase):
    def _pins(self) -> dict:
        return json.loads(VALID_FIXTURE.read_text(encoding="utf-8"))["behaviorPins"]

    def test_canonical_json_sorts_objects_preserves_unicode_and_array_order(self) -> None:
        first = {"z": ["Bergen", "Oslo"], "a": {"city": "Reykjavík", "units": "metric"}}
        reordered = {"a": {"units": "metric", "city": "Reykjavík"}, "z": ["Bergen", "Oslo"]}

        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(reordered))
        self.assertIn("Reykjavík".encode("utf-8"), canonical_json_bytes(first))
        self.assertNotEqual(
            canonical_json_bytes(first),
            canonical_json_bytes({**first, "z": list(reversed(first["z"]))}),
        )
        self.assertNotIn(b" ", canonical_json_bytes(first))

    def test_canonical_json_rejects_nan(self) -> None:
        with self.assertRaises(ValueError):
            canonical_json_bytes({"temperature": math.nan})

    def test_experiment_id_uses_only_canonical_behavior_pins(self) -> None:
        pins = self._pins()
        reordered = dict(reversed(list(pins.items())))
        changed = json.loads(json.dumps(pins))
        changed["sampling"]["temperature"]["value"] = 0.1

        self.assertEqual(derive_experiment_id(pins), derive_experiment_id(reordered))
        self.assertNotEqual(derive_experiment_id(pins), derive_experiment_id(changed))

    def test_valid_fixture_experiment_id_matches_its_behavior_pins(self) -> None:
        fixture = json.loads(VALID_FIXTURE.read_text(encoding="utf-8"))

        self.assertEqual(
            derive_experiment_id(fixture["behaviorPins"]),
            fixture["experimentId"],
        )

    def test_create_run_manifest_uses_uuid4_and_excludes_environment_from_experiment(self) -> None:
        pins = self._pins()
        run_uuid = UUID("12345678-1234-4abc-8def-1234567890ab")
        executed_at = datetime(2026, 7, 16, 19, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            first = create_run_manifest(
                pins,
                {"pythonVersion": "3.12.3", "platform": "linux", "architecture": "x86_64", "region": None},
                Path(directory),
                uuid_factory=lambda: run_uuid,
                now=lambda: executed_at,
            )
            second = create_run_manifest(
                pins,
                {"pythonVersion": "3.13.0", "platform": "other", "architecture": "arm64", "region": "us-east-1"},
                Path(directory),
                uuid_factory=lambda: UUID("87654321-4321-4abc-8def-1234567890ab"),
                now=lambda: executed_at,
            )

        self.assertEqual(first["experimentId"], second["experimentId"])
        self.assertNotEqual(first["runId"], second["runId"])
        self.assertEqual("2026-07-16T19:00:00Z", first["executedAt"])
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual([], [error.message for error in Draft202012Validator(schema).iter_errors(first)])

    def test_create_run_manifest_rejects_non_uuid4_and_store_collision(self) -> None:
        pins = self._pins()
        environment = {"pythonVersion": "3.12.3", "platform": "linux", "architecture": "x86_64", "region": None}
        not_v4 = UUID("12345678-1234-1abc-8def-1234567890ab")
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            with self.assertRaisesRegex(RunIdentityError, "UUID4"):
                create_run_manifest(pins, environment, store, uuid_factory=lambda: not_v4)

            collision = UUID("12345678-1234-4abc-8def-1234567890ab")
            (store / str(collision)).mkdir()
            with self.assertRaisesRegex(RunIdentityError, "collision"):
                create_run_manifest(pins, environment, store, uuid_factory=lambda: collision)


if __name__ == "__main__":
    unittest.main()
