# 實驗計畫（2026-10-12 定案版）

主軸：**VRAM 固定時，資源該花在權重精度、context 長度，還是讓模型多想幾個 token？**

**範圍原則：** 核心實驗只承諾做得完的；任何一項不如預期，報告仍能完整交出。延伸實驗時間允許才做。新點子一律先放進「延伸」，不改核心。

## 研究問題與實驗對應

| 實驗 | 回答 | 產出 | 時程 |
|---|---|---|---|
| E1 速度 | RQ1、RQ2 | pp／tg 對照表、context 深度曲線、部分卸載曲線、頻寬使用率、J/token、MTP 開／關 | 期中前 |
| E2 記憶體 | RQ2 | 實測 vs 公式比對表、各設定最大可用 context | 期中前 |
| E3 品質 | RQ1 | 各量化的 KL 散度（主要）與困惑度 | 期中前 |
| E4 量化 × 思考預算 | RQ3 | 同樣耗時下的答對率、答對率 vs 耗時曲線 | 期中前做難度校準，期末做正式實驗 |
| E5 計算工具 | RQ4 | 有／無計算工具的答對率 | 期末 |
| X1～X4 延伸 | 補強 RQ2 | 見「延伸實驗」 | 時間允許 |

## 自變數

| 變數 | 水準 | 用在 |
|---|---|---|
| 硬體 | RTX 3060 12GB（kururinpa-svr）、RTX 5060 Ti 16GB（主力機 Ubuntu） | E1、E2 |
| 權重量化 | UD-IQ2_XXS（6.77 GiB）、UD-Q2_K_XL（9.15）、UD-IQ3_XXS（10.18，已有）、UD-IQ4_XS（13.27，已有）、UD-Q4_K_XL（16.35）；基準 Q8_0（27.05） | E1、E2、E3；E4 取其中 2～3 種 |
| context 深度 | 0、4096、16384、32768（E1）；E2 另外掃描最大值 | E1、E2 |
| 思考預算 | `--reasoning-budget` 1024、4096、16384 token | E4 |
| MTP 推測解碼 | 關、開（`--spec-type draft-mtp`＋`MTP/mtp-Qwen3.8-27B-Q4_0.gguf`，1.28 GiB） | E1；E4 只當一個候選設定 |

檔案大小取自 HF API（2026-10-12）。下載前再確認一次，並記錄 sha256（HF 快取的 blob 檔名就是 sha256）。

**放得下與放不下（預估，以 E2 實測為準）：**

| | 16GB 全 GPU | 16GB 部分卸載 | 12GB 全 GPU | 12GB 部分卸載 |
|---|---|---|---|---|
| UD-IQ2_XXS、UD-Q2_K_XL、UD-IQ3_XXS | ✔ | | ✔ | |
| UD-IQ4_XS | ✔ | | | ✔ |
| UD-Q4_K_XL | | ✔ | | 不做 |
| Q8_0 | | 只用於 E3 基準（64GB RAM 部分卸載） | | |

**不納入：** `Huihui-Qwen3.8-27B-abliterated` 等第三方修改版（改的是權重本身，不是量化等級，會混淆變因）。

## 控制變數

1. **llama.cpp 版本與執行環境一致**（已完成）：兩台都用 Docker、驅動 595.91.07、鎖定 digest
   - server 映像：`ghcr.io/ggml-org/llama.cpp@sha256:936e9d2afab78662a05fd300c4a829ba931777bcd8372334da629b468511f90e`（`server-cuda13-b11347`）
   - full 映像（含 llama-bench、llama-perplexity）：`ghcr.io/ggml-org/llama.cpp@sha256:3f7b5ae419f81c940b6171e004ee780091787a9cdb1c413b192fcb338a2d8590`（`full-cuda13-b11347`）。server 上還沒拉這個映像
