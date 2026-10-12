# 實驗計畫

## 研究問題對應

| 實驗 | 回答 | 產出 |
|---|---|---|
| E1 速度 | RQ1、RQ2 | pp／tg 對照表、context 深度曲線、部分卸載曲線 |
| E2 記憶體 | RQ1、RQ2 | 實測 vs 公式比對表、各設定最大可用 context |
| E3 品質（困惑度） | RQ1 | 各量化的 PPL（±誤差） |
| E4 任務正確率 | RQ1 | 兩組題目的答對率與信賴區間 |
| E5 工具輔助 | RQ3 | 有／無工具的正確率比較 |

## 自變數

| 變數 | 水準 |
|---|---|
| 硬體 | RTX 3060 12GB（kururinpa-svr）、RTX 5060 Ti 16GB（主力機） |
| 量化 | UD-IQ3_XXS、UD-IQ4_XS |
| prompt 長度／context 深度 | 512、2048、8192、16384 token |

實驗矩陣：

| | UD-IQ3_XXS | UD-IQ4_XS |
|---|---|---|
| 5060 Ti 16GB | 全 GPU | 全 GPU |
| 3060 12GB | 全 GPU | **部分卸載**（檔案 13.26 GiB 放不下，刻意保留作為對照條件） |

**不納入主實驗：** `Huihui-Qwen3.8-27B-abliterated` 等第三方修改版。它改變的是模型權重（移除拒答）而非量化等級，且量化校準資料不同，放進來會混淆變因。若使用者之後想加，作為獨立的附加實驗，並在報告中分開討論。

## 控制變數（最容易被質疑的部分）

1. **llama.cpp 版本與執行環境必須一致。** 目前主力機是 Windows＋conda（版本不明），server 是 Docker build 11347，直接比較會混入 OS 與版本差異。做法：
   - 在主力機的 Ubuntu 雙系統安裝驅動＋Docker＋NVIDIA Container Toolkit
   - 兩台都用**同一個映像 digest**（不是只寫 tag，tag 會更新）。用 `docker image inspect --format '{{index .RepoDigests 0}}'` 取得 digest 並記錄，之後以 `image@sha256:...` 指定
   - 若使用者決定不架主力機的 Ubuntu，則在報告的限制章節說明，並記錄雙方版本
2. 相同的模型檔（比對 sha256）
3. 固定參數：`-fa 1`、KV cache `q8_0`、`-np 1`（server 測試時）、執行緒數記錄下來
4. 量測時 GPU 上沒有其他負載：5060 Ti 須在螢幕接內顯的狀態；server 上停掉常駐 llama 容器
5. **Minecraft 伺服器**：與使用者討論後二選一並記錄 —（a）使用者同意暫停 MC 再量測，或（b）不暫停，但每次量測同時記錄 `uptime` 的 load average 與 `free -m`。部分卸載條件（用到 CPU 與 RAM）受影響最大
6. 正式量測前先跑一次暖機
7. 每個條件重複 5 次（llama-bench `-r 5`），報告平均 ± 標準差
8. 記錄 GPU 溫度、功耗、時脈（`nvidia-smi --query-gpu=temperature.gpu,power.draw,clocks.sm --format=csv -l 1` 背景記錄），排除過熱降頻
9. 跑基準測試時加 `-fit off` 或確認 log 沒有自動調整參數，避免 fit 機制偷偷改設定

## E1 速度

工具：`llama-bench`（Docker 映像 `full-cuda13` 含此工具；或用 `--entrypoint /app/llama-bench`，先確認映像內路徑）。

```bash
llama-bench -m /models/<模型>.gguf -ngl 99 -fa 1 -ctk q8_0 -ctv q8_0 \
  -p 512,2048,8192,16384 -n 128 -r 5 -o json > results/raw/e1_<機器>_<量化>_<日期>.json
```

- context 深度對生成速度的影響：若該版本支援 `-d`（depth），加 `-d 0,4096,16384`；用 `llama-bench --help` 確認
- 部分卸載（3060＋IQ4_XS）：從可行的最大 `-ngl` 開始往下掃，例如 `-ngl 60,56,52,48`，畫「GPU 層數 vs 速度」曲線
- 輸出用 `-o json` 或 `-o csv` 方便解析，同時保留一份 `-o md` 給人看

## E2 記憶體

- 每個條件啟動 llama-server（`-lv 4`），從 log 解析：`CUDA0 model buffer size`、`CPU_Mapped model buffer size`、`KV buffer size`、`RS buffer size`、`compute buffer size`、fit 的 memory breakdown
- 同時記錄 `nvidia-smi --query-gpu=memory.used --format=csv`
- 與公式預測值（見 findings §3）比對，算出誤差
- 找出每個（硬體 × 量化）在全 GPU 下的最大 context：以 `-fit off` 逐步加大 `-c`，以「能啟動且 log 顯示 66/66 layers」為準
- 寫一個 `scripts/parse_server_log.py` 從 log 抽出上述欄位，輸出 CSV

## E3 品質：困惑度

```bash
llama-perplexity -m /models/<模型>.gguf -f wiki.test.raw -ngl 99 -fa 1 -c 2048 \
  > results/raw/e3_<量化>_<日期>.txt 2>&1
```

