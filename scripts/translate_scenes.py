"""Translate a generated zh-TW scenes.json into an English version.

Reuses the same scene structure (and the same background images downstream); only
the narration is translated to natural spoken English. Also writes English SEO
title / description / tags. Lets us produce a parallel English video that shares
the Chinese video's visuals.

CLI: --scenes scenes.json --output scenes_en.json
     --title-out title_en.txt --desc-out description_en.txt --tags-out tags_en.txt
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import complete  # noqa: E402

TR_SYS = ("You are a professional subtitle/voice-over translator. Translate Traditional "
          "Chinese video narration into natural, fluent, engaging spoken English for an "
          "English voice-over. Output ONLY the English translation, no notes or quotes.")
SEO_SYS = "You are a YouTube SEO & growth expert. Output strict JSON only, no markdown fences."


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1:
        text = text[s:e + 1]
    return json.loads(text)


def en_seo(zh_title: str, scenes: list[dict]) -> dict:
    outline = "; ".join(s.get("narration", "")[:40] for s in scenes[:6])
    prompt = (
        f"Original (Chinese) title: {zh_title}\nContent outline: {outline}\n\n"
        "Produce English YouTube metadata to maximize search reach and click-through. Strict JSON:\n"
        '{"title":"<=70 chars, keyword-front, curiosity-driven, clickable>",'
        '"description":"<strong first-line hook with the main keyword; 2-3 sentences with '
        'searchable keywords; 3 bullet points; final line CTA \'Subscribe & share if you enjoyed\'; '
        'end with 5 relevant #hashtags>",'
        '"tags":["<12-15 SEO tags, broad + specific + long-tail>"]}'
    )
    try:
        d = parse_json(complete(SEO_SYS, prompt, max_tokens=1200))
        title = (d.get("title") or "").strip()
        desc = (d.get("description") or "").strip()
        tags = d.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        tags = [t for t in (t.strip() for t in tags) if t][:15]
        if title and desc and tags:
            return {"title": title, "description": desc, "tags": ",".join(tags)}
    except Exception as e:  # noqa: BLE001
        print(f"[warn] EN SEO failed ({e}); using fallback.")
    return {"title": (zh_title + " | AI explained"),
            "description": "Quick, clear breakdown of today's topic. Subscribe & share if you enjoyed!\n\n#AI #explained #shorts #learn #tech",
            "tags": "AI,explained,knowledge,how to,technology,tutorial,daily,facts,learning,productivity"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="scenes.json")
    ap.add_argument("--output", default="scenes_en.json")
    ap.add_argument("--title-out", default="title_en.txt")
    ap.add_argument("--desc-out", default="description_en.txt")
    ap.add_argument("--tags-out", default="tags_en.txt")
    args = ap.parse_args()

    with open(args.scenes, encoding="utf-8") as fh:
        data = json.load(fh)
    scenes = data["scenes"]

    out_scenes = []
    for i, sc in enumerate(scenes):
        zh = sc.get("narration", "").strip()
        try:
            en = complete(TR_SYS, zh, max_tokens=600).strip().strip('"')
        except Exception as e:  # noqa: BLE001
            print(f"[warn] translate scene {i} failed ({e}); keeping source.")
            en = zh
        out_scenes.append({"narration": en, "image_prompt": sc.get("image_prompt", "")})
        print(f"[ok] scene {i:02d}: {len(en)} chars (en)")

    out = {"title": data.get("title", ""), "scenes": out_scenes}
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    meta = en_seo(data.get("title", ""), scenes)
    for path, key in ((args.title_out, "title"), (args.desc_out, "description"), (args.tags_out, "tags")):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(meta[key])
    print(f"[seo-en] title={meta['title']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
