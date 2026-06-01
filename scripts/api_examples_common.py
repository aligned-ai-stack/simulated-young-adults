from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--personas", type=int, default=1)
    return parser.parse_args()


def post_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _send(request)


def check_health(base_url: str) -> None:
    request = urllib.request.Request(f"{base_url}/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            health = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Could not reach the simulation API at {base_url}. "
            "Check that FastAPI is running and that --base-url points to the right port."
        ) from exc
    print_section("API HEALTH", health)


def get_json(base_url: str, path: str) -> dict[str, Any] | list[Any]:
    request = urllib.request.Request(f"{base_url}{path}", method="GET")
    return _send(request)


def _send(request: urllib.request.Request) -> dict[str, Any] | list[Any]:
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {request.full_url}: {body}") from exc


def print_section(title: str, value: Any) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)
    print(json.dumps(value, indent=2, ensure_ascii=False))


def print_export_summary(export: dict[str, Any]) -> None:
    summary = {
        "session_id": export["session"]["id"],
        "experiment_setup_id": export["session"]["experiment_setup_id"],
        "persona_id": export["persona"].get("persona_id"),
        "age": export["persona"].get("age"),
        "turn_count": len(export["turns"]),
        "trace_event_count": len(export["traces"]),
        "turns": [
            {
                "turn_id": turn["turn_id"],
                "trial_id": turn["trial_id"],
                "response": _try_parse_json(turn["response"]),
                "qualitative_thinking": turn["qualitative_thinking"],
                "provider_trace": turn["provider_trace"],
            }
            for turn in export["turns"]
        ],
    }
    print_section("FINAL EXPORT SUMMARY", summary)


def print_response_checks(
    turn: dict[str, Any],
    *,
    required_fields: list[str] | None = None,
    rating_fields: list[str] | None = None,
) -> None:
    required_fields = required_fields or []
    rating_fields = rating_fields or []
    parsed = _try_parse_json(turn["response"])
    checks: dict[str, Any] = {
        "turn_id": turn["turn_id"],
        "trial_id": turn["trial_id"],
        "response_is_json_object": isinstance(parsed, dict),
        "missing_required_fields": [],
        "out_of_range_1_to_7_fields": {},
    }

    if isinstance(parsed, dict):
        checks["missing_required_fields"] = [
            field for field in required_fields if field not in parsed
        ]
        checks["out_of_range_1_to_7_fields"] = {
            field: parsed.get(field)
            for field in rating_fields
            if field in parsed
            and not (
                isinstance(parsed[field], int)
                and not isinstance(parsed[field], bool)
                and 1 <= parsed[field] <= 7
            )
        }

    checks["ok"] = (
        checks["response_is_json_object"]
        and not checks["missing_required_fields"]
        and not checks["out_of_range_1_to_7_fields"]
    )
    print_section("RESPONSE CHECK", checks)


def _try_parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