- 資料集：WikiText-2 raw 測試集（量化論文最常用，可與文獻對照）。取得方式可參考 llama.cpp repo 的 `scripts/get-wikitext-2-raw.sh`
- **困惑度與硬體無關**：每種量化只需在 5060 Ti 上跑一次；另在 3060 上用 IQ3_XXS 抽測一次，驗證結果一致（本身就是一個驗證點）
- 記錄最終 PPL 與其 ± 估計誤差
- 選配（期末）：KL 散度。需要高精度參考模型（Q8_0 或 BF16）的 logits，可在主力機用 64GB RAM 部分卸載跑一次 `--kl-divergence-base`，再對各量化跑 `--kl-divergence`。很慢，先問使用者

## E4 任務正確率

題目：`eval/questions.json`，`easy` 組 8 題、`hard` 組 8 題，答案已用程式驗證。

### 評估腳本規格：`scripts/run_eval.py`

- 透過 llama-server 的 OpenAI 相容 API（`/v1/chat/completions`）送題
- 參數：伺服器 URL、題組（easy/hard/all）、每題重複次數（預設 5）、思考模式（on/off）、思考預算、輸出路徑
- 每次送題都是**全新的對話**（不帶歷史）
- 使用模型內建取樣參數（temp 1.0、top_p 0.95、top_k 20），不另外覆寫，並在結果中記錄
- **思考控制**（必要，避免一題跑一小時）：
  - 關閉思考：嘗試 request 中 `"chat_template_kwargs": {"enable_thinking": false}`，或伺服器的 `--reasoning-budget 0`；先用 `llama-server --help` 與一次試送確認哪個有效
  - 開啟思考時設上限（例如 8192 token），並設定 `max_tokens`，超時或截斷記為失敗並標記原因
- 每筆紀錄存 JSONL：題號、第幾次、完整回應（含 reasoning_content）、擷取出的答案、是否正確、prompt／completion token 數、耗時、是否截斷、伺服器資訊（model、build）
- 批改依 `grading` 欄位：
  - `exact_int`：從「答案：」那行擷取整數比對
  - `exact_text`：去除空白、全形半形正規化後比對
  - `fraction`：解析為分數後比對（接受 5/11、等值分數）
  - `multi_field`：多個欄位都要對
  - `json_fields`：解析 JSON，所有欄位相等
  - `python_tests`：擷取程式碼，在**隔離的子行程**中執行（timeout 10 秒、不給網路、暫存目錄），全部測資通過才算對；禁止使用 `eval` 的題目要做靜態檢查
- 擷取失敗（沒有「答案：」行）記為錯誤，另外統計擷取失敗率
- 輸出統計：每題答對率、整體答對率、Wilson 95% 信賴區間、平均 token 數與耗時

### 流程

1. **難度校準試跑**：hard 組每題用 IQ4_XS 跑 2～3 次。理想答對率 30%～70%。全對或全錯的題目沒有鑑別力，回報使用者討論是否替換（**不要自行改題**，新題目的答案必須用程式驗證後才能加入）
2. 正式實驗：IQ3_XXS 與 IQ4_XS 各跑 hard 組（思考開、有上限）與 easy 組（思考關），每題 5 次
3. 與困惑度對照討論：兩者趨勢是否一致
4. 任務正確率與硬體無關，只需在一台機器上跑（建議 5060 Ti，較快）

## E5 工具輔助（RQ3）

兩個子實驗，期中只需寫設計，期末執行：

- **E5a 計算工具**：讓模型可以呼叫一個計算函式（function calling，或在 prompt 中允許輸出 Python 再由腳本執行）。用含大數運算的題目（如 easy 組的 E8、hard 組的 H7，可再出幾題同類型）比較有／無工具的正確率。以「600 vs 601」案例當動機
- **E5b 網頁搜尋 MCP**：llama-server Web UI 支援 MCP（`--webui-mcp-proxy`），或用腳本串接 SearXNG。準備 10～15 題需要知識截止日之後資訊才能回答的問題（由使用者協助出題並確認答案與出題日期），比較有／無搜尋的正確率。系統提示中加入當天日期
- 時效性題目的答案會過期，題目檔中要記錄出題日期與答案來源連結

## 紀錄格式

每次實驗在 `results/raw/` 產生原始輸出，並在 `results/runs.csv` 追加一列：

```
run_id, datetime, experiment, machine, gpu, driver, llamacpp_build, image_digest, model_file, model_sha256, command, mc_server_state, notes, raw_output_path
```

`run_id` 格式：`<實驗>_<機器>_<量化>_<YYYYMMDD-HHMM>`，例如 `e1_svr_iq3xxs_20261015-2130`。

## 時間估算

- 主力機 Ubuntu 環境架設：半天（最花時間的一步，建議最先做）
- E1：每台約 1～2 小時（含部分卸載掃描）
- E2：每台約 1 小時
- E3：每種量化約 30～60 分鐘
- E4：取決於思考預算；hard 組思考開啟時，8 題 × 5 次 × 2 量化，可能需要數小時，建議晚上背景跑
