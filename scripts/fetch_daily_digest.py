#!/usr/bin/env python3
"""Fetch top Hacker News tech items and produce a concise zh-TW markdown digest.

No required args. Outputs markdown to STDOUT (the workflow redirects to digest.md).
Degrades to a small static digest on any network/LLM error so the pipeline continues.
"""
import argparse
import os
import sys

# Allow importing the shared llm helper that sits next to this script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

# Static fallback used when the network or LLM is unavailable.
FALLBACK = """# 今日科技摘要(離線備援)

- 無法連線至資料來源,以下為占位內容,管線將繼續執行。
- 請稍後重試以取得最新的科技新聞摘要。
"""


def fetch_items(limit: int):
    """Return a list of {title, url} dicts from Hacker News, or [] on failure."""
    import requests  # imported lazily so a missing dep doesn't break import time

    resp = requests.get(HN_TOP, timeout=15)
    resp.raise_for_status()
    ids = resp.json()[: max(limit, 1)]

    items = []
    for sid in ids:
        try:
            r = requests.get(HN_ITEM.format(id=sid), timeout=15)
            r.raise_for_status()
            data = r.json() or {}
            title = data.get("title")
            if not title:
                continue
            url = data.get("url") or f"https://news.ycombinator.com/item?id={sid}"
            items.append({"title": title, "url": url})
        except Exception:
            continue  # skip individual broken items
    return items


def build_digest(items) -> str:
    """Use the LLM to render a zh-TW bullet digest with 1-line takeaways."""
    from llm import complete

    listing = "\n".join(f"- {it['title']} ({it['url']})" for it in items)
    system = (
        "你是科技新聞編輯。請用繁體中文(zh-TW)整理成精簡的 markdown 摘要,"
        "以項目符號列出,每則含標題與一句重點(takeaway)。"
    )
    user = f"以下是今日熱門科技項目,請整理:\n{listing}"
    return complete(system, user, max_tokens=1200).strip()


def main():
    parser = argparse.ArgumentParser(description="Fetch daily tech digest (zh-TW).")
    parser.add_argument("--limit", type=int, default=10, help="number of items")
    args = parser.parse_args()

    try:
        items = fetch_items(args.limit)
        if not items:
            raise RuntimeError("no items fetched")
        print(build_digest(items))
    except Exception as exc:
        print(f"[warn] digest generation failed ({exc}); using fallback.", file=sys.stderr)
        # Try a minimal markdown from whatever titles we managed to fetch.
        try:
            if items:  # type: ignore[name-defined]
                lines = ["# 今日科技摘要(備援)\n"]
                for it in items:
                    lines.append(f"- [{it['title']}]({it['url']})")
                print("\n".join(lines))
                return
        except Exception:
            pass
        print(FALLBACK)


if __name__ == "__main__":
    main()
