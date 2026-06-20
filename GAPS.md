# 還缺什麼 / 需要你提供的東西（GAPS）

repo 本身已經**可以跑完整條流程**（缺憑證時自動降級 dry-run，不會失敗）。

## ✅ 已定案（依你 2026-06-20 的決定）
1. **數字人形式 = 圖文影片**（背景 + 字幕 + 語音），不做真人臉 → 已移除 GPU/Wav2Lip 路徑，不需 self-hosted runner。
2. **LLM = Claude**（Anthropic，預設 `claude-sonnet-4-6`；`scripts/llm.py`）。
3. **發布平台 = YouTube + TikTok + Bilibili** → 已實作三個 uploader，`publish` job 以 matrix 平行發布。

## 🔑 還需要你提供的「憑證」（給了才會真的發出去/用真 AI 生成）
全部設在 repo → Settings → Secrets and variables → Actions。任一缺少 → 該部分自動 dry-run。

| 用途 | Secret | 沒給的後果 |
|------|--------|-----------|
| Claude 生成腳本（雲端自動） | `ANTHROPIC_API_KEY` | 用離線範本（內容是範本，非 AI 生成）|
| YouTube 發布 | `YOUTUBE_CLIENT_ID` / `_SECRET` / `_REFRESH_TOKEN` | YouTube dry-run |
| TikTok 發布 | `TIKTOK_ACCESS_TOKEN` | TikTok dry-run |
| Bilibili 發布 | `BILIBILI_COOKIES`（+ runner 裝 biliup）| Bilibili dry-run |
| Discord 通知 | `DISCORD_WEBHOOK` | 略過通知 |

## 📌 關於「你自己就是 LLM」
腳本生成就是用 Claude。兩種運作方式：
- **A. 雲端全自動**：設 `ANTHROPIC_API_KEY` 一個 secret，GitHub Actions 排程時自動呼叫 Claude 寫腳本（最省事、24h 自動）。
- **B. 我在這邊先寫好**：我（Claude Code）直接在對話這側產生腳本並 commit 進 repo，workflow 只做 TTS+合成+發布。完全不用任何 key，但需要我被觸發來補稿（非 24h 全自動）。
> 我已放一支我親自寫的示範腳本在 `samples/sample_script.md`，示範 B 模式的產出品質。你選 A 或 B 跟我說即可。

## 🧩 未來可加（目前未做）
- 多語版本（自動翻譯 + 多語 TTS + 字幕）
- 績效儀表板（YouTube/B站 數據 → GitHub Pages 視覺化）
- A/B 測試、品質檢查、異常監控與降級
- 升級 TTS（ElevenLabs/Azure 情感語音）
