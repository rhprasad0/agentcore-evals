"""Export one accepted private Week 7 run as public Week 8 fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

from evals.fixtures.public_export import export_fixture_set


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"
OUTPUT_DIRECTORY = REPO_ROOT / "evals/fixtures/weather-only-62"
ARTIFACT_PREFIX = "evals/fixtures/weather-only-62"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_directory",
        type=Path,
        help="Ignored exact synthetic run directory to publish",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=OUTPUT_DIRECTORY,
        help="Destination directory; must not already exist",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    manifest = export_fixture_set(
        args.run_directory,
        PROJECTION_PATH,
        args.output_directory,
        artifact_prefix=ARTIFACT_PREFIX,
        repo_root=REPO_ROOT,
    )
    counts = manifest["counts"]
    print(
        f"exported {counts['expected']} fixtures "
        f"({counts['canonicalTrace']} traces, "
        f"{counts['instrumentError']} instrument errors)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
