#!/usr/bin/env python3
"""
Generate videos using Volcano Engine Seedance via EasyClaw API.

Usage:
    python generate_video.py --prompt "your video description" --duration 8
    python generate_video.py --prompt "motion description" -i /path/to/image.jpg --duration 8
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import time
from pathlib import Path
from io import BytesIO
import httpx
from PIL import Image as PILImage

DEFAULT_BASE_URL = "https://aibot-srv.easyclaw.cn"
DEFAULT_MODEL = "doubao-seedance-1-5-pro-251215"
SUPPORTED_MODELS = (
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-1-0-pro-fast-251015",
)
CREATE_TASK_PATHS = (
    "/contents/generations/tasks",
    "/api/v1/contents/generations/tasks",
)
MAX_INPUT_PIXELS = 2_560_000  # Same as image-gen


class ConfigError(RuntimeError):
    """Raised when required Easyclaw runtime config is missing."""


def resize_image_if_needed(image: PILImage.Image) -> tuple[PILImage.Image, bool]:
    """Resize image if it exceeds MAX_INPUT_PIXELS (same as image-gen)."""
    width, height = image.size
    if width * height <= MAX_INPUT_PIXELS:
        return image, False

    scale = (MAX_INPUT_PIXELS / float(width * height)) ** 0.5
    resized_width = max(1, int(width * scale))
    resized_height = max(1, int(height * scale))

    resized = image.resize((resized_width, resized_height), PILImage.Resampling.LANCZOS)
    return resized, True


def encode_image_path(image_path: str) -> str:
    """
    Encode a local image path to base64 data URL (same as image-gen).
    Returns a data URL string like: data:image/jpeg;base64,xxxxx
    """
    try:
        with PILImage.open(image_path) as image:
            copied = image.copy()
            image_format = (copied.format or "PNG").lower()
    except Exception as error:
        raise ConfigError(f"Error loading input image '{image_path}': {error}") from error

    processed_image, resized = resize_image_if_needed(copied)
    width, height = processed_image.size

    if resized:
        print(
            f"Resized input image: {image_path} -> {width}x{height} "
            f"({width * height} pixels)"
        )

    mime_type = "image/png" if image_format == "png" else f"image/{image_format}"
    buffer = BytesIO()
    save_format = "PNG" if image_format == "png" else (processed_image.format or image_format).upper()
    processed_image.save(buffer, format=save_format)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _normalize_non_empty(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in file: {path}") from exc


def _normalize_base_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    if not normalized:
        raise ConfigError("BASE_URL cannot be empty")
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


def _load_easyclaw_runtime_config(state_dir: Path) -> tuple[str, str, str]:
    """Load EasyClaw config from state files (same as image-gen)."""
    config_path = state_dir / "easyclaw.json"
    userinfo_path = state_dir / "identity" / "easyclaw-userinfo.json"
    config_data = _load_json(config_path)
    userinfo_data = _load_json(userinfo_path)

    if not isinstance(config_data, dict):
        raise ConfigError("easyclaw.json must be a JSON object")
    if not isinstance(userinfo_data, dict):
        raise ConfigError("easyclaw-userinfo.json must be a JSON object")

    models = config_data.get("models")
    providers = models.get("providers") if isinstance(models, dict) else None
    easyclaw = providers.get("easyclaw") if isinstance(providers, dict) else None
    base_url = _normalize_non_empty(
        easyclaw.get("baseUrl") if isinstance(easyclaw, dict) else None
    )
    if not base_url:
        raise ConfigError("easyclaw.json missing models.providers.easyclaw.baseUrl")

    uid = _normalize_non_empty(userinfo_data.get("uid"))
    token = _normalize_non_empty(userinfo_data.get("token"))
    if not uid or not token:
        raise ConfigError("easyclaw-userinfo.json missing uid or token")

    return _normalize_base_url(base_url), uid, token


def _resolve_runtime() -> tuple[str, str, str]:
    """Load EasyClaw runtime config from environment or state files.

    Environment variables take precedence over state files.
    Raises ConfigError if required config is missing.
    """
    env_base_url = _normalize_non_empty(os.environ.get("BASE_URL"))
    env_uid = _normalize_non_empty(os.environ.get("AUTH_UID"))
    env_token = _normalize_non_empty(os.environ.get("AUTH_TOKEN"))

    # If all env vars are provided, use them
    if env_base_url and env_uid and env_token:
        return _normalize_base_url(env_base_url), env_uid, env_token

    # Otherwise, load from state files
    state_dir = Path(
        _normalize_non_empty(os.environ.get("EASYCLAW_STATE_DIR")) or "~/.easyclaw"
    ).expanduser()
    return _load_easyclaw_runtime_config(state_dir)


def _build_request_headers(uid: str, token: str) -> dict[str, str]:
    return {
        "X-AUTH-UID": uid,
        "X-AUTH-TOKEN": token,
        "Content-Type": "application/json",
    }


def _build_content(prompt: str, image_input: str | None) -> list[dict[str, str]]:
    """
    Build content array for video generation request.

    image_input can be:
    - A local file path (e.g., "/path/to/image.jpg")
    - A remote URL (e.g., "https://example.com/image.jpg")
    - A base64 data URL (e.g., "data:image/jpeg;base64,xxxxx")
    """
    content: list[dict[str, str]] = []
    normalized_image = _normalize_non_empty(image_input)

    if normalized_image:
        # Check if it's a local file path
        if os.path.isfile(normalized_image):
            print(f"Loading local image: {normalized_image}")
            image_data = encode_image_path(normalized_image)
            content.append({"type": "image", "image_url": image_data})
        else:
            # Assume it's a URL or data URL
            content.append({"type": "image", "image_url": normalized_image})

    content.append({"type": "text", "text": prompt})
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


def _submit_with_fallback_paths(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    payload: dict,
) -> tuple[dict, str]:
    last_404_payload: dict | None = None
    for path in CREATE_TASK_PATHS:
        create_url = f"{base_url}{path}"
        create_resp = client.post(create_url, headers=headers, json=payload)
        if create_resp.status_code == 404:
            last_404_payload = _decode_json_response(create_resp)
            continue
        return _ensure_http_ok(create_resp, "Task submission"), path
    detail = (
        json.dumps(last_404_payload, ensure_ascii=False)
        if isinstance(last_404_payload, dict)
        else "Not Found"
    )
    raise RuntimeError(
        f"Task submission failed, gateway does not expose video routes (tried: {', '.join(CREATE_TASK_PATHS)}): {detail}"
    )


def _extract_video_url(payload: dict) -> str:
    content = payload.get("content")
    if isinstance(content, dict):
        for key in ("video_url", "file_url"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def generate_video(
    prompt: str,
    image_input: str | None = None,
    model_id: str = DEFAULT_MODEL,
    poll_interval: float = 10.0,
    duration: int | None = None,
    generate_audio: bool = False,
) -> None:
    base_url, auth_uid, auth_token = _resolve_runtime()
    headers = _build_request_headers(auth_uid, auth_token)

    payload: dict = {
        "model": model_id,
        "content": _build_content(prompt.strip(), image_input),
        "generate_audio": generate_audio,
    }
    if duration is not None:
        payload["duration"] = duration

    print("----- Creating video generation task via EasyClaw API -----")
    print(f"API Base URL: {base_url}")
    print(f"Create endpoint candidates: {', '.join(CREATE_TASK_PATHS)}")
    print(f"Model: {model_id}")
    print(f"Audio: {'enabled' if generate_audio else 'disabled (default)'}")

    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
        create_payload, used_create_path = _submit_with_fallback_paths(
            client=client,
            base_url=base_url,
            headers=headers,
            payload=payload,
        )
        task_id = _normalize_non_empty(create_payload.get("id"))
        if not task_id:
            raise RuntimeError(f"Task created successfully but missing id: {create_payload}")

        print(f"Actual create endpoint: {used_create_path}")
        print(f"Task submitted, Task ID: {task_id}")
        print(f"Polling task status (every {poll_interval:g} seconds)...")

        query_url = f"{base_url}{used_create_path}/{task_id}"
        while True:
            query_resp = client.get(query_url, headers=headers)
            query_payload = _ensure_http_ok(query_resp, "Task query")
            status = _normalize_non_empty(query_payload.get("status")).lower()

            if status == "succeeded":
                video_url = _extract_video_url(query_payload)
                if video_url:
                    print(f"\nVideo generated successfully, download URL: {video_url}")
                else:
                    print("\nVideo generated successfully, but no video_url/file_url in response.")
                    print(json.dumps(query_payload, ensure_ascii=False, indent=2))
                return

            if status in {"failed", "cancelled", "expired"}:
                raise RuntimeError(
                    f"Task failed with terminal status ({status}): "
                    f"{json.dumps(query_payload, ensure_ascii=False)}"
                )

            print(f"Task in progress (status={status or 'unknown'})...", end="\r", flush=True)
            time.sleep(poll_interval)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Volcano Engine Seedance video generation script (EasyClaw authenticated)"
    )
    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        required=True,
        help="Text prompt describing the video",
    )
    parser.add_argument(
        "-i",
        "--image",
        type=str,
        default=None,
        dest="image_input",
        help="Reference image for image-to-video: local path or URL (optional)",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        choices=SUPPORTED_MODELS,
        help=f"Model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Polling interval in seconds (default: 10)",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=int,
        default=None,
        help="Video duration in seconds (optional). Pro: 4-12s, Fast: 2-12s",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        default=False,
        help="Generate video with audio (default: no audio)",
    )
    args = parser.parse_args()

    prompt = args.prompt.strip()
    if not prompt:
        raise ConfigError("Prompt cannot be empty")
    if args.poll_interval <= 0:
        raise ConfigError("--poll-interval must be greater than 0")
    if args.duration is not None and args.duration <= 0:
        raise ConfigError("--duration must be greater than 0")

    try:
        generate_video(
            prompt=prompt,
            image_input=args.image_input,
            model_id=args.model,
            poll_interval=args.poll_interval,
            duration=args.duration,
            generate_audio=args.audio,
        )
    except (ConfigError, RuntimeError, httpx.HTTPError) as exc:
        print(f"Execution failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
