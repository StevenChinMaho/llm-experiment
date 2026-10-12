# 實驗環境

> 以下資訊整理自先前的對話與 log。有疑問時以實機指令輸出為準（`nvidia-smi`、`llama-server --version`、`docker image inspect`），並更新本文件。
>
> **操作端：** Claude Code 跑在第三台電腦（Windows，無模型、無實驗用 GPU），經 VPN 連回區網，以 SSH 操作兩台機器。本機 `~/.ssh/config` 別名：`main`（主力機 Windows）、`main-ubuntu`（主力機 Ubuntu）、`svr`（server，maho）。**不要在本機跑實驗或找模型。**

## 機器 A：主力機（RTX 5060 Ti 16GB）

| 項目 | 規格 |
|---|---|
| CPU | AMD Ryzen 7 7700（8 核 16 緒，有內顯 Radeon Graphics） |
| 主機板 | Gigabyte B650E Aorus Elite X AX Ice |
| RAM | 64GB DDR5-6000 CL30（32GB × 2，雙通道，理論頻寬約 96 GB/s） |
| GPU | NVIDIA RTX 5060 Ti 16GB（Blackwell，GDDR7，約 448 GB/s） |
| 儲存 | Gen4 NVMe 2TB（Windows C:）、Gen3 NVMe 1TB、120GB SATA SSD（Ubuntu 雙系統） |
| 區網 IP | 192.168.0.57 |

### Windows 端（目前的主要使用環境）

- 驅動 617.14，`nvidia-smi` 顯示 CUDA 13.4
- llama.cpp 由 conda-forge 安裝在 Miniforge 的 `llm` 環境（CUDA＋Vulkan 雙後端），路徑 `C:\Users\MahoKururinpa\miniforge3\envs\llm\Library\bin\llama-server.exe`。`--version` 顯示 `0.3.0-dev (build 0, commit unknown)`、MSVC 19.44 編譯。`--version` 不顯示 build，但 **`conda list -n llm` 顯示 conda-forge 套件 `llama.cpp 10751 cuda130_h0f3e06c_0`，即 build 10751**（cuda-version 13.0、libcublas 13.1.1.3；2026-10-12 查）。比 server／Ubuntu 的 b11347 舊約 600 個 build
- `--list-devices`：CUDA0（5060 Ti）、Vulkan0（5060 Ti）、Vulkan1（AMD 內顯）
- 模型存放：`C:\models`（環境變數 `LLAMA_CACHE`），透過 `-hf unsloth/Qwen3.8-27B-GGUF:<tag>` 下載。HF 快取格式，`snapshots/` 下的 .gguf 是指向 blob 的 symlink（直接看大小會顯示 0）。2026-10-12 現有：unsloth 的 UD-IQ3_XXS（10,934,860,704 bytes，與 server 位元組數相同，sha256 未比對）、UD-IQ4_XS、mmproj-BF16；另有 huihui-ai 的 abliterated UD-IQ4_XS 與其 mmproj（不納入主實驗）
- 使用者從別台機器 SSH 進 PowerShell 7 操作，並用 `ssh -L 8000:127.0.0.1:8000` 開通道使用 Web UI；也會用 Google 遠端桌面
- PowerShell profile 位於 OneDrive 的文件資料夾內，已用 `Set-Alias` 或 conda hook 讓 `llama-server` 可直接呼叫
- **螢幕接內顯**時 5060 Ti 完全空閒（`nvidia-smi` 顯示 21 MiB 已用、Disp.A Off）；打遊戲時使用者會改用獨顯輸出。跑實驗前確認目前是哪種模式
- 使用者回報可穩定跑約 83K context 並保留看圖功能（視覺模組放 CPU，`--no-mmproj-offload`）

### Ubuntu 端（雙系統，2026-10-12 架設完成，實驗用）

- 2026-10-12 試跑（測試用，非正式數據）：與 server 相同參數＋`-lv 4` 啟動 IQ3_XXS，log 顯示 `no changes needed`、`offloaded 66/66 layers to GPU`；KV buffer 1,334.50 MiB（實際 n_ctx 被補齊到 40,192 → 40,192 × 34,816 B = 1,334.50 MiB，符合 findings §3 公式）。**預設 verbosity 3 不會印出 buffer 資訊，E2 必須加 `-lv 4`**
- 2026-10-12 試跑 IQ4_XS（測試用）：Windows 上慣用的 `-c 83536` 在 Ubuntu **啟動失敗**（compute buffer 489 MiB cudaMalloc OOM；fit 預估 16,144 MiB > 可用 15,544 MiB）。`-c 65536` 可以啟動（66/66 層、KV 2,176 MiB、compute 400.28 MiB、nvidia-smi 15,626 MiB）。Windows 為何放得下 83K 尚未確認（推測：Sysmem Fallback 偷用系統 RAM，或舊版 build 的 compute buffer 較小），待查
- 日常 Web UI（非實驗）：容器名 `llama`，無 restart policy，從操作端 `ssh -N -L 8000:127.0.0.1:8000 main-ubuntu` 後開 `http://localhost:8000`

