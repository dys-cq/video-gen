from __future__ import annotations
import argparse
import sys
import urllib.request
from datetime import datetime
from pathlib import Path


def download_video(url: str, output: str | None) -> Path:
    if output:
        save_path = Path(output).expanduser().resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        downloads_dir = Path("~/Downloads").expanduser()
        downloads_dir.mkdir(parents=True, exist_ok=True)
        save_path = downloads_dir / f"generated_video_{timestamp}.mp4"

    save_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"正在下载视频...")
    print(f"来源: {url}")
    print(f"目标: {save_path}")

    def _progress(block_count: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            downloaded = block_count * block_size
            pct = min(downloaded * 100 // total_size, 100)
            print(f"\r下载进度: {pct}% ({downloaded}/{total_size} bytes)", end="", flush=True)

    urllib.request.urlretrieve(url, save_path, reporthook=_progress)
    print()  # 换行
    return save_path


def main() -> int:
    parser = argparse.ArgumentParser(description="视频下载脚本")
    parser.add_argument("url", help="视频下载链接")
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="保存路径（默认: ~/Downloads/generated_video_<时间戳>.mp4）",
    )
    args = parser.parse_args()

    if not args.url.strip():
        print("错误: url 不能为空")
        return 1

    try:
        save_path = download_video(args.url.strip(), args.output)
        print(f"下载完成，视频已保存至: {save_path}")
        return 0
    except Exception as exc:
        print(f"下载失败: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
