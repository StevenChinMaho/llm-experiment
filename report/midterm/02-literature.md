## 2. 國內外相關研究情況與重要參考文獻之評述

**模型架構與 KV cache。** Transformer [1] 以自注意力取代遞迴結構，成為現今 LLM 的基礎，但每個 token 都要保存各層的 Key 與 Value（KV cache），使記憶體隨 context 線性成長。GQA [2] 讓多個 query head 共用一組 key／value head，在品質接近的前提下縮小 KV cache；本研究的模型即採用 24 個 query head 共用 4 個 KV head 的配置。FlashAttention [3] 從 GPU 記憶體階層的角度重新安排注意力計算，減少高頻寬記憶體的讀寫，是本研究推論引擎預設開啟的選項。Gated DeltaNet [4] 結合閘控與 delta rule，以固定大小的遞迴狀態取代 KV cache，並提出與注意力層交錯的混合架構。本研究的模型同樣是混合架構：64 層中有 48 層是以固定大小遞迴狀態運作的線性層（模型檔以 SSM 參數描述，其確切設計以官方文件為準），只有 16 層需要 KV cache，這是其 KV cache 極小的原因。

**權重量化。** GPTQ [5] 利用近似二階資訊做一次性的後訓練量化，能把 1750 億參數的模型壓到 3～4 位元，並以困惑度評估品質損失。AWQ [6] 觀察到只有少數「重要」權重主宰誤差，依啟動值的統計決定保護哪些通道。本研究使用的 GGUF 量化檔同樣利用重要性資訊（imatrix），並對不同張量分配不同精度。困惑度評估常用的 WikiText-2 資料集出自 [7]。上述研究多以困惑度作為品質指標，本研究的初步結果則顯示困惑度在 4 位元附近已無法分辨差異，因此改以 KL 散度為主要指標（見 2.1.7）。

**推論系統與效能模型。** PagedAttention [8] 借用作業系統的分頁概念管理 KV cache，解決多使用者伺服器的記憶體碎片問題；本研究的情境是單一使用者，關注的則是單張消費級顯示卡上 VRAM 的分配。Roofline 模型 [9] 以「每位元組記憶體流量對應的運算量」說明程式的效能上限受頻寬或運算力限制，本研究以它解釋生成（受頻寬限制）與讀取 prompt（受運算限制）的差異。

**推測解碼與多 token 預測。** 推測解碼 [10] 以小模型先猜數個 token，再由大模型一次驗證，在不改變輸出分布的前提下加速 2～3 倍；推測取樣 [11] 證明在使用溫度取樣時，經修正的拒絕取樣仍能在硬體數值精度內保持目標分布。多 token 預測 [12] 在訓練時加入預測後續多個 token 的輸出頭，可直接拿來做自我推測解碼；DeepSeek-V3 [13] 在大型模型上採用此設計並報告約 1.8 倍的生成速度。本研究的模型檔內含一層 MTP 層，量化檔發布者另提供獨立的 MTP 模組 [20]；本研究量測它在消費級顯示卡上的實際加速與 VRAM 代價，並發現混合架構會額外放大遞迴狀態的記憶體需求（見 2.1.8）。

**測試時運算與思考模式。** Snell 等人 [14] 指出，在適當分配下，推論時投入更多運算有時比使用更大的模型更有效率。Qwen3 技術報告 [15] 描述了思考／非思考模式與「思考預算」的設計。本研究的 RQ3 將這個問題放到單張顯示卡的情境：權重精度與思考預算互相競爭同一份 VRAM 與時間，兩者如何取捨。

**工具使用與評測。** ReAct [16] 讓模型交錯產生推理與動作，Toolformer [17] 讓模型自行學會呼叫計算器等工具，兩者是 RQ4 的基礎。評測方面，MathArena [18] 主張以新近舉辦的數學競賽題評估模型，以降低訓練資料汙染的風險；本研究的任務題目即採用其整理的 AIME 2026 題組。

