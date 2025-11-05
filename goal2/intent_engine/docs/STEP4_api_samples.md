# STEP4 API Samples
### /intent/parse — 有没有快返型，最好5年内能返的
```json
{
  "intent": "BENEFIT_RETURN",
  "confidence": 0.9698934308677097,
  "probabilities": {
    "BENEFIT_RETURN": 0.9698934308677097,
    "CLAIM_PROCESS": 0.0034618087952251538,
    "COVERAGE_EXCLUSION": 0.003314784638709651,
    "ELIGIBILITY": 0.008764521385464472,
    "POLICY_VALIDITY": 0.010739962788814303,
    "PREMIUM_RATE": 0.0038254915240767064
  },
  "normalized": "生存金短期返还(≤5年),最好5年内能返的",
  "slots": {
    "benefit_type": "生存金短期返还(≤5年)"
  },
  "need_clarify": false,
  "threshold": 0.77
}
```

### /intent/parse — 臻享年金2024版的投保年龄是多少
```json
{
  "intent": "ELIGIBILITY",
  "confidence": 0.9810020605881572,
  "probabilities": {
    "BENEFIT_RETURN": 0.00531244776745562,
    "CLAIM_PROCESS": 0.001983775077777507,
    "COVERAGE_EXCLUSION": 0.0027497092950698426,
    "ELIGIBILITY": 0.9810020605881572,
    "POLICY_VALIDITY": 0.007001782952821115,
    "PREMIUM_RATE": 0.0019502243187188046
  },
  "normalized": "臻享养老/年金2024版的投保年龄是多少",
  "slots": {
    "product_line": "养老/年金",
    "field": "投保年龄",
    "version_year": "2024"
  },
  "need_clarify": false,
  "threshold": 0.77
}
```

### /intent/parse — 长护险理赔需要什么材料？
```json
{
  "intent": "CLAIM_PROCESS",
  "confidence": 0.5468946725250354,
  "probabilities": {
    "BENEFIT_RETURN": 0.12400875933142537,
    "CLAIM_PROCESS": 0.5468946725250354,
    "COVERAGE_EXCLUSION": 0.014224624851853588,
    "ELIGIBILITY": 0.03358420326445525,
    "POLICY_VALIDITY": 0.2686093628816884,
    "PREMIUM_RATE": 0.012678377145541916
  },
  "normalized": "护理保险理赔理赔材料?",
  "slots": {
    "product_line": "护理保险",
    "field": "理赔材料"
  },
  "need_clarify": true,
  "threshold": 0.77
}
```

### /intent/rewrite
```json
{
  "rewrites": [
    "包含生存金短期返还(≤5年)的终身寿险产品有哪些？",
    "生存金在5年内返还的寿险条款有哪些？"
  ],
  "diagnostics": {
    "used_intent": "BENEFIT_RETURN",
    "slots": {
      "benefit_type": "生存金短期返还(≤5年)",
      "product_line": "终身寿险"
    },
    "templates_considered": 2,
    "generated": 2
  },
  "slots": {
    "benefit_type": "生存金短期返还(≤5年)",
    "product_line": "终身寿险"
  }
}
```

### /intent/clarify
```json
{
  "question": "偏向查询 CCRC 资格权益、生存金短期返还，还是其他权益？",
  "follow_up": [],
  "suggestions": [],
  "slots": {
    "product_line": "护理保险",
    "field": "保障期间"
  }
}
```

### /intent/feedback
```json
{
  "ok": true
}
```
