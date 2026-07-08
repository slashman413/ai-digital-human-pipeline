#!/usr/bin/env python3
"""Synthesize spoken audio from a script using edge-tts (free, no API key).

Strips non-spoken markers before synthesis. On any failure (missing package,
network error) it writes an empty file at the output path and exits 0, so the
pipeline can detect-and-skip downstream steps instead of crashing CI.
"""
import argparse
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def clean_text(text: str) -> str:
    """Remove non-spoken markers so only readable content is synthesized.

    Drops lines wrapped in 【】 (section markers) or starting with （）
    (stage directions / parentheticals), then collapses blank lines.
    """
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Full 【...】 marker lines.
        if stripped.startswith("【") and stripped.endswith("】"):
            continue
        # Lines that are purely a （...）/(...）parenthetical aside.
        if re.match(r"^[（(].*[)）]$", stripped):
            continue
        # Strip inline 【...】 markers anywhere in the line.
        stripped = re.sub(r"【[^】]*】", "", stripped).strip()
        if stripped:
            kept.append(stripped)
    return "\n".join(kept).strip()


async def _synthesize(text: str, voice: str, output: str) -> None:
    import edge_tts  # imported lazily so missing package is handled gracefully

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output)


def write_empty(output: str) -> None:
    """Create an empty placeholder file so downstream steps can skip cleanly."""
    open(output, "wb").close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Text-to-speech via edge-tts.")
    parser.add_argument("--input", required=True, help="Path to the script text file.")
    parser.add_argument("--voice", required=True, help="edge-tts voice, e.g. zh-CN-XiaoxiaoNeural.")
    parser.add_argument("--output", required=True, help="Output mp3 path.")
    args = parser.parse_args()

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)

    # Read input; if it is missing/empty there is nothing to speak.
    text = ""
    if os.path.exists(args.input):
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    text = clean_text(text)
    if not text:
        print("[warn] input text is empty after cleaning; writing empty output file.")
        write_empty(args.output)
        return

    try:
        asyncio.run(_synthesize(text, args.voice, args.output))
    except ImportError:
        print("[warn] edge-tts is not installed; writing empty output file so downstream can skip.")
        write_empty(args.output)
        return
    except Exception as exc:  # network errors, voice errors, etc.
        print(f"[warn] edge-tts synthesis failed ({exc}); writing empty output file.")
        write_empty(args.output)
        return

    # Guard against a "successful" call that produced nothing usable.
    if not os.path.exists(args.output) or os.path.getsize(args.output) == 0:
        print("[warn] edge-tts produced no audio; writing empty output file.")
        write_empty(args.output)
        return

    print(f"[ok] wrote audio to {args.output} ({os.path.getsize(args.output)} bytes)")


if __name__ == "__main__":
    main()
