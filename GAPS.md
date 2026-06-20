# 還缺什麼 / 需要你提供的東西（GAPS）

repo 本身已經**可以跑完整條流程**（缺憑證時自動降級 dry-run，不會失敗）。

## ✅ 已定案（依你 2026-06-20 的決定）
1. **數字人形式 = 圖文影片**（背景 + 字幕 + 語音），不做真人臉 → 已移除 GPU/Wav2Lip 路徑，不需 self-hosted runner。
2. **LLM = DeepSeek V4 Flash**（`deepseek-v4-flash`，優先採用；走 OpenAI 相容 API）。仍保留 Claude/OpenAI 作為 fallback。
3. **發布平台 = YouTube + TikTok + Bilibili** → 已實作三個 uploader，`publish` job 以 matrix 平行發布。

## 🔑 還需要你提供的「憑證」（給了才會真的發出去/用真 AI 生成）
全部設在 repo → Settings → Secrets and variables → Actions。任一缺少 → 該部分自動 dry-run。

| 用途 | Secret | 沒給的後果 |
|------|--------|-----------|
| DeepSeek 生成腳本（雲端自動，優先） | `DEEPSEEK_API_KEY` | 用離線範本（內容是範本，非 AI 生成）|
| YouTube 發布 | `YOUTUBE_CLIENT_ID` / `_SECRET` / `_REFRESH_TOKEN` | YouTube dry-run |
| TikTok 發布 | `TIKTOK_ACCESS_TOKEN` | TikTok dry-run |
| Bilibili 發布 | `BILIBILI_COOKIES`（+ runner 裝 biliup）| Bilibili dry-run |
| Discord 通知 | `DISCORD_WEBHOOK` | 略過通知 |

## 📌 LLM 運作方式（已選 A）
- **A. 雲端全自動（已選）**：設 `DEEPSEEK_API_KEY` 一個 secret，GitHub Actions 排程時自動呼叫 DeepSeek V4 Flash 寫腳本（最省事、24h 自動）。
- 仍保留 Claude/OpenAI 作為 fallback（設對應 key 即可切換；優先序 DeepSeek → Claude → OpenAI）。
> `samples/sample_script.md` 是一支示範腳本，供你參考輸出品質。

## 🧩 未來可加（目前未做）
- 多語版本（自動翻譯 + 多語 TTS + 字幕）
- 績效儀表板（YouTube/B站 數據 → GitHub Pages 視覺化）
- A/B 測試、品質檢查、異常監控與降級
- 升級 TTS（ElevenLabs/Azure 情感語音）
