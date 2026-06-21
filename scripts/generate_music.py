"""Generate a track with Replicate MusicGen (meta/musicgen) and download it.

Used by the daily dreamscape music-video pipeline. Needs env REPLICATE_API_TOKEN.

CLI: --prompt "<style>" --duration 150 --output output/music.mp3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

API = "https://api.replicate.com/v1/predictions"
# meta/musicgen pinned version (stereo-large, mp3 output supported)
MUSICGEN_VERSION = "671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb"


def _req(url: str, token: str, data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def generate(prompt: str, duration: int, out_path: str, token: str,
             model_version: str = "stereo-large", output_format: str = "mp3") -> bool:
    payload = {
        "version": MUSICGEN_VERSION,
        "input": {
            "prompt": prompt,
            "duration": int(duration),
            "model_version": model_version,
            "output_format": output_format,
            "normalization_strategy": "loudness",
        },
    }
    pred = _req(API, token, payload)
    get_url = pred["urls"]["get"]
    print(f"[music] prediction {pred['id']} ({duration}s) ...")
    for _ in range(120):  # up to ~12 min
        time.sleep(6)
        p = _req(get_url, token)
        st = p["status"]
        if st == "succeeded":
            out = p["output"]
            url = out[0] if isinstance(out, list) else out
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            urllib.request.urlretrieve(url, out_path)
            sz = os.path.getsize(out_path)
            print(f"[music] downloaded {sz // 1024}KB -> {out_path}")
            return sz > 5000
        if st in ("failed", "canceled"):
            print(f"[music] {st}: {p.get('error')}")
            return False
    print("[music] timed out")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--duration", type=int, default=150)
    ap.add_argument("--output", default="output/music.mp3")
    ap.add_argument("--model-version", default="stereo-large")
    ap.add_argument("--output-format", default="mp3", choices=["mp3", "wav"])
    args = ap.parse_args()
    token = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not token:
        print("[music] ERROR: REPLICATE_API_TOKEN not set")
        return 1
    ok = generate(args.prompt, args.duration, args.output, token, args.model_version, args.output_format)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