2. 相同的模型檔（比對 sha256）
3. 固定參數：`-fa on`、KV cache `q8_0`、`-np 1`，執行緒數記錄下來；不載入 mmproj
4. 量測時 GPU 上沒有其他負載：主力機 Ubuntu 預設 `multi-user.target`、沒有桌面（實驗前仍記錄 `nvidia-smi`）；server 上停掉常駐 llama 容器
5. **Minecraft 伺服器**：每次實驗前和使用者確認二選一並記錄：（a）使用者同意暫停 MC，或（b）不暫停，但每次量測同時記錄 `uptime` 的 load average 與 `free -m`。部分卸載條件（會用到 CPU 和 RAM）受影響最大
6. 正式量測前先跑一次暖機
7. 每個條件重複 5 次（llama-bench `-r 5`），報告平均 ± 標準差
8. 背景記錄 GPU 溫度、功耗、時脈（`nvidia-smi --query-gpu=timestamp,temperature.gpu,power.draw,clocks.sm,memory.used,utilization.gpu --format=csv -l 1`），排除過熱降頻，也用來計算 J/token
9. 跑基準測試時加 `-fit off`，或確認 log 沒有自動調整參數
10. E2 啟動時一律加 `-lv 4`（預設 verbosity 3 不會印出 buffer 大小）
11. 正式實驗只在 Linux 上做。Windows 的結果（findings §2.2）只當作背景與動機

## E1 速度（期中前）

工具：full 映像的 `llama-bench`。

```bash
llama-bench -m /models/<模型>.gguf -ngl 99 -fa 1 -ctk q8_0 -ctv q8_0 \
  -p 512 -n 128 -d 0,4096,16384,32768 -r 5 -o json > results/raw/e1_<機器>_<量化>_<日期>.json
```

- 先用 `llama-bench --help` 確認 b11347 的 `-d`（depth）語法
- 部分卸載（3060＋IQ4_XS、5060 Ti＋Q4_K_XL）：從可行的最大 `-ngl` 往下掃，例如 `-ngl 60,56,52,48`，畫「GPU 層數 vs 速度」曲線
- 同時保留一份 `-o md` 給人看

**衍生指標（從同一批數據計算，不需要另外量）：**

- **頻寬使用率** ＝ 權重 bytes × tg ÷ 理論頻寬（5060 Ti 448 GB/s、3060 360 GB/s）。用來檢驗 findings §5「3060 只有 66% 速度與 L2 快取有關」的推測
- **J/token** ＝ 量測期間平均功耗 ÷ tg
- **TTFT 估計** ＝ prompt 長度 ÷ pp

**MTP 可行性測試（期中前，先做）：**

1. 用 llama-server 加 `--spec-type draft-mtp --spec-draft-model /models/MTP/mtp-Qwen3.8-27B-Q4_0.gguf` 啟動，確認能正常運作、記錄額外佔用的 VRAM
2. 用 `/completion` 送固定題目，比較開／關的 tg，並從 log 記錄**接受率**
3. 掃描 `--spec-draft-n-max` 1、2、3、4
4. 題目類型會影響接受率：至少用程式碼、數學、一般問答三類各量一次
5. MTP 是無損的（輸出分布不變），它的代價是 VRAM，也就是 context 容量
6. ~~若 b11347 無法搭配這顆模型使用 MTP~~ → **2026-10-13 已確認可用**（findings §2.3）：-c 16384 時多佔約 1.7 GiB（以 39 KiB/token 計約等於 4.5 萬 token 的 context，推導值），程式碼／數學 tg 約 2.4～2.6 倍、中文問答約 1.36 倍
7. 正式量測時要補：掃 `--spec-draft-n-max` 並記錄 RS buffer（驗證「RS ＝ 149.62 ×（1＋n_max）」的推測）；greedy（temp 0）開／關各跑一次，比對輸出是否逐字相同；思考開啟時的接受率

## E2 記憶體（期中前）

- 每個條件啟動 llama-server（`-lv 4 -fit off`），從 log 解析：`CUDA0 model buffer size`、`CPU_Mapped model buffer size`、`KV buffer size`、`RS buffer size`、`compute buffer size`，以及 fit 的 memory breakdown
- 同時記錄 `nvidia-smi --query-gpu=memory.used --format=csv`
- 與公式預測值（findings §3：每 token 34 KiB）比對，計算誤差
- 找出每個（硬體 × 量化）全 GPU 時的最大 context：以 `-fit off` 逐步加大 `-c`，以「能啟動、log 顯示 66/66 layers、能完成一次 prefill」為準（Linux 放不下會直接 OOM，界線明確）
- MTP 開啟時的最大 context 也量一次
- 寫 `scripts/parse_server_log.py`，從 log 抽出上述欄位，輸出 CSV

## E3 品質：KL 散度與困惑度（期中前）

