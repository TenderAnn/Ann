# STEP6 Dialog Cases

## Case 1: 快返型模糊险种

- User: 有没有快返型，最好5年内能返的
- Engine: intent=BENEFIT_RETURN, conf=0.99, slots=benefit_type 生存金短期返还(≤5年); 缺 product_line
- Clarify: 您关注养老/年金、终身寿险还是重疾/意外险种？
- User: 养老/年金产品
- Engine: slots 更新 product_line=养老/年金，rewrite 推出 ‘生存金在5年内返还的养老/年金条款有哪些？’

## Case 2: 护理险缺字段

- User: 护理险有什么要求
- Engine: intent=ELIGIBILITY, slots 仅 product_line=护理保险
- Clarify: 想了解投保年龄、等待期、交费年期或理赔材料中的哪一项？
- User: 想知道职业类别
- Engine: slots field=职业类别，rewrite 输出 ‘护理保险的职业类别要求是什么？’

## Case 3: 低置信干扰词

- User: 社保里的养老院保险怎么弄
- Engine: conf=0.61<thr=0.77, slots 空
- Clarify: 请说明是否查询商业养老/年金、终身寿险或其他险种？
- User: 想了解CCRC资格权益
- Engine: slots benefit_type=CCRC资格权益，need_clarify False

## Case 4: 版本年份缺失

- User: 臻享年金新版的投保年龄多少
- Engine: conf=0.96, slots缺version_year
- Clarify: 是否限定某个版本年份？例如‘2024版’
- User: 2024版
- Engine: slots version_year=2024, rewrite ‘臻享年金2024版的投保年龄是多少？’

## Case 5: 并列问句

- User: 快返型交费年期和等待期分别是多少
- Engine: intent=BENEFIT_RETURN, slots 识别 benefit_type, field 未定
- Clarify: 想先了解交费年期还是等待期？
- User: 交费年期
- Engine: field=交费年期，建议拆分第二问

## Case 6: 趸交与分期对比

- User: 趸交是不是一定比分期好
- Engine: intent=PREMIUM_RATE, slots 无
- Clarify: 想咨询投保年龄、交费年期还是具体权益？
- User: 我想确认交费年期
- Engine: field=交费年期，rewrite ‘趸交与分期交费年期如何比较？’

## Case 7: 理赔材料缺险种

- User: 理赔需要哪些材料
- Engine: intent=CLAIM_PROCESS, field=理赔材料, product_line 缺
- Clarify: 请告知关注的险种（养老/年金、终身寿险、重疾等）
- User: 重疾
- Engine: product_line=重疾保险，rewrite ‘重疾保险理赔需要哪些材料？’

## Case 8: 拼音混入

- User: yanglao shequ 的保险等待期多久
- Engine: normalize→CCRC资格权益, slots: benefit_type=CCRC资格权益, field=等待期
- Clarify: 缺乏险种限制→询问养老/年金 vs 终寿
- User: 养老/年金
- Engine: product_line=养老/年金, rewrite 完成

## Case 9: 多轮版本补充

- User: 利安鑫利来金瑜终身寿险投保年龄
- Engine: intent=ELIGIBILITY, slots 无 version_year
- Clarify: 是否限定 2022/2024 版？
- User: 2022
- Engine: slots version_year=2022

## Case 10: 无关句触发拒答

- User: 明天天气怎么样
- Engine: conf=0.32<thr, slots 空
- Clarify: 当前问题不在寿险范围，请说明具体保险意图
- User: 想知道年金返本规则
- Engine: intent=BENEFIT_RETURN, 重试成功
