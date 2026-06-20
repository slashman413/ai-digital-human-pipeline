"""Pick a random trending topic and frame it into a video subject.

Source: Google Trends daily RSS (no API key). Falls back across geos, then to
a static list. The raw trend (often a name/place) is reframed by the LLM into a
concrete, video-friendly topic; without an LLM key it uses the raw term.

CLI: --geo TW --output topic.txt   (also prints the topic to stdout)
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import complete  # noqa: E402

FALLBACK = [
    "AI 工具如何提升生產力", "個人理財的五個關鍵習慣", "睡眠科學：如何睡得更好",
    "高效學習的方法", "氣候變遷對日常生活的影響", "社群媒體與心理健康",
    "咖啡因如何影響大腦", "太空探索的最新進展", "海洋生態為何重要",
    "運動科學：間歇訓練的好處", "飲食與長壽的關聯", "記憶力的運作原理",
]

# Skip / reframe sensitive trends (politics, adult, violence/crime, scandal, religion-conflict).
SENSITIVE = [
    # politics
    "政治", "政黨", "選舉", "大選", "總統", "立委", "立法委員", "議員", "市長", "縣長",
    "國民黨", "民進黨", "民眾黨", "時代力量", "黨主席", "參選", "競選", "投票", "罷免",
    "執政", "在野", "統獨", "兩岸", "藍營", "綠營", "白營", "總統府", "行政院", "立法院",
    # adult
    "色情", "情色", "性愛", "做愛", "a片", "av女優", "裸", "成人片", "援交", "賣淫", "情趣",
    # violence / crime
    "兇殺", "命案", "槍擊", "槍殺", "毒品", "性侵", "強姦", "自殺", "恐攻", "綁架", "虐待",
    # scandal / privacy
    "外遇", "出軌", "劈腿", "醜聞", "緋聞", "爆料", "私密照",
]


def is_sensitive(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in SENSITIVE)


def fetch_trends(geo: str) -> list[str]:
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    xml = urllib.request.urlopen(req, timeout=30).read()
    root = ET.fromstring(xml)
    return [t for t in (it.findtext("title") for it in root.iter("item")) if t]


def frame_topic(trend: str) -> str:
    sys_p = "你是內容企劃。只輸出一句繁體中文的影片主題，不要解釋、不要引號。"
    user = (
        f"今天的熱門關鍵字是「{trend}」。請把它轉化成一個適合做成約 10 分鐘"
        "『資訊型/科普型』影片的具體主題（繁體中文，一句話）。\n"
        "嚴格避開：政治/政黨/選舉/政治人物、色情/性、暴力/犯罪、醜聞/八卦/個人隱私、宗教爭議。\n"
        "若這個關鍵字屬於上述敏感類別，請『完全改成』一個中性、正面、有知識含量的主題"
        "（可以與關鍵字無關，例如科學、健康、科技、生活、歷史文化、自然）。"
    )
    for _ in range(3):
        try:
            raw = complete(sys_p, user, max_tokens=200).strip()
            out = (raw.splitlines()[0].strip("「」\"' 　") if raw else "")
            if out and out.lower() != trend.lower() and "離線示範" not in out and not is_sensitive(out):
                return out
        except Exception:  # noqa: BLE001
            pass
    return random.choice(FALLBACK)  # safe default if framing keeps producing sensitive/empty


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo", default="TW")
    ap.add_argument("--output", default="topic.txt")
    args = ap.parse_args()

    trends: list[str] = []
    for geo in [args.geo, "US"]:
        try:
            trends = fetch_trends(geo)
            if trends:
                print(f"[trending] {len(trends)} trends from geo={geo}")
                break
        except Exception as e:  # noqa: BLE001
            print(f"[warn] trends fetch failed for {geo}: {e}")
    safe_trends = [t for t in trends if not is_sensitive(t)]
    if len(safe_trends) < len(trends):
        print(f"[trending] filtered out {len(trends) - len(safe_trends)} sensitive trend(s)")
    if safe_trends:
        trend = random.choice(safe_trends)
        topic = frame_topic(trend)
    else:
        trend = random.choice(FALLBACK)
        topic = trend
    if is_sensitive(topic):  # final safety net
        print("[trending] framed topic still sensitive; using safe fallback")
        topic = random.choice(FALLBACK)
    print(f"[trending] picked trend={trend!r} -> topic={topic!r}")

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(topic)
    # also emit on stdout (last line) for shell capture
    print(topic)
    return 0


if __name__ == "__main__":
    sys.exit(main())
