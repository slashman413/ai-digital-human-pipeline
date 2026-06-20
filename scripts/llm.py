"""Shared LLM helper for the digital-human pipeline.

Provider-agnostic: uses Anthropic Claude if ANTHROPIC_API_KEY is set, else
OpenAI if OPENAI_API_KEY is set. If neither is present (e.g. a CI dry-run with
no secrets), it returns a deterministic templated string so the whole pipeline
still completes end-to-end without crashing.

Usage:
    from llm import complete
    text = complete(system="You are ...", user="Write ...", max_tokens=1200)
"""
from __future__ import annotations

import os

# Sensible, current defaults. Override via env.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


def _via_anthropic(system: str, user: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in msg.content if block.type == "text").strip()


def _via_openai(system: str, user: str, max_tokens: int) -> str:
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _offline_stub(system: str, user: str) -> str:
    """No API key available — return a usable placeholder so CI still runs."""
    return (
        "【離線示範稿 / offline demo script】\n"
        "（未設定 ANTHROPIC_API_KEY 或 OPENAI_API_KEY，使用範本輸出）\n\n"
        f"主題提示：{user[:200]}\n\n"
        "大家好，歡迎來到今天的 AI 數字人頻道。今天我們要聊的主題非常有趣，"
        "讓我用三個重點帶你快速了解。第一，背景與為什麼重要；第二，關鍵的運作原理；"
        "第三，你今天就能採取的行動。希望這支影片對你有幫助，記得訂閱與分享，我們下支影片見！"
    )


def complete(system: str, user: str, max_tokens: int = 1200) -> str:
    """Return an LLM completion, preferring Anthropic, then OpenAI, then a stub."""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _via_anthropic(system, user, max_tokens)
        except Exception as e:  # noqa: BLE001 — never hard-fail the pipeline
            print(f"[llm] Anthropic call failed ({e}); trying next provider.")
    if os.getenv("OPENAI_API_KEY"):
        try:
            return _via_openai(system, user, max_tokens)
        except Exception as e:  # noqa: BLE001
            print(f"[llm] OpenAI call failed ({e}); falling back to stub.")
    print("[llm] No LLM API key set — using offline stub output.")
    return _offline_stub(system, user)
