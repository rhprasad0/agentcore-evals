"""Derive complete weather fixtures from projection metadata, never model output."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from src.dataset_projection import load_projection
from src.deterministic_mocks import CANONICALIZER_VERSION, FixtureKey


WEATHER_TOOL_ID = "weather.get_current_weather"
WEATHER_CONTRACT_VERSION = "2.0.0"
OPTIONAL_UNIT_VARIANTS = (None, "metric", "imperial", "standard")


class WeatherFixtureGenerationError(ValueError):
    """Projection metadata cannot deterministically define fixture coverage."""


def required_weather_projection_calls(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Return exact keys covering expectations and unconstrained optional units."""

    root = repo_root.resolve()
    projection = load_projection(
        root / "datasets/projections/weather-only-62.json",
        repo_root=root,
    )
    existing = _load_fixture_documents(
        root / "datasets/fixtures/mocks/tool-calling.jsonl"
    )
    contract = json.loads(
        (
            root
            / "contracts/tools/weather.get_current_weather/2.0.0.json"
        ).read_text(encoding="utf-8")
    )
    default_units = contract["inputSchema"]["properties"]["units"]["default"]
    existing_city = {
        document["exampleId"]: document["arguments"].get("city")
        for document in existing
        if document.get("toolId") == WEATHER_TOOL_ID
        and isinstance(document.get("arguments"), dict)
        and "city" in document["arguments"]
    }
    calls: list[dict[str, Any]] = []
    for row in projection.rows:
        expected = row["expected"]
        if WEATHER_TOOL_ID not in expected["toolIds"] or expected["maxCalls"] == 0:
            continue
        cities: list[str] = []
        constrained_units: str | None = None
        for constraint in expected["argConstraints"]:
            if constraint.get("toolId") != WEATHER_TOOL_ID:
                continue
            if constraint.get("path") == "$.city":
                if "equals" in constraint:
                    cities = [constraint["equals"]]
                elif "coversExactlyOnce" in constraint:
                    cities = list(constraint["coversExactlyOnce"])
            elif constraint.get("path") == "$.units" and "equals" in constraint:
                constrained_units = constraint["equals"]
        if not cities:
            if row["exampleId"] not in existing_city:
                raise WeatherFixtureGenerationError(
                    f"{row['exampleId']} has no predeclared city constraint or baseline fixture"
                )
            cities = [existing_city[row["exampleId"]]]
        if constrained_units == default_units:
            unit_variants = (None, constrained_units)
        elif constrained_units is not None:
            unit_variants = (constrained_units,)
        else:
            unit_variants = OPTIONAL_UNIT_VARIANTS
        for city in cities:
            for units in unit_variants:
                arguments: dict[str, Any] = {"city": city}
                if units is not None:
                    arguments["units"] = units
                calls.append({"exampleId": row["exampleId"], "arguments": arguments})
    return tuple(calls)


def generate_weather_projection_fixture_documents(
    repo_root: Path,
) -> tuple[dict[str, Any], ...]:
    """Replace projected weather rows while preserving unrelated baseline fixtures."""

    root = repo_root.resolve()
    fixture_path = root / "datasets/fixtures/mocks/tool-calling.jsonl"
    existing = _load_fixture_documents(fixture_path)
    projection = load_projection(
        root / "datasets/projections/weather-only-62.json",
        repo_root=root,
    )
    rows_by_id = {row["exampleId"]: row for row in projection.rows}
    projected_ids = set(rows_by_id)
    preserved = [
        document
        for document in existing
        if not (
            document.get("toolId") == WEATHER_TOOL_ID
            and document.get("exampleId") in projected_ids
        )
    ]
    baseline_results = {
        document["exampleId"]: document["result"]
        for document in existing
        if document.get("toolId") == WEATHER_TOOL_ID
    }
    exact_baseline_results = {
        (
            document["exampleId"],
            FixtureKey.from_call(
                WEATHER_TOOL_ID,
                WEATHER_CONTRACT_VERSION,
                document["arguments"],
            ).canonical_arguments,
        ): document["result"]
        for document in existing
        if document.get("toolId") == WEATHER_TOOL_ID
    }
    generated = []
    for call in required_weather_projection_calls(root):
        example_id = call["exampleId"]
        row = rows_by_id[example_id]
        arguments = call["arguments"]
        exact_baseline = exact_baseline_results.get(
            (
                example_id,
                FixtureKey.from_call(
                    WEATHER_TOOL_ID,
                    WEATHER_CONTRACT_VERSION,
                    arguments,
                ).canonical_arguments,
            )
        )
        if exact_baseline is not None:
            result = exact_baseline
        elif row.get("failureInjection") is not None:
            result = baseline_results.get(example_id)
            if not isinstance(result, dict) or result.get("ok") is not False:
                raise WeatherFixtureGenerationError(
                    f"{example_id} failure injection has no reviewed baseline failure result"
                )
        else:
            result = _synthetic_success(arguments)
        key = FixtureKey.from_call(
            WEATHER_TOOL_ID,
            WEATHER_CONTRACT_VERSION,
            arguments,
        )
        generated.append(
            {
                "arguments": arguments,
                "argumentsHash": key.arguments_hash,
                "canonicalizerVersion": CANONICALIZER_VERSION,
                "contractVersion": WEATHER_CONTRACT_VERSION,
                "exampleId": example_id,
                "result": result,
                "toolId": WEATHER_TOOL_ID,
            }
        )
    documents = preserved + generated
    documents.sort(
        key=lambda document: (
            document["exampleId"],
            document["toolId"],
            json.dumps(document["arguments"], ensure_ascii=False, sort_keys=True),
        )
    )
    return tuple(documents)


def render_fixture_jsonl(documents: tuple[Mapping[str, Any], ...]) -> str:
    return "".join(
        json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
        for document in documents
    )


def _synthetic_success(arguments: Mapping[str, Any]) -> dict[str, Any]:
    city = arguments["city"]
    units = arguments.get("units", "metric")
    digest = sha256(str(city).encode("utf-8")).digest()
    celsius = round((int.from_bytes(digest[:2], "big") % 900) / 20 - 10, 1)
    if units == "imperial":
        temperature = round(celsius * 9 / 5 + 32, 1)
    elif units == "standard":
        temperature = round(celsius + 273.15, 2)
    else:
        temperature = celsius
    conditions = ("clear", "cloudy", "rain", "windy")[digest[2] % 4]
    return {
        "ok": True,
        "city": city,
        "temp": temperature,
        "units": units,
        "conditions": conditions,
    }


def _load_fixture_documents(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
