"""Canonical Week 7 experiment identity and per-execution run identity."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


class RunIdentityError(ValueError):
    """A run identity is invalid or collides with an existing execution."""


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize structured behavior pins as deterministic UTF-8 JSON."""

    return json.dumps(
        dict(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def derive_experiment_id(behavior_pins: Mapping[str, Any]) -> str:
    """Return the content identity of behavior pins only."""

    return f"sha256:{sha256(canonical_json_bytes(behavior_pins)).hexdigest()}"


def create_run_manifest(
    behavior_pins: Mapping[str, Any],
    environment: Mapping[str, Any],
    run_store: Path,
    *,
    uuid_factory: Callable[[], UUID] = uuid4,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Build a pending run manifest without creating run-store content."""

    run_id = uuid_factory()
    if run_id.version != 4:
        raise RunIdentityError(f"runId must be UUID4, got version {run_id.version}")
    if (run_store / str(run_id)).exists():
        raise RunIdentityError(f"runId collision in run store: {run_id}")
    executed_at = now()
    if executed_at.tzinfo is None or executed_at.utcoffset() is None:
        raise RunIdentityError("executedAt provider must return a timezone-aware datetime")
    executed_at_utc = executed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    pins = dict(behavior_pins)
    return {
        "schemaVersion": "1.0.0",
        "experimentId": derive_experiment_id(pins),
        "runId": str(run_id),
        "executedAt": executed_at_utc,
        "behaviorPins": pins,
        "environment": dict(environment),
        "outputs": None,
    }
