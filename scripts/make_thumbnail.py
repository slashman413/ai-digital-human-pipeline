"""Generate an eye-catching 1280x720 YouTube thumbnail.

A strong thumbnail is the #1 lever for click-through rate. Takes a clean
background image (a generated scene image, no burned subtitles) + the title,
darkens/saturates the background, and overlays big bold title text (1-2 lines)
with a heavy outline for readability at small sizes.

CLI: --image build/img_00.jpg --title "<title>" --output output/thumbnail.jpg
     --font "Noto Sans CJK TC"  (or --fontfile on Windows)
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-1500:])
        raise SystemExit("ffmpeg failed")


def esc(text: str) -> str:
    # escape for ffmpeg drawtext text=
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def split_two(title: str, max_line: int = 11) -> list[str]:
    """Split a (mostly CJK) title into up to 2 punchy lines."""
    t = re.sub(r"\s+", "", title)
    # drop a leading bracketed tag if any
    t = re.sub(r"^[【\[(（].*?[】\])）]", "", t).strip() or title
    if len(t) <= max_line:
        return [t]
    # try to break at a punctuation near the middle
    mid = len(t) // 2
    best = mid
    for i in range(len(t)):
        if t[i] in "，,、：:！!？?。．·-—":
            if abs(i - mid) < abs(best - mid):
                best = i
    cut = best + 1 if t[best] in "，,、：:！!？?。．·-—" else mid
    cut = min(max(cut, 4), len(t) - 1)
    return [t[:cut], t[cut:]][:2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--output", default="output/thumbnail.jpg")
    ap.add_argument("--font", default="Noto Sans CJK TC")
    ap.add_argument("--fontfile", default="")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    if not os.path.isfile(args.image):
        print(f"[warn] thumbnail bg not found: {args.image}; skipping.")
        return 0

    font_expr = (f"fontfile='{args.fontfile.replace(chr(92),'/').replace(':',chr(92)+':')}'"
                 if args.fontfile else f"font='{args.font}'")
    lines = split_two(args.title)
    # base: fill 1280x720, darken + punch saturation, slight vignette via gradient overlay
    filt = ["[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
            "eq=brightness=-0.10:saturation=1.25,boxblur=1:1[bg]"]
    prev = "[bg]"
    fontsize = 96 if len(lines) == 1 else 88
    n = len(lines)
    for i, ln in enumerate(lines):
        y = f"h*0.5-{(n-1-2*i)*int(fontsize*0.62)}" if n > 1 else "h*0.62"
        out = "[out]" if i == n - 1 else f"[t{i}]"
        filt.append(
            f"{prev}drawtext=text='{esc(ln)}':{font_expr}:fontsize={fontsize}:"
            f"fontcolor=white:borderw=10:bordercolor=black@0.95:shadowx=4:shadowy=4:shadowcolor=black@0.6:"
            f"x=(w-text_w)/2:y={y}{out}"
        )
        prev = out
    run(["ffmpeg", "-y", "-i", args.image, "-filter_complex", ";".join(filt),
         "-map", "[out]", "-frames:v", "1", "-q:v", "2", args.output])
    print(f"[ok] thumbnail -> {args.output}  ({' / '.join(lines)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
