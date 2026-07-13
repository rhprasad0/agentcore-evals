"""Offline tests for the Week 2 weather tool boundary."""

from __future__ import annotations

import unittest

import requests

from src.tools.weather import FAILURE_KINDS, fetch_current_weather, get_current_weather


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def fake_get_response(status_code: int, payload: dict | None = None):
    def _get(*args, **kwargs):
        return FakeResponse(status_code, payload)

    return _get


class WeatherToolTests(unittest.TestCase):
    def assert_failure(self, result: dict, kind: str, retryable: bool) -> None:
        self.assertEqual(result["ok"], False)
        self.assertEqual(result["error"]["kind"], kind)
        self.assertEqual(result["error"]["retryable"], retryable)
        self.assertTrue(result["error"]["message"])

    def test_success_envelope(self) -> None:
        result = fetch_current_weather(
            "Seattle",
            "imperial",
            api_key="test-key",
            http_get=fake_get_response(
                200,
                {"name": "Seattle", "main": {"temp": 52.5}, "weather": [{"description": "rain"}]},
            ),
        )

        self.assertEqual(
            result,
            {"ok": True, "city": "Seattle", "temp": 52.5, "units": "imperial", "conditions": "rain"},
        )

    def test_model_visible_units_match_the_closed_runtime_set(self) -> None:
        units_schema = get_current_weather.tool_spec["inputSchema"]["json"]["properties"]["units"]

        self.assertEqual(["metric", "imperial", "standard"], units_schema["enum"])
        self.assertEqual("metric", units_schema["default"])

    def test_bad_input_empty_city(self) -> None:
        result = fetch_current_weather(" ", api_key="test-key", http_get=fake_get_response(200))

        self.assert_failure(result, "bad_input", False)

    def test_bad_input_invalid_units(self) -> None:
        result = fetch_current_weather("Seattle", "kelvin-ish", api_key="test-key", http_get=fake_get_response(200))

        self.assert_failure(result, "bad_input", False)

    def test_auth_missing_key(self) -> None:
        result = fetch_current_weather("Seattle", api_key="", http_get=fake_get_response(200))

        self.assert_failure(result, "auth", False)

    def test_auth_status(self) -> None:
        result = fetch_current_weather("Seattle", api_key="bad-key", http_get=fake_get_response(401))

        self.assert_failure(result, "auth", False)

    def test_upstream_4xx(self) -> None:
        result = fetch_current_weather("Atlantis", api_key="test-key", http_get=fake_get_response(404))

        self.assert_failure(result, "upstream_4xx", False)

    def test_upstream_429_is_retryable_4xx(self) -> None:
        result = fetch_current_weather("Seattle", api_key="test-key", http_get=fake_get_response(429))

        self.assert_failure(result, "upstream_4xx", True)

    def test_upstream_5xx(self) -> None:
        result = fetch_current_weather("Seattle", api_key="test-key", http_get=fake_get_response(503))

        self.assert_failure(result, "upstream_5xx", True)

    def test_timeout(self) -> None:
        def timeout_get(*args, **kwargs):
            raise requests.Timeout("slow")

        result = fetch_current_weather("Seattle", api_key="test-key", http_get=timeout_get)

        self.assert_failure(result, "timeout", True)

    def test_network(self) -> None:
        def network_get(*args, **kwargs):
            raise requests.ConnectionError("offline")

        result = fetch_current_weather("Seattle", api_key="test-key", http_get=network_get)

        self.assert_failure(result, "network", True)

    def test_all_failure_kinds_are_reachable(self) -> None:
        observed = {
            fetch_current_weather("", api_key="test-key")["error"]["kind"],
            fetch_current_weather("Seattle", api_key="")["error"]["kind"],
            fetch_current_weather("Seattle", api_key="test-key", http_get=fake_get_response(404))["error"]["kind"],
            fetch_current_weather("Seattle", api_key="test-key", http_get=fake_get_response(503))["error"]["kind"],
        }

        def timeout_get(*args, **kwargs):
            raise requests.Timeout("slow")

        def network_get(*args, **kwargs):
            raise requests.ConnectionError("offline")

        observed.add(fetch_current_weather("Seattle", api_key="test-key", http_get=timeout_get)["error"]["kind"])
        observed.add(fetch_current_weather("Seattle", api_key="test-key", http_get=network_get)["error"]["kind"])

        self.assertEqual(observed, set(FAILURE_KINDS))


if __name__ == "__main__":
    unittest.main()
