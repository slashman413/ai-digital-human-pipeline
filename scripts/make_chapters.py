"""Generate YouTube chapter timestamps from the scene manifest and append them to the
description (improves retention + SEO). YouTube needs the first stamp at 0:00, >=3 chapters.

CLI: --manifest build/manifest.json --scenes scenes.json --description description.txt
     [--lang zh|en]  (writes chapters into the description file in place)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import complete  # noqa: E402


def ts(sec: float) -> str:
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def labels(narrations: list[str], lang: str) -> list[str]:
    joined = "\n".join(f"{i}. {n[:60]}" for i, n in enumerate(narrations))
    lng = "Traditional Chinese" if lang == "zh" else "English"
    sysp = "You write concise YouTube chapter titles. Output strict JSON array of strings only."
    prompt = (f"For each numbered snippet, give a {lng} chapter title of <=6 words (catchy, "
              f"keyword-rich, no numbering). Return a JSON array of {len(narrations)} strings.\n{joined}")
    try:
        raw = complete(sysp, prompt, max_tokens=600).strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        arr = json.loads(raw[raw.find("["):raw.rfind("]") + 1])
        out = [str(x).strip() for x in arr]
        if len(out) >= len(narrations):
            return out[:len(narrations)]
    except Exception as e:  # noqa: BLE001
        print(f"[chapters] label gen failed ({e}); using fallback.")
    return [(n[:24].strip() or (f"Part {i+1}" if lang == "en" else f"段落 {i+1}"))
            for i, n in enumerate(narrations)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="build/manifest.json")
    ap.add_argument("--scenes", default="scenes.json")
    ap.add_argument("--description", default="description.txt")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--max-chapters", type=int, default=8)
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8-sig") as fh:
        scenes = json.load(fh)["scenes"]
    narrs = []
    try:
        with open(args.scenes, encoding="utf-8-sig") as fh:
            narrs = [s.get("narration", "") for s in json.load(fh)["scenes"]]
    except Exception:  # noqa: BLE001
        narrs = [s.get("subtitle", "") for s in scenes]

    # cumulative start times
    starts, t = [], 0.0
    for s in scenes:
        starts.append(t)
        t += float(s.get("duration", 0))
    n = min(len(scenes), len(narrs)) if narrs else len(scenes)
    if n < 3:
        print("[chapters] too few scenes; skipping.")
        return 0

    # group into <= max_chapters chapters (avoid one-per-scene clutter)
    step = max(1, (n + args.max_chapters - 1) // args.max_chapters)
    idxs = list(range(0, n, step))
    picked_narr = [narrs[i] if narrs else scenes[i].get("subtitle", "") for i in idxs]
    labs = labels(picked_narr, args.lang)
    lines = []
    for k, i in enumerate(idxs):
        stamp = "0:00" if k == 0 else ts(starts[i])
        lines.append(f"{stamp} {labs[k]}")

    header = "⏱️ 章節 Chapters:" if args.lang == "zh" else "⏱️ Chapters:"
    block = header + "\n" + "\n".join(lines)
    desc = ""
    if os.path.isfile(args.description):
        with open(args.description, encoding="utf-8") as fh:
            desc = fh.read().strip()
    with open(args.description, "w", encoding="utf-8") as fh:
        fh.write(desc + "\n\n" + block + "\n")
    print(f"[chapters] added {len(lines)} chapters to {args.description}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
