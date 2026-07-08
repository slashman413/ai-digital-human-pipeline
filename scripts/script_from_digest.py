#!/usr/bin/env python3
"""Turn a markdown digest into a ~150-word zh-TW spoken short-video script draft."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Generate short-video script from digest.")
    parser.add_argument("--input", required=True, help="path to digest.md")
    parser.add_argument("--format", required=True, help="target format, e.g. short_video")
    parser.add_argument("--output", required=True, help="path to write draft script")
    args = parser.parse_args()

    # Read the digest; tolerate a missing file with an empty body.
    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            digest = fh.read().strip()
    except FileNotFoundError:
        print(f"[warn] input not found: {args.input}; using empty digest.", file=sys.stderr)
        digest = ""

    # Ensure the output directory exists.
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)

    try:
        from llm import complete

        system = (
            "你是短影音腳本寫手。請用繁體中文(zh-TW)撰寫適合口語朗讀的腳本草稿,"
            f"格式為 {args.format},約 150 字,語氣自然、節奏明快,開頭要抓住注意力。"
        )
        user = f"根據以下摘要撰寫腳本:\n{digest or '(無內容,請寫一段通用的科技開場白)'}"
        script = complete(system, user, max_tokens=1200).strip()
    except Exception as exc:
        print(f"[warn] LLM unavailable ({exc}); writing fallback draft.", file=sys.stderr)
        script = (
            "大家好!今天為你帶來最新的科技焦點。\n"
            "(備援腳本:LLM 暫時無法使用,請稍後重新生成。)\n"
            + (digest[:300] if digest else "")
        )

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(script + "\n")
    print(f"[ok] wrote script draft -> {args.output}")


if __name__ == "__main__":
    main()
