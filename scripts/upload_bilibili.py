"""Publish a video to Bilibili.

CLI (shared contract with the other uploaders):
    --video <path> --title <str> --description <str> --tags <comma-separated>

Bilibili has no simple official open upload API for individuals; the practical
route is the community CLI `biliup` (https://github.com/biliup/biliup-rs) driven
by your login cookies. This script:
  - If `biliup` is on PATH and BILIBILI_COOKIES (path to a cookies json) is set,
    it shells out to biliup to upload.
  - Otherwise it DRY RUNs (prints what it would post) and exits 0.

Env:
    BILIBILI_COOKIES  path to a biliup cookies.json (from `biliup login`)
    BILIBILI_TID      partition id (default 21 = 日常)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# Product CTA — appended once to every description (idempotent).
# ---------------------------------------------------------------------------
_CTA_MARKER = "slashman413-cta-v1"
_CTA_TEMPLATE = (
    "\n\n"
    "🛠 SaaS Starter — ship a multi-tenant SaaS this weekend:\n"
    "https://slashman413.gumroad.com/l/saas-starter"
    "?utm_source={src}&utm_medium=video&utm_campaign={camp}\n"
    "📈 台股大飆股 DNA 量化訊號（免費回測＋每日精選）:\n"
    "https://slashman413.github.io/twse-backtests/"
    "?utm_source={src}&utm_medium=video&utm_campaign={camp}\n"
    f"<!-- {_CTA_MARKER} -->"
)


def _append_cta(desc: str, src: str, camp: str = "ai-digital-human-pipeline") -> str:
    """Append the product CTA to *desc* unless already present."""
    if _CTA_MARKER in desc:
        return desc
    return desc.rstrip() + _CTA_TEMPLATE.format(src=src, camp=camp)


def _dry_run(reason: str, video: str, title: str, desc: str, tags: list[str]) -> None:
    print(f"[warn] Bilibili DRY RUN ({reason}). Would post:")
    print(f"  file       : {video}")
    print(f"  title      : {title}")
    print(f"  description : {desc}")
    print(f"  tags       : {tags}")
    print(f"  tid        : {os.getenv('BILIBILI_TID', '21')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--description", default="")
    ap.add_argument("--tags", default="")
    args = ap.parse_args()
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    args.description = _append_cta(args.description, src="bilibili")

    cookies = os.getenv("BILIBILI_COOKIES")
    biliup = shutil.which("biliup")

    if not os.path.isfile(args.video) or os.path.getsize(args.video) == 0:
        _dry_run(f"video missing or empty: {args.video}", args.video, args.title, args.description, tags)
        return 0
    if not biliup or not cookies or not os.path.isfile(cookies):
        _dry_run("biliup CLI or BILIBILI_COOKIES not configured", args.video, args.title, args.description, tags)
        return 0

    cmd = [
        biliup, "--user-cookie", cookies, "upload", args.video,
        "--title", (args.title or "AI 數字人影片")[:80],
        "--desc", args.description,
        "--tid", os.getenv("BILIBILI_TID", "21"),
    ]
    if tags:
        cmd += ["--tag", ",".join(tags)]
    try:
        subprocess.run(cmd, check=True)
        print("[ok] Bilibili upload submitted via biliup.")
        return 0
    except Exception as e:  # noqa: BLE001
        _dry_run(f"biliup error: {e}", args.video, args.title, args.description, tags)
        return 0


if __name__ == "__main__":
    sys.exit(main())
