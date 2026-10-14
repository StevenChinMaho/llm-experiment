# 目前已知的數據與發現

這些是正式實驗開始前的**初步觀察**，可放進期中的「初步結果」小節，但必須註明是非系統性的單次量測。每筆都標了來源；標「使用者回報」的沒有 log 佐證，報告中引用時要寫明，或在正式實驗中重新量測取代。

## 1. 初步效能數據

| # | 機器 | 執行環境 | 量化 | context | 讀 prompt（pp） | 生成（tg） | 來源 |
|---|---|---|---|---|---|---|---|
| P1 | 5060 Ti | Windows / conda（build 不明） | UD-IQ3_XXS | 4096 | — | 約 31 tok/s | 使用者回報 |
| P2 | 5060 Ti | Windows / conda（build 不明） | UD-IQ4_XS | 32768 | 約 945 tok/s（8,450 token prompt） | 26.07 tok/s（前 100 token） | `results/raw/preliminary/2026-10-01_mainpc_win_IQ4_XS_c32768_run.log` |
| P3 | 3060 | Ubuntu / Docker server-cuda13（build 11347） | UD-IQ3_XXS | 24576 | 490.50 tok/s（2,646 token prompt） | 20.36 tok/s（3,011 token 平均） | `results/raw/preliminary/2026-10-03_svr_docker_IQ3_XXS_c24576_run.log` |

**比較時的限制（報告中必須說明）：**
- P2 與 P3 的 llama.cpp 版本、作業系統都不同，量測方式也不同（P2 的 tg 只取前 100 token，P3 是全程平均，且 tg 會隨 context 加深而略降，P3 從 20.72 緩降到 20.36）
- 這正是正式實驗要統一用 llama-bench＋同一映像的原因

P2 生成期間的 `nvidia-smi`（使用者貼上，非 log 檔）：VRAM 15,520 / 16,311 MiB、GPU-Util 99%、170 W / 180 W、62°C。

## 2. 記憶體組成（實測，來自啟動 log）

單位 MiB。

| 項目 | P0：5060 Ti IQ3_XXS c4096 | P2：5060 Ti IQ4_XS c32768 | P3：3060 IQ3_XXS c24576 |
|---|---|---|---|
| 模型權重（CUDA0 model buffer） | 9,685.21 | 12,726.35 | 9,685.21 |
| 留在 CPU 的權重（CPU_Mapped，token embedding） | 397.85 | 521.00 | 397.85 |
| KV cache | 136.00 | 1,088.00 | 816.00 |
| 遞迴狀態（RS buffer） | 149.62 | 149.62 | 149.62 |
| 運算暫存（CUDA0 compute buffer） | 126.28 | 240.28 | 200.28 |
| 視覺編碼器 mmproj（權重＋暫存） | 887.99＋248.10 | 887.99＋248.10 | 未載入 |

P0 來源：`results/raw/preliminary/2026-09-30_mainpc_win_IQ3_XXS_c4096_load.log`。

其他觀察：
- 螢幕接獨顯時，Windows 桌面程式佔用約 989 MiB VRAM（`results/raw/preliminary/2026-09-30_mainpc_win_vulkan_build_devices.log`）；改接內顯後只剩 21 MiB（使用者貼上的 `nvidia-smi`）
- 記憶體在載入時**一次預先配置**，對話變長不會增加 VRAM；P2 的 `nvidia-smi` 實測 15,520 MiB 與 log 各項加總（約 15,340 MiB）相差約 180 MiB，推測為 CUDA runtime 開銷
- context checkpoint（每個 149.626 MiB，等於 RS buffer 大小）與 prompt cache 存在系統 RAM，不佔 VRAM

### 2.1 Windows 可超配 VRAM、Linux 不行（2026-10-12）

同一個 IQ4_XS 檔（sha256 一致）、同樣 `-c 83536`（實際 n_ctx 83,712），fit 預估需求兩邊都是 **16,144 MiB**（權重 12,726＋context 2,929＋compute 489）：

