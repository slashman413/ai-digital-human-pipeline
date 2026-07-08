#!/usr/bin/env python3
"""Generate a short-form spoken video script (zh-TW) plus title/description/tags.

Uses the shared `complete(...)` helper for all LLM calls. Degrades gracefully
when no API key is configured (the helper's offline stub) and always produces
usable artifacts so downstream pipeline steps can run.
"""
import argparse
import json
import os
import re
import sys

# Ensure the script's own directory is importable so `from llm import complete`
# works regardless of how the workflow invokes us.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import complete  # noqa: E402


def _extract_json(text: str):
    """Best-effort parse of a JSON object embedded in an LLM response.

    Returns a dict on success, or None so callers can fall back to heuristics.
    """
    if not text:
        return None
    # Try the whole thing first, then the first {...} block we can find.
    candidates = [text]
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def generate_script(topic: str) -> str:
    """Produce a ~150-220 word zh-TW spoken script. Invents a topic if needed."""
    topic = (topic or "").strip()
    if not topic or topic.lower() == "auto":
        system = (
            "你是一位專業的短影音腳本作家，擅長創作吸引人的口語化中文（繁體）腳本。"
        )
        user = (
            "請先自行構思一個目前可能熱門、適合短影音的主題，"
            "然後針對該主題撰寫一段約 150 到 220 字、適合口語朗讀的繁體中文短影音腳本。"
            "腳本要自然、有節奏感，不要加入任何旁白標記或舞台指示，直接輸出可朗讀的內容。"
        )
    else:
        system = (
            "你是一位專業的短影音腳本作家，擅長創作吸引人的口語化中文（繁體）腳本。"
        )
        user = (
            f"請針對主題「{topic}」撰寫一段約 150 到 220 字、"
            "適合口語朗讀的繁體中文短影音腳本。"
            "腳本要自然、有節奏感，不要加入任何旁白標記或舞台指示，直接輸出可朗讀的內容。"
        )
    script = complete(system, user, max_tokens=600)
    script = (script or "").strip()
    if not script:
        # Last-resort fallback so the pipeline never gets an empty script.
        topic_label = topic if topic and topic.lower() != "auto" else "今日話題"
        script = (
            f"嗨大家好，今天想跟你聊聊「{topic_label}」。"
            "這是一個越來越多人關注的主題，因為它正在悄悄改變我們的生活。"
            "其實只要掌握幾個簡單的重點，你也能輕鬆上手。"
            "首先，保持好奇心，多看、多問、多嘗試；"
            "接著，把學到的東西實際運用在日常裡，"
            "你會發現改變比想像中更快發生。"
            "如果你喜歡今天的內容，記得按讚、分享，並且追蹤我，"
            "我們下支影片再見，掰掰！"
        )
    return script


def derive_metadata(script: str) -> dict:
    """Ask the LLM for title/description/tags as JSON; fall back to heuristics."""
    system = (
        "你是社群媒體文案專家。根據提供的影片腳本，輸出嚴格的 JSON 物件，"
        '格式為 {"title": "...", "description": "...", "tags": ["...", ...]}。'
        "只輸出 JSON，不要有多餘文字。"
    )
    user = (
        "請根據以下短影音腳本產生中繼資料：\n"
        "title：不超過 60 字、吸睛的繁體中文標題。\n"
        "description：2 到 3 句的繁體中文描述，並在結尾附上 3 個 hashtag。\n"
        "tags：5 到 8 個相關標籤（字串陣列）。\n\n"
        f"腳本：\n{script}"
    )
    raw = complete(system, user, max_tokens=400)
    obj = _extract_json(raw)

    title = ""
    description = ""
    tags = []
    if obj:
        title = str(obj.get("title", "")).strip()
        description = str(obj.get("description", "")).strip()
        raw_tags = obj.get("tags", [])
        if isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        elif isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    # Heuristic fallbacks derived directly from the script text.
    first_line = next((ln.strip() for ln in script.splitlines() if ln.strip()), "短影音")
    if not title:
        title = first_line[:60]
    title = title[:60]
    if not description:
        snippet = first_line[:40]
        description = f"{snippet}。立即觀看完整內容，了解更多精彩重點。 #短影音 #必看 #分享"
    if not tags:
        tags = ["短影音", "影音", "教學", "分享", "熱門"]
    # Clamp tag count to the required 5-8 range.
    if len(tags) < 5:
        tags = (tags + ["短影音", "影音", "教學", "分享", "熱門"])[:5]
    tags = tags[:8]

    return {"title": title, "description": description, "tags": tags}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a zh-TW short video script.")
    parser.add_argument("--topic", required=True, help='Topic, or the literal "auto".')
    parser.add_argument("--output", required=True, help="Path to write the script body.")
    args = parser.parse_args()

    script = generate_script(args.topic)

    # Ensure parent dir of the main output exists before writing.
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(script + "\n")
    print(f"[ok] wrote script to {args.output} ({len(script)} chars)")

    meta = derive_metadata(script)
    # Sibling metadata files use fixed names in the current working directory.
    with open("title.txt", "w", encoding="utf-8") as f:
        f.write(meta["title"] + "\n")
    with open("description.txt", "w", encoding="utf-8") as f:
        f.write(meta["description"] + "\n")
    with open("tags.txt", "w", encoding="utf-8") as f:
        f.write(", ".join(meta["tags"]) + "\n")
    print("[ok] wrote title.txt, description.txt, tags.txt")


if __name__ == "__main__":
    main()
