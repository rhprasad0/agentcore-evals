"""Generate the public-safe Week 8 Stage B evaluation report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Callable

from evals.harness import HarnessEvidenceError, run_stage_b
from evals.reporting import (
    ReportContractError,
    build_stage_b_aggregate,
    render_json,
    render_markdown,
    render_text,
    validate_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RENDERERS: dict[str, Callable[[dict[str, object]], str]] = {
    "json": render_json,
    "text": render_text,
    "markdown": render_markdown,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--format", choices=tuple(RENDERERS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    repo_root = arguments.repo_root.resolve()
    try:
        result = run_stage_b(repo_root)
        aggregate = build_stage_b_aggregate(result.evidence, result.report)
        validate_report(aggregate, repo_root=repo_root)
        rendered = RENDERERS[arguments.format](aggregate)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    except (HarnessEvidenceError, ReportContractError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
