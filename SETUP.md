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

## 3. YouTube 發布（OAuth refresh token）
1. Google Cloud Console 建專案 → 啟用 **YouTube Data API v3**。
2. 建 **OAuth client（Desktop）** → 拿到 client id / secret。
3. 用 OAuth playground 或一次性腳本取得 **refresh token**（scope：`https://www.googleapis.com/auth/youtube.upload`）。
4. 設三個 secret：`YOUTUBE_CLIENT_ID`、`YOUTUBE_CLIENT_SECRET`、`YOUTUBE_REFRESH_TOKEN`。

未設 → `upload_youtube.py` 自動 dry-run（只印出會上傳什麼，不會失敗）。預設隱私為 `private`，確認沒問題再改 public。

## 4. Discord 通知（可選）
`DISCORD_WEBHOOK` = 你頻道的 webhook URL。未設則略過通知。

## 5. 本機 GPU（口型同步 Wav2Lip / SadTalker）
1. 在你的 Windows GPU 機器：repo → Settings → Actions → Runners → **New self-hosted runner**，labels 設 `self-hosted, windows, gpu`。
2. clone Wav2Lip，放好 `checkpoints/wav2lip_gan.pth`，設 secret `WAV2LIP_DIR` 指向該資料夾。
3. 把 `content-pipeline.yml` 的 `gpu-processing` job 的 `if: false` 改成 `if: true`（或改用 `vars.ENABLE_GPU`）。

未設 → `wav2lip_process.py` 會把原影片原樣輸出（pass-through），流程不中斷。

## 6. 素材（可選）
把 `assets/background.png`（背景）、`assets/avatar.png`（頭像）、背景音樂放進 `assets/`。沒放的話，合成階段會自動產生純色佔位背景。
