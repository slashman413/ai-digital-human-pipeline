"""Generate a long-form, multi-scene script with per-scene image prompts.

Output JSON shape:
  { "topic": str, "title": str,
    "scenes": [ { "narration": "<zh-TW 旁白>", "image_prompt": "<english visual>" }, ... ] }

The per-scene `image_prompt` drives the auto-generated, switching background
images (see generate_scene_assets.py).

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

SYSTEM = (
    "你是專業的長影音腳本與分鏡作者。輸出嚴格的 JSON，不要加任何說明或 markdown 圍欄。"
)


def build_prompt(topic: str, minutes: int, scenes: int, target_chars: int) -> str:
    topic_line = "請自行決定一個有趣、適合長影音的主題。" if topic in ("", "auto") else f"主題：{topic}"
    return (
        f"{topic_line}\n"
        f"請寫一支約 {minutes} 分鐘的中文（台灣用語、繁體）口語旁白，"
        f"全長總字數約 {target_chars} 字，切成剛好 {scenes} 個分鏡(scene)。\n"
        "每個 scene 要有：\n"
        "1) narration：該段的繁體中文旁白（口語、流暢、可直接朗讀）。\n"
        "2) image_prompt：一句英文，描述這段對應的『背景示意圖』"
        "（風格統一：modern flat illustration, soft gradient, cinematic, 16:9；不要文字）。\n"
        "嚴格只輸出這個 JSON：\n"
        '{"title":"<吸睛標題>","scenes":[{"narration":"...","image_prompt":"..."}]}'
    )


def parse_json(text: str) -> dict:
    text = text.strip()
    # strip ```json fences if present
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def fallback(topic: str, scenes: int) -> dict:
    t = topic if topic not in ("", "auto") else "AI 與生活"
    return {
        "title": f"{t}：你需要知道的事",
        "scenes": [
            {
                "narration": f"這是第 {i + 1} 段關於「{t}」的旁白。（未設定 LLM 金鑰，使用範本內容。）"
                "我們會用簡單的方式，帶你了解重點，並給你可以馬上行動的建議。",
                "image_prompt": f"modern flat illustration about {t}, scene {i + 1}, soft gradient, cinematic, 16:9, no text",
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

    scenes = args.scenes if args.scenes > 0 else max(6, args.minutes * 2)
    target_chars = args.minutes * 300  # ~300 spoken zh chars per minute

    try:
        raw = complete(SYSTEM, build_prompt(args.topic, args.minutes, scenes, target_chars), max_tokens=8000)
        data = parse_json(raw)
        if not data.get("scenes"):
            raise ValueError("no scenes in LLM output")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] long-form generation failed ({e}); using fallback.")
        data = fallback(args.topic, scenes)

    data["topic"] = args.topic
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"[ok] wrote {args.output}: title={data.get('title')!r}, scenes={len(data['scenes'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
