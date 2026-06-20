"""Assemble scene segments into one 480p@30fps video with:
  - Ken Burns motion (slow zoom in/out + center pan) on each still background
  - Crossfade transitions between scenes (xfade + acrossfade)
  - Time-synced burned-in subtitles (timeline adjusted for transition overlaps)

Reads <workdir>/manifest.json (from generate_scene_assets.py).

CLI: --manifest build/manifest.json --output output/final_video.mp4
     --fps 30 --transition 0.6 --font "Noto Sans CJK TC"
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import re
import sys


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-1500:])
        raise SystemExit(f"ffmpeg failed: {cmd[:6]} ...")


def srt_time(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


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
            cues.append((ct, min(ct + cd, win_end), c))
            ct += cd
    with open(path, "w", encoding="utf-8") as fh:
        for i, (a, b, txt) in enumerate(cues, 1):
            fh.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n\n")


def kenburns_vf(idx: int, frames: int, w: int, h: int, fps: int) -> str:
    """Alternate slow zoom-in / zoom-out, centered. Pre-upscale for smoothness."""
    rate = 0.16 / max(frames, 1)
    if idx % 2 == 0:
        z = f"min(1.0+{rate:.6f}*on,1.16)"
    else:
        z = f"max(1.16-{rate:.6f}*on,1.0)"
    return (
        f"scale={w*2}:{h*2},"
        f"zoompan=z='{z}':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},"
        f"setsar=1"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="build/manifest.json")
    ap.add_argument("--output", default="output/final_video.mp4")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--transition", type=float, default=0.6)
    ap.add_argument("--font", default="Noto Sans CJK TC")
    args = ap.parse_args()

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

    # 1) per-scene segment with Ken Burns motion
    seg_paths = []
    for i, sc in enumerate(scenes):
        d = float(sc["duration"])
        seg = os.path.join(workdir, f"seg_{i:02d}.mp4")
        frames = int(round(d * fps)) + fps  # a little extra so zoompan covers full audio
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", sc["image"], "-i", sc["audio"],
            "-filter_complex", f"[0:v]{kenburns_vf(i, frames, w, h, fps)}[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), "-t", f"{d:.3f}",
            "-c:a", "aac", "-b:a", "128k", "-shortest", seg,
        ])
        seg_paths.append(seg)
        print(f"[ok] segment {i:02d} (kenburns {'in' if i%2==0 else 'out'})")

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
            vchain.append(f"{vprev}[{i}:v]xfade=transition=fade:duration={T}:offset={offset:.3f}{vout}")
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
          f"kenburns+xfade(T={T}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