```bash
# 1. 用 Q8_0 產生基準 logits（主力機 64GB RAM，部分卸載，很慢）
llama-perplexity -m /models/Qwen3.8-27B-Q8_0.gguf -f wiki.test.raw -c 2048 -ngl <可行值> -fa 1 \
  --kl-divergence-base /models/kld/q8_0_base.kld --chunks <N>
# 2. 各量化對基準計算 KL 散度，同時得到困惑度
llama-perplexity -m /models/<量化>.gguf -f wiki.test.raw -c 2048 -ngl 99 -fa 1 \
  --kl-divergence-base /models/kld/q8_0_base.kld --kl-divergence > results/raw/e3_<量化>_<日期>.txt 2>&1
```

- 資料集：WikiText-2 raw 測試集（取得方式參考 llama.cpp repo 的 `scripts/get-wikitext-2-raw.sh`）
- **基準 logits 檔可能很大**（詞彙量 248,320）：正式跑之前先用小 `--chunks` 估算檔案大小，再決定 N，並確認 `/nvme477` 剩餘空間。基準檔不放進 git
- 主要指標：平均 KL 散度、99% 分位 KL 散度、Same top p（top-1 token 與基準一致的比例）；輔助：困惑度 ± 誤差
- **品質與硬體無關**：每種量化只在主力機跑一次；在 3060 上用 IQ3_XXS 抽測一次困惑度，確認結果一致（本身就是一個驗證點）
- 注意：以 Q8_0 當基準是近似（不是 BF16），要在報告的限制章節說明
- 分析時檢驗「KL 散度能不能預測 E4 答對率的下降」

## E4 量化 × 思考預算（RQ3）

題目（2026-10-13 定案，使用者決定用公開 benchmark）：

- **`eval/aime_2026.json`：AIME 2026 I＋II 共 30 題**（來源 MathArena/aime_2026，CC BY-NC-SA 4.0；引用 references #21）。答案皆為 0～999 整數，用 `exact_int` 批改。答案與 math-ai/aime26 逐題比對 30/30 一致；題目文字和三份來源逐字比對，I-10、I-13 有抄寫錯誤，已依 AoPS Wiki 官方題目改正並以 `eval/verify_aime_2026.py` 程式重算答案
- **`eval/questions.json` 的 `hard` 組 8 題**：自己出的題目，不可能出現在訓練資料中，用來對照汙染的影響
- 合計 **38 題**，使用**配對設計**
- **汙染風險**：AIME 2026 在 2026 年 2 月舉行，早於 Qwen3.8-27B 發布（第三方報導為 2026-08-14，未經官方確認），模型可能看過這些題目。報告的限制章節要說明，並比較 AIME 與 hard 組的答對率差異
- `easy` 組 8 題留作「關閉思考」條件的對照

### 設計

**2026-10-14 校準後的決定（使用者確認）：** 題目不換（38 題）；每題每條件**重複 2 次**；兩台機器**分工**（答對率與硬體無關，16GB 才放得下的條件放主力機）；max_tokens 改為「預算 ＋ 4096」（校準時 I-15 因答案空間不足被截斷）

- 量化：3 種（UD-Q2_K_XL、UD-IQ3_XXS、UD-IQ4_XS）
- 思考預算：1024、4096、16384 token（`--reasoning-budget`）
- 每題每條件重複 2 次（原計畫 3 次）。粗估總時數約 31 小時
- context 固定 **32768**
- 每個條件都答同一批題目 → 用 McNemar 檢定或配對 bootstrap 比較
- **答對率與 token 數和硬體無關**，只在 5060 Ti 上跑。各硬體的耗時，用 E1 量到的 pp／tg（隨深度變化）推算，標示為**推導值**，再到 3060 上抽測 2～3 個設定驗證推算準確度
- 主要比較：在同樣的 TTA 之下，哪個（量化 × 預算）組合答對率最高

### 時間指標

| 指標 | 定義 |
|---|---|
| TTFT | 送出 → 第一個 token（通常是思考內容）。反映 prefill 延遲 |
| TTA | 送出 → 思考結束、答案第一個字出現。使用者實際等待的時間 |
| 總耗時 | 送出 → 回答結束 |

TTA 需要用串流（`"stream": true`）在客戶端記錄每段內容的到達時間。

### 評估腳本規格：`scripts/run_eval.py`

