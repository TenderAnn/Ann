# STEP5 Rewrite Samples

## Sample 1
- Input: 有没有快返型，最好5年内能返的
- Normalized: 生存金短期返还(≤5年),最好5年内能返的
- Slots: {'benefit_type': '生存金短期返还(≤5年)'}
- Rewrites: ['生存金在5年内返还的寿险条款有哪些？']
- Diagnostics: {'intent_requested': None, 'intent_used': 'BENEFIT_RETURN', 'fallback_mode': False, 'slots': {'benefit_type': '生存金短期返还(≤5年)'}, 'templates_considered': 1, 'generated': 1}

## Sample 2
- Input: 臻享年金2024版的投保年龄是多少
- Normalized: 臻享养老/年金2024版的投保年龄是多少
- Slots: {'product_line': '养老/年金', 'field': '投保年龄', 'version_year': '2024'}
- Rewrites: ['养老/年金产品中，投保年龄一般如何约定？']
- Diagnostics: {'intent_requested': None, 'intent_used': 'ELIGIBILITY', 'fallback_mode': False, 'slots': {'product_line': '养老/年金', 'field': '投保年龄', 'version_year': '2024'}, 'templates_considered': 1, 'generated': 1}

## Sample 3
- Input: 请问护理险职业等级有什么要求
- Normalized: 护理保险职业类别有什么要求
- Slots: {'product_line': '护理保险', 'field': '职业类别'}
- Rewrites: ['养老/年金产品中，职业类别一般如何约定？']
- Diagnostics: {'intent_requested': None, 'intent_used': 'ELIGIBILITY', 'fallback_mode': False, 'slots': {'product_line': '护理保险', 'field': '职业类别'}, 'templates_considered': 1, 'generated': 1}

## Sample 4
- Input: 想了解康宁重疾等待期多长
- Normalized: 想了解康宁重疾保险等待期多长
- Slots: {'product_line': '重疾保险', 'field': '等待期'}
- Rewrites: ['请补充险种、权益或字段信息，以便定位规范问句。']
- Diagnostics: {'intent_requested': None, 'intent_used': 'POLICY_VALIDITY', 'fallback_mode': False, 'slots': {'product_line': '重疾保险', 'field': '等待期'}, 'templates_considered': 0, 'generated': 1}

## Sample 5
- Input: 连客优养老护理2023版交费年期多久
- Normalized: 连客优养老/年金护理保险2023版交费年期多久
- Slots: {'product_line': '养老/年金', 'field': '交费年期', 'version_year': '2023'}
- Rewrites: ['养老/年金的费率表如何阅读？']
- Diagnostics: {'intent_requested': None, 'intent_used': 'PREMIUM_RATE', 'fallback_mode': False, 'slots': {'product_line': '养老/年金', 'field': '交费年期', 'version_year': '2023'}, 'templates_considered': 1, 'generated': 1}

## Sample 6
- Input: 有什么年金发放规则可以参考
- Normalized: 有什么年金领取规则可以参考
- Slots: {'product_line': '养老/年金', 'benefit_type': '年金领取'}
- Rewrites: ['包含年金领取的养老/年金产品有哪些？', '生存金在5年内返还的寿险条款有哪些？']
- Diagnostics: {'intent_requested': None, 'intent_used': 'BENEFIT_RETURN', 'fallback_mode': False, 'slots': {'product_line': '养老/年金', 'benefit_type': '年金领取'}, 'templates_considered': 2, 'generated': 2}

## Sample 7
- Input: 意外险理赔流程怎么走
- Normalized: 意外保险理赔流程怎么走
- Slots: {'product_line': '意外保险', 'field': '理赔流程'}
- Rewrites: ['意外保险产品的理赔须知如何表述？']
- Diagnostics: {'intent_requested': None, 'intent_used': 'CLAIM_PROCESS', 'fallback_mode': False, 'slots': {'product_line': '意外保险', 'field': '理赔流程'}, 'templates_considered': 1, 'generated': 1}

## Sample 8
- Input: 增额寿2023版的职业类别限制是什么
- Normalized: 增额终身寿险2023版的职业类别限制是什么
- Slots: {'product_line': '增额终身寿险', 'field': '职业类别', 'version_year': '2023'}
- Rewrites: ['养老/年金产品中，职业类别一般如何约定？']
- Diagnostics: {'intent_requested': None, 'intent_used': 'ELIGIBILITY', 'fallback_mode': False, 'slots': {'product_line': '增额终身寿险', 'field': '职业类别', 'version_year': '2023'}, 'templates_considered': 1, 'generated': 1}

## Sample 9
- Input: 冷静期一般多长
- Normalized: 犹豫期一般多长
- Slots: {'field': '犹豫期'}
- Rewrites: ['请补充险种、权益或字段信息，以便定位规范问句。']
- Diagnostics: {'intent_requested': None, 'intent_used': 'POLICY_VALIDITY', 'fallback_mode': False, 'slots': {'field': '犹豫期'}, 'templates_considered': 0, 'generated': 1}

## Sample 10
- Input: 想知道趸交还是分期更适合
- Normalized: 趸交还是分期更适合
- Slots: {'pay_years': '趸交'}
- Rewrites: ['生存金在5年内返还的寿险条款有哪些？', '养老型保险的免责条款有哪些？']
- Diagnostics: {'intent_requested': None, 'intent_used': None, 'fallback_mode': False, 'slots': {'pay_years': '趸交'}, 'templates_considered': 2, 'generated': 2}
