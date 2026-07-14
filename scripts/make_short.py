"""Cut a ~20s vertical (9:16) teaser Short from the long-form video.

Takes the landscape long video, extracts a segment, reframes to 1080x1920 with a
blurred fill background (so nothing is cropped away), and overlays a small
"完整版 ▶ YouTube" hint. Output is a Shorts-ready clip; the full-video link goes
in the upload description (see the workflow).

CLI: --video output/final_video.mp4 --output output/short.mp4
     --start 0 --duration 20 --font "Noto Sans CJK TC"
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-1500:])
        raise SystemExit("ffmpeg failed")


def probe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, check=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--output", default="output/short.mp4")
    ap.add_argument("--start", type=float, default=-1, help="start sec; -1 = auto (t=0, the cold-open hook)")
    ap.add_argument("--duration", type=float, default=20)
    ap.add_argument("--font", default="Noto Sans CJK TC", help="fontconfig name (Linux/runner)")
    ap.add_argument("--fontfile", default="", help="path to a .ttf/.ttc (use on Windows where fontconfig is absent)")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    total = probe_duration(args.video)
    start = args.start
    if start < 0:
        # Scene 1 is written as a self-contained loopable hook (see
        # generate_longform.py) — cut the Short from t=0 to use it.
        start = 0.0
    dur = min(args.duration, max(5.0, total - start)) if total else args.duration

    # 9:16 canvas: blurred, zoom-filled background + the full landscape frame centered;
    # a small hint banner near the bottom.
    hint = "完整版看 YouTube"
    if args.fontfile:
        ff = args.fontfile.replace("\\", "/").replace(":", "\\:")
        font_expr = f"fontfile='{ff}'"
    else:
        font_expr = f"font='{args.font}'"
    vf = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=24:6,eq=brightness=-0.08[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]drawtext=text='{hint}':{font_expr}:fontcolor=white:fontsize=46:"
        "box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=h-260[v]"
    )
    run([
        "ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", args.video,
        "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-r", "30", "-c:a", "aac", "-b:a", "128k", args.output,
    ])
    print(f"[ok] wrote {args.output}: {dur:.0f}s vertical 1080x1920 (from {start:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
