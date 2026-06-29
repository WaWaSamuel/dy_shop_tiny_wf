# 软上下文隔离策略

## 目标

在 workflow、agent 和 skill 之间建立轻量隔离层：上游保留完整执行现场，下游只接收压缩后的 `handoff_packet`；下游执行结束后只返回结构化 `result_packet`，由上一级继续判断、回流或收口。

## 核心规则

1. 所有 workflow handoff 必须使用 `handoff_packet`，不得直接转发完整聊天记录、完整日志、原始大文件内容、Cookie、Token、密钥或未脱敏外部数据。
2. `handoff_packet` 是压缩输入，不是全量上下文副本。它只保留任务摘要、已确认事实、必要约束、风险、阻断项、引用路径和返回契约。
3. 所有 workflow 执行结束、暂停、阻断、打回或完成时，必须输出 `result_packet` 给上一级 workflow 或调用方。
4. `result_packet` 是结果摘要，不得夹带下游完整推理链、完整运行日志或下游私有中间态；需要追溯时只传 `packet_refs`、文件路径、日志 ID 或 artifact ID。
5. 所有 workflow 的入口角色负责 packet 能力：接收并校验 `handoff_packet`、展开为本 workflow state、生成下游最小 `handoff_packet`、把终态压缩为 `result_packet`。
6. 普通执行节点只消费入口角色展开后的结构化字段；跨 workflow 传递必须回到入口角色或 workflow controller，不允许末端节点私自把全量上下文交给其他 workflow。
7. 软隔离允许下游按 `packet_refs` 主动读取必要事实来源，但必须只读取完成任务所需的最小范围，并在结果中记录引用。

## `handoff_packet` 契约

必填字段：

- `packet_id`
- `packet_type`: 固定为 `handoff_packet`
- `schema_version`
- `source_workflow`
- `source_node`
- `source_agent_or_skill`
- `target_workflow`
- `target_entry_role`
- `task_brief`
- `intent_fields`
- `accepted_facts`
- `constraints`
- `risk_flags`
- `blocked_items`
- `packet_refs`
- `return_contract`

可选字段：

- `parent_packet_id`
- `run_id`
- `workflow_edge`
- `artifact_refs`
- `decision_history`
- `privacy_omissions`
- `expected_result_fields`

## `result_packet` 契约

必填字段：

- `packet_id`
- `packet_type`: 固定为 `result_packet`
- `schema_version`
- `source_workflow`
- `source_node`
- `source_agent_or_skill`
- `target_workflow`
- `parent_packet_id`
- `status`: `completed` / `blocked` / `paused` / `cancelled` / `reroute_required` / `failed`
- `result_summary`
- `state_delta`
- `pass_flags`
- `node_completion_sources`
- `artifact_refs`
- `packet_refs`
- `next_recommendation`

可选字段：

- `review_required`
- `reroute_target`
- `blocked_reason`
- `residual_risks`
- `acceptance_evidence_refs`

## 入口角色职责

每个 workflow 的 `minister_role` 或 `workflow_controller` 必须承担以下职责：

- 校验 `handoff_packet.packet_type == "handoff_packet"`，缺失时把当前用户输入压缩成首个 `handoff_packet`。
- 校验 `target_workflow` 与当前 workflow 一致；不一致时输出 `result_packet.status = "reroute_required"`。
- 只把 `accepted_facts`、`intent_fields`、`constraints`、`packet_refs` 展开到本 workflow state。
- 生成给下游节点或子 workflow 的最小 `handoff_packet`。
- workflow 结束时生成 `result_packet`，并交回 `return_contract.parent_workflow` 或上一级入口角色。
- 对 `pass_flags` 和完成态写明 `node_completion_sources`，不得由上游代写下游通过态。

## 禁止项

- 禁止把完整 prompt、完整聊天历史、完整 debug 日志、完整浏览器快照或未压缩原始数据直接塞入 packet。
- 禁止在日志中记录完整 packet；日志只记录 `packet_id`、`packet_refs`、摘要和状态。
- 禁止下游 workflow 修改 `parent_packet_id` 或伪造上游来源。
- 禁止用自然语言“已完成”替代 `result_packet.status` 和 `node_completion_sources`。
