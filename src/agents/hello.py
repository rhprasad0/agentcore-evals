"""Week 1 hello-world Strands agent.

Runs one tool-backed question and prints a scrubbed view of the agent loop.
"""

from __future__ import annotations

import json
import re
from typing import Any

import boto3
from strands import Agent, tool


ACCOUNT_RE = re.compile(r"\b\d{12}\b")
ARN_RE = re.compile(r"arn:aws[a-zA-Z-]*:[A-Za-z0-9_+=,.@:/-]+")


def scrub(value: Any) -> Any:
    """Replace AWS account IDs and ARNs before printing local receipts."""
    if isinstance(value, str):
        return ACCOUNT_RE.sub("<AWS_ACCOUNT_ID>", ARN_RE.sub("<AWS_ARN>", value))
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    return value


@tool
def caller_identity() -> dict[str, str]:
    """Return the AWS account ID and ARN this environment is authenticated as."""
    ident = boto3.client("sts").get_caller_identity()
    return {"account": ident["Account"], "arn": ident["Arn"]}


agent = Agent(
    system_prompt="You are a lab assistant. Answer AWS facts only via tools; never guess.",
    tools=[caller_identity],
    callback_handler=None,
)


def main() -> None:
    result = agent("Which AWS identity am I running as?")
    print("=== Final answer (scrubbed) ===")
    print(json.dumps(scrub(str(result)), indent=2))
    print("\n=== Agent messages (scrubbed) ===")
    print(json.dumps(scrub(agent.messages), indent=2))


if __name__ == "__main__":
    main()
