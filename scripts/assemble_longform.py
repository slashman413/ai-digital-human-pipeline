"""Assemble scene segments into one 480p@30fps video with switching backgrounds
and time-synced subtitles.

Reads <workdir>/manifest.json (from generate_scene_assets.py). For each scene it
builds a segment (its image, shown for the scene's audio duration), concatenates
all segments, then burns a subtitle track derived from per-scene narration timing.

CLI: --manifest build/manifest.json --output output/final_video.mp4
     --fps 30 --font "Noto Sans CJK TC"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def srt_time(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def split_chunks(text: str, max_len: int = 20) -> list[str]:
    # split on Chinese/ASCII sentence punctuation, then pack to <= max_len
    parts = re.split(r"(?<=[。！？!?，,、；;])", text)
    chunks, cur = [], ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) <= max_len:
            cur += p
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks or [text]


def build_srt(scenes: list[dict], path: str) -> None:
    cues = []
    t = 0.0
    for sc in scenes:
        dur = float(sc["duration"])
        text = sc.get("subtitle", "").strip()
        chunks = split_chunks(text)
        total_chars = sum(len(c) for c in chunks) or 1
        ct = t
        for c in chunks:
            cd = dur * (len(c) / total_chars)
            cues.append((ct, ct + cd, c))
            ct += cd
        t += dur
    with open(path, "w", encoding="utf-8") as fh:
        for i, (a, b, txt) in enumerate(cues, 1):
            fh.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="build/manifest.json")
    ap.add_argument("--output", default="output/final_video.mp4")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--font", default="Noto Sans CJK TC")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as fh:
        m = json.load(fh)
    scenes = m["scenes"]
    w, h, fps = m.get("width", 854), m.get("height", 480), args.fps
    workdir = os.path.dirname(args.manifest) or "."
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    # 1) per-scene segment: image looped for its audio duration, scaled to WxH@fps
    seg_paths = []
    for i, sc in enumerate(scenes):
        seg = os.path.join(workdir, f"seg_{i:02d}.mp4")
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", sc["image"], "-i", sc["audio"],
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-vf", f"scale={w}:{h},fps={fps}",
            "-c:a", "aac", "-b:a", "128k", "-shortest", seg,
        ])
        seg_paths.append(os.path.abspath(seg))
        print(f"[ok] segment {i:02d}")

    # 2) concat all segments
    listfile = os.path.join(workdir, "segments.txt")
    with open(listfile, "w", encoding="utf-8") as fh:
        for p in seg_paths:
            fh.write(f"file '{p}'\n")
    combined = os.path.join(workdir, "combined.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", combined])

    # 3) burn synced subtitles
    srt = os.path.join(workdir, "subs.srt")
    build_srt(scenes, srt)
    srt_ff = srt.replace("\\", "/").replace(":", "\\:")
    style = f"FontName={args.font},FontSize=22,PrimaryColour=&H00FFFFFF,Outline=2,Shadow=1,MarginV=30"
    run([
        "ffmpeg", "-y", "-i", combined,
        "-vf", f"subtitles='{srt_ff}':charenc=UTF-8:force_style='{style}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy", args.output,
    ])
    total = sum(float(s["duration"]) for s in scenes)
    print(f"[ok] wrote {args.output}: {len(scenes)} scenes, ~{total:.0f}s @ {w}x{h}/{fps}fps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
