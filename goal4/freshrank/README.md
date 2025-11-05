# Freshrank Regulatory Ranking

Freshrank 提供寿险语料的动态时效排序与监管规则加权能力，支持服务化 API 与离线评估流水线。

## 快速开始（服务/测试）
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `uvicorn freshrank.service.api:app --reload`
4. `python -m pytest tests -q`
5. 使用 `python scripts/rerank_offline.py --input data/parsed/sample.jsonl` 进行离线验证。

## Regulatory 知识包说明
- taxonomy.yaml：定义寿险条款多层分类（产品线/责任/监管标签）。
- rulebook.yaml：描述监管与ESG打分策略、触发条件及降权逻辑。
- weights.yaml：存储针对时效、合规、相关性的系数基线。
- lexicon/：主题词典（如退休保障、健康管理、ESG），驱动实体抽取。
- scripts/build_manifest.py 会在部署前验证上述文件并生成可追踪版本哈希。
