# 設定指南（把離線範本變成真正自動化）

所有設定都在 **repo → Settings → Secrets and variables → Actions → New repository secret**。

## 1. LLM（腳本/摘要品質）— 擇一
| Secret | 取得 |
|--------|------|
| `ANTHROPIC_API_KEY` | console.anthropic.com（優先採用；模型預設 `claude-sonnet-4-6`）|
| `OPENAI_API_KEY` | platform.openai.com（預設 `gpt-4o`）|

兩者皆未設 → 腳本用內建離線範本（流程能跑，但內容是範本）。

## 2. TTS — 免費，無需設定
edge-tts 不需金鑰。想要台灣口音可在觸發 workflow 時把 voice 改成 `zh-TW-HsiaoChenNeural`。
（要升級成 ElevenLabs / Azure 情感語音，再加對應 key 並擴充 `generate_tts.py`。）

## 3. 發布平台（三個都接，缺憑證自動 dry-run）
`publish` job 用 matrix 平行發到 **YouTube / TikTok / Bilibili**。任一平台沒設好憑證 → 該平台自動 dry-run，不影響其他平台與整體流程。

### 3a. YouTube（OAuth refresh token）
1. Google Cloud Console 建專案 → 啟用 **YouTube Data API v3**。
2. 建 **OAuth client（Desktop）** → client id / secret。
3. 取得 **refresh token**（scope：`https://www.googleapis.com/auth/youtube.upload`）。
4. Secrets：`YOUTUBE_CLIENT_ID`、`YOUTUBE_CLIENT_SECRET`、`YOUTUBE_REFRESH_TOKEN`。預設隱私 `private`，確認後改 public。

### 3b. TikTok（Content Posting API）
1. 申請 TikTok for Developers app，開 **Content Posting API**，scope `video.publish`。
2. 跑一次 OAuth 拿到 user access token。
3. Secret：`TIKTOK_ACCESS_TOKEN`（可選 `TIKTOK_PRIVACY`，預設 `SELF_ONLY` 測試用）。

### 3c. Bilibili（biliup CLI + 登入 cookies）
1. 安裝 [`biliup`](https://github.com/biliup/biliup-rs)，本機 `biliup login` 產生 cookies.json。
2. 把 cookies.json 內容存成 secret `BILIBILI_COOKIES`（或放可存取路徑），可選 `BILIBILI_TID`（分區，預設 21）。
   > 註：GHA hosted runner 需先安裝 biliup；若未安裝則該平台 dry-run。

## 4. Discord 通知（可選）
`DISCORD_WEBHOOK` = 你頻道的 webhook URL。未設則略過通知。

## 5. 數字人形式：圖文影片（不需 GPU）
已依需求設定為「**背景 + 字幕 + 語音**」的圖文影片，**不做真人臉口型同步**，所以不需要 self-hosted GPU runner。想換背景/頭像圖只要把 `assets/background.png`（或 `avatar.png`）放進 `assets/`；沒放會自動產生純色佔位背景。
