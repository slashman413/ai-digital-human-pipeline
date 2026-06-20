# AI Digital Human Pipeline — GitHub Actions 自動化數字人產線

把「文字腳本 → 語音 → 字幕 → 影片合成 → (口型同步) → 發布」整條數字人產線，用 **GitHub Actions** 自動編排。純 CPU 階段跑在免費的 GitHub Hosted Runner，需要 GPU 的口型同步走你本機的 self-hosted runner。

> 這個 repo 是把 `Github-Actions-Research` 那份研究藍圖**落地成可實際執行的程式碼**：研究列出了每個階段能不能在 GHA 跑，這裡補上了它引用、但原本不存在的所有 Python 腳本 + 設定 + 文件。

[![Content Pipeline](https://github.com/slashman413/ai-digital-human-pipeline/actions/workflows/content-pipeline.yml/badge.svg)](../../actions/workflows/content-pipeline.yml)
[![Daily Digest](https://github.com/slashman413/ai-digital-human-pipeline/actions/workflows/daily-digest.yml/badge.svg)](../../actions/workflows/daily-digest.yml)

## 🚀 先跑起來（零設定）

不需要任何 API key 就能驗證整條流程 —— 缺 key 時 LLM 用離線範本、TTS/發布自動降級為 dry-run：

1. Fork / 建立此 repo 到你的 GitHub。
2. 到 **Actions** 分頁 → 啟用 workflows。
3. 開 **AI Digital Human — Content Pipeline** → **Run workflow**（可填主題，或留空讓 LLM 自動產生）。
4. 跑完到該 run 的 **Artifacts** 下載 `final-video`（一支含字幕的影片）。

接著照 [SETUP.md](SETUP.md) 把 secrets 補上，就會從「離線範本」變成真正的 AI 生成 + 真實發布。

## 🧩 架構

數字人採「**圖文影片**」(背景 + 字幕 + 語音)，不做真人臉口型同步 → 全程純 CPU、免費 runner、無需 GPU。

```
                 ┌──────────────── GitHub Actions（排程 + 編排）────────────────┐
  schedule /     │                                                              │
  workflow_dispatch ─► generate-content ─► compose-video ─► publish (matrix)    │
                 │   (Claude腳本+edge-tts)  (Whisper字幕+FFmpeg)   ├─ YouTube    │
                 │                                                ├─ TikTok     │
                 │                                                └─ Bilibili   │
                 │                                                    │         │
                 │                                                 notify(Discord)│
                 └──────────────────────────────────────────────────────────────┘
```

| 階段 | 腳本 | Runner | 需要 |
|------|------|--------|------|
| 腳本生成 | `scripts/generate_script.py`（LLM=Claude）| hosted (CPU) | `ANTHROPIC_API_KEY`（可無，用範本）|
| 語音 TTS | `scripts/generate_tts.py` | hosted (CPU) | 無（edge-tts 免費）|
| 字幕 | `scripts/generate_subtitles.py` | hosted (CPU) | 無（Whisper tiny）|
| 影片合成 | FFmpeg（workflow 內）| hosted (CPU) | 無 |
| 發布 | `upload_youtube.py` / `upload_tiktok.py` / `upload_bilibili.py` | hosted (CPU) | 各平台憑證（缺則 dry-run）|
| 摘要選題 | `scripts/fetch_daily_digest.py` `script_from_digest.py` | hosted (CPU) | `ANTHROPIC_API_KEY`（可無）|

## 📁 結構

```
ai-digital-human-pipeline/
├── .github/workflows/
│   ├── content-pipeline.yml   # 主產線：腳本→TTS→字幕→合成→多平台發布→通知
│   └── daily-digest.yml       # 每日選題：熱點→摘要→腳本草稿
├── scripts/                    # 全部可獨立 CLI 執行
│   ├── llm.py                  # 共用 LLM 呼叫（Claude/OpenAI/離線範本）
│   ├── generate_script.py  generate_tts.py  generate_subtitles.py
│   ├── fetch_daily_digest.py  script_from_digest.py
│   ├── upload_youtube.py  upload_tiktok.py  upload_bilibili.py
├── samples/sample_script.md    # Claude 親自撰寫的示範稿
├── config/pipeline.example.yaml
├── assets/                     # background.png / avatar.png（沒放會自動生成佔位圖）
├── requirements.txt   .env.example
├── SETUP.md   GAPS.md
```

## 🔧 本機測試單一腳本

```bash
pip install -r requirements.txt
python scripts/generate_script.py --topic "auto" --output script.txt
python scripts/generate_tts.py --input script.txt --voice zh-CN-XiaoxiaoNeural --output audio/voice.mp3
```

## ⚠️ 還缺什麼

見 [GAPS.md](GAPS.md) —— 列出要變成「全自動真實發布」還需要你提供的 API 金鑰、素材、GPU runner 與平台選擇。
