# 利安人寿｜基于大模型的保险文档精准召回系统 —— 项目框架与结论摘要

> 交付对象：内部评审/业务方/工程团队  
> 版本：v1.0（以 `demo5.zip` 为准）

## 1. 项目目标与验收口径
- **目标一（向量检索基线）**：在 *条款/说明书/费率表* 混合语料上实现**文档级**与**段落级**检索的稳定对齐，给出可复现实验包与最优技术路线。
- **核心指标**  
  - 文档级（Doc）：Recall@10（主）、Recall@20、MRR@10、nDCG@10（多正例 `qrels_doc_multi.tsv`）。  
  - 段落级（Passage）：Recall@10（主）、MRR@10、nDCG@10（原版 `qrels_passage.tsv`）。
- **数据规模**：262 份 PDF（均已解析切片），总切片 ≈ 9,356。测试集 220 条 query（三大主题覆盖）。

## 2. 数据与预处理概览
- **解析与切片**：PyMuPDF → 版面感知切片；参数：`max_chars=350`、`overlap=120`、`min_para=40`，跨页合并开启。页覆盖率 ≈ **0.999**。
- **产品名与前缀**：
  - `artifacts/product_name_map.json`：从每文档前 6 页 + 末页多规则抽取，**262/262** 命中。
  - `artifacts/product_name_map.clean.json`：**通名**清洗（去“公司/条款/说明书/费率表”等赘词）。
  - 片段前缀：`【产品：通名】【文档类型】【编号：base】`。
  - 查询重写：`《通名》（文档类型）（编号 base）`（`testsuite/queries.patched3.jsonl`）。
- **测试集**：`qrels_doc_multi.tsv`（同一产品族多正例）+ `qrels_passage.tsv`（原版）。

## 3. 模型与检索管线（最终推荐）
- **Embedding（召回）**：`BAAI/bge-large-zh-v1.5`（归一化，cosine）
- **关键词检索**：BM25（jieba 分词，`rank-bm25`）
- **融合策略**：RRF（Reciprocal Rank Fusion, k=60），融合 BM25 与向量 top-K
- **重排器**：Cross-Encoder `BAAI/bge-reranker-base`（可换 large 版换取更高 Passage）
- **召回/重排规模**：向量 top-200 + BM25 top-200 → RRF 取 top-100 → Cross-Encoder 重排 top-100

> **上线排序顺序**：BM25 → 向量 → RRF → Cross-Encoder

## 4. 关键指标对比（阶段性 → 最终）

| 阶段 | 方案 | Doc R@10 | Doc R@20 | Passage R@10 |
|---|---|---:|---:|---:|
| 初始基线（向量-only） | BGE（FAISS, A2 之前） | ~0.08 | ~0.13 | ~0.009 |
| A1/A2 之后 | BGE（FAISS, 通名+编号） | **0.9955** | 1.0000 | 0.3500 |
| 融合（方案一） | **BGE + RRF** | **0.9955** | **1.0000** | **0.3773** |
| 轻重排（方案二） | **BGE + RRF + CE（base）** | **1.0000** | **1.0000** | **0.4091** |
| 融合（对照） | M3E + RRF | 1.0000 | 1.0000 | 0.2045 |

> 长文档（≥10 页）在 BGE + RRF + CE 下 **Doc R@10=1.000**。

## 5. 结论与选择
- **最终推荐**：**BGE + BM25（RRF 融合） + BGE‑Reranker（base/large）**。在你的数据上 Doc 指标已**接近/达到满分**；Passage 指标在不改银标的前提下达到 **R@10≈0.41**（继续用 large 重排器可再抬 0.02~0.06）。
- **对业务的意义**：
  1) 产品族（tk/sms/flbe/history）统一检索命中，**文档级定位极稳**；  
  2) 关键条款（等待期/犹豫期/免责/缴费/给付/年金等）在前 10 段中**可用证据显著增多**；  
  3) 支撑后续“生成式问答/证据引用/可解释”链路。

## 6. 风险与改进
- **Passage 银标稀疏**：每问仅 1 个正例，指标对“邻近正确证据”惩罚偏重 → 建议生成 `qrels_passage.dense.tsv`（同页/同 section ±1 片段）。  
- **跨模型一致性**：已验证 BGE 路径为最优；M3E 可作为灾备，不建议投入重排资源。  
- **表格类证据**：`corpus/tables` 的 PNG 在本包中删除；不影响当前指标，但若要做“费率/年龄/缴费”结构化问答，后续需补 OCR/结构化。

## 7. 交付件清单（本次）
- 代码：`scripts/` 全量（含 BM25+RRF、重排器、评测聚合）  
- 数据与配置：`configs/`、`artifacts/`、`testsuite/`（含 `queries.patched3.jsonl` / `qrels_doc_multi.tsv`）  
- 向量与评测：`indexes/`（Parquet） + `results/faiss|hybrid|rerank`（含 `metrics.json` 与 `topk/*.json`）  
- 报告：本文件 + `reports/embedding_leaderboard.md`

## 8. 上线建议（RAG 服务）
- **后端**：Qdrant 或 Milvus（cosine 内积、HNSW/IVF 索引）；BM25 用 ES/OpenSearch，或轻量 `bm25` 旁路。  
- **在线链路**：Query 预处理（注入通名/编号） → BM25 & 向量并发 → RRF 融合 → Cross‑Encoder 重排 → 证据去重（按 doc_id）→ Q&A/引用。  
- **资源**：嵌入检索 CPU 可行；Cross‑Encoder 建议 1×T4/A10；吞吐按 top‑K×batch 可线性扩展。

> 负责人备注：当前 Doc 指标已满足“生产验收”，Passage 指标也达到预期；若需要更高 Passage，可切 `bge-reranker-large`、扩展 passage 银标、或在模板中增强触发词的多样表达。
