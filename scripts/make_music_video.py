"""Assemble a serene nature meditation music video.

Fetches calm nature images (Pollinations), gives each a slow smooth Ken Burns
move, crossfades between them, overlays a small spaced lowercase title, optionally
mixes a real water+birdsong ambience under the piano, and muxes the music track —
trimmed to the music length with a gentle audio fade-out. 1080p.

CLI: --music output/music.wav --prompts-file prompts.txt --title "morning lake"
     --output output/video.mp4 [--nature assets/nature.mp3]
     [--font "Noto Sans CJK TC" | --fontfile C:/Windows/Fonts/...]
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
STYLE = ("serene peaceful nature, soft natural morning light, calm and tranquil, "
         "lush greens and gentle warm tones, light mist, cinematic, dreamy, soothing, "
         "highly detailed, no text, no watermark")


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
    global W, H
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", required=True)
    ap.add_argument("--prompts-file", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--output", default="output/video.mp4")
    ap.add_argument("--workdir", default="build_mv")
    ap.add_argument("--font", default="")          # fontconfig name (runner)
    ap.add_argument("--fontfile", default="")       # explicit file (Windows)
    ap.add_argument("--xfade", type=float, default=2.5)
    ap.add_argument("--seg-seconds", type=float, default=25.0,
                    help="target seconds each scene is shown before crossfading (transition cadence)")
    ap.add_argument("--end-fade", type=float, default=4.0,
                    help="seconds of audio fade-out at the very end (0 = none, for a seamless loop base)")
    ap.add_argument("--width", type=int, default=W, help="output width (use 1080 for a 9:16 Short)")
    ap.add_argument("--height", type=int, default=H, help="output height (use 1920 for a 9:16 Short)")
    ap.add_argument("--loop-to", type=float, default=0,
                    help="if music is shorter than this many seconds, seamlessly loop it up to it")
    ap.add_argument("--snow", default="",
                    help="path to a tall snow texture PNG; overlaid as gentle falling snow")
    ap.add_argument("--nature", default="",
                    help="path to a nature ambience clip (water+birds); looped and mixed under the music")
    ap.add_argument("--nature-volume", type=float, default=0.75,
                    help="volume of the nature ambience in the mix (water/birds audibility)")
    ap.add_argument("--music-volume", type=float, default=0.8,
                    help="volume of the music in the mix")
    args = ap.parse_args()

    W, H = args.width, args.height  # supports vertical 9:16 Shorts (1080x1920)

    os.makedirs(args.workdir, exist_ok=True)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    music_dur = ffprobe_duration(args.music)
    if music_dur < 5:
        print(f"[mv] ERROR: music too short/invalid ({music_dur}s)")
        return 1
    if args.loop_to and args.loop_to > music_dur + 1:
        looped = os.path.join(args.workdir, "music_looped.wav")  # lossless intermediate
        args.music = loop_audio(args.music, looped, args.loop_to)
        music_dur = ffprobe_duration(args.music)

    # mix real water+birdsong ambience under the piano (looped to full length, kept quieter)
    if args.nature and os.path.isfile(args.nature):
        mixed = os.path.join(args.workdir, "music_nature.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", args.music, "-stream_loop", "-1", "-i", args.nature,
             "-filter_complex",
             f"[0:a]volume={args.music_volume}[m];[1:a]volume={args.nature_volume},afade=t=in:st=0:d=2[n];"
             "[m][n]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
             "-map", "[a]", "-t", f"{music_dur}", mixed], check=True, capture_output=True)
        args.music = mixed
        print(f"[mv] mixed nature ambience '{os.path.basename(args.nature)}' "
              f"(music={args.music_volume}, nature={args.nature_volume}) under music")

    prompts = [ln.strip() for ln in open(args.prompts_file, encoding="utf-8") if ln.strip()]
    if not prompts:
        prompts = ["calm misty lake at sunrise, soft golden light, gentle reflections"]

    # fetch one image per unique prompt (cheap; reused across segments below)
    images = []
    for i, p in enumerate(prompts):
        img = os.path.join(args.workdir, f"img_{i:02d}.jpg")
        if os.path.exists(img) and os.path.getsize(img) > 5000:
            images.append(img)  # reuse (retry / local re-run); CI workdir is always fresh
        elif fetch_image(p, img, seed=100 + i * 7):
            images.append(img)
        else:
            print(f"[mv] image {i} failed; skipping")
    if not images:
        print("[mv] ERROR: no images")
        return 1

    # transition cadence is driven by --seg-seconds (not image count), so a 20-min track
    # gets a cut every ~25s instead of 10 huge 2-min scenes. Images are cycled to fill.
    xf = args.xfade
    target = max(args.seg_seconds, xf + 4)
    # cadence drives the count (not image count); short clips use a subset, long ones cycle
    num_seg = max(2, round((music_dur - xf) / max(1.0, target - xf)))
    seg_dur = (music_dur + xf * (num_seg - 1)) / num_seg
    seg_dur = max(seg_dur, xf + 2)

    segs = []
    for i in range(num_seg):
        img = images[i % len(images)]
        seg = os.path.join(args.workdir, f"seg_{i:03d}.mp4")
        ken_burns_segment(img, seg, seg_dur, zoom_in=(i % 2 == 0))
        segs.append(seg)
    print(f"[mv] {num_seg} scenes x {seg_dur:.1f}s (cadence ~{seg_dur - xf:.0f}s) from {len(images)} images")
    if not segs:
        print("[mv] ERROR: no segments")
        return 1
    rng = random.Random(7)

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

    if args.end_fade and args.end_fade > 0:
        fade_start = max(0.0, music_dur - args.end_fade)
        afilter = f"afade=t=out:st={fade_start:.2f}:d={args.end_fade}"
    else:
        afilter = "anull"  # seamless loop base: no end fade
    has_snow = bool(args.snow and os.path.isfile(args.snow))

    if has_snow:
        # gentle falling snow: tile the texture 2x vertically so the downward scroll loops seamlessly
        chain = ("[1:v]split=2[sa][sb];[sa][sb]vstack=inputs=2[snow];"
                 "[0:v][snow]overlay=0:'mod(t*90,2400)-2400':eof_action=pass[vo]")
        chain += f";[vo]{draw}[v]" if draw else ";[vo]copy[v]"
        cmd = ["ffmpeg", "-y", "-i", silent, "-loop", "1", "-i", args.snow, "-i", args.music,
               "-filter_complex", chain, "-map", "[v]", "-map", "2:a",
               "-af", afilter, "-shortest", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
               "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-pix_fmt", "yuv420p", args.output]
    else:
        cmd = ["ffmpeg", "-y", "-i", silent, "-i", args.music]
        if draw:
            cmd += ["-vf", draw]
        cmd += ["-af", afilter, "-shortest", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-pix_fmt", "yuv420p", args.output]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"[mv] wrote {args.output}: {ffprobe_duration(args.output):.1f}s @ {W}x{H}/{FPS}fps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
