"""Offline tests for the Week 4 Lambda-behind-Gateway seam."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import socket
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.tools.weather import get_current_weather
from weatheragent.app.weather_agent import weather_core

ROOT = Path(__file__).resolve().parents[1]
LAMBDA_PATH = ROOT / "infra" / "cloudformation" / "week4-weather-gateway" / "lambda" / "lambda_function.py"
DEPLOY_PATH = ROOT / "scripts" / "week4_weather_gateway.py"
SCHEMA_PATH = ROOT / "schemas" / "weather-tool.json"
TEMPLATE_PATH = ROOT / "infra" / "cloudformation" / "week4-weather-gateway" / "template.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


weather_lambda = load_module("week4_weather_lambda", LAMBDA_PATH)
deploy_helper = load_module("week4_weather_deploy", DEPLOY_PATH)


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class GatewayWeatherLambdaTests(unittest.TestCase):
    def assert_failure(self, result: dict, kind: str, retryable: bool) -> None:
        self.assertEqual(result["ok"], False)
        self.assertEqual(result["error"]["kind"], kind)
        self.assertEqual(result["error"]["retryable"], retryable)
        self.assertTrue(result["error"]["message"])

    def test_success_matches_direct_weather_envelope(self) -> None:
        result = weather_lambda.fetch_current_weather(
            "Seattle",
            "imperial",
            api_key="test-key",
            http_open=lambda *args, **kwargs: FakeResponse(
                {"name": "Seattle", "main": {"temp": 52.5}, "weather": [{"description": "rain"}]}
            ),
        )

        self.assertEqual(
            result,
            {"ok": True, "city": "Seattle", "temp": 52.5, "units": "imperial", "conditions": "rain"},
        )

    def test_http_timeout_is_ten_seconds(self) -> None:
        observed: dict[str, object] = {}

        def recording_open(*args, **kwargs):
            observed.update(kwargs)
            return FakeResponse(
                {"name": "Seattle", "main": {"temp": 12.5}, "weather": [{"description": "cloudy"}]}
            )

        result = weather_lambda.fetch_current_weather(
            "Seattle",
            api_key="test-key",
            http_open=recording_open,
        )

        self.assertEqual(True, result["ok"])
        self.assertEqual(10, observed["timeout"])

    def test_lambda_outer_timeout_exceeds_upstream_timeout(self) -> None:
        template = json.loads(TEMPLATE_PATH.read_text())

        self.assertEqual(15, template["Resources"]["WeatherFunction"]["Properties"]["Timeout"])

    def test_bad_input_and_auth_use_typed_envelopes(self) -> None:
        self.assert_failure(weather_lambda.fetch_current_weather("", api_key="test-key"), "bad_input", False)
        self.assert_failure(
            weather_lambda.fetch_current_weather("Seattle", "kelvin-ish", api_key="test-key"),
            "bad_input",
            False,
        )
        self.assert_failure(weather_lambda.fetch_current_weather("Seattle", api_key=""), "auth", False)

    def test_http_failure_mapping_matches_direct_contract(self) -> None:
        def not_found(request, timeout):
            raise HTTPError(request.full_url, 404, "not found", Message(), None)

        result = weather_lambda.fetch_current_weather(
            "Atlantis",
            api_key="test-key",
            http_open=not_found,
        )

        self.assert_failure(result, "upstream_4xx", False)

    def test_timeout_and_network_are_retryable(self) -> None:
        def timeout_open(*args, **kwargs):
            raise socket.timeout("slow")

        def network_open(*args, **kwargs):
            raise URLError(OSError("offline"))

        self.assert_failure(
            weather_lambda.fetch_current_weather("Seattle", api_key="test-key", http_open=timeout_open),
            "timeout",
            True,
        )
        self.assert_failure(
            weather_lambda.fetch_current_weather("Seattle", api_key="test-key", http_open=network_open),
            "network",
            True,
        )

    def test_lambda_handler_adapts_gateway_argument_map(self) -> None:
        with patch.dict(os.environ, {"OWM_API_KEY": "test-key"}), patch.object(
            weather_lambda,
            "HTTP_OPEN",
            lambda *args, **kwargs: FakeResponse(
                {"name": "Oslo", "main": {"temp": 12.5}, "weather": [{"description": "cloudy"}]}
            ),
        ):
            result = weather_lambda.lambda_handler({"city": "Oslo"}, None)

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["units"], "metric")
        self.assertEqual(result["temp"], 12.5)

    def test_schema_description_matches_direct_model_facing_description(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text())

        self.assertEqual(len(schema), 1)
        self.assertEqual(schema[0]["name"], "get_current_weather")
        self.assertEqual(schema[0]["description"], get_current_weather.tool_spec["description"])
        self.assertEqual(schema[0]["inputSchema"]["required"], ["city"])
        self.assertNotIn("units", schema[0]["inputSchema"]["required"])

    def test_template_keeps_secret_hidden_and_gateway_permission_scoped(self) -> None:
        template = json.loads(TEMPLATE_PATH.read_text())

        self.assertEqual(template["Parameters"]["OpenWeatherApiKey"]["NoEcho"], True)
        statement = template["Resources"]["GatewayInvokePolicy"]["Properties"]["PolicyDocument"]["Statement"][0]
        self.assertEqual(statement["Action"], "lambda:InvokeFunction")
        self.assertEqual(statement["Resource"], {"Fn::GetAtt": ["WeatherFunction", "Arn"]})
        self.assertEqual(
            template["Resources"]["WeatherGatewayTarget"]["Properties"]["CredentialProviderConfigurations"],
            [{"CredentialProviderType": "GATEWAY_IAM_ROLE"}],
        )

    def test_rendered_template_injects_exact_schema_and_content_addressed_code(self) -> None:
        rendered = json.loads(deploy_helper._render_template("artifact-bucket", "assets/code.zip"))
        schema = json.loads(SCHEMA_PATH.read_text())

        self.assertEqual(
            rendered["Resources"]["WeatherFunction"]["Properties"]["Code"],
            {"S3Bucket": "artifact-bucket", "S3Key": "assets/code.zip"},
        )
        self.assertEqual(
            rendered["Resources"]["WeatherGatewayTarget"]["Properties"]["TargetConfiguration"]["Mcp"][
                "Lambda"
            ]["ToolSchema"]["InlinePayload"],
            [deploy_helper._tool_definition_to_cloudformation(schema[0])],
        )
        converted = rendered["Resources"]["WeatherGatewayTarget"]["Properties"]["TargetConfiguration"]["Mcp"][
            "Lambda"
        ]["ToolSchema"]["InlinePayload"][0]
        self.assertEqual(converted["Name"], schema[0]["name"])
        self.assertEqual(converted["Description"], schema[0]["description"])
        self.assertEqual(converted["InputSchema"]["Required"], ["city"])

    def test_lambda_archive_is_deterministic(self) -> None:
        first_payload, first_digest = deploy_helper._lambda_archive()
        second_payload, second_digest = deploy_helper._lambda_archive()

        self.assertEqual(first_payload, second_payload)
        self.assertEqual(first_digest, second_digest)

    def test_direct_and_lambda_seams_share_contract_core(self) -> None:
        lambda_core_path = Path(inspect.getsourcefile(weather_lambda.normalize_arguments) or "").resolve()
        direct_core_path = Path(inspect.getsourcefile(weather_core.normalize_arguments) or "").resolve()
        self.assertEqual(lambda_core_path, direct_core_path)

    def test_review_in_progress_is_not_treated_as_deployed_stack(self) -> None:
        class ReviewStackClient:
            def describe_stacks(self, **kwargs):
                return {"Stacks": [{"StackStatus": "REVIEW_IN_PROGRESS"}]}

        self.assertEqual(deploy_helper._stack_exists(ReviewStackClient()), False)


if __name__ == "__main__":
    unittest.main()
