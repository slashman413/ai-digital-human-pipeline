#!/usr/bin/env python3
"""Send a rich Discord notification with embed + thumbnails for video upload results."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request


def read_url(path: str) -> str | None:
    """Read one line from a file, return None if missing/empty."""
    try:
        v = open(path).read().strip()
        return v if v else None
    except FileNotFoundError:
        return None


def extract_video_id(url: str | None) -> str | None:
    """Extract YouTube video ID from youtu.be or youtube.com URLs."""
    if not url:
        return None
    m = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
    if m:
        return m.group(1)
    return None


def get_thumbnail(video_id: str) -> str:
    """YouTube thumbnail URL, falling back to lower quality if maxresdefault is 404."""
    # maxresdefault is 1280x720 — best quality
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"


def main() -> int:
    webhook = os.environ.get("WEBHOOK", "")
    if not webhook:
        print("[skip] WEBHOOK not set")
        return 0

    run_url = os.environ.get("RUN_URL", "")

    # Read title
    title = "AI 影片"
    try:
        t = open("title.txt").read().strip()
        if t:
            title = t
    except FileNotFoundError:
        pass

    # Read URLs
    url_zh = read_url("youtube_url.txt")
    url_en = read_url("youtube_en_url.txt")
    url_short = read_url("youtube_short_url.txt")

    urls = {
        "🇹🇼 中文版": url_zh,
        "🇺🇸 English": url_en,
        "📱 Short": url_short,
    }
    success_count = sum(1 for v in urls.values() if v)

    # Pick thumbnail (prefer Chinese, then Short, then English)
    thumbnail_url = None
    for key in ("🇹🇼 中文版", "📱 Short", "🇺🇸 English"):
        vid = extract_video_id(urls[key])
        if vid:
            thumbnail_url = get_thumbnail(vid)
            break

    # Color: green=all OK, orange=partial, red=all fail
    if success_count == len(urls):
        color = 0x2ECC71  # green
        status_icon = "✅"
    elif success_count > 0:
        color = 0xE67E22  # orange
        status_icon = "⚠️"
    else:
        color = 0xE74C3C  # red
        status_icon = "🔴"

    # Build embed
    embed = {
        "title": f"🎬 每日自動影片：{title}",
        "color": color,
        "fields": [
            {
                "name": k,
                "value": f"[{v}]({v})" if v else "❌ 上傳失敗",
                "inline": True,
            }
            for k, v in urls.items()
        ],
        "footer": {"text": "🤖 AI Digital Human Pipeline"},
    }

    if run_url:
        embed["url"] = run_url

    if success_count < len(urls) and success_count > 0:
        missing = [k for k, v in urls.items() if not v]
        embed["description"] = "⚠️ 部分上傳失敗：" + ", ".join(missing)
    elif success_count == 0:
        embed["description"] = "🔴 **所有平台均未成功**"

    if thumbnail_url:
        embed["image"] = {"url": thumbnail_url}

    payload = {
        "content": f"{status_icon} {success_count}/{len(urls)} 上傳成功",
        "embeds": [embed],
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 204:
                print("[ok] Discord notification sent")
            else:
                print(f"[warn] Discord returned HTTP {resp.status}: {resp.read().decode()}")
    except urllib.error.HTTPError as e:
        print(f"[error] Discord HTTP {e.code}: {e.read().decode()}")
        return 1
    except urllib.error.URLError as e:
        print(f"[error] Discord connection failed: {e.reason}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
