#!/usr/bin/env python3
"""Upload a video to YouTube via OAuth refresh-token flow.

Dry-runs (exit 0) when any required env var is missing or the video file is
missing/empty, so CI never crashes.
"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Upload a video to YouTube.")
    parser.add_argument("--video", required=True, help="path to video file")
    parser.add_argument("--title", required=True, help="video title")
    parser.add_argument("--description", required=True, help="video description")
    parser.add_argument("--tags", required=True, help="comma-separated tags")
    parser.add_argument("--privacy", default="private",
                        choices=["public", "unlisted", "private"], help="privacy status")
    parser.add_argument("--url-out", default="", help="write the uploaded video URL to this file")
    parser.add_argument("--thumbnail", default="", help="path to a custom thumbnail image")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    # Determine whether we have a real, non-empty video file.
    has_video = os.path.isfile(args.video) and os.path.getsize(args.video) > 0
    has_creds = bool(client_id and client_secret and refresh_token)

    if not has_creds or not has_video:
        reasons = []
        if not has_creds:
            reasons.append("missing YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN env var(s)")
        if not has_video:
            reasons.append(f"video missing or empty: {args.video}")
        print(f"[warn] DRY RUN ({'; '.join(reasons)}). Would upload:")
        print(f"  file       : {args.video}")
        print(f"  title      : {args.title}")
        print(f"  description: {args.description}")
        print(f"  tags       : {tags}")
        print(f"  privacy    : {args.privacy}")
        print("  category   : 22")
        sys.exit(0)

    # Real upload path. Dependencies imported lazily.
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except Exception as exc:
        print(f"[warn] DRY RUN (google client libs unavailable: {exc}). Would upload:")
        print(f"  file: {args.video} | title: {args.title} | tags: {tags}")
        sys.exit(0)

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": args.title,
            "description": args.description,
            "tags": tags,
            "categoryId": "22",
        },
        "status": {"privacyStatus": args.privacy},
    }

    media = MediaFileUpload(args.video, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response.get("id")
    url = f"https://youtu.be/{video_id}"
    print(f"[ok] uploaded video id: {video_id}")
    print(f"[ok] url: {url}")
    if args.url_out:
        with open(args.url_out, "w", encoding="utf-8") as fh:
            fh.write(url)

    # set a custom thumbnail (biggest CTR lever) if provided
    if args.thumbnail and os.path.isfile(args.thumbnail) and os.path.getsize(args.thumbnail) > 0:
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(args.thumbnail)
            ).execute()
            print(f"[ok] custom thumbnail set: {args.thumbnail}")
        except Exception as exc:  # noqa: BLE001 — requires a verified channel; non-fatal
            print(f"[warn] thumbnail set failed (channel may need verification): {exc}")


if __name__ == "__main__":
    main()
