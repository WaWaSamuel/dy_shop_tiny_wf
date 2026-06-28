# im.send_card

`im.send_card` 是项目内统一的 IM 消息卡片发送 cmd/runtime tool。

它负责把上游 skill 产出的结构化文本拼装成飞书交互式消息卡片，并通过后端 Feishu Bot 发送到指定用户或会话。

## 定位

- 类型：cmd runtime tool
- 后端统一入口：`POST /api/v1/tools/invoke`
- 调用名：`im.send_card`
- 实现位置：`backend/app/tools/runtime_tools.py`
- 底层发送服务：`backend/app/services/feishu_bot.py`
- 底层飞书 API：`lark_oapi.api.im.v1.CreateMessageRequest` → `im.v1.message.acreate`

## 输入

```json
{
  "title": "需要展示在卡片标题里的文本",
  "lines": ["卡片正文第一行", "卡片正文第二行"],
  "template": "blue",
  "open_id": "可选，优先使用的目标飞书用户 open_id",
  "chat_id": "可选，未指定 open_id 时使用的目标会话"
}
```

字段规则：

- `title` 必填。
- `lines` 必填，必须是非空字符串数组。
- `template` 可选，默认 `blue`，可使用飞书卡片支持的模板色。
- `open_id` 优先级高于 `chat_id`。
- 未传 `open_id` 和 `chat_id` 时，由后端按 `FEISHU_BOT_TARGET_OPEN_ID` / `FEISHU_BOT_DEFAULT_CHAT_ID` 兜底。

## 调用方式

通过后端工具统一入口调用：

```http
POST /api/v1/tools/invoke
Content-Type: application/json

{
  "name": "im.send_card",
  "args": {
    "title": "人工确认待处理",
    "lines": [
      "事项：供应商选择确认",
      "推荐动作：选择报价最低且履约风险可控的供应商",
      "请回复确认结果后继续 workflow。"
    ],
    "template": "orange",
    "open_id": "ou_xxx"
  }
}
```

## 输出

```json
{
  "receive_id_type": "open_id",
  "receive_id": "ou_xxx",
  "target_hint": "指定飞书用户",
  "message_id": "om_xxx"
}
```

## 使用规则

- 需要发送 IM 消息的 skill 必须显式调用 `im.send_card`，不要直接调用飞书 SDK。
- skill 负责决定“为什么发、发什么、等待什么结果”；`im.send_card` 只负责拼装卡片并发送。
- 高风险动作的确认结果不能只依赖“消息已发送”，必须由对应 workflow 记录 `waiting_human`、恢复条件和最终人工决策。
- 如果发送失败，skill 必须把失败作为阻断输出，不允许伪造“已通知”。