2026-10-12 實機狀態（hostname `MyWhiteUbuntu`，SSH 別名 `main-ubuntu`，sudo 需密碼）：

- Ubuntu 24.04.5、kernel 7.0.0-34；預設 `multi-user.target`，**沒有啟動桌面**（gdm inactive）
- 驅動：使用者已改裝 `nvidia-driver-595-server-open`，核心模組 **595.91.07**（與 server 完全相同）
- Docker 29.9.0，Docker Root `/nvme477/docker-data`；NVIDIA Container Toolkit 1.20.1（runtime `nvidia` 已註冊）
- 兩個 b11347 映像已以 digest 拉下並加上本地 tag；容器內 `--version` 顯示 build 11347 (5fc4f3c8c)，`--list-devices` 看得到 CUDA0（15,841 MiB）
- 螢幕線接獨顯但無桌面時：VRAM 10 MiB、0%、P8、約 8 W，視為無負載。每次實驗前仍記錄 `nvidia-smi`；若之後改開桌面要重新確認
- 磁碟：`/`（sda1）只剩 8.3G；`/nvme477`（ext4，label `ubuntu_nvme477`）→ 模型放 **`/nvme477/llama/models`**；Windows C: 是 1.8T 那顆的第 3 分割區（NTFS）
- **NVMe 編號每次開機可能對調**（10-12 第一次查時 C: 是 `nvme1n1p3`，重開後變 `nvme0n1p3`）。指令不要寫死 `nvmeXnY`，先 `lsblk` 確認，或用 UUID／`/dev/disk/by-label/`
- 掛載 Windows C:（唯讀）：`sudo mount -t ntfs3 -o ro /dev/<C槽分割區> /mnt/win`，模型在 `/mnt/win/models/`（HF 快取，snapshot `4ca72078…`）
- 螢幕：NVIDIA 的 DP-5 與內顯的 HDMI-A-2 **都有接**，nvidia-smi 顯示 Disp.A On
- 映像 tag 可鎖定 build：`server-cuda13-b11347` 的 digest＝server 現用的 `sha256:936e9d2a…`；`full-cuda13-b11347` = `sha256:3f7b5ae419f81c940b6171e004ee780091787a9cdb1c413b192fcb338a2d8590`（含 llama-bench／perplexity）。映像內為 CUDA 13.4.1

- 位於 120GB SATA SSD，空間很小。模型檔要放哪裡（另切 ext4 分割區、掛載 NTFS 讀取 Windows 的 `C:\models`），**先問使用者**
- 實驗計畫建議在這裡安裝 NVIDIA 驅動＋Docker＋NVIDIA Container Toolkit，使用與 server **完全相同的映像 digest**，讓兩台機器只差在硬體（見 experiment-plan 的控制變數）
- 50 系列需要 open kernel module 版的驅動

## 機器 B：kururinpa-svr（RTX 3060 12GB）

| 項目 | 規格 |
|---|---|
| CPU | Intel i5-11400F（6 核 12 緒，無內顯） |
| 主機板 | ROG STRIX B560-A GAMING WIFI |
| RAM | 16GB DDR4-3600（8GB × 2） |
| GPU | ZOTAC RTX 3060 AMP 12GB（Ampere，GDDR6，約 360 GB/s） |
| 儲存 | Samsung 128GB NVMe（2017 年製），LVM，空間有限 |
| OS | Ubuntu Server 26.04 LTS，headless，只能 SSH（金鑰登入） |
| 區網 IP | 192.168.0.66，使用者 `maho` |

- 驅動：`nvidia-driver-595-server-open`（595.91.07），支援 CUDA 13.2；建議已開啟 `nvidia-persistenced`
- Docker＋NVIDIA Container Toolkit 已安裝，`docker run --rm --gpus all ubuntu nvidia-smi` 可看到 GPU
- llama.cpp 映像：`ghcr.io/ggml-org/llama.cpp:server-cuda13`，`--version` 顯示 `0.5.0-dev` **build 11347 (5fc4f3c8c)**，GNU 14.2.0 編譯
- 映像 digest（2026-10-12 查，映像建立於 2026-10-02）：`ghcr.io/ggml-org/llama.cpp@sha256:936e9d2afab78662a05fd300c4a829ba931777bcd8372334da629b468511f90e`
- 模型存放：`/llama/models/`，目前有 `Qwen3.8-27B-UD-IQ3_XXS.gguf`
- **同一台機器上跑著大型模組 Minecraft 伺服器**（原生 Java/Forge，`java -Xmx8G -Xms6G -jar server.jar nogui`；通知服務是 template unit **`mc-notify@maho.service`**，不是 `mc-notify.service`），會佔用 CPU 與 RAM。不得擅自停止（見 CLAUDE.md 絕對規則 3）
- 同機還有網站相關的 Docker 服務（nginx、MariaDB 等），RAM 只有 16GB，llama-server 的 `--cache-ram` 與 `--ctx-checkpoints` 必須壓低