| | 啟動時可用 VRAM | 結果 | 來源 |
|---|---|---|---|
| 主力機 Ubuntu（Docker b11347，驅動 595.91.07） | 15,544 MiB | compute buffer 489.03 MiB `cudaMalloc failed: out of memory`，無法啟動 | 本次 `docker logs`（未另存檔，見 docs/environment.md） |
| 主力機 Windows（conda build 不明，驅動 617.14） | 15,022 MiB | 正常啟動並推論 | `results/raw/preliminary/2026-10-12_mainpc_win_IQ4_XS_c83536_run.log` |

Windows 執行中以效能計數器查得：該行程 **Dedicated 16,014 MiB＋Shared 470 MiB**（`results/raw/preliminary/2026-10-12_mainpc_win_IQ4_XS_c83536_gpumem.txt`）。→ Windows（WDDM）允許超過可用 VRAM 的配置，部分放在共享的系統記憶體；Linux 直接失敗。Ubuntu 上 IQ4_XS 改 `-c 65536` 可啟動。

**Web UI 使用感受（使用者回報，無 log）：** Ubuntu 約 6 萬 context（當時容器為 `-c 65536`）tg 穩定約 27.5 tok/s；Windows 8 萬 context 一開始約 27，隨對話變長慢慢降到 26 以下。

### 2.2 控制實驗：Windows 上只改 `-c`，量 pp／tg 與 context 深度（2026-10-12）

- 條件：主力機 Windows、conda llama.cpp **b10751**、驅動 617.14、螢幕接內顯、IQ4_XS（sha256 `40fac405…`）、`-ngl 99 -fa on -ctk/-ctv q8_0 -np 1 --no-mmproj --cache-ram 0 --ctx-checkpoints 0`；`/completion` 送剛好 depth 個 token、生成 128 token（ignore_eos），每點 3 次
- 原始資料：`results/raw/ctxprobe_win_iq4xs_20261012/`；表格：`results/processed/ctxprobe_win_iq4xs_20261012.md`；圖：`results/figures/ctxprobe_win_iq4xs_20261012.png`；腳本：`scripts/ctx_depth_probe.py`、`scripts/analyze_ctxprobe.py`

| -c | 專用／共享 (MiB) | pp @1K | pp @48K | tg @1K | tg @48K | prefill 功耗 @48K |
|---|---|---|---|---|---|---|
| 49152 | 14,968 / 148 | 971.0 | 780.6 | 27.04 | 21.47 | 178.3 W |
| 65536 | 15,592 / 164 | 959.7 | 780.5 | 26.99 | 21.54 | 178.5 W |
| 83536 | 16,008 / 458 | **374.5** | **97.0** | 27.10 | 21.75 | **57.6 W** |

（83536 另量到 d=80K：pp 60.2、tg 19.04；標準差都很小，見 processed 表）

**結論（實測）：**
1. **超配只拖慢 prefill，不影響生成。** 同深度下三種 `-c` 的 tg 差距 < 0.3 tok/s；83536 的 pp 在 1K 深度只剩 39%，80K 深度只剩約 8%，越深越嚴重
2. prefill 期間 GPU 使用率顯示 100%，但功耗只有 52～78 W（正常約 178 W）→ GPU 在等透過 PCIe 存取的系統記憶體
3. **使用者在 Web UI 看到的 tg 緩降是正常的深度效應**（完全放得進 VRAM 的 49152 也一樣從 27.0 降到 21.5），不是 Sysmem Fallback 造成的。之前沒發現問題，是因為 Web UI 只顯示 tg；10-12 的 log 裡 pp 365 tok/s（P2 在 32K context 時是 945）其實已經顯示了問題
4. Windows 啟動時回報的 free（約 15,022 MiB）偏保守：65536 預估需要 15,452 MiB 仍完整放進專用 VRAM（實際 15,592）。Windows 上不超配的實用上限介於 65536 與 83536 之間

**推測（未驗證）：** 被放到系統記憶體的是 compute buffer（83536 時 489 MiB；prefill 一次處理 512 token，需要大量使用它，而且其中 attention 相關的暫存會隨深度變大；生成時一次只處理 1 個 token，只用到一小部分）。可驗證的方式：`-c 83536` 加 `-ub 256` 或 `-ub 128` 縮小 compute buffer，看共享記憶體是否回到約 150 MiB、pp 是否恢復。

