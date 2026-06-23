"""Generate a daily dreamscape concept: melancholic title, music prompt, dark dreamscape
image prompts, and YouTube SEO metadata. LLM-driven with a curated fallback so it always
produces something. Writes title.txt, music_prompt.txt, prompts.txt, description.txt, tags.txt.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import complete  # noqa: E402

SYS = ("You are a creative director for an ethereal dark-ambient music channel "
       "(think Øneheart, Antent, 'made from dreams' — calm, mysterious, emotional, cinematic). "
       "Output strict JSON only.")

PROMPT = (
    "Design ONE short ambient track concept in the style of the YouTube channel 'dreamscape..' "
    "(dark, melancholic, lonely, cinematic, snowy/winter night mood). Strict JSON:\n"
    '{"title":"<2-3 word lowercase melancholic title, e.g. first snow / distant memories>",'
    '"seo_title":"<a YouTube title: the title + a VARIED descriptive tail using different wording '
    'each time (mix of: dark/ethereal ambient, for sleep/study/relax/focus, winter/snow/night, '
    'calm/atmospheric) — must be relevant but NOT a fixed boilerplate; <=80 chars>",'
    '"music_prompt":"<MusicGen prompt: dark atmospheric ambient, slow, ethereal reverb pads, '
    'no drums, plus 2-3 mood words>",'
    '"image_prompts":["<10 distinct dark dreamscape SCENES: snowy cabins, frozen lakes, foggy '
    'forests, empty winter roads, aurora, lonely mountains — one short phrase each>"],'
    '"description":"<short youtube description: mood line + \'perfect for sleep, study, relax\' + '
    '3 lines + 5 #hashtags like #ambient #darkambient #sleep #study #relax>",'
    '"tags":["<12-15 SEO tags: dark ambient, ambient music, sleep music, study music, etc>"]}'
)

FALLBACK_TITLES = ["first snow", "distant memories", "fading light", "winter solitude",
                   "lonely night", "frozen time", "silent dreams", "after the storm"]
FALLBACK_SCENES = [
    "lone wooden cabin glowing windows on a snowy hill at night, faint aurora",
    "frozen lake under a starry winter night, distant mountains, mist",
    "empty snowy forest path at dusk, soft falling snow, lonely lamppost",
    "misty pine forest at blue hour, deep snow, fog between trees",
    "abandoned cabin in a vast snowfield, northern lights overhead",
    "quiet mountain village at night, warm window lights, heavy snowfall",
    "snow-covered evergreen forest under a full moon, soft blue light, mist",
    "icy fjord at twilight, calm water reflecting purple sky, distant cabin",
    "cozy cabin window from inside, frost on glass, candle glow, snowfall outside",
    "endless snowy plain at night, faint green aurora, a single distant light",
]


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1:
        text = text[s:e + 1]
    return json.loads(text)


SEO_SUFFIXES = [
    "dark ambient for deep sleep", "ethereal ambient to study & relax",
    "calm winter ambient music", "atmospheric ambient for sleep & focus",
    "dreamy dark ambient music", "ambient soundscape to relax & unwind",
    "snowy night ambient for sleep", "lonely dark ambient to study",
]


def fallback() -> dict:
    rng = random.Random()
    title = rng.choice(FALLBACK_TITLES)
    return {
        "title": title,
        "seo_title": f"{title} | {rng.choice(SEO_SUFFIXES)}",
        "music_prompt": "ethereal dark ambient, slow, calm, mysterious, emotional, lush reverb pads, dreamy, cinematic, no drums, no percussion",
        "image_prompts": FALLBACK_SCENES,
        "description": (f"{title} — dark ambient music for sleep, study and relaxation.\n\n"
                        "drift away into a quiet winter dream.\nput it on, breathe, and let go.\n\n"
                        "#ambient #darkambient #sleep #study #relax"),
        "tags": ["dark ambient", "ambient music", "sleep music", "study music", "relaxing music",
                 "winter ambient", "snowfall", "calm music", "dreamscape", "lonely ambient",
                 "background music", "focus music", "ambient mix", "chill"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    try:
        d = parse_json(complete(SYS, PROMPT, max_tokens=900))
        if not (d.get("title") and d.get("image_prompts")):
            raise ValueError("missing fields")
        if isinstance(d.get("tags"), str):
            d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
    except Exception as e:  # noqa: BLE001
        print(f"[concept] LLM failed ({e}); using fallback.")
        d = fallback()

    o = args.outdir
    title_l = str(d["title"]).strip().lower()
    with open(os.path.join(o, "title.txt"), "w", encoding="utf-8") as fh:
        fh.write(title_l)
    # varied-but-relevant YouTube title (no fixed boilerplate suffix)
    seo = str(d.get("seo_title") or "").strip()
    if not seo or len(seo) < len(title_l) + 3:
        seo = f"{title_l} | {random.choice(SEO_SUFFIXES)}"
    if "min" not in seo.lower() and "hour" not in seo.lower():
        seo = seo.strip() + " | 20 Min Dark Ambient"
    seo = seo[:1].upper() + seo[1:]
    with open(os.path.join(o, "yt_title.txt"), "w", encoding="utf-8") as fh:
        fh.write(seo)
    with open(os.path.join(o, "music_prompt.txt"), "w", encoding="utf-8") as fh:
        fh.write(str(d.get("music_prompt") or fallback()["music_prompt"]))
    with open(os.path.join(o, "prompts.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(str(p).strip() for p in d["image_prompts"][:10]))
    with open(os.path.join(o, "description.txt"), "w", encoding="utf-8") as fh:
        fh.write(str(d.get("description") or fallback()["description"]))
    tags = d.get("tags") or fallback()["tags"]
    with open(os.path.join(o, "tags.txt"), "w", encoding="utf-8") as fh:
        fh.write(",".join(str(t).strip() for t in tags[:15]))
    print(f"[concept] title={d['title']!r}  scenes={len(d['image_prompts'][:10])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
