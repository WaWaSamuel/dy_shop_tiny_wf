# agents.log

`agents.log` 是项目内统一的 agent 跳转日志 cmd tool。

它负责把上游 agent 或 `agents-log` skill 产出的结构化跳转信息离线写入本地 JSONL 文件。后端激活时可以从该本地文件加载一次，用于运行记录中心、展示台或复盘。

## 定位

- 类型：cmd tool
- 调用名：`agents.log`
- 命令入口：`python3 .trae/tools/agents-log/agents_log.py --payload '<json>'`
- 实现位置：`.trae/tools/agents-log/agents_log.py`
- 本地存储：`.trae/runtime/agents-log.jsonl`
- 后端加载：后端启动时可从本地 JSONL 加载到 `runtime_execution_records`

## 输入

```json
{
  "event_type": "jump",
  "from_agent": "ceo-orchestrator-agent",
  "to_agent": "technology-minister-agent",
  "from_workflow": "ceo_orchestration_workflow",
  "to_workflow": "development_workflow",
  "trigger": "用户提出页面改造任务",
  "reason": "命中 orchestration-policy 中 development_workflow 规则",
  "handoff_summary": "进入开发工作流，由 technology-minister-agent 做入口评估。",
  "run_id": "可选，同一轮任务可复用",
  "metadata": {}
}
```

字段规则：

- `from_agent` 必填，表示发起跳转的 agent。
- `to_agent` 必填，表示目标 agent。
- `event_type` 可选，默认 `jump`，允许 `jump`、`handoff`、`reroute`。
- `from_workflow`、`to_workflow` 可选，但跨 workflow 转交时必须填写。
- `reason` 必填，必须说明跳转依据。
- `trigger` 和 `handoff_summary` 建议填写，用于复盘。
- `run_id` 可选，未传时 tool 自动生成。
- `metadata` 可选，只能放结构化补充信息，不放密钥、Cookie 或隐私凭证。
- tool 会自动补充 `local_log_id`、`created_at`、`schema_version`。

## 调用方式

```bash
python3 .trae/tools/agents-log/agents_log.py --payload '{
  "event_type": "jump",
  "from_agent": "ceo-orchestrator-agent",
  "to_agent": "news-digest-agent",
  "from_workflow": "ceo_orchestration_workflow",
  "to_workflow": "news_workflow",
  "trigger": "用户要求整理微信读书公众号摘要",
  "reason": "命中 orchestration-policy 中 news_workflow 规则",
  "handoff_summary": "进入情报部工作流，由 news-digest-agent 规划守门与摘要执行。"
}'
```

## 输出

```json
{
  "ok": true,
  "log_path": "/Users/bytedance/StickerProductive/DYShop/.trae/runtime/agents-log.jsonl",
  "local_log_id": "uuid",
  "run_id": "agents-log:uuid",
  "created_at": "2026-06-28T12:00:00+00:00",
  "from_agent": "ceo-orchestrator-agent",
  "to_agent": "news-digest-agent",
  "event_type": "jump"
}
```

## 使用规则

- 出现 agent 跳转、workflow handoff 或 reroute 时，上游 skill / agent 必须显式调用 `agents.log`。
- `agents.log` 只负责写本地 JSONL，不负责决定是否允许跳转。
- 本地写入成功不等于目标 agent 已执行完成，只代表跳转事实和依据已被记录到离线日志。
- 写入失败必须作为日志阻断信息暴露给上游，不允许伪造已记录结果。
- 后端不可用时仍应写本地日志；后端恢复后从 `.trae/runtime/agents-log.jsonl` 加载。