**Tee-Object 現象（使用者回報）：** Windows 上以 `llama-server ... 2>&1 | Tee-Object` 存 log 時，tg 掉到約 14 tok/s，原因不明（該次啟動時可用 VRAM 15,003 MiB，和正常那次 15,022 差不多，記憶體應不是原因）。之後改用 llama.cpp 內建的 `--log-file`。

### 2.3 MTP 推測解碼可行性測試（2026-10-13，非正式數據）

- 條件：主力機 Ubuntu、Docker b11347（digest `936e9d2a…`）、驅動 595.91.07、IQ4_XS、`-c 16384 -fa on -ctk/-ctv q8_0 -np 1 --cache-ram 0`；開 MTP 時加 `--spec-type draft-mtp --spec-draft-model MTP/mtp-Qwen3.8-27B-Q4_0.gguf`（預設 n_max=3）。關閉思考、`max_tokens` 512、每類 2 次。測試期間背景同時在下載量化檔（只佔網路與磁碟）
- 原始資料：`results/raw/mtp_probe_ubuntu_iq4xs_20261013/`；腳本：`scripts/mtp_probe.py`

| 題目類型 | tg 不開 MTP | tg 開 MTP | 草稿接受率 |
|---|---|---|---|
| 程式碼 | 27.75 / 27.75 | 69.65 / 63.71 | 0.843 / 0.739 |
| 數學 | 27.75 / 27.75 | 71.29 / 71.01 | 0.872 / 0.866 |
| 一般中文問答 | 27.75 / 27.73 | 37.58 / 37.76 | 0.301 / 0.304 |

**VRAM 代價（實測，-c 16384）：** nvidia-smi 13,754 MiB → 15,494～15,518 MiB，多約 **1.7 GiB**（多於 MTP 檔本身的 1.28 GiB）。log 的組成：

| 項目 | 不開 | 開 |
|---|---|---|
| 主模型 CUDA0 權重 | 12,726.35 | 13,061.10（+334.75） |
| 遞迴狀態 RS | 149.62 | 598.50（**正好 4 倍**） |
| 草稿模型 | — | 權重 774.71＋KV 64.00（f16）＋運算暫存 114.02 |
| 主模型 KV／運算暫存 | 544.00 / 160.28 | 544.00 / 160.28（不變） |

觀察與推測：
- MTP 可以用，而且在程式碼、數學這類可預測性高的內容上，tg 達到約 2.4～2.6 倍；開放式中文問答只有約 1.36 倍。**速度提升取決於內容**，所以 RQ3 的耗時推算必須用實際題目量到的接受率
- 1.7 GiB 約等於 5.2 萬 token 的 q8_0 KV（推導值），這是 RQ2 取捨的具體數字
- RS 變成 4 倍，**推測**是推測解碼需要為「1＋n_max（3）」個位置保留可退回的遞迴狀態，這是混合架構特有的額外成本。驗證方式：E1 掃 `--spec-draft-n-max`，看 RS 是否等於 149.62 ×（1＋n_max）
- 主模型權重多出的 334.75 MiB，推測是啟用 MTP 後主檔內的 `blk.64.*`（平常被忽略的 MTP 層）也被載入，未確認
- 「推測解碼無損」是理論保證；本次使用 temperature 1.0 取樣，無法直接比對輸出是否相同。E1 可用 greedy（temp 0）各跑一次，比對輸出是否逐字相同

### 2.4 E1 正式結果：RTX 3060（2026-10-13）

- 原始資料：`results/raw/e1_svr_20261013-1537/`、`..._1600_partial2/`、`..._1600_partial2_ngl57/`；整理表：`results/processed/e1_svr.md`；runs.csv 三筆
- 條件：b11347 full 映像、驅動 595.91.07、MC 關閉、無顯示輸出、`-fa on -ctk/-ctv q8_0`、6 執行緒

| 量化 | GPU 層數 | tg @0 | tg @32K | pp512 @0 | 頻寬使用率（推導） | J/token（推導） |
|---|---|---|---|---|---|---|
| UD-IQ2_XXS（6.77 GiB） | 全部 | 24.37 | 18.69 | 542.9 | 49.1% | 6.96 |
| UD-Q2_K_XL（9.15） | 全部 | 22.38 | 17.57 | 526.3 | 61.0% | 7.58 |
| UD-IQ3_XXS（10.18） | 全部 | 21.44 | 16.89 | 526.0 | 65.0% | 7.91 |
| UD-IQ4_XS（13.27） | 56（上限） | 8.88 | — | 360.6 | — | 12.05 |
| UD-IQ4_XS | 44 | 5.30 | — | 308.2 | — | 11.83 |

