# 參考文獻候選清單

**這份清單是憑記憶整理的候選，全部尚未查證。** 作者、標題、年份、出處都可能有誤。放進報告前，每一條都必須：

1. 在 Google Scholar（或 arXiv、會議官網）找到該論文
2. 由使用者確認（或你用 WebSearch 找到後附連結請使用者確認）
3. 從 Google Scholar 的「引用 → MLA」複製正確格式，依老師範例加上編號 `[n]`
4. 把狀態改為「已查證」並填入連結

**絕不可新增沒有出處的文獻。** 使用者沒讀過的論文也不要引用；至少要讀過摘要和被引用觀點所在的段落。

## 論文

| # | 主題 | 候選文獻 | 在報告中的用途 | 狀態 | 查證連結 |
|---|---|---|---|---|---|
| 1 | Transformer | Vaswani et al. (2017), "Attention Is All You Need" | 模型基礎架構 | 未查證 | |
| 2 | GQA | Ainslie et al. (2023), "GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints" | 解釋 head_count_kv=4 如何縮小 KV cache | 未查證 | |
| 3 | FlashAttention | Dao et al. (2022), "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness" | `-fa` 的原理、記憶體 IO | 未查證 | |
| 4 | 量化 | Frantar et al. (2022), "GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers" | 後訓練量化、以困惑度評估 | 未查證 | |
| 5 | 量化 | Lin et al. (2023), "AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration" | 依重要性保留精度（對應 imatrix 概念） | 未查證 | |
| 6 | MoE | Fedus et al. (2021/2022), "Switch Transformers: Scaling to Trillion Parameter Models with Simple and Efficient Sparsity" | 說明 MoE 與 dense 的差異（替代方案討論） | 未查證 | |
| 7 | 混合線性注意力 | Yang et al. (2024), "Gated Delta Networks: Improving Mamba2 with Delta Rule" | 解釋 log 中 SSM／遞迴層與固定大小的遞迴狀態 | 未查證 | |
| 8 | 推測解碼 | Leviathan et al. (2023), "Fast Inference from Transformers via Speculative Decoding" | MTP 層的用途、未來加速方向 | 未查證 | |
| 9 | 推論系統 | Kwon et al. (2023), "Efficient Memory Management for Large Language Model Serving with PagedAttention" | KV cache 管理、與 llama.cpp 的比較 | 未查證 | |
| 10 | 效能模型 | Williams et al. (2009), "Roofline: An Insightful Visual Performance Model for Multicore Architectures" | decode 受頻寬限制、prefill 受運算限制 | 未查證 | |
| 11 | 工具使用 | Yao et al. (2022/2023), "ReAct: Synergizing Reasoning and Acting in Language Models" | RQ3 工具輔助的理論基礎 | 未查證 | |
| 12 | 工具使用 | Schick et al. (2023), "Toolformer: Language Models Can Teach Themselves to Use Tools" | 模型呼叫計算器等工具 | 未查證 | |
| 13 | 資料集 | Merity et al. (2016), "Pointer Sentinel Mixture Models" | WikiText-2 資料集出處 | 未查證 | |
| 14 | 模型 | Qwen 團隊在 arXiv 的技術報告（Qwen3 Technical Report，或 Qwen3.8 若有） | 所用模型的官方說明 | 未查證，需確認 Qwen3.8 是否有正式報告 | |
| 15 | 邊緣運算（選配） | Mao et al. (2017), "A Survey on Mobile Edge Computing: The Communication Perspective" | 與無線網路／邊緣部署的連結 | 未查證 | |
| 16 | 思考預算（RQ3） | Snell et al. (2024), "Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters" | 「多想」能否替代「更大／更精確的模型」，是 RQ3 的直接理論基礎 | 未查證 | |
| 17 | MTP（RQ2） | Gloeckle et al. (2024), "Better & Faster Large Language Models via Multi-token Prediction" | 多 token 預測頭的原理，以及拿它做推測解碼加速 | 未查證 | |
| 18 | MTP（RQ2） | DeepSeek-AI (2024), "DeepSeek-V3 Technical Report" | 大型模型實際採用 MTP 模組的案例 | 未查證 | |
| 19 | 推測解碼（RQ2） | Chen et al. (2023), "Accelerating Large Language Model Decoding with Speculative Sampling" | 推測取樣在使用 temperature 時仍保持輸出分布不變（說明 MTP 無損）；與 #8 互補 | 未查證 | |
| 20 | 長 context 評估（延伸 X1） | Hsieh et al. (2024), "RULER: What's the Real Context Size of Your Long-Context Language Models?" | 以程式產生、可控長度的長文件檢索題設計 | 未查證，只有做 X1 才需要 | |

**KL 散度作為量化評估指標：** 這是 llama.cpp 社群常用的做法，但我目前沒有能確定出處的論文可以推薦。先以官方文件（W7）引用；若要找學術文獻，請在 Google Scholar 搜尋「quantization KL divergence LLM evaluation」，找到並讀過後再加入。

## 官方文件與技術資源

MLA 網頁格式大致為：`作者或組織. "頁面標題." 網站名稱, 網址. 存取日期.` 實際格式請依 MLA 規則確認。

| # | 資源 | 用途 | 狀態 |
|---|---|---|---|
| W1 | llama.cpp GitHub repository（ggml-org/llama.cpp） | 推論引擎、llama-bench、llama-perplexity | 未整理 |
| W2 | llama.cpp Docker 文件（docs/docker.md） | 部署方式 | 未整理 |
| W3 | unsloth/Qwen3.8-27B-GGUF（Hugging Face 模型頁） | 量化檔來源、Dynamic 量化說明 | 未整理 |
| W4 | Qwen/Qwen3.8-27B（Hugging Face 模型頁） | 原始模型、授權、建議取樣參數 | 未整理 |
| W5 | Model Context Protocol 規範（modelcontextprotocol.io） | RQ3 的 MCP 架構 | 未整理 |
| W6 | NVIDIA Container Toolkit 安裝文件 | 部署環境 | 未整理 |
| W7 | llama.cpp 的 llama-perplexity 說明文件（tools/perplexity 的 README） | KL 散度、Same top p 等指標的定義 | 未整理 |
| W8 | unsloth/Qwen3.8-27B-GGUF 的 MTP 檔與說明 | MTP 推測解碼的使用方式 | 未整理 |

## 建議比例

約 10 篇論文＋3～5 個官方文件。文獻評述依主題分段，每篇回答三件事：解決什麼問題、核心想法、與本研究的關係。
