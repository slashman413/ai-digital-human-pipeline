"""Generate a long-form, multi-scene script with per-scene image prompts.

Two-stage generation for reliable length:
  1. Outline  -> title + N scenes, each {brief, image_prompt}
  2. Expand   -> per scene, write a full ~target-length zh-TW narration

A single call asking for N full scenes tends to under-deliver on length, which
yields a too-short video; expanding each scene individually fixes that.

Output JSON: { "topic", "title",
  "scenes": [ {"narration": "<zh-TW 旁白>", "image_prompt": "<english visual>"}, ... ] }

CLI: --topic <str|auto> --minutes <int=10> --scenes <int=0 auto> --output scenes.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import complete  # noqa: E402

OUTLINE_SYS = "你是專業長影音的內容企劃。只輸出嚴格 JSON，不要 markdown 圍欄或任何說明。"
WRITER_SYS = "你是專業旁白作家，寫台灣用語、繁體中文、口語、可直接朗讀的影片旁白。只輸出旁白本身，不要標題、不要前言、不要引號。"


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1:
        text = text[s : e + 1]
    return json.loads(text)


def outline(topic: str, scenes: int) -> dict:
    topic_line = "請自行決定一個有趣、適合長影音的主題。" if topic in ("", "auto") else f"主題：{topic}"
    prompt = (
        f"{topic_line}\n"
        f"規劃一支長影音，切成剛好 {scenes} 個分鏡(scene)，要有起承轉合、循序漸進、不重複。\n"
        "每個 scene 給：\n"
        "1) brief：用一句話說明這段要講什麼（之後會擴寫成旁白）。\n"
        "2) image_prompt：一句英文，描述這段對應的『真實照片』背景"
        "（photorealistic real photograph of a concrete scene/place/object, "
        "realistic, sharp, 16:9, no text；不要插畫、不要手繪、不要抽象）。\n"
        '只輸出：{"title":"<吸睛標題>","scenes":[{"brief":"...","image_prompt":"..."}]}'
    )
    data = parse_json(complete(OUTLINE_SYS, prompt, max_tokens=4000))
    if not data.get("scenes"):
        raise ValueError("outline has no scenes")
    return data


def expand(title: str, briefs: list[str], idx: int, per_chars: int) -> str:
    brief = briefs[idx]
    context = (
        f"影片標題：{title}\n"
        f"這是第 {idx + 1}/{len(briefs)} 段。本段要點：{brief}\n"
        f"前一段要點：{briefs[idx - 1] if idx > 0 else '（開場）'}\n"
        f"下一段要點：{briefs[idx + 1] if idx + 1 < len(briefs) else '（結尾收束）'}\n"
        f"請把『本段要點』擴寫成約 {per_chars} 字的繁體中文口語旁白，"
        "承接前段、自然帶到下段，舉例具體、節奏流暢。只輸出這段旁白文字。"
    )
    return complete(WRITER_SYS, context, max_tokens=1200).strip()


def fallback(topic: str, scenes: int, per_chars: int) -> dict:
    t = topic if topic not in ("", "auto") else "AI 與生活"
    pad = "我們用簡單的方式帶你了解重點，並給出可以馬上行動的建議。"
    return {
        "title": f"{t}：完整指南",
        "scenes": [
            {
                "narration": (f"第 {i + 1} 段：關於「{t}」。" + pad * (per_chars // len(pad) + 1))[:per_chars],
                "image_prompt": f"photorealistic professional photograph related to {t}, scene {i + 1}, realistic, sharp focus, 16:9, no text",
            }
            for i in range(scenes)
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="auto")
    ap.add_argument("--minutes", type=int, default=10)
    ap.add_argument("--scenes", type=int, default=0)
    ap.add_argument("--output", default="scenes.json")
    args = ap.parse_args()

    # Measured: zh-TW edge-tts speaks ~215 chars/min (~0.28s per char).
    # ~12 scenes for a 10-min video → ~179 chars (~50s) each.
    CHARS_PER_MIN = 215
    scenes = args.scenes if args.scenes > 0 else max(4, round(args.minutes * 1.2))
    per_chars = max(120, args.minutes * CHARS_PER_MIN // scenes)

    try:
        ol = outline(args.topic, scenes)
        title = ol.get("title", args.topic)
        briefs = [s.get("brief", "") for s in ol["scenes"]]
        prompts = [s.get("image_prompt", "photorealistic professional photograph, realistic, sharp, 16:9, no text") for s in ol["scenes"]]
        out_scenes = []
        for i in range(len(briefs)):
            try:
                narration = expand(title, briefs, i, per_chars)
            except Exception as e:  # noqa: BLE001
                print(f"[warn] expand scene {i} failed ({e}); using brief.")
                narration = briefs[i]
            out_scenes.append({"narration": narration, "image_prompt": prompts[i]})
            print(f"[ok] scene {i:02d}: {len(narration)} chars")
        data = {"title": title, "scenes": out_scenes}
    except Exception as e:  # noqa: BLE001
        print(f"[warn] long-form generation failed ({e}); using fallback.")
        data = fallback(args.topic, scenes, per_chars)

    data["topic"] = args.topic
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    # Publish metadata (consumed by upload_*.py via the workflow)
    title = data.get("title", "AI 影片")
    topic_disp = args.topic if args.topic not in ("", "auto") else title
    with open("title.txt", "w", encoding="utf-8") as fh:
        fh.write(title)
    with open("description.txt", "w", encoding="utf-8") as fh:
        fh.write(f"{title}\n\n本片主題：{topic_disp}。由 AI 每日自動生成（腳本/配音/畫面）。")
    words = [w for w in re.split(r"[：:，,、\s]+", title) if 2 <= len(w) <= 8][:4]
    tags = ",".join(dict.fromkeys(words + ["AI", "知識", "科普", "每日更新"]))
    with open("tags.txt", "w", encoding="utf-8") as fh:
        fh.write(tags)

    chars = sum(len(s["narration"]) for s in data["scenes"])
    print(f"[ok] wrote {args.output}: title={data.get('title')!r}, scenes={len(data['scenes'])}, "
          f"~{chars} chars (~{chars * 60 // 215}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
