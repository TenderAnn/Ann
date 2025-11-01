# 利安人寿｜精准召回系统 技术路线与复现手册

> 以 `demo5/insurance-emb-eval/` 为根；仅需 Python 环境（CPU 即可完成大部分流程）。

## 0. 环境
```bash
python -m pip install -r requirements.txt
python -m pip install -U torch transformers accelerate pyarrow openai rank-bm25 jieba
```

## 1. 数据解析与切片
```
审计：python scripts/unpack_and_audit.py --zip shuju.zip
解析：python scripts/extract_pdf.py --max-workers 4
切片：python scripts/chunking.py
质检：python scripts/quality_report.py
```
参数（configs/config.yaml）：max_chars=350, overlap=120, min_para=40, cross_page_merge=true

## 2. 测试集构建
- 术语模板：`configs/terms.yaml`
- 构建：`python scripts/build_testsuite.py`
- 校验：`python scripts/validate_testsuite.py`

## 3. 产品名与前缀
```
抽取：python scripts/build_product_map.py
通名清洗：python scripts/sanitize_product_map.py → artifacts/product_name_map.clean.json
语料前缀：python scripts/augment_corpus_with_productname.py → corpus/chunks/all_chunks.with_name.jsonl
查询重写：python scripts/rewrite_queries_with_clean_name_and_base.py → testsuite/queries.patched3.jsonl
```

## 4. 嵌入与索引（BGE/M3E）
语料向量：
```bash
python scripts/encode_embeddings.py \
  --input corpus/chunks/all_chunks.with_name.jsonl \
  --field text --id-field chunk_id \
  --model BAAI/bge-large-zh-v1.5 \
  --model-alias bge_large_zh_v1_5_mean_cos \
  --provider sentence_transformers --max-length 512 --normalize
```
查询向量：同上，改 `--input testsuite/queries.patched3.jsonl --field query --id-field qid`。

## 5. 评测（向量-only 基线）
```
python scripts/eval_faiss.py --alias bge_large_zh_v1_5_mean_cos --topk 100 --qrels-doc testsuite/qrels_doc_multi.tsv
python scripts/report_faiss.py
```

## 6. 融合（BM25 + 向量，RRF）
```
python scripts/bm25_and_fusion_eval.py --alias bge_large_zh_v1_5_mean_cos
# 输出：results/hybrid/<alias>/{topk,metrics.json}
```

## 7. 轻重排（Cross‑Encoder）
```
python scripts/rerank_cross_encoder.py \
  --alias bge_large_zh_v1_5_mean_cos \
  --topk-dir results/hybrid/bge_large_zh_v1_5_mean_cos/topk \
  --queries testsuite/queries.patched3.jsonl \
  --corpus corpus/chunks/all_chunks.with_name.jsonl \
  --model BAAI/bge-reranker-base --batch 16 --max-length 256

python scripts/eval_topk_from_json.py \
  --topk-dir results/rerank/bge_large_zh_v1_5_mean_cos/topk \
  --qrels-doc testsuite/qrels_doc_multi.tsv
```
若需更高 Passage，可切换 `BAAI/bge-reranker-large`。

## 8. 可选：文档质心索引（Doc‑FAISS）
```
python scripts/build_doc_centroids.py --alias bge_large_zh_v1_5_mean_cos
python scripts/eval_doc_faiss.py --alias bge_large_zh_v1_5_mean_cos --qrels-doc testsuite/qrels_doc_multi.tsv
```

## 9. 上线建议
- 向量库：Qdrant/Milvus（cosine），HNSW/IVF；
- 关键词库：OpenSearch/ES（BM25）；
- 在线排序：BM25 → 向量 → RRF → Cross‑Encoder；
- Query 预处理：根据 doc_id 注入通名/编号；术语标准化与别名展开；
- 监控：离线回归（本工程）+ 线上 A/B（Doc 命中率、首屏证据可读性、用户满意度）。

## 10. 指标复刻（关键结果）
- BGE + RRF：Doc R@10 0.9955、Pass R@10 0.3773
- BGE + RRF + CE(base)：Doc R@10 1.0000、Pass R@10 0.4091
- M3E + RRF：Doc R@10 1.0000、Pass R@10 0.2045

建议将 BGE 路线作为生产链路；M3E 保留为对照/灾备。

> 复现提示：若需 BM25/重排，务必保留 `corpus/chunks/all_chunks.with_name.jsonl`；向量-only 评测不受影响。
