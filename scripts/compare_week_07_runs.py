"""Compare two completed Week 7 projection runs without exposing case content."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.probe_week_07_telemetry import REPO_ROOT
from src.run_comparison import compare_projection_runs


RUN_STORE = REPO_ROOT / "datasets/runs"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left_run_id")
    parser.add_argument("right_run_id")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    comparison = compare_projection_runs(
        RUN_STORE / arguments.left_run_id,
        RUN_STORE / arguments.right_run_id,
    )
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = arguments.output.with_suffix(arguments.output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(arguments.output)
    print(json.dumps(comparison["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
