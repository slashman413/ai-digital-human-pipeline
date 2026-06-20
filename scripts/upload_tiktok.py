"""Publish a video to TikTok via the Content Posting API.

CLI (shared contract with the other uploaders):
    --video <path> --title <str> --description <str> --tags <comma-separated>

Auth: set TIKTOK_ACCESS_TOKEN (an OAuth user access token with
`video.publish` scope). Optionally TIKTOK_PRIVACY (default SELF_ONLY while you
test; use PUBLIC_TO_EVERYONE to go live).

If the token is missing, the libs are unavailable, or the video file is
missing/empty, it does a DRY RUN (prints what it would post) and exits 0 —
never crashes the pipeline.
"""
from __future__ import annotations

import argparse
import os
import sys

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"


def _dry_run(reason: str, video: str, title: str, desc: str, tags: list[str]) -> None:
    print(f"[warn] TikTok DRY RUN ({reason}). Would post:")
    print(f"  file       : {video}")
    print(f"  title      : {title}")
    print(f"  description : {desc}")
    print(f"  tags       : {tags}")
    print(f"  privacy    : {os.getenv('TIKTOK_PRIVACY', 'SELF_ONLY')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--description", default="")
    ap.add_argument("--tags", default="")
    args = ap.parse_args()
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    token = os.getenv("TIKTOK_ACCESS_TOKEN")
    if not token:
        _dry_run("missing TIKTOK_ACCESS_TOKEN", args.video, args.title, args.description, tags)
        return 0
    if not os.path.isfile(args.video) or os.path.getsize(args.video) == 0:
        _dry_run(f"video missing or empty: {args.video}", args.video, args.title, args.description, tags)
        return 0

    try:
        import requests
    except ImportError:
        _dry_run("requests not installed", args.video, args.title, args.description, tags)
        return 0

    size = os.path.getsize(args.video)
    caption = (args.title + "\n" + args.description).strip()
    try:
        # 1) init a direct-post upload (single chunk)
        init = requests.post(
            INIT_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {
                    "title": caption,
                    "privacy_level": os.getenv("TIKTOK_PRIVACY", "SELF_ONLY"),
                    "disable_comment": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": size,
                    "total_chunk_count": 1,
                },
            },
            timeout=60,
        )
        init.raise_for_status()
        data = init.json()["data"]
        upload_url = data["upload_url"]

        # 2) PUT the file bytes to the returned upload URL
        with open(args.video, "rb") as fh:
            put = requests.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes 0-{size - 1}/{size}",
                },
                data=fh,
                timeout=300,
            )
        put.raise_for_status()
        print(f"[ok] TikTok upload submitted. publish_id={data.get('publish_id')}")
        return 0
    except Exception as e:  # noqa: BLE001 — never hard-fail the pipeline
        _dry_run(f"API error: {e}", args.video, args.title, args.description, tags)
        return 0


if __name__ == "__main__":
    sys.exit(main())
