#!/usr/bin/env python3
"""
Image input adapter for video-gen.

Purpose:
- Convert local image paths into public URLs when the downstream API only accepts URL inputs.
- Keep upload provider logic isolated from model invocation logic.

Current providers:
- kieai: upload local image bytes as base64 to KieAI temporary file hosting
- catbox: upload local file directly to Catbox, no API key required
- none: reject local files; only allow http(s) URLs
"""
from __future__ import annotations

import argparse
import base64
import mimetypes
import os
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

SKILL_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(SKILL_ROOT / ".env")

KIEAI_BASE_URL = os.getenv("KIEAI_BASE_URL", "https://kieai.redpandaai.co").rstrip("/")
KIEAI_API_KEY = (os.getenv("KIEAI_API_KEY") or "").strip()
DEFAULT_UPLOAD_PROVIDER = (os.getenv("IMAGE_UPLOAD_PROVIDER") or "kieai").strip().lower()
DEFAULT_UPLOAD_PATH = (os.getenv("IMAGE_UPLOAD_PATH") or "images/video-gen").strip()
CATBOX_UPLOAD_URL = "https://catbox.moe/user/api.php"
MAX_FILE_SIZE_MB = int((os.getenv("IMAGE_UPLOAD_MAX_MB") or "20").strip())
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"
}


class ImageAdapterError(RuntimeError):
    pass


def _normalize_non_empty(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _guess_mime_type(file_path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "application/octet-stream"


def _validate_local_file(file_path: Path) -> None:
    if not file_path.is_file():
        raise ImageAdapterError("本地图片路径无效或文件不存在")
    suffix = file_path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ImageAdapterError(
            f"不支持的图片格式: {suffix}，允许格式: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ImageAdapterError(
            f"图片过大: {size_mb:.2f}MB，超过限制 {MAX_FILE_SIZE_MB}MB"
        )


def _to_data_url(file_path: Path) -> tuple[str, str]:
    mime_type = _guess_mime_type(file_path)
    with file_path.open("rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}", mime_type


def upload_to_kieai_base64(base64_data: str, file_name: str, upload_path: str = DEFAULT_UPLOAD_PATH) -> dict:
    if not KIEAI_API_KEY:
        raise ImageAdapterError("KIEAI_API_KEY 未配置，无法上传本地图片")

    url = f"{KIEAI_BASE_URL}/api/file-base64-upload"
    headers = {
        "Authorization": f"Bearer {KIEAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "base64Data": base64_data,
        "uploadPath": upload_path,
        "fileName": file_name,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        raise ImageAdapterError(f"KieAI 上传失败: {exc}") from exc
    except ValueError as exc:
        raise ImageAdapterError("KieAI 返回的不是合法 JSON") from exc

    if not isinstance(result, dict):
        raise ImageAdapterError(f"KieAI 返回结构异常: {result!r}")
    if not result.get("success"):
        raise ImageAdapterError(f"KieAI 上传未成功: {result}")
    return result


def upload_to_catbox(file_path: Path) -> str:
    try:
        with file_path.open("rb") as f:
            response = requests.post(
                CATBOX_UPLOAD_URL,
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (file_path.name, f, _guess_mime_type(file_path))},
                timeout=120,
            )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ImageAdapterError(f"Catbox 上传失败: {exc}") from exc

    text = response.text.strip()
    if not text:
        raise ImageAdapterError("Catbox 返回空响应")
    if not (text.startswith("http://") or text.startswith("https://")):
        raise ImageAdapterError(f"Catbox 返回异常: {text}")
    return text


def get_file_url(upload_result: dict) -> str:
    data = upload_result.get("data") if isinstance(upload_result, dict) else None
    if not isinstance(data, dict):
        raise ImageAdapterError(f"上传结果缺少 data 字段: {upload_result!r}")

    for key in ("fileUrl", "downloadUrl"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise ImageAdapterError(f"上传结果中未找到 fileUrl/downloadUrl: {upload_result!r}")


def _is_http_url(value: str) -> bool:
    normalized = _normalize_non_empty(value).lower()
    return normalized.startswith("http://") or normalized.startswith("https://")


def resolve_image_to_public_url(image_input: Optional[str], provider: Optional[str] = None) -> Optional[str]:
    normalized = _normalize_non_empty(image_input)
    if not normalized:
        return None

    if _is_http_url(normalized):
        return normalized

    chosen_provider = (provider or DEFAULT_UPLOAD_PROVIDER or "kieai").strip().lower()
    file_path = Path(normalized).expanduser()
    _validate_local_file(file_path)

    if chosen_provider == "none":
        raise ImageAdapterError("当前配置禁止自动上传本地图片，请改用公网 URL")

    if chosen_provider == "kieai":
        data_url, _mime_type = _to_data_url(file_path)
        upload_result = upload_to_kieai_base64(
            base64_data=data_url,
            file_name=file_path.name,
            upload_path=DEFAULT_UPLOAD_PATH,
        )
        return get_file_url(upload_result)

    if chosen_provider == "catbox":
        return upload_to_catbox(file_path)

    raise ImageAdapterError(f"暂不支持的 IMAGE_UPLOAD_PROVIDER: {chosen_provider}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a local image path into a public URL")
    parser.add_argument("image", help="local image path or http(s) URL")
    parser.add_argument("--provider", default=None, help="upload provider: kieai|catbox|none")
    args = parser.parse_args()

    try:
        result = resolve_image_to_public_url(args.image, provider=args.provider)
        print(result or "")
        return 0
    except ImageAdapterError as exc:
        print(f"Execution failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
