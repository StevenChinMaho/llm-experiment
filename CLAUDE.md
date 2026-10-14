# CLAUDE.md

本專案是「人工智慧」選修課的期中／期末報告：在消費級 GPU 上部署本地大型語言模型（LLM），量化分析**推論速度、記憶體用量、回答品質**之間的權衡。你（Claude Code）負責協助進行實驗、整理數據、撰寫報告草稿與產生 Word 檔。

使用者：Kururinpa，資工系大學生。**一律使用繁體中文（臺灣用語）溝通與撰寫報告**，技術名詞可保留英文。使用者主要用 Ubuntu 與 VSCode。

## 先讀這些文件

| 檔案 | 內容 | 什麼時候讀 |
|---|---|---|
| `docs/report-spec.md` | 期中、期末的格式要求、大綱、頁數分配、Word 產生方式 | 撰寫或排版報告前 |
| `docs/experiment-plan.md` | 實驗設計、變數、指令、紀錄格式、評估腳本規格 | 進行或分析實驗前 |
| `docs/environment.md` | 兩台機器的硬體、軟體、啟動指令、已知陷阱 | 碰任何機器或指令前 |
| `docs/findings-so-far.md` | 已量到的數據、驗證過的記憶體公式、觀察到的現象 | 寫初步結果或分析時 |
| `docs/references.md` | 參考文獻候選清單與查證狀態 | 寫文獻評述或參考文獻時 |
| `eval/questions.json` | 任務正確率題組與標準答案 | 寫評估腳本或跑任務實驗時 |
| `eval/verify_answers.py` | 以獨立程式重新驗證所有標準答案（需 numpy） | 修改或新增題目後必跑 |
| `results/raw/preliminary/` | 先前實際跑出的 llama-server 啟動與推論 log | 需要引用初步數據時，以 log 為準 |
| `docs/format/*.pdf` | 老師給的期中、期末格式原檔 | 有格式疑問時 |

## 報告題目與研究問題

**消費級 GPU 上本地大型語言模型之推論速度、記憶體與品質權衡分析**（暫定，使用者可改）

**主軸（2026-10-12 定案）：VRAM 固定時，資源該花在權重精度、context 長度，還是讓模型多想幾個 token？** 這顆模型是混合架構（64 層只有 16 層有 KV，每 token 34 KiB），context 很便宜、權重才是瓶頸；它又是思考型模型，答對率和「想多久」有關。

核心研究問題（只承諾做得完的，任何一項不如預期報告仍能完整交出）：

- **RQ1**：量化等級（5 種＋Q8_0 基準）如何影響品質（KL 散度、困惑度）與速度？
- **RQ2**：在 12GB 與 16GB VRAM 下的最佳設定為何？（Pareto 前緣、最大 context、MTP 推測解碼的速度與 VRAM 代價）
- **RQ3**：低精度多想，能不能補回高精度少想？（同樣耗時下比較答對率）
- **RQ4**：計算工具能否修正本地模型的算術錯誤？

延伸（時間允許才做，計畫書寫「若時間允許」）：長文件情境、KV cache 精度、繁體中文困惑度、網頁搜尋 MCP。**新點子一律先放進延伸，不改核心。**

計畫總覽網頁：<https://claude.ai/artifact/6zoEs6rVaeeAtcAvasS9Hp>

期中＝研究計畫書（**剛好 25 頁**），提出計畫並附初步數據。期末＝研究方法（70%）＋執行結果（30%），交完整實驗結果。

## 絕對規則

1. **不得捏造任何數據。** 報告中每個實測數字都必須能追溯到 `results/` 裡的原始紀錄或 `results/raw/preliminary/` 的 log。沒有數據就寫「待量測」。理論推導值要明確標示為推導值，不可與實測混用。
2. **不得捏造參考文獻。** `docs/references.md` 中標為「未查證」的條目，必須由使用者在 Google Scholar（或論文官方頁面）確認作者、標題、年份、出處後，才能放進報告。你可以用 WebSearch 協助查證，但要把查到的連結給使用者確認，並更新狀態欄。絕不自行生成看似合理的文獻。
3. **不要動 Minecraft 伺服器。** kururinpa-svr 上同時跑著大型模組 Minecraft 伺服器（原生 Java/Forge，非 Docker，有 systemd 的通知服務 mc-notify）。未經使用者明確同意，不得停止、重啟、修改它或它的服務。若它可能干擾實驗（CPU／RAM 競爭），告訴使用者，由他決定是否暫停。
4. **破壞性或不可逆的操作先問。** 刪除模型檔、`docker system prune`、改驅動、改系統設定、改防火牆、刪除使用者資料，都要先確認。
5. **每筆實驗紀錄必須附上環境資訊**：機器、GPU、驅動版本、llama.cpp build 編號、執行方式（Docker 映像 tag 或 conda）、模型檔名、完整指令、日期時間、GPU 溫度與功耗。缺這些的數據不算數。
6. **不要相信模型自己的計算。** 本地模型在大數運算常出錯（見 findings 中「600 vs 601」案例）。批改一律用程式比對標準答案，不可讓 LLM 批改 LLM。
7. **不要把 API key、密碼或使用者的 email 寫進任何會被提交或公開的檔案。**

