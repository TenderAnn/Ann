# Embedding 保险场景评测报告

## 一、数据与评测配置
- 文档数：**262**（来自 artifacts/product_name_map.clean.json）
- 切片数：**9356**
- 测试集：**220** 条（文件：testsuite/queries.patched3.jsonl）
- 指标：Doc（R@5/10/20、MRR@10、nDCG@10），Pass（R@10、MRR@10、nDCG@10）
- 召回链路：向量（FAISS）/ BM25 + RRF / Cross‑Encoder 重排；Doc 评测采用多正例 `qrels_doc_multi.tsv`

### A. 向量基线（FAISS）

| Alias | Doc R@5 | Doc R@10 | Doc R@20 | Pass R@10 | Doc MRR@10 | Doc nDCG@10 |
|---|---:|---:|---:|---:|---:|---:|
| te3_small_cos | 0.9818 | 1.0000 | 1.0000 | 0.3000 | 0.9031 | 0.9274 |
| qwen_text_emb_v3 | 0.9682 | 0.9773 | 0.9818 | 0.3409 | 0.8959 | 0.9161 |
| bge_large_zh_v1_5_mean_cos | 0.9773 | 0.9955 | 0.9955 | 0.3500 | 0.9146 | 0.9345 |
| m3e_large_mean_cos | 0.8682 | 0.9455 | 0.9818 | 0.0909 | 0.7349 | 0.7853 |

### B. 融合（BM25 + 向量，RRF）

| Alias | Doc R@5 | Doc R@10 | Doc R@20 | Pass R@10 | Doc MRR@10 | Doc nDCG@10 |
|---|---:|---:|---:|---:|---:|---:|
| te3_small_cos | 1.0000 | 1.0000 | 1.0000 | 0.3545 | 0.9780 | 0.9837 |
| qwen_text_emb_v3 | 0.9955 | 1.0000 | 1.0000 | 0.3864 | 0.9634 | 0.9726 |
| bge_large_zh_v1_5_mean_cos | 0.9955 | 0.9955 | 1.0000 | 0.3773 | 0.9765 | 0.9813 |
| m3e_large_mean_cos | 1.0000 | 1.0000 | 1.0000 | 0.2045 | 0.9661 | 0.9747 |

### C. 轻重排（Cross‑Encoder on Top‑100）

| Alias | Doc R@5 | Doc R@10 | Doc R@20 | Pass R@10 | Doc MRR@10 | Doc nDCG@10 |
|---|---:|---:|---:|---:|---:|---:|
| te3_small_cos | 1.0000 | 1.0000 | 1.0000 | 0.4000 | 0.9871 | 0.9904 |
| qwen_text_emb_v3 | 1.0000 | 1.0000 | 1.0000 | 0.4045 | 0.9816 | 0.9862 |
| bge_large_zh_v1_5_mean_cos | 1.0000 | 1.0000 | 1.0000 | 0.4091 | 0.9879 | 0.9910 |

## 二、结论与推荐
- **模型表现综述**  
  - **OpenAI `te3_small_cos`**：Doc R@10=1.0000，Pass R@10=0.3000，在云侧模型中表现稳定，可满足对外 API 场景。  
  - **Qwen `text-embedding-v3`**：Doc R@10=0.9773，Pass R@10=0.3409，兼顾中文标准化与向量质量，是国产 API 的优先备选。  
  - **BGE-large-zh-v1.5**：Doc R@10=0.9955，Pass R@10=0.3500，本地模型中指标最佳；后续融合与重排可进一步提升到 Doc≈1.000、Pass≈0.41。  
  - **M3E-large**：Doc R@10=0.9455，Pass R@10=0.0909，更适合做对照或低资源场景，不建议作为主线。  
- **融合策略（BM25 + RRF）**  
  - 四条链路在融合后 Doc 指标均逼近 1.000，Pass 指标依次为 Qwen 0.3864、BGE 0.3773、OpenAI 0.3545、M3E 0.2045；其中 **Qwen/BGE** 在段落召回方面领先。  
  - 实战中建议保留 BM25 精确匹配（条款、术语）与向量召回并行，RRF 以优势互补。  
- **重排策略（Cross-Encoder）**  
  - 在 RRF top‑100 基础上，`BAAI/bge-reranker-base` 将 BGE 的 Pass R@10 提升到 **0.4091**；同流程下，Qwen 与 OpenAI 也能达到 Pass R@10≈0.40、Doc≈1.00。  
  - 若需要更高 Passage 精度，可切换 `bge-reranker-large` 或扩展 Passage 银标（dense qrels）。  
- **推荐上线方案**  
  - **召回层**：`BAAI/bge-large-zh-v1.5` 向量召回 + `rank-bm25`（jieba）。  
  - **融合层**：RRF（k=60），向量 top-200 ∪ BM25 top-200 → fused top-100。  
  - **重排层**：`BAAI/bge-reranker-base`（batch=16，max_len=256）。  
  - 该链路在条款/说明书/费率表混合语料上实现 Doc≈1.000、Pass≈0.409，满足目标一“可复现基线”要求。  
- **备选建议**  
  - Qwen `text-embedding-v3`（DashScope）与 OpenAI `text-embedding-3` 可作为多云或对外 API 方案；M3E 保留为对照/灾备。  
  - “通名 + 文档类型 + 编号” 前缀方案与多正例 Doc 标签对所有模型均适用，后续引入 DeepSeek、Nomic 等模型时可沿用同流程快速横评。

## 三、复现实操（关键命令）
详见仓库 `technical_route.md`：包含切片、编码、评测、融合、重排与报告生成的完整命令。

## 四、附录
- 环境变量：`BIANXIE_API_KEY` / `OPENAI_API_KEY`；`OPENAI_BASE_URL`。
- 评测标签：Doc 用 `testsuite/qrels_doc_multi.tsv`；Pass 用 `testsuite/qrels_passage.tsv`。