**綜合評述。** 既有研究多在資料中心等級的硬體上，分別探討量化、推測解碼或測試時運算其中一項。針對「單張消費級顯示卡、混合架構的思考型模型」，同時量測權重精度、context 容量、推測解碼與思考預算之間取捨的研究仍然有限，這正是本研究要補足的部分。

## 參考文獻

<!-- MLA 格式依老師範例。論文 [1]–[18] 已由使用者確認（2026-10-21，docs/references.md）。網頁資源的存取日期以實際查閱日為準。 -->

[1] Vaswani, Ashish, et al. "Attention is all you need." *Advances in Neural Information Processing Systems* 30 (2017).

[2] Ainslie, Joshua, et al. "GQA: Training generalized multi-query transformer models from multi-head checkpoints." *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*. 2023.

[3] Dao, Tri, et al. "FlashAttention: Fast and memory-efficient exact attention with IO-awareness." *Advances in Neural Information Processing Systems* 35 (2022).

[4] Yang, Songlin, Jan Kautz, and Ali Hatamizadeh. "Gated delta networks: Improving Mamba2 with delta rule." *International Conference on Learning Representations*. 2025.

[5] Frantar, Elias, et al. "GPTQ: Accurate post-training quantization for generative pre-trained transformers." *International Conference on Learning Representations*. 2023.

[6] Lin, Ji, et al. "AWQ: Activation-aware weight quantization for on-device LLM compression and acceleration." *Proceedings of Machine Learning and Systems* 6 (2024).

[7] Merity, Stephen, et al. "Pointer sentinel mixture models." *International Conference on Learning Representations*. 2017.

[8] Kwon, Woosuk, et al. "Efficient memory management for large language model serving with PagedAttention." *Proceedings of the 29th Symposium on Operating Systems Principles*. 2023.

[9] Williams, Samuel, Andrew Waterman, and David Patterson. "Roofline: An insightful visual performance model for multicore architectures." *Communications of the ACM* 52.4 (2009): 65-76.

[10] Leviathan, Yaniv, Matan Kalman, and Yossi Matias. "Fast inference from transformers via speculative decoding." *International Conference on Machine Learning*. PMLR, 2023.

[11] Chen, Charlie, et al. "Accelerating large language model decoding with speculative sampling." *arXiv preprint arXiv:2302.01318* (2023).

[12] Gloeckle, Fabian, et al. "Better & faster large language models via multi-token prediction." *Proceedings of the 41st International Conference on Machine Learning*. PMLR, 2024.

[13] DeepSeek-AI. "DeepSeek-V3 technical report." *arXiv preprint arXiv:2412.19437* (2024).

[14] Snell, Charlie, et al. "Scaling LLM test-time compute optimally can be more effective than scaling model parameters." *arXiv preprint arXiv:2408.03314* (2024).

[15] Qwen Team. "Qwen3 technical report." *arXiv preprint arXiv:2505.09388* (2025).

[16] Yao, Shunyu, et al. "ReAct: Synergizing reasoning and acting in language models." *International Conference on Learning Representations*. 2023.

[17] Schick, Timo, et al. "Toolformer: Language models can teach themselves to use tools." *Advances in Neural Information Processing Systems* 36 (2023).

[18] Balunović, Mislav, et al. "MathArena: Evaluating LLMs on uncontaminated math competitions." *Advances in Neural Information Processing Systems* 38 (2025).

[19] ggml-org. "llama.cpp." *GitHub*, github.com/ggml-org/llama.cpp. Accessed 14 Oct. 2026.

[20] Unsloth. "unsloth/Qwen3.8-27B-GGUF." *Hugging Face*, huggingface.co/unsloth/Qwen3.8-27B-GGUF. Accessed 14 Oct. 2026.

[21] Qwen. "Qwen/Qwen3.8-27B." *Hugging Face*, huggingface.co/Qwen/Qwen3.8-27B. Accessed 14 Oct. 2026.
