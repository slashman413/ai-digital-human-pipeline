"""Assemble a dreamscape-style ambient music video.

Fetches dark dreamscape images (Pollinations), gives each a slow smooth Ken Burns
move, crossfades between them, overlays a small spaced lowercase title, and muxes
a music track — trimmed to the music length with a gentle audio fade-out. 1080p.

CLI: --music output/music.mp3 --prompts-file prompts.txt --title "first snow"
     --output output/video.mp4 [--font "Noto Sans CJK TC" | --fontfile C:/Windows/Fonts/...]
prompts-file: one image prompt per line.
"""
from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request

W, H, FPS = 1920, 1080, 30
STYLE = ("dark moody atmospheric, deep teal and blue color grade, misty, cinematic, "
         "melancholic, film grain, lonely, dreamy, highly detailed, no text, no watermark")


def fetch_image(prompt: str, path: str, seed: int) -> bool:
    full = f"{prompt}, {STYLE}"
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full) +
           f"?width={W}&height={H}&nologo=true&enhance=true&model=flux&seed={seed}")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) > 5000:
                with open(path, "wb") as fh:
                    fh.write(data)
                return True
        except Exception as e:  # noqa: BLE001
            print(f"[img] attempt {attempt + 1} failed ({e})")
            time.sleep(3)
    return False


def ffprobe_duration(path: str) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, check=True)
        return float(out.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def loop_audio(src: str, out: str, target: float, xfade: float = 3.0) -> str:
    """Seamlessly loop a short clip up to `target` seconds via crossfades (cost saver:
    generate ~30s once, loop it instead of paying for long generation)."""
    import math
    L = ffprobe_duration(src)
    if L <= 0 or target <= L + 1:
        return src
    n = max(2, math.ceil((target - xfade) / max(1.0, L - xfade)))
    inputs: list[str] = []
    for _ in range(n):
        inputs += ["-i", src]
    fc, prev = [], "0:a"
    for i in range(1, n):
        lbl = f"a{i}"
        fc.append(f"[{prev}][{i}:a]acrossfade=d={xfade}:c1=tri:c2=tri[{lbl}]")
        prev = lbl
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
                    "-map", f"[{prev}]", "-t", f"{target}", out], check=True, capture_output=True)
    print(f"[mv] looped music {L:.0f}s x{n} -> {target:.0f}s")
    return out


