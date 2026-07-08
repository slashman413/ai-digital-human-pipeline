"""For each scene: synthesize voice (edge-tts) + fetch a matching background
image (Pollinations.ai, free/no-key), and record the audio duration.

Reads scenes.json (from generate_longform.py), writes <workdir>/manifest.json:
  { "title": str, "fps": int, "width": int, "height": int,
    "scenes": [ {"audio","image","duration","subtitle"} , ... ] }

CLI: --scenes scenes.json --voice <edge voice> --workdir build
     --width 854 --height 480

Image provider: Pollinations by default (https://image.pollinations.ai). No key.
Override base via env IMAGE_BASE_URL if you later swap in another service.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "https://image.pollinations.ai/prompt/")
STYLE_SUFFIX = (
    ", photorealistic, ultra-realistic professional photograph, DSLR photo, "
    "high resolution, sharp focus, fine detail, natural lighting, 16:9, "
    "no text, no caption, no watermark, no illustration, not a drawing"
)


def ffprobe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, check=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return 4.0  # safe fallback


def ffprobe_duration_strict(path: str) -> float:
    """Like ffprobe_duration but returns 0.0 (not a fallback) on any error —
    used to detect a corrupt/empty audio file that must be regenerated."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, check=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return 0.0


async def tts(text: str, voice: str, out_path: str) -> None:
    import edge_tts

    # strip non-spoken markers
    clean = "\n".join(
        ln for ln in text.splitlines()
        if not ln.strip().startswith(("【", "（", "("))
    ).strip() or text
    await edge_tts.Communicate(clean, voice).save(out_path)


def fetch_image(prompt: str, out_path: str, width: int, height: int, seed: int) -> bool:
    url = (IMAGE_BASE_URL + urllib.parse.quote(prompt + STYLE_SUFFIX)
           + f"?width={width}&height={height}&nologo=true&enhance=true&model=flux&seed={seed}")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "digital-human-pipeline"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) > 1000:
                with open(out_path, "wb") as fh:
                    fh.write(data)
                return True
        except Exception as e:  # noqa: BLE001
            print(f"[warn] image fetch attempt {attempt + 1} failed: {e}")
            time.sleep(3)
    return False


def placeholder_image(out_path: str, width: int, height: int, idx: int) -> None:
    color = ["0x1f2937", "0x374151", "0x4b5563", "0x111827"][idx % 4]
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    f"color=c={color}:s={width}x{height}", "-frames:v", "1", out_path],
                   capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="scenes.json")
    ap.add_argument("--voice", default="zh-TW-HsiaoChenNeural")
    ap.add_argument("--workdir", default="build")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--reuse-images-from", default="",
                    help="reuse img_NN.jpg from this dir (e.g. the zh build) instead of generating")
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    with open(args.scenes, encoding="utf-8") as fh:
        data = json.load(fh)
    scenes = data["scenes"]

    manifest_scenes = []
    for i, sc in enumerate(scenes):
        audio = os.path.join(args.workdir, f"audio_{i:02d}.mp3")
        image = os.path.join(args.workdir, f"img_{i:02d}.jpg")
        narration = sc.get("narration", "").strip()
        # TTS with validation + retry (edge-tts can write a corrupt/empty mp3 without raising)
        audio_ready = False
        for attempt in range(3):
            try:
                if os.path.isfile(audio):
                    os.remove(audio)
                asyncio.run(tts(narration, args.voice, audio))
                if os.path.isfile(audio) and os.path.getsize(audio) > 1200 and ffprobe_duration_strict(audio) > 0.3:
                    audio_ready = True
                    break
                print(f"[warn] scene {i} TTS produced invalid audio (attempt {attempt + 1}); retrying.")
            except Exception as e:  # noqa: BLE001
                print(f"[warn] TTS attempt {attempt + 1} scene {i} failed ({e}).")
            time.sleep(2)
        if not audio_ready:
            print(f"[warn] scene {i} audio still invalid; using silent fallback.")
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                            "anullsrc=r=24000:cl=mono", "-t", "6", audio], capture_output=True)
        reuse_src = os.path.join(args.reuse_images_from, f"img_{i:02d}.jpg") if args.reuse_images_from else ""
        if reuse_src and os.path.isfile(reuse_src) and os.path.getsize(reuse_src) > 1000:
            import shutil
            shutil.copyfile(reuse_src, image)
            print(f"[reuse] scene {i} image from {reuse_src}")
        elif not fetch_image(sc.get("image_prompt", "abstract background"), image,
                             args.width, args.height, seed=1000 + i):
            print(f"[warn] image gen failed on scene {i}; using placeholder.")
            placeholder_image(image, args.width, args.height, i)
        dur = ffprobe_duration(audio)
        manifest_scenes.append({"audio": audio, "image": image,
                                "duration": round(dur, 3), "subtitle": narration})
        print(f"[ok] scene {i:02d}: {dur:.1f}s  img={os.path.basename(image)}")

    manifest = {"title": data.get("title", "AI 影片"), "fps": 30,
                "width": args.width, "height": args.height, "scenes": manifest_scenes}
    mpath = os.path.join(args.workdir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    total = sum(s["duration"] for s in manifest_scenes)
    print(f"[ok] wrote {mpath}: {len(manifest_scenes)} scenes, total {total:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