### 目前的常駐指令（server）

```bash
docker run -d --name llama --gpus all --restart unless-stopped \
  -v /llama/models:/models -p 127.0.0.1:8000:8080 \
  ghcr.io/ggml-org/llama.cpp:server-cuda13 \
  -m /models/Qwen3.8-27B-UD-IQ3_XXS.gguf \
  -ngl 99 -c 40000 -fa on -np 1 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --cache-ram 2048 --ctx-checkpoints 8 \
  --no-reasoning-preserve --jinja --port 8080
```

（2026-10-12 以 `docker inspect llama` 確認：已背景常駐、`restart=unless-stopped`，參數與上方完全一致，含 `--no-reasoning-preserve`。常駐時佔 VRAM 約 11,796 MiB。）

## 模型

- 基礎模型：**Qwen3.8-27B**（Apache 2.0），GGUF 量化由 Unsloth 製作：`unsloth/Qwen3.8-27B-GGUF`
- 架構重點（來自 log metadata）：`general.architecture = qwen35`；64 層（另有 1 層 MTP 層 `blk.64.nextn.*` 未啟用）；`full_attention_interval = 4`（每 4 層 1 層全注意力，其餘為 SSM／線性遞迴層）；`head_count = 24`、`head_count_kv = 4`（GQA）、`key_length = value_length = 256`；原生 context 262144；內含視覺編碼器（mmproj）
- GGUF 內建取樣參數：temp 1.0、top_p 0.95、top_k 20（llama.cpp 會自動套用）
- 聊天模板預設推理強度 **xhigh**，思考模式開啟

| 量化檔 | 檔案大小 | 實際 BPW | 說明 |
|---|---|---|---|
| UD-IQ3_XXS | 10.17 GiB | 3.20 | 兩台都放得下 |
| UD-IQ4_XS | 13.26 GiB | 4.17 | 只有 5060 Ti 放得下；3060 需部分卸載 |

模型檔 sha256（2026-10-12 以 `sha256sum` 實算；HF revision `4ca720788d1e01f1bff70c033e0d0028fd02e502`）：

| 檔案 | bytes | sha256 | 已比對 |
|---|---|---|---|
| Qwen3.8-27B-UD-IQ3_XXS.gguf | 10,934,860,704 | `c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee` | 主力機 Ubuntu、server、HF blob 名稱三者一致 |
| Qwen3.8-27B-UD-IQ4_XS.gguf | 14,252,845,984 | `40fac4050e940397dbf13087afd50f4734a11805bf9d65ef8ddd7483470e6199` | 主力機 Ubuntu 與 HF blob 名稱一致（server 沒有此檔） |

## 已知陷阱（都實際踩過）

- **winget 安裝的 llama.cpp 是 Vulkan 版**，不是 CUDA。部署後一定先跑 `llama-server --list-devices`，要看到 `CUDA0`
- **`-hf` 下載會自動載入視覺模組**（mmproj，約 888 MiB＋248 MiB 暫存）。不需要看圖時加 `--no-mmproj`，或用 `--no-mmproj-offload` 讓它跑在 CPU
- **`-np` 預設值大於 1 會讓 KV cache 倍增**，一律加 `-np 1`
- **新版 build 預設開啟 reasoning preserve**，多輪對話會累積思考內容吃掉 context；需要時加 `--no-reasoning-preserve`
- **思考預算預設無上限**（log：`budget=2147483647 tokens`）。曾發生一題思考 82,300 token、耗盡 context 而沒有輸出最終答案的情況。評估實驗必須限制思考長度或關閉思考
- **Windows 的 Sysmem Fallback** 會讓 VRAM 溢出時默默改用系統 RAM，速度掉到個位數。NVIDIA 控制面板應設為 Prefer No Sysmem Fallback
- **SSH 斷線會殺掉前景的 llama-server**（Windows 上直接在 SSH 裡啟動時）。長時間任務要背景執行
- **llama.cpp 的 fit 機制**在放不下時會自動調參數；看到 `no changes needed` 與 `offloaded 66/66 layers to GPU` 才代表全放進 GPU。log 中「cannot meet free memory target」只代表沒達到它的安全餘裕目標，記憶體是預先配置的，使用中不會再成長
- 映像預設環境變數已設 `--host 0.0.0.0`，指令中再寫會出現覆蓋警告，無害
- 新版 llama.cpp 預告預設 port 將改為 9931，指令中要明確寫 `--port`