觀察（實測）：

1. **在 3060 上，量化降得更低，速度幾乎沒有變快。** IQ2_XXS 比 IQ3_XXS 小 33%，tg 只快 14%；頻寬使用率從 65% 降到 49%。表示權重小到一定程度後，瓶頸不再是記憶體頻寬（推測是遞迴層的運算與固定開銷，未驗證）。這對 RQ2 很重要：12GB 卡上把量化從 IQ3 降到 IQ2，換到的主要是 VRAM 空間（可以放更長的 context），而不是速度
2. **部分卸載的懸崖：** IQ4_XS 在 3060 上最多只能放 56 層（57 層以上 cudaMalloc OOM），tg 從全 GPU 的 IQ3_XXS 21.44 掉到 8.88（−59%），每少 4 層再掉約 1～1.7 tok/s
3. 深度效應：IQ3_XXS 的 tg 從 21.44（0）降到 16.89（32K），−21%
4. 與初步數據一致：P3（Docker 常駐、平均 3,011 token 深度）tg 20.36，本次 d=4096 為 20.60

### 2.5 E1 正式結果：RTX 5060 Ti，與 3060 比較（2026-10-14）

- 原始資料：`results/raw/e1_main_20261014-0925/`、`..._0939_ngl63/`；整理表：`results/processed/e1_main.md`；圖：`results/figures/e1_tg_vs_size.png`
- 條件：主力機 Ubuntu、b11347 full 映像、驅動 595.91.07、獨顯無顯示輸出（Disp.A Disabled）、`-fa on -ctk/-ctv q8_0`、預設執行緒數

| 量化 | 5060 Ti tg @0 | 5060 Ti tg @32K | 5060 Ti 頻寬使用率（推導） | 3060 tg @0 | 5060 Ti ÷ 3060 |
|---|---|---|---|---|---|
| UD-IQ2_XXS | 41.36 | 32.08 | 67.0% | 24.37 | 1.70 |
| UD-Q2_K_XL | 35.38 | 28.53 | 77.5% | 22.38 | 1.58 |
| UD-IQ3_XXS | 32.82 | 26.87 | 80.0% | 21.44 | 1.53 |
| UD-IQ4_XS | 27.92 | 23.57 | 88.7% | 8.88（部分卸載 56 層） | — |
| UD-Q4_K_XL | 17.49（部分卸載 62 層，上限） | — | — | （不做） | — |

觀察（實測）：

1. **5060 Ti 上，量化越低速度越快，趨勢比 3060 明顯。** IQ4_XS → IQ2_XXS 快 48%；3060 上 IQ3_XXS → IQ2_XXS 只快 14%。頻寬使用率 5060 Ti 是 67～89%，3060 是 49～65%
2. **兩張卡的速度差距大於頻寬差距。** 理論頻寬比是 448 ÷ 360 ＝ 1.24，實測速度比 1.53～1.70，而且量化越低差距越大。表示 3060 在低位元量化時不只是被頻寬限制（推測與運算能力、L2 快取有關，未驗證；findings §5 的舊推測方向一致）
3. **16GB 上的部分卸載懸崖：** Q4_K_XL 最多放 62 層（63 層 OOM），tg 17.49，比全 GPU 的 IQ4_XS（27.92）慢 37%；每少 2 層約再掉 1.5～2 tok/s
4. 與先前數據一致：MTP 可行性測試中不開 MTP 的 IQ4_XS（-c 16384，llama-server）tg 27.75，本次 llama-bench 為 27.92

### 2.6 E3 品質：KL 散度與困惑度（2026-10-14）

- 原始資料：`results/raw/e3_main_*_20261014/`；整理表：`results/processed/e3_main.md`；圖：`results/figures/e3_quality_speed.png`；腳本：`scripts/run_e3.sh`、`scripts/analyze_e3.py`；runs.csv 六筆
- 條件：主力機 Ubuntu、b11347 full 映像、WikiText-2 raw 測試集（297,193 token，**全部 145 個 chunk**，-c 2048）、基準 **Q8_0**（部分卸載，層數由 fit 自動決定）。基準 Final estimate PPL = 6.3541 ± 0.04055

