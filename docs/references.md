# 參考文獻候選清單

**狀態說明：**

- **已確認**：2026-10-21 使用者已在 Google Scholar 確認全部 21 篇，並把 PDF 下載到 `docs/references-pdf/`（檔名＝本表編號）。Roofline 頁碼以 PDF 為準修正為 65-76
- 已查到（待確認）：Claude 已用 WebSearch 在官方來源找到，等使用者確認
- **已確認**：使用者確認過，可以放進報告
- 未查證：還沒找到

使用者確認時請做兩件事：（1）點開連結確認是同一篇；（2）到 Google Scholar 搜尋標題，按「引用 → MLA」，和下表的 MLA 草稿比對，不一致時以 Scholar 為準。標「⚠」的欄位是 Claude 沒能從搜尋結果確認的部分，一定要以 Scholar 為準。

**絕不可新增沒有出處的文獻。** 使用者沒讀過的論文也不要引用；至少要讀過摘要和被引用觀點所在的段落。

## 論文（2026-10-13 查證）

| # | 主題 | MLA 草稿 | 在報告中的用途 | 狀態 | 查證連結 |
|---|---|---|---|---|---|
| 1 | Transformer | Vaswani, Ashish, et al. "Attention is all you need." *Advances in Neural Information Processing Systems* 30 (2017). | 模型基礎架構 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [NeurIPS](https://proceedings.neurips.cc/paper/7181-attention-is-all) |
| 2 | GQA | Ainslie, Joshua, et al. "GQA: Training generalized multi-query transformer models from multi-head checkpoints." *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*. 2023. | 解釋 head_count_kv=4 如何縮小 KV cache | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [ACL Anthology](https://aclanthology.org/2023.emnlp-main.298) |
| 3 | FlashAttention | Dao, Tri, et al. "FlashAttention: Fast and memory-efficient exact attention with IO-awareness." *Advances in Neural Information Processing Systems* 35 (2022). ⚠頁碼 | `-fa` 的原理、記憶體 IO | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2022/hash/67d57c32e20fd0a7a302cb81d36e40d5-Abstract-Conference.html) |
| 4 | 量化 | Frantar, Elias, et al. "GPTQ: Accurate post-training quantization for generative pre-trained transformers." *International Conference on Learning Representations (ICLR)*. 2023. | 後訓練量化、以困惑度評估 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [arXiv 2210.17323](https://arxiv.org/abs/2210.17323) |
| 5 | 量化 | Lin, Ji, et al. "AWQ: Activation-aware weight quantization for on-device LLM compression and acceleration." *Proceedings of Machine Learning and Systems* 6 (2024). | 依重要性保留精度（對應 imatrix 概念） | **已確認**（2026-10-21，PDF：`docs/references-pdf/`）。MLSys 版標題多了 "On-Device"，引用時用 MLSys 版 | [MLSys](https://proceedings.mlsys.org/paper_files/paper/2024/hash/42a452cbafa9dd64e9ba4aa95cc1ef21-Abstract-Conference.html) |
| 6 | MoE | Fedus, William, Barret Zoph, and Noam Shazeer. "Switch transformers: Scaling to trillion parameter models with simple and efficient sparsity." *Journal of Machine Learning Research* 23.120 (2022): 1-39. | 說明 MoE 與 dense 的差異（替代方案討論） | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [JMLR](https://www.jmlr.org/papers/v23/21-0998.html) |
| 7 | 混合線性注意力 | Yang, Songlin, Jan Kautz, and Ali Hatamizadeh. "Gated delta networks: Improving Mamba2 with delta rule." *International Conference on Learning Representations (ICLR)*. 2025. | 解釋 log 中的遞迴層與固定大小的遞迴狀態（官方程式碼 README 提到已被 Qwen3-Next 採用） | **已確認**（2026-10-21，PDF：`docs/references-pdf/`）。年份是 **2025**，不是 2024 | [ICLR](https://proceedings.iclr.cc/paper_files/paper/2025/hash/4904fad153f6434a7bcf04465d4be2cc-Abstract-Conference.html) |
| 8 | 推測解碼 | Leviathan, Yaniv, Matan Kalman, and Yossi Matias. "Fast inference from transformers via speculative decoding." *International Conference on Machine Learning*. PMLR, 2023. (pp. 19274-19286) | MTP 推測解碼的原理；輸出分布不變 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [PMLR](https://proceedings.mlr.press/v202/leviathan23a.html) |
| 9 | 推論系統 | Kwon, Woosuk, et al. "Efficient memory management for large language model serving with PagedAttention." *Proceedings of the 29th Symposium on Operating Systems Principles*. 2023. ⚠屆數 | KV cache 管理、與 llama.cpp 的比較 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`）。DOI 10.1145/3600006.3613165 | [arXiv 2309.06180](https://arxiv.org/abs/2309.06180) |
| 10 | 效能模型 | Williams, Samuel, Andrew Waterman, and David Patterson. "Roofline: An insightful visual performance model for multicore architectures." *Communications of the ACM* 52.4 (2009): 65-76. | decode 受頻寬限制、prefill 受運算限制 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [CACM](https://cacm.acm.org/?p=21109) |
| 11 | 工具使用 | Yao, Shunyu, et al. "ReAct: Synergizing reasoning and acting in language models." *International Conference on Learning Representations (ICLR)*. 2023. | RQ4 工具輔助的理論基礎 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [ICLR](https://iclr.cc/virtual/2023/poster/11003) |
| 12 | 工具使用 | Schick, Timo, et al. "Toolformer: Language models can teach themselves to use tools." *Advances in Neural Information Processing Systems* 36 (2023). | 模型呼叫計算器等工具（論文的工具之一就是計算器） | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [NeurIPS](https://proceedings.neurips.cc/paper/2023/hash/d842425e4bf79ba039352da0f658a906-Abstract.html) |
| 13 | 資料集 | Merity, Stephen, et al. "Pointer sentinel mixture models." *International Conference on Learning Representations (ICLR)*. 2017. | WikiText-2 資料集出處 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [arXiv 1609.07843](https://arxiv.org/abs/1609.07843) |
| 14 | 模型 | Qwen Team. "Qwen3 technical report." *arXiv preprint arXiv:2505.09388* (2025). ⚠作者 | 所用模型家族的官方說明（思考／非思考模式、思考預算） | **已確認**（2026-10-21，PDF：`docs/references-pdf/`）。**Qwen3.8 沒有找到正式技術報告**，模型本身改引 W4。Scholar 上的作者欄可能列為個人姓名，以 Scholar 為準 | [arXiv 2505.09388](https://arxiv.org/abs/2505.09388) |
| 15 | 邊緣運算（選配） | Mao, Yuyi, et al. "A survey on mobile edge computing: The communication perspective." *IEEE Communications Surveys & Tutorials* 19.4 (2017): 2322-2358. | 與無線網路／邊緣部署的連結 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [DOI](https://doi.org/10.1109/COMST.2017.2745201) |
| 16 | 思考預算（RQ3） | Snell, Charlie, et al. "Scaling LLM test-time compute optimally can be more effective than scaling model parameters." *arXiv preprint arXiv:2408.03314* (2024). ⚠是否有會議版 | 「多想」能否替代「更大／更精確的模型」，是 RQ3 的直接理論基礎 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`）。如果 Scholar 顯示有會議版，改引會議版 | [arXiv 2408.03314](https://arxiv.org/abs/2408.03314) |
| 17 | MTP（RQ2） | Gloeckle, Fabian, et al. "Better & faster large language models via multi-token prediction." *Proceedings of the 41st International Conference on Machine Learning*. PMLR 235 (2024): 15706-15734. | 多 token 預測頭的原理，以及拿它做推測解碼加速 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [PMLR](https://proceedings.mlr.press/v235/gloeckle24a.html) |
| 18 | MTP（RQ2） | DeepSeek-AI. "DeepSeek-V3 technical report." *arXiv preprint arXiv:2412.19437* (2024). ⚠作者 | 大型模型實際採用 MTP 並搭配推測解碼的案例（報告中第二個 token 接受率 85～90%、約 1.8 倍 tok/s） | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [arXiv 2412.19437](https://arxiv.org/abs/2412.19437) |
| 19 | 推測解碼（RQ2） | Chen, Charlie, et al. "Accelerating large language model decoding with speculative sampling." *arXiv preprint arXiv:2302.01318* (2023). | 推測取樣在使用 temperature 時仍保持輸出分布不變（說明 MTP 無損）；與 #8 互補 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [arXiv 2302.01318](https://arxiv.org/abs/2302.01318) |
| 20 | 長 context 評估（延伸 X1） | Hsieh, Cheng-Ping, et al. "RULER: What's the real context size of your long-context language models?" *First Conference on Language Modeling (COLM)*. 2024. | 以程式產生、可控長度的長文件檢索題設計 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`），只有做 X1 才需要 | [arXiv 2404.06654](https://arxiv.org/abs/2404.06654) |
| 21 | Benchmark（E4） | Balunović, Mislav, et al. "MathArena: Evaluating LLMs on uncontaminated math competitions." *Advances in Neural Information Processing Systems* 38 (2025), Datasets and Benchmarks Track. | E4 題目來源（MathArena/aime_2026）；「用新競賽題降低訓練資料汙染」的方法依據 | **已確認**（2026-10-21，PDF：`docs/references-pdf/`） | [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2025/hash/1d27c01ebd3e3aebe226b44fc970d803-Abstract-Datasets_and_Benchmarks_Track.html) |

**KL 散度作為量化評估指標：** 這是 llama.cpp 社群常用的做法，目前沒有找到能確定出處的論文。先以官方文件（W7）引用；之後若找到學術文獻，讀過後再加入。

## 官方文件、資料集與技術資源

MLA 網頁格式大致為：`作者或組織. "頁面標題." 網站名稱, 網址. 存取日期.` 實際格式請依 MLA 規則確認。

| # | 資源 | 用途 | 狀態 |
|---|---|---|---|
| W1 | llama.cpp GitHub repository（ggml-org/llama.cpp） | 推論引擎、llama-bench、llama-perplexity | 未整理 |
| W2 | llama.cpp Docker 文件（docs/docker.md） | 部署方式 | 未整理 |
| W3 | unsloth/Qwen3.8-27B-GGUF（Hugging Face 模型頁） | 量化檔來源、Dynamic 量化說明 | 未整理 |
| W4 | Qwen/Qwen3.8-27B（Hugging Face 模型頁） | 原始模型、授權、建議取樣參數（Qwen3.8 沒有技術報告，模型本身以此引用） | 未整理 |
| W5 | Model Context Protocol 規範（modelcontextprotocol.io） | 延伸 X4 的 MCP 架構 | 未整理 |
| W6 | NVIDIA Container Toolkit 安裝文件 | 部署環境 | 未整理 |
| W7 | llama.cpp 的 llama-perplexity 說明文件（tools/perplexity 的 README） | KL 散度、Same top p 等指標的定義 | 未整理 |
| W8 | unsloth/Qwen3.8-27B-GGUF 的 MTP 檔與說明 | MTP 推測解碼的使用方式 | 未整理 |
| W9 | MathArena/aime_2026（Hugging Face 資料集，<https://huggingface.co/datasets/MathArena/aime_2026>） | E4 題目。授權 CC BY-NC-SA 4.0（非商業、須署名、相同方式分享） | 2026-10-13 已下載並與 math-ai/aime26 交叉比對答案 30/30 一致 |

## 建議比例

約 10 篇論文＋3～5 個官方文件。文獻評述依主題分段，每篇回答三件事：解決什麼問題、核心想法、與本研究的關係。
