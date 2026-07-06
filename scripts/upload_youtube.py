#!/usr/bin/env python3
"""Upload a video to YouTube via OAuth refresh-token flow.

Dry-runs (exit 0) when any required env var is missing or the video file is
missing/empty, so CI never crashes.
"""
import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Product CTA — appended once to every description (idempotent).
# {SRC} = upload platform slug, {CAMP} = campaign name.
# ---------------------------------------------------------------------------
_CTA_MARKER = "slashman413-cta-v1"
_CTA_TEMPLATE = (
    "\n\n"
    "🛠 SaaS Starter — ship a multi-tenant SaaS this weekend:\n"
    "https://slashmaster6.gumroad.com/l/kuvajr"
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
    parser.add_argument("--playlist", default="", help="playlist ID to add the uploaded video to")
    parser.add_argument("--channel-id", default="", help="channel ID — appends a subscribe CTA to the description")
    parser.add_argument("--affiliate", default="", help="affiliate recommendation line appended to the description")
    parser.add_argument("--kofi", default="", help="Ko-fi support URL — appends a support line to the description")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    desc = _append_cta(args.description.rstrip(), src="youtube")

    # C: place the Amazon affiliate recommendation near the TOP (visible in the collapsed
    # description = far more clicks) right after the hook line, with the required disclosure.
    if args.affiliate:
        aff = args.affiliate + "\n（廣告/含 Amazon 聯盟連結 · As an Amazon Associate I earn from qualifying purchases.）"
        parts = desc.split("\n", 1)
        desc = parts[0] + "\n\n" + aff + ("\n\n" + parts[1] if len(parts) == 2 else "")

    # A3: subscribe + playlist link-drive at the bottom
    cta = []
    if args.channel_id:
        cta.append(f"▶ 訂閱 Subscribe: https://www.youtube.com/channel/{args.channel_id}?sub_confirmation=1")
    if args.playlist:
        cta.append(f"🎵 播放清單 Playlist: https://www.youtube.com/playlist?list={args.playlist}")
    if args.kofi:
        cta.append(f"☕ 支持頻道 Support us: {args.kofi}")
    if cta:
        desc = desc + "\n\n" + "\n".join(cta)
    args.description = desc

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

    # A1: add the video to a playlist (needs youtube.force-ssl scope)
    if args.playlist:
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={"snippet": {"playlistId": args.playlist,
                                  "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
            ).execute()
            print(f"[ok] added to playlist: {args.playlist}")
        except Exception as exc:  # noqa: BLE001 — non-fatal
            print(f"[warn] playlist add failed: {exc}")


if __name__ == "__main__":
    main()
