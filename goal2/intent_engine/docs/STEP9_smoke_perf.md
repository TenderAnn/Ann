# STEP9 Smoke & Perf Notes

## Functional smoke (10 utterances)
| # | Query | Intent | Conf | Need Clarify | Clarify question |
|---|-------|--------|------|--------------|------------------|
|1|有没有快返型，最好5年内能返的|BENEFIT_RETURN|0.97|否|—|
|2|护理险有什么要求|POLICY_VALIDITY|0.65|是|偏向查询 CCRC 资格权益、生存金短期返还，还是其他权益？|
|3|社保里的养老院保险怎么弄|BENEFIT_RETURN|0.96|否|—|
|4|臻享年金新版的投保年龄多少|ELIGIBILITY|0.99|否|—|
|5|快返型交费年期和等待期分别是多少|BENEFIT_RETURN|0.89|否|—|
|6|趸交是不是一定比分期好|BENEFIT_RETURN|0.57|是|您关注养老/年金、终身寿险还是重疾/意外险种？|
|7|理赔需要哪些材料|CLAIM_PROCESS|0.47|是|您关注养老/年金、终身寿险还是重疾/意外险种？|
|8|yanglao shequ 的保险等待期多久|BENEFIT_RETURN|0.95|否|—|
|9|利安鑫利来金瑜终身寿险投保年龄|ELIGIBILITY|0.77|是|偏向查询 CCRC 资格权益、生存金短期返还，还是其他权益？|
|10|明天天气怎么样|BENEFIT_RETURN|0.38|是|您关注养老/年金、终身寿险还是重疾/意外险种？|

## Micro benchmark (TestClient, 200 sequential /intent/parse calls)
- Mean latency: **1.51 ms**
- P50 / P95 / P99: **1.44 / 1.73 / 1.93 ms**
- Environment: macOS local, single Uvicorn worker (TestClient)

> For real QPS testing, run `locust` or `hey` against the Dockerized service (suggested targets: 100/200/300 QPS) and monitor CPU/latency charts. This quick loop only validates parser stability prior to heavier load.