| 量化 | 檔案 (GiB) | 困惑度 | 平均 KLD | KLD 99% | Same top p |
|---|---|---|---|---|---|
| UD-IQ2_XXS | 6.77 | 7.5459 ± 0.0491 | 0.2442 | 2.372 | 79.70% |
| UD-Q2_K_XL | 9.15 | 6.6573 ± 0.0424 | 0.1020 | 1.052 | 87.50% |
| UD-IQ3_XXS | 10.18 | 6.5676 ± 0.0420 | 0.0725 | 0.720 | 89.50% |
| UD-IQ4_XS | 13.27 | 6.3505 ± 0.0403 | 0.0267 | 0.236 | 94.09% |
| UD-Q4_K_XL | 16.35 | 6.3437 ± 0.0404 | 0.0134 | 0.091 | 96.36% |

觀察（實測）：

1. **困惑度分辨不出 4-bit 等級的量化，KL 散度可以。** IQ4_XS、Q4_K_XL 的困惑度和 Q8_0 基準在誤差範圍內相同（Q4_K_XL 甚至略低），但平均 KLD 相差一倍（0.0267 vs 0.0134），Same top p 差 2.3 個百分點。這支持「以 KLD 為主要品質指標」的設計
2. **品質隨權重大小平滑變化，沒有斷崖**：KLD 在對數軸上大致隨檔案大小線性下降；IQ2_XXS 的 KLD 是 IQ3_XXS 的 3.4 倍，每 5 個 token 約有 1 個的最高機率 token 與基準不同
3. **與 E1 結合（圖 e3_quality_speed.png (b)）**：16GB 上 IQ4_XS 是「全部放進 GPU」的最高品質選項（27.92 tok/s、KLD 0.027）；再往上到 Q4_K_XL，品質再提升一倍，代價是速度掉 37%（部分卸載）。12GB 上 IQ3_XXS 是全 GPU 的最高品質選項（21.44 tok/s、KLD 0.072），往上的 IQ4_XS 速度掉 59%
4. 限制：基準是 Q8_0 而不是 BF16；WikiText-2 是英文；只代表「逐 token 分布」的差異，對任務答對率的影響要看 E4

### 2.7 E2 記憶體：RTX 3060（2026-10-14）

- 原始資料：`results/raw/e2_svr_20261014-1027/`、`results/raw/e2_svr_20261014-1048_iq2/`；整理表：`results/processed/e2_svr.md`；腳本：`scripts/run_e2.py`、`scripts/parse_server_log.py`、`scripts/analyze_e2.py`
- 條件：kururinpa-svr、server 映像 b11347、`-fit off -fa on -ctk/-ctv q8_0 -np 1 --cache-ram 0 -lv 4`、MC 關閉。成功＝能啟動、全部層在 GPU、能完成一次短 completion

**全 GPU 的最大 context（實測，二分搜尋解析度 1024）：**

| 量化 | 最大 -c | 失敗 | 最大時 nvidia-smi |
|---|---|---|---|
| UD-IQ2_XXS | **131,072** | 132,096 | 11,889 MiB |
| UD-Q2_K_XL | **75,520** | 76,544 | 11,883 MiB |
| UD-IQ3_XXS | **48,384** | 49,408 | 11,905 MiB |

**記憶體模型（21 個點全部吻合）：**

1. KV cache ＝ n_ctx × 34 KiB：21 個點誤差全為 **0.00 MiB**
2. 運算暫存（n_ctx ≥ 16384）＝ 80.28 MiB ＋ 5 KiB × n_ctx：15 個點殘差 0.00 MiB（擬合值；n_ctx = 4096 時 126.28 MiB，高於直線）
3. 遞迴狀態固定 149.62 MiB；nvidia-smi 比 log 四項加總固定多約 146 MiB（CUDA 本身的開銷）
4. → **每多 1 個 token 的 VRAM 成本是 39 KiB**（KV 34＋運算暫存 5，推導值）。對比：若當成 64 層全注意力、KV f16 的傳統 Transformer，是 256 KiB

