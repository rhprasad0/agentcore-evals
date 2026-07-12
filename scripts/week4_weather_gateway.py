#!/usr/bin/env python3
"""Preview, deploy, inspect, or delete the Week 4 Gateway weather stack."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError, WaiterError

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "infra" / "cloudformation" / "week4-weather-gateway" / "template.json"
LAMBDA_PATH = ROOT / "infra" / "cloudformation" / "week4-weather-gateway" / "lambda" / "lambda_function.py"
CORE_PATH = ROOT / "weatheragent" / "app" / "weather_agent" / "weather_core.py"
SCHEMA_PATH = ROOT / "schemas" / "weather-tool.json"
STATE_PATH = ROOT / "weatheragent" / "agentcore" / ".cli" / "deployed-state.json"
STACK_NAME = "weatheragent-week4-weather-gateway"
BOOTSTRAP_STACK_NAME = "CDKToolkit"
ASSET_PREFIX = "agentcore-evals/week4-weather-gateway"


def _load_gateway_id() -> str:
    try:
        state = json.loads(STATE_PATH.read_text())
        gateway_id = state["targets"]["default"]["resources"]["mcp"]["gateways"]["eval-gateway"]["gatewayId"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Deploy eval-gateway first so ignored AgentCore state can identify the existing Gateway."
        ) from error
    if not isinstance(gateway_id, str) or not gateway_id:
        raise RuntimeError("AgentCore deployment state contains no eval-gateway identifier.")
    return gateway_id


def _bootstrap_bucket(cloudformation: Any) -> str:
    response = cloudformation.describe_stacks(StackName=BOOTSTRAP_STACK_NAME)
    outputs = response["Stacks"][0].get("Outputs", [])
    bucket = next((item["OutputValue"] for item in outputs if item.get("OutputKey") == "BucketName"), None)
    if not bucket:
        raise RuntimeError("CDKToolkit has no BucketName output for Lambda asset staging.")
    return bucket


def _gateway_role_name(agentcore: Any, gateway_id: str) -> str:
    response = agentcore.get_gateway(gatewayIdentifier=gateway_id)
    role_arn = response.get("roleArn")
    if not isinstance(role_arn, str) or "/" not in role_arn:
        raise RuntimeError("GetGateway returned no usable execution role ARN.")
    return role_arn.rsplit("/", 1)[-1]


def _lambda_archive() -> tuple[bytes, str]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for archive_name, source_path in (
            ("lambda_function.py", LAMBDA_PATH),
            ("weather_core.py", CORE_PATH),
        ):
            info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source_path.read_bytes())
    payload = buffer.getvalue()
    return payload, hashlib.sha256(payload).hexdigest()


def _upload_lambda_asset(s3: Any, bucket: str) -> tuple[str, str]:
    payload, digest = _lambda_archive()
    key = f"{ASSET_PREFIX}/{digest}.zip"
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
            raise
        s3.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="application/zip")
    return bucket, key


def _schema_definition_to_cloudformation(schema: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {"Type": schema["type"]}
    if "description" in schema:
        converted["Description"] = schema["description"]
    if "required" in schema:
        converted["Required"] = schema["required"]
    if "properties" in schema:
        converted["Properties"] = {
            name: _schema_definition_to_cloudformation(definition)
            for name, definition in schema["properties"].items()
        }
    if "items" in schema:
        converted["Items"] = _schema_definition_to_cloudformation(schema["items"])
    return converted


def _tool_definition_to_cloudformation(tool: dict[str, Any]) -> dict[str, Any]:
    converted = {
        "Name": tool["name"],
        "Description": tool["description"],
        "InputSchema": _schema_definition_to_cloudformation(tool["inputSchema"]),
    }
    if "outputSchema" in tool:
        converted["OutputSchema"] = _schema_definition_to_cloudformation(tool["outputSchema"])
    return converted


def _render_template(bucket: str, key: str) -> str:
    template = json.loads(TEMPLATE_PATH.read_text())
    schema = json.loads(SCHEMA_PATH.read_text())
    if not isinstance(schema, list) or len(schema) != 1:
        raise RuntimeError("schemas/weather-tool.json must contain exactly one tool definition.")
    template["Resources"]["WeatherFunction"]["Properties"]["Code"] = {
        "S3Bucket": bucket,
        "S3Key": key,
    }
    template["Resources"]["WeatherGatewayTarget"]["Properties"]["TargetConfiguration"]["Mcp"]["Lambda"][
        "ToolSchema"
    ]["InlinePayload"] = [_tool_definition_to_cloudformation(tool) for tool in schema]
    return json.dumps(template, separators=(",", ":"))


def _stack_exists(cloudformation: Any) -> bool:
    try:
        response = cloudformation.describe_stacks(StackName=STACK_NAME)
    except ClientError as error:
        if "does not exist" in error.response.get("Error", {}).get("Message", ""):
            return False
        raise
    return response["Stacks"][0]["StackStatus"] != "REVIEW_IN_PROGRESS"


def _delete_review_stack(cloudformation: Any) -> None:
    try:
        response = cloudformation.describe_stacks(StackName=STACK_NAME)
    except ClientError as error:
        if "does not exist" in error.response.get("Error", {}).get("Message", ""):
            return
        raise
    if response["Stacks"][0]["StackStatus"] != "REVIEW_IN_PROGRESS":
        return
    cloudformation.delete_stack(StackName=STACK_NAME)
    cloudformation.get_waiter("stack_delete_complete").wait(
        StackName=STACK_NAME,
        WaiterConfig={"Delay": 3, "MaxAttempts": 100},
    )


def _create_change_set(cloudformation: Any, template_body: str, parameters: list[dict[str, str]]) -> tuple[str, bool]:
    change_set_type = "UPDATE" if _stack_exists(cloudformation) else "CREATE"
    change_set_name = f"week4-weather-{int(time.time())}"
    response = cloudformation.create_change_set(
        StackName=STACK_NAME,
        ChangeSetName=change_set_name,
        ChangeSetType=change_set_type,
        Description="Week 4 direct-versus-Gateway weather seam comparison",
        TemplateBody=template_body,
        Parameters=parameters,
        Capabilities=["CAPABILITY_IAM"],
        Tags=[
            {"Key": "agentcore-evals:week", "Value": "4"},
            {"Key": "agentcore-evals:purpose", "Value": "gateway-weather-seam"},
        ],
    )
    change_set_id = response["Id"]
    try:
        cloudformation.get_waiter("change_set_create_complete").wait(
            ChangeSetName=change_set_id,
            StackName=STACK_NAME,
            WaiterConfig={"Delay": 3, "MaxAttempts": 100},
        )
    except WaiterError:
        details = cloudformation.describe_change_set(ChangeSetName=change_set_id, StackName=STACK_NAME)
        reason = details.get("StatusReason", "")
        if details.get("Status") == "FAILED" and "didn't contain changes" in reason:
            return change_set_id, False
        raise RuntimeError(f"CloudFormation change set failed: {reason}") from None
    return change_set_id, True


def _summarize_change_set(cloudformation: Any, change_set_id: str) -> list[dict[str, str]]:
    details = cloudformation.describe_change_set(ChangeSetName=change_set_id, StackName=STACK_NAME)
    summary = []
    for item in details.get("Changes", []):
        change = item.get("ResourceChange", {})
        summary.append(
            {
                "action": change.get("Action", "UNKNOWN"),
                "resourceType": change.get("ResourceType", "UNKNOWN"),
                "replacement": change.get("Replacement", "N/A"),
            }
        )
    return summary


def _clients(region: str) -> tuple[Any, Any, Any]:
    session = boto3.Session(region_name=region)
    return (
        session.client("cloudformation"),
        session.client("s3"),
        session.client("bedrock-agentcore-control"),
    )


def _prepare(region: str) -> tuple[Any, str, list[dict[str, str]]]:
    api_key = os.environ.get("OWM_API_KEY")
    if not api_key:
        raise RuntimeError("OWM_API_KEY must be set in the process environment for preview or deploy.")
    cloudformation, s3, agentcore = _clients(region)
    gateway_id = _load_gateway_id()
    gateway_role_name = _gateway_role_name(agentcore, gateway_id)
    bucket = _bootstrap_bucket(cloudformation)
    asset_bucket, asset_key = _upload_lambda_asset(s3, bucket)
    template_body = _render_template(asset_bucket, asset_key)
    cloudformation.validate_template(TemplateBody=template_body)
    parameters = [
        {"ParameterKey": "GatewayIdentifier", "ParameterValue": gateway_id},
        {"ParameterKey": "GatewayRoleName", "ParameterValue": gateway_role_name},
        {"ParameterKey": "OpenWeatherApiKey", "ParameterValue": api_key},
    ]
    return cloudformation, template_body, parameters


def preview(region: str) -> None:
    cloudformation, template_body, parameters = _prepare(region)
    existed = _stack_exists(cloudformation)
    change_set_id, has_changes = _create_change_set(cloudformation, template_body, parameters)
    if not has_changes:
        cloudformation.delete_change_set(ChangeSetName=change_set_id, StackName=STACK_NAME)
        print(json.dumps({"status": "NO_CHANGES"}))
        return
    summary = _summarize_change_set(cloudformation, change_set_id)
    cloudformation.delete_change_set(ChangeSetName=change_set_id, StackName=STACK_NAME)
    if not existed:
        _delete_review_stack(cloudformation)
    print(json.dumps({"status": "PREVIEW", "changes": summary}, indent=2))


def deploy(region: str) -> None:
    cloudformation, template_body, parameters = _prepare(region)
    existed = _stack_exists(cloudformation)
    change_set_id, has_changes = _create_change_set(cloudformation, template_body, parameters)
    if not has_changes:
        cloudformation.delete_change_set(ChangeSetName=change_set_id, StackName=STACK_NAME)
        print(json.dumps({"status": "NO_CHANGES"}))
        return
    print(json.dumps({"status": "APPROVED_CHANGE_SET", "changes": _summarize_change_set(cloudformation, change_set_id)}, indent=2))
    cloudformation.execute_change_set(ChangeSetName=change_set_id, StackName=STACK_NAME)
    waiter_name = "stack_update_complete" if existed else "stack_create_complete"
    cloudformation.get_waiter(waiter_name).wait(
        StackName=STACK_NAME,
        WaiterConfig={"Delay": 5, "MaxAttempts": 240},
    )
    status(region)


def status(region: str) -> None:
    cloudformation, _, _ = _clients(region)
    if not _stack_exists(cloudformation):
        print(json.dumps({"status": "ABSENT"}))
        return
    stack = cloudformation.describe_stacks(StackName=STACK_NAME)["Stacks"][0]
    resources = cloudformation.list_stack_resources(StackName=STACK_NAME).get("StackResourceSummaries", [])
    print(
        json.dumps(
            {
                "status": stack["StackStatus"],
                "resources": [
                    {"type": item["ResourceType"], "status": item["ResourceStatus"]}
                    for item in resources
                ],
            },
            indent=2,
        )
    )


def delete(region: str) -> None:
    cloudformation, _, _ = _clients(region)
    if not _stack_exists(cloudformation):
        print(json.dumps({"status": "ABSENT"}))
        return
    cloudformation.delete_stack(StackName=STACK_NAME)
    cloudformation.get_waiter("stack_delete_complete").wait(
        StackName=STACK_NAME,
        WaiterConfig={"Delay": 5, "MaxAttempts": 240},
    )
    print(json.dumps({"status": "DELETED"}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preview", "deploy", "status", "delete"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()
    globals()[args.action](args.region)


if __name__ == "__main__":
    main()
