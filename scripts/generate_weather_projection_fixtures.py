"""Regenerate exact weather fixtures from reviewed projection metadata."""

from __future__ import annotations

from scripts.probe_week_07_telemetry import REPO_ROOT
from src.weather_fixture_generation import (
    generate_weather_projection_fixture_documents,
    render_fixture_jsonl,
)


def main() -> int:
    path = REPO_ROOT / "datasets/fixtures/mocks/tool-calling.jsonl"
    documents = generate_weather_projection_fixture_documents(REPO_ROOT)
    path.write_text(render_fixture_jsonl(documents), encoding="utf-8")
    print(f"Wrote {len(documents)} exact deterministic fixtures to {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