**對 RQ2 的意義：** 12GB 卡上從 IQ3_XXS 降到 IQ2_XXS，KLD 變成 3.4 倍（§2.6）、tg 只快 14%（§2.4），但最大 context 從 4.8 萬增加到 13.1 萬（2.7 倍）。低量化在 12GB 卡上換到的主要是 context 容量

**待驗證的預測（推導值）：** 用上面的模型預測主力機 5060 Ti（CUDA 可見 15,841 MiB）上 IQ4_XS 的最大 context ≈ (15,841 − 12,726.35 − 149.62 − 80.28 − 146) ÷ 39 KiB ≈ **7.2 萬**。已知 -c 65536 可以、83536 不行（§2.1），與預測一致；E2 主力機實測後確認

### 2.8 MTP 正式量測：RTX 3060（2026-10-14）

- 原始資料：`results/raw/mtp_svr_iq3xxs_20261014-1105/`、`mtp_svr_q2kxl_20261014-1043/`、`mtp_svr_q2kxl_20261014-1112_n6/`；整理表：`results/processed/mtp_svr_q2kxl.md`；腳本：`scripts/run_mtp.sh`、`scripts/mtp_probe.py`、`scripts/analyze_mtp.py`
- 條件：kururinpa-svr、server 映像 b11347、`-c 16384`、`--spec-type draft-mtp`、MTP 檔 Q4_0；關閉思考、512 token；每類一般取樣 2 次＋greedy 1 次。MC 關閉

**1. 12GB 卡放不下 IQ3_XXS＋MTP。** IQ3_XXS 在 `-c 16384` 下，n_max = 1～6 全部在載入草稿模型（774.71 MiB）時 cudaMalloc OOM。改用 UD-Q2_K_XL 才放得下

**2. 遞迴狀態 ＝ 149.62 MiB ×（1 ＋ n_max），推測確認。** n_max = 1、2、3、4、6 分別為 299.25、448.88、598.50、748.12、1047.38 MiB，全部吻合（§2.3 的推測）。混合架構做推測解碼，要為每個草稿位置各存一份可退回的遞迴狀態

**3. 速度（Q2_K_XL，倍數相對於不開 MTP 的 22.0 tok/s）：**

| n_max | 程式碼 | 數學 | 中文問答 | 啟動後 VRAM |
|---|---|---|---|---|
| 1 | ×1.51（接受率 0.92） | ×1.53（0.93） | **×1.20**（0.51） | 11,061 MiB |
| 2 | ×1.72 | ×1.78 | ×1.17 | 11,211 |
| 3 | ×1.79 | ×1.90 | ×1.02 | 11,361 |
| 4 | **×1.82**（0.71） | **×1.97**（0.78） | **×0.94**（0.24，比不開還慢） | 11,511 |
| 6 | 啟動成功（11,809 MiB），第一個請求時 CUDA OOM 當掉 | | | |

→ **最佳 n_max 取決於內容**：可預測性高的程式碼／數學 n_max 越大越好；開放式中文問答 n_max = 1 最好，太大反而變慢。E4 的 AIME 屬於數學，應使用較大的 n_max

**4. greedy 是否逐字相同（「無損」的檢驗）：** 12 組中 7 組相同（程式碼 4/4、數學 3/4、中文問答 0/4）；不開 MTP 重跑 greedy 則 3/3 完全相同，所以差異確實來自 MTP。**推測**是驗證草稿時一次處理多個 token，GPU 運算路徑與加總順序不同造成的數值誤差，遇到機率幾乎相同的候選時讓 argmax 翻轉（與 Chen et al. 2023 「在硬體數值精度內」的說法一致，未證明）。報告中不能寫「輸出完全相同」，只能寫「理論上分布不變、實測 7/12 逐字相同」，品質影響以 E4 答對率判斷

## 3. KV cache 公式（推導，已用 log 驗證）

```
每 token KV cache = 有 KV cache 的層數 × (n_embd_k_gqa + n_embd_v_gqa) × 每元素位元組數
```

代入 Qwen3.8-27B 與 q8_0：
- 有 KV cache 的層數 = 64 / full_attention_interval(4) = **16**（log 也寫 `16 layers`）
- n_embd_k_gqa = n_head_kv(4) × head_dim(256) = **1024**，V 相同
- q8_0 每 32 個元素存 32 個 int8＋1 個 fp16 scale = 34 bytes → **1.0625 bytes/元素**