## 工作方式

- 開始時先確認你在哪台機器上（`hostname`、`nvidia-smi`），不要假設。兩台機器的 IP 與路徑見 `docs/environment.md`。
- 長時間任務（llama-bench、perplexity、整輪評估）一律背景執行並把輸出寫到 `results/raw/`：用 `tmux`、`nohup` 或 Docker `-d`，避免 SSH 斷線導致中斷。
- 跑實驗前先跟使用者確認三件事：GPU 上有沒有其他負載、Minecraft 伺服器狀態、這次要跑哪些條件。
- 同一時間一張 GPU 只跑一個實驗。跑 llama-bench 或 perplexity 前，要先停掉常駐的 llama-server 容器（`docker stop llama`），跑完再啟動回來，並告知使用者。
- 實驗腳本放 `scripts/`，原始輸出放 `results/raw/`，整理後的表格放 `results/processed/`（CSV＋Markdown），圖放 `results/figures/`（PNG，300 dpi，圖中文字用繁體中文）。
- 報告先以 Markdown 寫在 `report/midterm/` 或 `report/final/`，使用者審閱後再轉成 Word（方式見 `docs/report-spec.md`）。
- 不確定的事（實驗條件、題目、報告寫法、要不要加某個實驗）直接問使用者，不要自己腦補。
- 建議用 git 管理本資料夾（模型檔與大型 log 加入 `.gitignore`）。commit 前先問使用者。

## 目錄結構

```
.
├── CLAUDE.md
├── docs/
│   ├── report-spec.md
│   ├── experiment-plan.md
│   ├── environment.md
│   ├── findings-so-far.md
│   ├── references.md
│   └── format/                 # 老師的格式 PDF
├── eval/
│   └── questions.json          # 任務題組
├── scripts/                    # 實驗與評估腳本（待建立）
├── results/
│   ├── raw/
│   │   └── preliminary/        # 先前的 llama-server log（初步數據的證據）
│   ├── processed/
│   └── figures/
└── report/
    ├── midterm/
    └── final/
```

## 目前進度

- [x] 兩台機器皆已部署 Qwen3.8-27B，能正常推論
- [x] 已取得初步數據（見 `docs/findings-so-far.md`）
- [x] 已設計兩組任務題目，答案皆已用程式驗證
- [x] 統一兩台機器的 llama.cpp 版本與執行環境（2026-10-12：兩台都是驅動 595.91.07＋b11347 映像，digest 鎖定）
- [x] 附帶發現：Windows 超配 VRAM 只拖慢 prefill（docs/findings-so-far.md §2.2）
- [x] 研究問題定案（2026-10-12）
- [ ] 向老師確認研究範圍，以及封面／目錄／參考文獻是否算進 25 頁
- [x] 撰寫評估腳本 `scripts/run_eval.py`（2026-10-13；`--self-test` 38 題全過，已對 svr 做端對端測試）
- [x] 下載額外量化檔（2026-10-13，全部 sha256 吻合）
- [x] MTP 可行性測試（2026-10-13，可用，findings §2.3）
- [x] E1 速度（llama-bench）—— 兩台完成（findings §2.4、§2.5）
- [x] E2 記憶體 —— 兩台完成（findings §2.7、§2.10）
- [x] E3 品質（KL 散度＋困惑度，WikiText-2 全 145 chunk）—— 完成（findings §2.6）
- [x] MTP 正式量測（3060）—— 完成（findings §2.8）
- [x] E4 難度校準 —— 完成（findings §2.9；IQ4_XS／16K 下有天花板效應）
- [ ] E4 正式的量化 × 思考預算實驗 —— 期末（規模待使用者決定）
- [ ] E5 計算工具 —— 期末
- [ ] 參考文獻查證
- [ ] 期中計畫書撰寫與排版（25 頁）
- [ ] 期末報告

截止日期：期中 2026/11/07 17:10、期末 2027/01/02

時程：10/13–10/19 腳本＋E1／E2／E3＋MTP 可行性；10/20–10/31 期中 Markdown 草稿；11/01–11/06 轉 Word、調到 25 頁。
