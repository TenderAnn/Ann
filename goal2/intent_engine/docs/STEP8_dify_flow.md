# STEP8 Dify Flow Notes

## Tool import
1. 在 Dify 控制台 → `工具` → `导入 OpenAPI`，上传 `api/openapi.yaml`。
2. 设置服务器地址为 `http://<host>:8080`（本地调试可用 `http://127.0.0.1:8080`）。
3. Dify 会自动生成四个操作：`POST /intent/parse`、`/intent/rewrite`、`/intent/clarify`、`/intent/feedback`。验证 `测试` 面板，复现 `docs/STEP4_api_samples.md` 中的三条请求。

## Flow 编排
```
[User Input]
   ↓
[intent_parse]
   ↙ need_clarify? ↘
[clarify]        [intent_rewrite]
   ↑                ↓
  loop        [retriever (预留)]
                  ↓
            [feedback]
```
- `intent_parse` 输出：`intent`、`confidence`、`need_clarify`、`slots`、`normalized`
- 当 `need_clarify == true` → `clarify` 节点向用户追问，用户回复后回流到 `intent_parse`
- 当 `need_clarify == false` → `intent_rewrite` 生成 1–2 条规范问句 → （可选）发送到检索节点
- 最后把用户的点击/满意度写入 `intent_feedback`

## 调用日志示例
- `intent_parse`: 输入 “有没有快返型，最好5年内能返的” → 200 OK，intent=BENEFIT_RETURN
- `intent_rewrite`: 输入 parse 的 slots+intent → 200 OK，返回两条规范问句
- `intent_clarify`: 输入 “护理险保障期间” → 200 OK，输出追问

> 截图：请在 Dify UI 中截取工具导入成功界面、Flow 编排图和三条调用日志，随部署资料提交。
