#!/usr/bin/env python3
"""
Generate videos using Volcano Engine Seedance via official Ark API.

Usage:
    python generate_video_ark.py --prompt "your video description" --duration 8
    python generate_video_ark.py --prompt "motion description" -i /path/to/image.jpg --duration 8
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

from download_video import download_video
from image_url_adapter import ImageAdapterError, resolve_image_to_public_url

SKILL_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(SKILL_ROOT / ".env")

DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedance-1-5-pro-251215"
SUPPORTED_MODELS = (
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-1-0-pro-fast-251015",
)
TERMINAL_SUCCESS_STATUSES = {"succeeded", "success", "completed"}
TERMINAL_FAILURE_STATUSES = {"failed", "cancelled", "expired", "canceled"}


class ConfigError(RuntimeError):
    pass


def _normalize_non_empty(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _resolve_runtime() -> tuple[str, str]:
    base_url = _normalize_non_empty(os.getenv("ARK_BASE_URL")) or DEFAULT_ARK_BASE_URL
    api_key = _normalize_non_empty(os.getenv("ARK_API_KEY"))

    base_url = base_url.rstrip("/")
    if not base_url:
        raise ConfigError("ARK_BASE_URL 不能为空")
    if not api_key:
        raise ConfigError("ARK_API_KEY 未配置，请检查 .env 文件")
    return base_url, api_key


def _build_request_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _build_content(prompt: str, image_input: Optional[str], upload_provider: Optional[str]) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": prompt}]
    normalized_image = _normalize_non_empty(image_input)
    if normalized_image:
        image_url = resolve_image_to_public_url(normalized_image, provider=upload_provider)
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    return content


def _decode_json_response(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(
            f"Response is not JSON, HTTP {response.status_code}: {response.text[:500]}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Response JSON is not an object: {payload!r}")
    return payload


def _ensure_http_ok(response: httpx.Response, action: str) -> dict:
    payload = _decode_json_response(response)
    if response.status_code >= 400:
        raise RuntimeError(
            f"{action} failed, HTTP {response.status_code}: {json.dumps(payload, ensure_ascii=False)}"
        )
    return payload


def _extract_task_id(payload: dict) -> str:
    for key in ("id", "task_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise RuntimeError(f"Task created successfully but missing id/task_id: {payload}")


def _extract_status(payload: dict) -> str:
    for key in ("status", "task_status"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("status", "task_status"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    return ""


def _extract_video_url(payload: dict) -> str:
    possible_containers = [payload]
    for key in ("content", "data", "result", "output"):
        value = payload.get(key)
        if isinstance(value, dict):
            possible_containers.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    possible_containers.append(item)

    for container in possible_containers:
        for key in ("video_url", "file_url", "url", "download_url", "videoUrl", "fileUrl"):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        media = container.get("media")
        if isinstance(media, dict):
            for key in ("video_url", "file_url", "url", "download_url"):
                value = media.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


def _extract_error_message(payload: dict) -> str:
    for key in ("message", "error", "error_message", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("message", "error", "error_message", "detail"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _query_task(client: httpx.Client, query_url: str, headers: dict[str, str]) -> dict:
    query_resp = client.get(query_url, headers=headers)
    return _ensure_http_ok(query_resp, "Task query")


def _maybe_download(video_url: str, auto_download: bool, download_output: Optional[str]) -> None:
    if not auto_download:
        return
    save_path = download_video(video_url, download_output)
    print(f"Auto-downloaded video to: {save_path}")


def generate_video(
    prompt: str,
    image_input: Optional[str] = None,
    model_id: str = DEFAULT_MODEL,
    poll_interval: float = 10.0,
    duration: Optional[int] = None,
    generate_audio: bool = False,
    upload_provider: Optional[str] = None,
    dry_run: bool = False,
    max_polls: int = 120,
    auto_download: bool = False,
    download_output: Optional[str] = None,
) -> None:
    base_url, api_key = _resolve_runtime()
    headers = _build_request_headers(api_key)

    payload: dict = {
        "model": model_id,
        "content": _build_content(prompt.strip(), image_input, upload_provider),
    }
    if duration is not None:
        payload["duration"] = duration
    if generate_audio:
        payload["generate_audio"] = True

    create_url = f"{base_url}/contents/generations/tasks"

    print("----- Creating video generation task via official Ark API -----")
    print(f"API Base URL: {base_url}")
    print(f"Create endpoint: {create_url}")
    print(f"Model: {model_id}")
    print(f"Audio: {'enabled' if generate_audio else 'disabled (request-side)'}")

    if dry_run:
        print("----- Dry Run Payload -----")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
        create_resp = client.post(create_url, headers=headers, json=payload)
        create_payload = _ensure_http_ok(create_resp, "Task submission")
        task_id = _extract_task_id(create_payload)

        print(f"Task submitted, Task ID: {task_id}")
        print(f"Create response: {json.dumps(create_payload, ensure_ascii=False)}")
        print(f"Polling task status (every {poll_interval:g} seconds, max {max_polls} polls)...")

        query_url = f"{base_url}/contents/generations/tasks/{task_id}"
        for poll_index in range(1, max_polls + 1):
            query_payload = _query_task(client, query_url, headers)
            status = _extract_status(query_payload)
            video_url = _extract_video_url(query_payload)

            if video_url and (not status or status in TERMINAL_SUCCESS_STATUSES):
                print(f"\nVideo generated successfully, download URL: {video_url}")
                _maybe_download(video_url, auto_download, download_output)
                return

            if status in TERMINAL_SUCCESS_STATUSES:
                print("\nTask reached success status.")
                if video_url:
                    print(f"Video generated successfully, download URL: {video_url}")
                    _maybe_download(video_url, auto_download, download_output)
                else:
                    print("No direct video URL found in response. Full payload:")
                    print(json.dumps(query_payload, ensure_ascii=False, indent=2))
                return

            if status in TERMINAL_FAILURE_STATUSES:
                error_message = _extract_error_message(query_payload)
                raise RuntimeError(
                    f"Task failed with terminal status ({status})"
                    + (f": {error_message}" if error_message else "")
                    + f" | payload={json.dumps(query_payload, ensure_ascii=False)}"
                )

            print(
                f"Task in progress (poll {poll_index}/{max_polls}, status={status or 'unknown'})...",
                end="\r",
                flush=True,
            )
            time.sleep(poll_interval)

        raise RuntimeError(
            f"Polling timeout after {max_polls} polls. Last known task state kept on server."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Volcano Engine Seedance video generation script (official Ark API)"
    )
    parser.add_argument("-p", "--prompt", type=str, required=True, help="Text prompt describing the video")
    parser.add_argument(
        "-i", "--image", type=str, default=None, dest="image_input",
        help="Reference image for image-to-video: local path or URL (optional)",
    )
    parser.add_argument(
        "-m", "--model", type=str, default=DEFAULT_MODEL, choices=SUPPORTED_MODELS,
        help=f"Model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("--poll-interval", type=float, default=10.0, help="Polling interval in seconds")
    parser.add_argument(
        "-d", "--duration", type=int, default=None,
        help="Video duration in seconds (optional). Pro: 4-12s, Fast: 2-12s",
    )
    parser.add_argument("--audio", action="store_true", default=False, help="Generate video with audio")
    parser.add_argument(
        "--upload-provider", default=None,
        help="Upload provider for local image paths: kieai|catbox|none (default from .env)",
    )
    parser.add_argument("--dry-run", action="store_true", default=False, help="Print request payload only")
    parser.add_argument("--max-polls", type=int, default=120, help="Maximum number of polling attempts")
    parser.add_argument("--auto-download", action="store_true", default=False, help="Download the video automatically when ready")
    parser.add_argument("--download-output", type=str, default=None, help="Optional output path for auto-downloaded video")
    args = parser.parse_args()

    prompt = args.prompt.strip()
    if not prompt:
        raise ConfigError("Prompt cannot be empty")
    if args.poll_interval <= 0:
        raise ConfigError("--poll-interval must be greater than 0")
    if args.duration is not None and args.duration <= 0:
        raise ConfigError("--duration must be greater than 0")
    if args.max_polls <= 0:
        raise ConfigError("--max-polls must be greater than 0")

    try:
        generate_video(
            prompt=prompt,
            image_input=args.image_input,
            model_id=args.model,
            poll_interval=args.poll_interval,
            duration=args.duration,
            generate_audio=args.audio,
            upload_provider=args.upload_provider,
            dry_run=args.dry_run,
            max_polls=args.max_polls,
            auto_download=args.auto_download,
            download_output=args.download_output,
        )
    except (ConfigError, RuntimeError, httpx.HTTPError, ImageAdapterError) as exc:
        print(f"Execution failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