16 × 2048 × 1.0625 = **34,816 bytes = 34 KiB / token**

驗證：
- 4096 × 34,816 B = 136.00 MiB ✔（P0）
- 24576 × 34,816 B = 816.00 MiB ✔（P3）
- 32768 × 34,816 B = 1,088.00 MiB ✔（P2）

對照：若把它當成 64 層全注意力的傳統 Transformer、KV 用 f16，會得到 64 × 2048 × 2 = 256 KiB / token，高估約 7.5 倍。這說明混合架構與 KV 量化對長 context 的影響，是報告可以強調的點。

遞迴狀態 149.62 MiB 與 context 長度無關（三份 log 一致）。運算暫存隨 context 增加而小幅成長（126 → 200 → 240 MiB），沒有簡單公式，需實測。

## 4. 量化檔的混合精度（來自 log 的 tensor 類型統計）

- UD-IQ3_XXS：檔案標示 IQ3_XXS（3.0625 bpw），實際平均 **3.20 BPW**；包含 q8_0 ×98、iq3_xxs ×120、iq3_s ×106、iq4_xs ×45、iq2 系列 ×71、iq1 系列 ×11 等
- UD-IQ4_XS：標示 IQ4_XS（4.25 bpw），實際平均 **4.17 BPW**；包含 q8_0 ×98、iq4_xs ×211、q4_K ×55、q5_K ×51、iq3_s ×46 等
- 兩者都使用 Unsloth 的 imatrix（`imatrix_unsloth.gguf`，496 entries、1,251 chunks）

說明 Unsloth Dynamic 量化不是全部壓成同一精度，而是依張量重要性分配位元。

## 5. 推論速度的理論觀察

- 生成（decode）受限於記憶體頻寬：每個 token 要讀過全部權重
  - 粗估上限 ≈ 頻寬 ÷ 權重大小。5060 Ti：448 GB/s ÷ 13.3 GB（IQ4_XS）≈ 34 tok/s；實測約 26
  - IQ3_XXS → IQ4_XS 權重增加約 31%，生成速度由約 31 降到約 26（約 −16%）
  - 3060 頻寬約為 5060 Ti 的 80%，但同檔案的生成速度只有約 66%（20.4 vs 31），推測與 Blackwell 較大的 L2 快取有關（**待查證、待正式量測**）
- 讀 prompt（prefill）受限於運算力：5060 Ti 約 945 tok/s、3060 約 490 tok/s

以上「推測」都必須在報告中標為推測，正式實驗後再下結論。

## 6. 模型行為觀察（可做為研究動機與應用實驗的素材）

**大數運算錯誤（600 vs 601）**
- 題目：150 Mbps 傳輸 10.5 GiB 需幾秒（四捨五入）
- 正確：10.5 × 2³⁰ × 8 = 90,194,313,216 bits → ÷ 1.5×10⁸ ≈ 601.3 → **601**
- 模型（最高推理強度）寫出 89,994,313,216，億位數錯了剛好 200,000,000，得到 599.96 → 600
- 推理步驟全對，只錯在長數字算術 → 支持「讓模型呼叫計算工具」的應用實驗（RQ3）

**長時間推理耗盡資源**
- 一題 CPE 五星題（UVa「玩具士兵＋魔法排列」題），模型思考 64 分鐘、約 82,300 token 後沒有輸出最終回答（推測撞到 context 上限，未確認）
- 它在思考中寫出的程式通過題目範例與小規模隨機對拍，但上傳 judge 得到 Wrong Answer：程式寫死「答案最多為 2」，而正確答案可能更大（例如上下起伏的走廊地形需要 3 次）
- 說明：程式看起來完整、能過範例，仍可能建立在未驗證的假設上；也說明思考預算必須設限

**簡單題組試跑**
- 第一版簡單題組（`eval/questions.json` 的 `easy` 組）在最高推理強度下，每題只思考約 300～500 token 就答出，除了單位換算題（答成 600）外都答對 → 對開啟思考的情況太簡單，改留作「關閉思考」時的題組；另設計 `hard` 組
