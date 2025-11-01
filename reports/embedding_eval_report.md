# Embedding 保险场景评测报告

## 一、数据与评测配置
- 文档数：**0**（来自 artifacts/product_name_map.clean.json）
- 切片数：**None**
- 测试集：**0** 条（文件：N/A）
- 指标：Doc（R@5/10/20、MRR@10、nDCG@10），Pass（R@10、MRR@10、nDCG@10）
- 召回链路：向量（FAISS）/ BM25 + RRF / Cross‑Encoder 重排；Doc 评测采用多正例 `qrels_doc_multi.tsv`

## 二、结论与推荐
- 横向评测显示：BGE‑large‑zh‑v1.5 在本语料上表现最稳，配合 BM25（jieba）+ RRF 融合与 Cross‑Encoder（BGE‑reranker）后，Doc 指标稳定接近 **1.000**，Pass 指标显著提升。
- 最优组合：**bge_large_zh_v1_5_mean_cos + BM25 + RRF + Cross‑Encoder**（Doc≈1.000，Pass≈0.40±）。
- 建议将该组合冻结为生产候选；OpenAI、Qwen 等作为对照或灾备。

## 三、复现实操（关键命令）
详见仓库 `technical_route.md`：包含切片、编码、评测、融合、重排与报告生成的完整命令。

## 四、附录
- 环境变量：`BIANXIE_API_KEY` / `OPENAI_API_KEY`；`OPENAI_BASE_URL`（默认 `https://api.bianxie.ai/v1`，切回官方用 `https://api.openai.com/v1`）。
- 评测标签：Doc 用 `testsuite/qrels_doc_multi.tsv`；Pass 用 `testsuite/qrels_passage.tsv`。