- 透過 llama-server 的 OpenAI 相容 API（`/v1/chat/completions`，串流）送題
- 參數：伺服器 URL、題組、每題重複次數、思考預算（伺服器端設定，腳本記錄）、`max_tokens`、輸出路徑
- 每次送題都是**全新的對話**（不帶歷史），請求帶 `"cache_prompt": false`；伺服器啟動加 `--cache-ram 0`
- 使用模型內建取樣參數（temp 1.0、top_p 0.95、top_k 20），不另外覆寫，並記錄在結果中
- 思考預算用完時，llama.cpp 會強制結束思考；`max_tokens` 用完而答案未完成，記為失敗並標記原因
- 每筆紀錄存 JSONL：題號、第幾次、完整回應（含 reasoning_content）、擷取出的答案、是否正確、prompt／reasoning／answer 各自的 token 數、TTFT、TTA、總耗時、是否截斷、伺服器資訊（model、build、啟動參數）
- 批改依 `grading` 欄位：
  - `exact_int`：從「答案：」那行擷取整數比對
  - `exact_text`：去除空白、全形半形正規化後比對
  - `fraction`：解析為分數後比對（接受 5/11、等值分數）
  - `multi_field`：多個欄位都要對
  - `json_fields`：解析 JSON，所有欄位相等
  - `python_tests`：擷取程式碼，在**隔離的子行程**中執行（timeout 10 秒、不給網路、暫存目錄），全部測資通過才算對；禁止使用 `eval` 的題目要做靜態檢查
- 擷取失敗（沒有「答案：」那行）記為錯誤，另外統計擷取失敗率
- 輸出統計：每題答對率、整體答對率、Wilson 95% 信賴區間、配對比較結果、平均 token 數與耗時

### 流程

1. **難度校準試跑（期中前）**：hard 組每題用 IQ4_XS、預算 16384 跑 2～3 次。理想答對率 30%～70%。全對或全錯的題目沒有鑑別力，回報使用者討論是否替換（**不要自行改題**）
2. 擴充題目（使用者決定方式）
3. 正式實驗（期末）：建議晚上背景跑。粗估：40 題 × 3 次 × 3 預算 × 3 量化，平均每題 2～3 分鐘 → 約 36～54 小時，需分多晚執行；必要時減少量化或預算水準

## E5 計算工具（RQ4，期末）

- 讓模型能呼叫計算函式（function calling，或在 prompt 中允許輸出 Python 再由腳本執行）
- 用含大數運算的題目（easy 組 E8、hard 組 H7，再出幾題同類型）比較有／無工具的答對率。動機：「600 vs 601」案例
- 批改一樣用程式比對標準答案

## 延伸實驗（時間允許才做）

| 代號 | 內容 | 價值 |
|---|---|---|
| X1 長文件情境 | 用程式產生 16K～64K 的長文件檢索題（類似 RULER 的作法，長度可控、可程式批改），比較不同 context 設定 | 讓「context 容量」在 RQ2 中真正被考驗 |
| X2 KV cache 精度 | f16／q8_0／q4_0 各算一次 KL 散度（IQ4_XS）；記憶體用公式推導（64／34／18 KiB/token） | 12GB 卡若 q4_0 無損，context 可加倍 |
| X3 繁體中文困惑度 | 用一份繁中語料算各量化的困惑度（語料來源待定） | 量化對中文的影響可能與英文不同（推測） |
| X4 網頁搜尋 MCP | llama-server Web UI 的 MCP，或腳本串接 SearXNG；10～15 題時效性問題（使用者出題並確認答案、日期、來源） | 原 RQ3 的另一半 |

## 紀錄格式

每次實驗在 `results/raw/` 產生原始輸出，並在 `results/runs.csv` 追加一列：

```
run_id, datetime, experiment, machine, gpu, driver, llamacpp_build, image_digest, model_file, model_sha256, command, mc_server_state, notes, raw_output_path
```

`run_id` 格式：`<實驗>_<機器>_<量化>_<YYYYMMDD-HHMM>`，例如 `e1_svr_iq3xxs_20261015-2130`。

## 時間估算

- 下載額外量化檔：約 60 GB（Q8_0、Q4_K_XL、Q2_K_XL、IQ2_XXS、MTP），取決於網速
- E1：每台約 1～2 小時（含部分卸載掃描）；MTP 可行性約 1 小時
- E2：每台約 1 小時
- E3：Q8_0 基準數小時（部分卸載），其他每種量化約 30～60 分鐘
- E4 校準：約 1～2 小時；正式實驗見上
