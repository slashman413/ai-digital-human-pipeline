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

SYS = ("You are a creative director for a peaceful piano meditation & relaxation music channel "
       "(soft solo piano, lakeside calm, gentle nature ambience — warm, soothing, meditative). "
       "Output strict JSON only.")

PROMPT = (
    "Design ONE short peaceful piano meditation track concept (soft solo piano with gentle water & birdsong) "
    "(lakeside / forest, calm, warm, for meditation & relaxation). Strict JSON:\n"
    '{"title":"<2-3 word lowercase calm nature title, e.g. morning lake / quiet stream>",'
    '"seo_title":"<a YouTube title: the title + a VARIED descriptive tail using different wording '
    'each time (mix of: relaxing piano, meditation music, nature sounds, for sleep/study/relax/focus, lake/forest/morning, '
    'calm/atmospheric) — must be relevant but NOT a fixed boilerplate; <=80 chars>",'
    '"music_prompt":"<MusicGen prompt: solo acoustic grand piano only, gentle slow meditative piano melody, intimate warm, '
    'clearly recognizable acoustic piano, soft dynamics, no synth, no pads, no strings, no drums, plus 2-3 mood words>",'
    '"image_prompts":["<10 distinct serene NATURE meditation SCENES: misty lake at sunrise, forest stream, sunlit '
    'trees, calm reflective water, green meadow morning, gentle waterfall, lakeside dawn — one short phrase each>"],'
    '"description":"<short youtube description: mood line + \'perfect for sleep, study, relax\' + '
    '3 lines + 5 #hashtags like #meditation #pianomusic #relaxingmusic #naturesounds #sleep>",'
    '"tags":["<12-15 SEO tags: meditation music, relaxing piano, piano music, nature sounds, water sounds, birdsong, sleep music, study music, etc>"]}'
)

FALLBACK_TITLES = ["morning lake", "quiet stream", "forest light", "still water",
                   "gentle dawn", "soft current", "misty morning", "calm waters"]
FALLBACK_SCENES = [
    "calm misty lake at sunrise, soft golden light, gentle reflections, distant forest",
    "clear forest stream over mossy rocks, dappled morning sunlight, lush green",
    "sunlight beams through tall green trees, soft fog, peaceful woodland path",
    "still mountain lake reflecting pink dawn sky, mist on the water, serene",
    "gentle waterfall in a green forest, soft mist, ferns, tranquil",
    "quiet green meadow at golden hour, wildflowers, soft warm light",
    "lakeside dawn, a single wooden jetty, calm water, birds in the sky",
    "soft sunrise over rolling green hills, light mist in the valley",
    "peaceful riverbank with reeds and warm morning light, smooth water",
    "tranquil pond in a zen garden, lily pads, soft reflections, calm",
]


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1:
        text = text[s:e + 1]
    return json.loads(text)


SEO_SUFFIXES = [
    "relaxing piano music for meditation", "soft piano with nature sounds for sleep",
    "calm piano & water sounds to study & relax", "peaceful piano for deep relaxation",
    "meditation music with birdsong & stream", "gentle piano music to unwind",
    "relaxing piano for sleep & focus", "calming piano with nature ambience",
]


def fallback() -> dict:
    rng = random.Random()
    title = rng.choice(FALLBACK_TITLES)
    return {
        "title": title,
        "seo_title": f"{title} | {rng.choice(SEO_SUFFIXES)}",
        "music_prompt": "solo acoustic grand piano only, gentle slow meditative piano melody, intimate warm, clearly recognizable acoustic piano, soft dynamics, calm, emotional, no synth, no pads, no strings, no drums, no percussion",
        "image_prompts": FALLBACK_SCENES,
        "description": (f"{title} — soft piano meditation music with gentle water & birdsong, for sleep, study and relaxation.\n\n"
                        "let the piano and nature sounds calm your mind.\nput it on, breathe, and let go.\n\n"
                        "#meditation #pianomusic #relaxingmusic #naturesounds #sleep"),
        "tags": ["meditation music", "relaxing piano", "piano music", "nature sounds", "water sounds",
                 "birdsong", "sleep music", "study music", "calm music", "relaxing music",
                 "background music", "focus music", "spa music", "stress relief"],
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
        seo = seo.strip() + " | 20 Min Relaxing Piano"
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
