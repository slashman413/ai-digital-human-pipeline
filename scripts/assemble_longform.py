"""Assemble scene segments into one 480p video with:
  - Static backgrounds (no Ken Burns / zoom — that caused visible jitter)
  - A RANDOM, natural transition between every scene (xfade + acrossfade)
  - Time-synced burned-in subtitles (timeline adjusted for transition overlaps)

Reads <workdir>/manifest.json (from generate_scene_assets.py).

CLI: --manifest build/manifest.json --output output/final_video.mp4
     --fps 15 --transition 0.8 --font "Noto Sans CJK TC" --seed 0
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import re
import sys

# Natural, non-gimmicky xfade transitions to pick from at random.
TRANSITIONS = [
    "fade", "dissolve", "fadeblack",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "circleopen", "radial",
]


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-1500:])
        raise SystemExit(f"ffmpeg failed: {cmd[:6]} ...")


def srt_time(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# Subtitles must show NO punctuation. Pause marks become a space; the rest drop.
_PUNCT_TO_SPACE = "，、,;；"
_PUNCT_DROP = "。.！!？?：:…—–~「」『』（）()【】《》〈〉\"'`·．,।"


def strip_punct(s: str) -> str:
    out = []
    for ch in s:
        if ch in _PUNCT_TO_SPACE:
            out.append(" ")
        elif ch in _PUNCT_DROP:
            continue
        else:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def split_chunks(text: str, max_len: int = 20) -> list[str]:
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


def build_srt(scenes: list[dict], starts: list[float], total: float, path: str) -> None:
    """starts[i] = scene i start time in the crossfaded timeline."""
    cues = []
    for i, sc in enumerate(scenes):
        win_start = starts[i]
        win_end = starts[i + 1] if i + 1 < len(starts) else total
        text = sc.get("subtitle", "").strip()
        chunks = split_chunks(text)
        total_chars = sum(len(c) for c in chunks) or 1
        ct = win_start
        span = max(win_end - win_start, 0.5)
        for c in chunks:
            cd = span * (len(c) / total_chars)
            disp = strip_punct(c)  # timing from original length; display without punctuation
            if disp:
                cues.append((ct, min(ct + cd, win_end), disp))
            ct += cd
    with open(path, "w", encoding="utf-8") as fh:
        for i, (a, b, txt) in enumerate(cues, 1):
            fh.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="build/manifest.json")
    ap.add_argument("--output", default="output/final_video.mp4")
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--transition", type=float, default=0.8)
    ap.add_argument("--font", default="Noto Sans CJK TC")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    with open(args.manifest, encoding="utf-8") as fh:
        m = json.load(fh)
    scenes = m["scenes"]
    w, h, fps = m.get("width", 854), m.get("height", 480), args.fps
    T = args.transition
    workdir = os.path.dirname(args.manifest) or "."
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    n = len(scenes)
    # transition can't exceed any scene; clamp
    min_dur = min(float(s["duration"]) for s in scenes)
    if T > min_dur / 2:
        T = round(max(0.2, min_dur / 3), 2)

    # 1) per-scene segment: STATIC background (no zoom/jitter), scaled to WxH@fps
    seg_paths = []
    for i, sc in enumerate(scenes):
        d = float(sc["duration"])
        seg = os.path.join(workdir, f"seg_{i:02d}.mp4")
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", sc["image"], "-i", sc["audio"],
            "-vf", f"scale={w}:{h},fps={fps},setsar=1,format=yuv420p",
            "-c:v", "libx264", "-tune", "stillimage", "-r", str(fps), "-t", f"{d:.3f}",
            "-c:a", "aac", "-b:a", "128k", "-shortest", seg,
        ])
        seg_paths.append(seg)
        print(f"[ok] segment {i:02d} (static)")

    # scene start times in the crossfaded timeline + total duration
    durs = [float(s["duration"]) for s in scenes]
    starts = [0.0]
    for i in range(1, n):
        starts.append(sum(durs[:i]) - i * T)
    total = sum(durs) - (n - 1) * T if n > 1 else durs[0]

    srt = os.path.join(workdir, "subs.srt")
    build_srt(scenes, starts, total, srt)
    srt_ff = srt.replace("\\", "/").replace(":", "\\:")
    style = f"FontName={args.font},FontSize=22,PrimaryColour=&H00FFFFFF,Outline=2,Shadow=1,MarginV=30"

    # 2) crossfade all segments (video xfade + audio acrossfade), then burn subtitles
    if n == 1:
        run(["ffmpeg", "-y", "-i", seg_paths[0],
             "-vf", f"subtitles='{srt_ff}':charenc=UTF-8:force_style='{style}'",
             "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "copy", args.output])
    else:
        inputs = []
        for p in seg_paths:
            inputs += ["-i", p]
        vchain, achain = [], []
        vprev, aprev = "[0:v]", "[0:a]"
        for i in range(1, n):
            offset = sum(durs[:i]) - i * T
            vout = f"[vx{i}]"
            aout = f"[ax{i}]"
            trans = rng.choice(TRANSITIONS)  # random, natural transition per switch
            vchain.append(f"{vprev}[{i}:v]xfade=transition={trans}:duration={T}:offset={offset:.3f}{vout}")
            achain.append(f"{aprev}[{i}:a]acrossfade=d={T}{aout}")
            vprev, aprev = vout, aout
        # burn subtitles on the final crossfaded video
        vchain.append(f"{vprev}subtitles='{srt_ff}':charenc=UTF-8:force_style='{style}'[vout]")
        fc = ";".join(vchain + achain)
        run([
            "ffmpeg", "-y", *inputs,
            "-filter_complex", fc,
            "-map", "[vout]", "-map", aprev,
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", args.output,
        ])
    print(f"[ok] wrote {args.output}: {n} scenes, ~{total:.0f}s @ {w}x{h}/{fps}fps, "
          f"static bg + random transitions (T={T}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
