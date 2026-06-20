# 還缺什麼 / 需要你提供的東西（GAPS）

repo 本身已經**可以跑完整條流程**（缺 key 時自動降級）。要把它變成「全自動、產出真實 AI 內容並發布」，還需要以下決策與資料。我把它分成「必要」「依需求」「未來擴充」。

## A. 必要（要真實內容，至少給其一/其二）
1. **LLM API key** — `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`。沒有的話腳本只會輸出範本文字。
2. **發布平台帳號** — 若要自動上 YouTube，需要 OAuth 三件組（client id / secret / refresh token，見 SETUP.md §3）。

## B. 依需求（看你要做到哪一步）
3. **數字人「臉」要怎麼來？** 三選一，影響成本與是否需要 GPU：
   - 本機 GPU + Wav2Lip/SadTalker（免費、最靈活，需註冊 self-hosted runner + 下載模型權重 `wav2lip_gan.pth`）。
   - 雲端 API（HeyGen / D-ID / Synthesia）——最簡單、純 API，但要付費 + 申請 key（目前 repo 尚未實作這條，需要你決定要哪家我再接）。
   - 不要真人臉，只用「背景 + 字幕 + 語音」的圖文影片（現在預設就是這種，零成本）。
4. **TTS 等級** — 免費 edge-tts（已可用）vs 付費 ElevenLabs/Azure（情感、語音克隆）。要升級請給對應 key + 指定語音。
5. **素材** — 品牌背景圖、頭像圖、片頭/片尾、背景音樂（放 `assets/`）。沒有就用佔位純色背景。
6. **目標語言/口音** — 預設 zh-TW 腳本 + `zh-CN-XiaoxiaoNeural` 語音；台灣口音可換 `zh-TW-HsiaoChenNeural`；要多語版本再說。

## C. 未來擴充（研究有提到、目前未實作）
7. **多平台發布** — 目前只實作 YouTube；Bilibili / TikTok / Shorts 需各自的 API 與授權。
8. **語音克隆 / 情感語音**（GPT-SoVITS、FishSpeech）— 需 GPU self-hosted。
9. **去背 / 綠幕、即時表情**（MuseTalk）— 需 GPU。
10. **績效儀表板** — 把 YouTube/B站分析數據收集後用 GitHub Pages 視覺化（研究有規劃，可再做一個 dashboard）。
11. **A/B 測試 / 異常監控 / 品質檢查** — 研究列出的進階面向，可後續加。

## D. 我需要你回覆的關鍵 3 個問題
1. **數字人要不要真人臉？** → 不要(圖文影片) / 本機 GPU Wav2Lip / 雲端 API（哪家？）
2. **LLM 用哪個？** → 給我 Anthropic 還是 OpenAI 的 key（或先用範本）
3. **發布到哪？** → 先只做 YouTube，還是要含 Bilibili/TikTok？

回了這三個，我就能把它從「能跑的骨架」收斂成「符合你需求的全自動產線」。