def ken_burns_segment(img: str, out: str, dur: float, zoom_in: bool) -> None:
    """Render one slow, smooth Ken Burns clip. Pre-upscale keeps the zoom sub-pixel smooth."""
    frames = max(1, int(dur * FPS))
    # zoom from 1.0->1.10 (in) or 1.10->1.0 (out); tiny per-frame step = smooth, no jitter
    if zoom_in:
        z = f"1.0+0.10*on/{frames}"
    else:
        z = f"1.10-0.10*on/{frames}"
    vf = (
        f"scale={W*2}:{H*2}:flags=lanczos,"
        f"zoompan=z='{z}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={W}x{H}:fps={FPS},format=yuv420p"
    )
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", img, "-t", f"{dur}",
                    "-vf", vf, "-r", str(FPS), "-an", out], check=True, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", required=True)
    ap.add_argument("--prompts-file", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--output", default="output/video.mp4")
    ap.add_argument("--workdir", default="build_mv")
    ap.add_argument("--font", default="")          # fontconfig name (runner)
    ap.add_argument("--fontfile", default="")       # explicit file (Windows)
    ap.add_argument("--xfade", type=float, default=2.5)
    ap.add_argument("--loop-to", type=float, default=0,
                    help="if music is shorter than this many seconds, seamlessly loop it up to it")
    ap.add_argument("--snow", default="",
                    help="path to a tall snow texture PNG; overlaid as gentle falling snow")
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    music_dur = ffprobe_duration(args.music)
    if music_dur < 5:
        print(f"[mv] ERROR: music too short/invalid ({music_dur}s)")
        return 1
    if args.loop_to and args.loop_to > music_dur + 1:
        looped = os.path.join(args.workdir, "music_looped.mp3")
        args.music = loop_audio(args.music, looped, args.loop_to)
        music_dur = ffprobe_duration(args.music)

    prompts = [ln.strip() for ln in open(args.prompts_file, encoding="utf-8") if ln.strip()]
    if not prompts:
        prompts = ["lone cabin glowing windows on a snowy hill at night, faint aurora"]
    n = len(prompts)

    # each image visible for seg_dur; segments overlap by xfade so total == music_dur
    xf = args.xfade
    seg_dur = (music_dur + xf * (n - 1)) / n
    seg_dur = max(seg_dur, xf + 2)

    rng = random.Random(7)
    segs = []
    for i, p in enumerate(prompts):
        img = os.path.join(args.workdir, f"img_{i:02d}.jpg")
        if not fetch_image(p, img, seed=100 + i * 7):
            print(f"[mv] image {i} failed; skipping")
            continue
        seg = os.path.join(args.workdir, f"seg_{i:02d}.mp4")
        ken_burns_segment(img, seg, seg_dur, zoom_in=(i % 2 == 0))
        segs.append(seg)
        print(f"[mv] segment {i:02d} ({seg_dur:.1f}s)")
    if not segs:
        print("[mv] ERROR: no segments")
        return 1

    # crossfade-chain the segments
    silent = os.path.join(args.workdir, "video_silent.mp4")
    if len(segs) == 1:
        subprocess.run(["ffmpeg", "-y", "-i", segs[0], "-an", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", silent], check=True, capture_output=True)
    else:
        inputs = []
        for s in segs:
            inputs += ["-i", s]
        fc, prev, offset = [], "0:v", 0.0
        for i in range(1, len(segs)):
            offset += seg_dur - xf
            out = f"v{i}"
            trans = rng.choice(["fade", "dissolve", "fadeblack"])
            fc.append(f"[{prev}][{i}:v]xfade=transition={trans}:duration={xf}:offset={offset:.3f}[{out}]")
            prev = out
        subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
                        "-map", f"[{prev}]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-r", str(FPS), silent], check=True, capture_output=True)

    # title overlay (small, spaced, lowercase, centered)
    draw = None
    if args.title:
        spaced = "  ".join(list(args.title.strip()))  # letter spacing between chars
        if args.fontfile:
            fontpath = args.fontfile.replace("\\", "/").replace(":", "\\:")
            font = f"fontfile='{fontpath}'"
        elif args.font:
            font = f"font='{args.font}'"
        else:
            font = "font='sans'"
        txt = spaced.replace("'", "").replace(":", "\\:")
        draw = (f"drawtext={font}:text='{txt}':fontcolor=white@0.82:fontsize=34:"
                f"x=(w-text_w)/2:y=(h-text_h)/2:shadowcolor=black@0.4:shadowx=1:shadowy=1")

    fade_start = max(0.0, music_dur - 4)
    afilter = f"afade=t=out:st={fade_start:.2f}:d=4"
    has_snow = bool(args.snow and os.path.isfile(args.snow))

    if has_snow:
        # gentle falling snow: tile the texture 2x vertically so the downward scroll loops seamlessly
        chain = ("[1:v]split=2[sa][sb];[sa][sb]vstack=inputs=2[snow];"
                 "[0:v][snow]overlay=0:'mod(t*90,2400)-2400':eof_action=pass[vo]")
        chain += f";[vo]{draw}[v]" if draw else ";[vo]copy[v]"
        cmd = ["ffmpeg", "-y", "-i", silent, "-loop", "1", "-i", args.snow, "-i", args.music,
               "-filter_complex", chain, "-map", "[v]", "-map", "2:a",
               "-af", afilter, "-shortest", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
               "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", args.output]
    else:
        cmd = ["ffmpeg", "-y", "-i", silent, "-i", args.music]
        if draw:
            cmd += ["-vf", draw]
        cmd += ["-af", afilter, "-shortest", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", args.output]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"[mv] wrote {args.output}: {ffprobe_duration(args.output):.1f}s @ {W}x{H}/{FPS}fps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
