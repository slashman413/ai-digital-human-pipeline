# AI Digital Human Pipeline — 全自動 AI 影片產線（GitHub Actions）

用 **GitHub Actions** 把「找題目 → 寫腳本 → 生成畫面與配音 → 合成影片 → 多平台發布」整條產線自動化。
重點工作流 **Daily Auto Publish** 每天自動跑：抓 Google Trends 熱門主題 → DeepSeek 寫腳本 → 仿真背景圖＋台灣腔配音 → 合成 720p 影片 → 自動發到 **YouTube / TikTok / Bilibili** → Discord 通知。

> 全程跑在免費的 GitHub Hosted Runner（純 CPU），不需要自備伺服器或 GPU。

---

## 🎬 一鍵理解整條流程

```
  ┌─────────────────────── GitHub Actions（排程 cron，每天自動）──────────────────────┐
  │                                                                                   │
  │  1. 找題目        scripts/trending_topic.py                                        │
  │     Google Trends RSS（免金鑰）→ 隨機挑熱門 → DeepSeek 轉成主題 → 過濾敏感題材      │
  │                         │                                                          │
  │  2. 寫腳本        scripts/generate_longform.py（兩階段：大綱 → 逐段擴寫）           │
  │     DeepSeek 產出 N 個分鏡，每段含「旁白」+「英文畫面描述」+ 標題/說明/標籤         │
  │                         │                                                          │
  │  3. 生素材        scripts/generate_scene_assets.py                                 │
  │     每段：edge-tts 台灣腔配音 ＋ Pollinations 仿真背景圖(1280x720，免金鑰)          │
  │                         │                                                          │
  │  4. 合成影片      scripts/assemble_longform.py                                     │
  │     720p@15fps，背景隨腳本切換，隨機自然轉場(xfade)，繁體字幕(去標點)               │
  │                         │                                                          │
  │  5. 發布          upload_youtube.py / upload_tiktok.py / upload_bilibili.py        │
  │     三平台平行發布，缺憑證的平台自動 dry-run（不影響其他平台）                       │
  │                         │                                                          │
  │  6. 通知          Discord webhook                                                  │
  └───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔁 Workflows 一覽（`.github/workflows/`）

| Workflow | 觸發 | 做什麼 |
|----------|------|--------|
| **`daily-auto.yml`** ⭐ | 每天 01:17 UTC（≈台灣 09:17）+ 手動 | 熱門題目 → 10 分鐘影片 → 自動發三平台 → 通知（**主力**）|
| `longform-video.yml` | 手動 | 指定主題 → 生成 720p 長影音（不自動發布，產出 artifact）|
| `content-pipeline.yml` | 每天 08:00 UTC + 手動 | 短影音版（圖文 + 字幕），可選發布 |
| `daily-digest.yml` | 每天 06:00/18:00 UTC + 手動 | 抓科技熱點 → 摘要 → 短影音腳本草稿（artifact）|

> 手動觸發：GitHub repo → **Actions** 分頁 → 選 workflow → **Run workflow**。
> 想暫停每日自動發布：把 `daily-auto.yml` 的 `schedule` 那段註解掉，或在 repo → Actions 把該 workflow 設為 Disabled。

---

## 🧱 每日自動流程逐步說明（`daily-auto.yml`）

1. **找題目** — `trending_topic.py`：抓 `https://trends.google.com/trending/rss?geo=TW`（免金鑰），隨機挑一個熱門關鍵字，請 DeepSeek 轉成「資訊型/科普型」影片主題。**內建敏感題材過濾**（見下）。
2. **寫腳本** — `generate_longform.py`：**兩階段生成**（先列分鏡大綱，再逐段擴寫到目標字數），確保長度穩定到 ~10 分鐘；同時輸出 `title.txt`/`description.txt`/`tags.txt` 給發布用。
3. **生素材** — `generate_scene_assets.py`：逐段用 `edge-tts`（台灣腔 `zh-TW-HsiaoChenNeural`）配音；每段的英文畫面描述丟給 `Pollinations.ai` 生成 1280×720 仿真照片背景。
4. **合成** — `assemble_longform.py`：每段背景靜止（避免抖動），段與段之間插入**隨機自然轉場**，燒上**去標點的繁體字幕**，輸出 720p@15fps。
5. **發布** — 三個 uploader 平行跑；任一平台缺憑證 → 自動 dry-run。
6. **通知** — Discord。

---

## 📜 Scripts 一覽（`scripts/`）

