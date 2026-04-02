#!/usr/bin/env python3
"""
Query a Volcano Engine Seedance task via official Ark API.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

SKILL_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(SKILL_ROOT / ".env")
DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


class ConfigError(RuntimeError):
    pass


def _normalize_non_empty(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def resolve_runtime() -> tuple[str, str]:
    base_url = _normalize_non_empty(os.getenv("ARK_BASE_URL")) or DEFAULT_ARK_BASE_URL
    api_key = _normalize_non_empty(os.getenv("ARK_API_KEY"))
    base_url = base_url.rstrip("/")
    if not base_url:
        raise ConfigError("ARK_BASE_URL 不能为空")
    if not api_key:
        raise ConfigError("ARK_API_KEY 未配置，请检查 .env 文件")
    return base_url, api_key


def build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def decode_json_response(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(
            f"Response is not JSON, HTTP {response.status_code}: {response.text[:500]}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Response JSON is not an object: {payload!r}")
    return payload


def ensure_http_ok(response: httpx.Response, action: str) -> dict:
    payload = decode_json_response(response)
    if response.status_code >= 400:
        raise RuntimeError(
            f"{action} failed, HTTP {response.status_code}: {json.dumps(payload, ensure_ascii=False)}"
        )
    return payload


def query_task(task_id: str) -> dict:
    base_url, api_key = resolve_runtime()
    headers = build_headers(api_key)
    query_url = f"{base_url}/contents/generations/tasks/{task_id}"
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        response = client.get(query_url, headers=headers)
        return ensure_http_ok(response, "Task query")


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Seedance task via official Ark API")
    parser.add_argument("task_id", help="Task ID returned by create API")
    args = parser.parse_args()

    task_id = args.task_id.strip()
    if not task_id:
        print("Execution failed: task_id 不能为空")
        return 1

    try:
        payload = query_task(task_id)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except (ConfigError, RuntimeError, httpx.HTTPError) as exc:
        print(f"Execution failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
