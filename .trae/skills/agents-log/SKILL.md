---
name: "agents-log"
description: "Records agent jump and handoff logs into the runtime database. Invoke whenever an agent jump, reroute, or workflow handoff happens."
---

# Agents Log

这个 Skill 用于把 agent 之间的“跳转 / 转交 / 改路由”记录成结构化日志，并通过 `agents.log` cmd tool 离线写入本地 JSONL。后端激活时可以从本地日志加载一次，用于数据库展示和复盘。

它的目标是让一人公司能追踪“任务为什么从 A 跳到 B、依据是什么、保留了哪些上下文”，避免工作流跳转只散落在聊天里。

## 适用场景

- `ceo-orchestrator-agent` 完成一级选流并跳到某个 workflow 入口角色时。
- 某个 workflow 明确 handoff 到另一个一级 workflow 时。
- 因 policy、guard、review、回归失败或人工确认结果触发 reroute 时。
- 自我优化流把开发需求 handoff 给 `development_workflow` 时。

## 显式调用 tool

当出现上述跳转行为时，必须显式调用已登记 tool：

- tool ID：`agents.log`
- 调用入口：`python3 .trae/tools/agents-log/agents_log.py --payload '<json>'`
- 实现位置：`.trae/tools/agents-log/agents_log.py`
- 离线存储：`.trae/runtime/agents-log.jsonl`
- 后端加载：后端启动时可从本地 JSONL 加载到 `runtime_execution_records`

示例：

```bash
python3 .trae/tools/agents-log/agents_log.py --payload '{
  "event_type": "jump",
  "from_agent": "ceo-orchestrator-agent",
  "to_agent": "technology-minister-agent",
  "from_workflow": "ceo_orchestration_workflow",
  "to_workflow": "development_workflow",
  "trigger": "用户提出页面改造任务",
  "reason": "命中 orchestration-policy 中 development_workflow 规则",
  "handoff_summary": "进入开发工作流，由 technology-minister-agent 做入口评估。",
  "run_id": "可选；未传由 tool 生成"
}'
```

## 输入

- `event_type`：默认 `jump`，也可记录 `handoff`、`reroute`。
- `from_agent`：发起跳转的 agent，必填。
- `to_agent`：目标 agent，必填。
- `from_workflow`：来源 workflow，可选。
- `to_workflow`：目标 workflow，可选。
- `trigger`：触发跳转的用户输入、系统状态或 workflow 结论。
- `reason`：跳转依据，必须引用 policy、workflow edge、guard 结果或 review 结论。
- `handoff_summary`：交给目标 agent 的上下文摘要。
- `run_id`：可选，同一轮任务应尽量复用同一个 run_id。
- `metadata`：可选，补充结构化上下文。

## 输出

- `local_log_id`：本地日志 ID。
- `run_id`：本次日志所属 run。
- `created_at`：写入时间。
- `log_path`：本地 JSONL 路径。

## 规则

- “消息已说明”不等于“日志已写入”；出现跳转行为时必须调用 `agents.log`。
- `reason` 不允许只写“按规则跳转”，必须写清楚依据来自哪里。
- 如果 `agents.log` 写入失败，应在当前 handoff 包里记录日志失败状态；不允许伪造“已记录”。
- 后端不可用时不能跳过日志记录；应先写本地 JSONL，等待后端恢复后加载。
- 该 Skill 只负责 agent 跳转日志，不替代 `workflow-log-publish` 的阶段日志，也不替代 `workflow-archive-report` 的最终归档。