| 檔案 | 用途 |
|------|------|
| `trending_topic.py` | 抓 Google Trends 熱門 → 轉主題 → 過濾敏感題材 |
| `generate_longform.py` | 兩階段生成多分鏡長腳本 + 標題/說明/標籤 |
| `generate_scene_assets.py` | 逐段 TTS + 生成仿真背景圖，輸出 manifest |
| `assemble_longform.py` | 合成 720p 影片：靜態背景 + 隨機轉場 + 去標點字幕 |
| `llm.py` | 共用 LLM 呼叫（DeepSeek → Claude → OpenAI → 離線範本）|
| `upload_youtube.py` / `upload_tiktok.py` / `upload_bilibili.py` | 各平台發布（缺憑證自動 dry-run）|
| `generate_script.py` / `generate_tts.py` / `generate_subtitles.py` | 短影音版用 |
| `fetch_daily_digest.py` / `script_from_digest.py` | 每日選題摘要用 |

---

## 🎥 影片規格（已為畫質最佳化）

- **1080p（1920×1080）@ 30fps**，CRF 20 高畫質編碼
- **背景**：依每段腳本自動生成的「仿真照片」（Pollinations flux 模型、enhance），隨內容切換
- **轉場**：段間隨機自然轉場（淡入淡出/溶解/滑入/擦除/圓形…）
- **配音**：台灣腔 `zh-TW-HsiaoChenNeural`，**音量 EBU R128 響度標準化**（loudnorm）
- **字幕**：繁體、時間軸對齊、不含標點、依解析度自動放大、燒進畫面
- **LLM**：DeepSeek V4 Flash（`deepseek-v4-flash`）為主

## 🚀 YouTube 成長最佳化（SEO + CTR）

- **SEO 標題/說明/標籤**：由 LLM 產生——標題關鍵字前置、引發好奇；說明含 hook + 可搜尋關鍵字 + 重點 bullet + 訂閱 CTA + hashtag；12–15 個中英混合 SEO 標籤（`generate_longform.py`）。
- **吸睛縮圖**：`make_thumbnail.py` 自動生成 1280×720 縮圖（仿真背景 + 大字粗體標題 + 描邊），上傳時自動套用（縮圖是點擊率最大槓桿）。
- **熱門選題**：`trending_topic.py` 從 Google Trends 挑題並用 LLM 轉成「高搜尋需求、廣泛受眾、易點擊」的角度（內建敏感題材過濾）。
- **導流 Shorts**：每支長片自動剪一支 9:16 短片，描述附完整版連結，公開發成 YouTube Shorts。

---

## 🛡 內容安全（避開敏感題材）

`trending_topic.py` 內建多層過濾，避開**政治/政黨/選舉/政治人物、色情/性、暴力/犯罪、醜聞/隱私、宗教爭議**：
1. 熱門清單先用關鍵字黑名單剔除明顯敏感項。
2. DeepSeek 轉主題時被明確要求「避開敏感類別，必要時改成中性知識主題」。
3. 產出的主題再做一次敏感字掃描，若仍命中 → 換成安全的預設主題（科學/健康/科技/生活/自然）。

---

## 🔑 設定 / Secrets

詳見 **[SETUP.md](SETUP.md)**。重點：
- `DEEPSEEK_API_KEY`（腳本生成；未設則用範本）
- `BILIBILI_COOKIES`（biliup 登入 cookies，已支援；runner 會自動安裝 biliup）
- `YOUTUBE_CLIENT_ID/_SECRET/_REFRESH_TOKEN`（YouTube）
- `TIKTOK_ACCESS_TOKEN`（TikTok）
- `DISCORD_WEBHOOK`（通知，可選）

缺哪個，對應平台/功能就自動降級，不會讓流程失敗。

---

## 💰 成本

幾乎免費：GitHub Actions（公有 repo 免費）、Google Trends RSS（免費）、Pollinations 生圖（免費）、edge-tts（免費）；只有 DeepSeek 腳本生成是付費但極便宜（一支幾分錢）。

---

## 📚 參考資源 / Reference repos

這個 repo 本身就是可直接參考、可執行的實作範例。它整合了以下開源工具，想深入可參考各自的 repo：

| 工具 | 用途 | Repo |
|------|------|------|
| biliup-rs | Bilibili 上傳 CLI | https://github.com/biliup/biliup-rs |
| edge-tts | 免費微軟 TTS | https://github.com/rany2/edge-tts |
| Pollinations | 免金鑰文字生圖 | https://github.com/pollinations/pollinations |
| openai-whisper | 語音轉字幕（短影音版用）| https://github.com/openai/whisper |
| FFmpeg | 影片合成/轉場 | https://github.com/FFmpeg/FFmpeg |
| Google Trends RSS | 熱門主題來源 | `https://trends.google.com/trending/rss?geo=TW` |

> 設計理念：純 CPU、免費資源優先、缺憑證自動降級、內容安全內建。把重複的交給機器，獨特的留給你。
