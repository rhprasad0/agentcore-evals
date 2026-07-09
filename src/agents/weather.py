"""Week 2 Strands weather agent runner.

This script can inspect the registered weather tool without calling a model or
OpenWeatherMap. Running it without --inspect-tool invokes the local Strands
agent and may call Bedrock plus OpenWeatherMap if the model selects the tool.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from strands import Agent

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tools.weather import get_current_weather

APPID_RE = re.compile(r"([?&]appid=)[^&\s]+")
OWM_KEY_RE = re.compile(r"\b[a-f0-9]{32}\b", re.IGNORECASE)

SYSTEM_PROMPT = """You are a weather assistant for an evaluation lab.
Use the weather tool only for current weather in a named city.
Do not use the weather tool for forecasts, historical weather, climate averages,
math, geography trivia, or unrelated questions.
If the tool returns {ok: false}, explain the failure honestly and do not invent
weather conditions or temperatures.
"""


def scrub(value: Any) -> Any:
    """Redact OpenWeatherMap keys before printing local receipts."""
    if isinstance(value, str):
        return OWM_KEY_RE.sub("<OWM_API_KEY>", APPID_RE.sub(r"\1<OWM_API_KEY>", value))
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    return value


def build_agent() -> Agent:
    """Build the Week 2 weather agent with explicit tool registration."""
    return Agent(system_prompt=SYSTEM_PROMPT, tools=[get_current_weather], callback_handler=None)


def print_tool_spec() -> None:
    """Print what Strands exposes to the model for schema archaeology."""
    print(json.dumps(scrub(get_current_weather.tool_spec), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or inspect the Week 2 weather agent.")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="What's the current weather in Seattle?",
        help="Prompt to send to the agent when not using --inspect-tool.",
    )
    parser.add_argument(
        "--inspect-tool",
        action="store_true",
        help="Print the Strands tool spec without invoking a model or weather API.",
    )
    args = parser.parse_args()

    if args.inspect_tool:
        print_tool_spec()
        return

    agent = build_agent()
    result = agent(args.prompt)
    print("=== Final answer (scrubbed) ===")
    print(json.dumps(scrub(str(result)), indent=2))
    print("\n=== Agent messages (scrubbed) ===")
    print(json.dumps(scrub(agent.messages), indent=2))


if __name__ == "__main__":
    main()
