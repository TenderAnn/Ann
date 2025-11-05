# STEP1 数据切分报告

## 切分策略
- 入口脚本：`scripts/split_dataset.py`。执行方式：`.venv/bin/python scripts/split_dataset.py`
- 数据读取自 `data/intent_dataset_zh_insurance_v1.csv`，按 `canonical_query` 分组，确保同一规范问句的所有口语变体不会跨集合泄漏。
- 采用 8/1/1 比例划分，并在每个意图内部按照上述比例分配分组样本，以减少小类缺失。随机种子固定为 42，保证结果可复现。
- 切分结果写入 `data/splits/{train,valid,test}.csv`，并生成 `docs/intent_distribution.png` 展示三个集合的意图分布。

## 数据量与类别占比
| Split | 样本数 | POLICY_VALIDITY | BENEFIT_RETURN | ELIGIBILITY | COVERAGE_EXCLUSION | CLAIM_PROCESS | PREMIUM_RATE |
|-------|-------:|----------------:|---------------:|------------:|-------------------:|--------------:|-------------:|
| train | 1680 | 957 (56.96%) | 393 (23.39%) | 201 (11.96%) | 45 (2.68%) | 42 (2.50%) | 42 (2.50%) |
| valid | 210 | 120 (57.14%) | 48 (22.86%) | 24 (11.43%) | 6 (2.86%) | 6 (2.86%) | 6 (2.86%) |
| test  | 210 | 120 (57.14%) | 48 (22.86%) | 24 (11.43%) | 6 (2.86%) | 6 (2.86%) | 6 (2.86%) |

> 备注：各集合样本总计 2100 条，与原始数据一致。小类（如 `COVERAGE_EXCLUSION`、`CLAIM_PROCESS`、`PREMIUM_RATE`）在验证与测试集中均保持 ≥6 条样本，便于后续评估。
