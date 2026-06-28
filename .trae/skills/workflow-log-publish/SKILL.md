---
name: "workflow-log-publish"
description: "将宿主问题、阶段结论、review 评分和改造结果写成结构化日志，通过接口同步到 web 展示台的日志面板。"
---

# Workflow Log Publish

这个 Skill 用于把一条 workflow 的关键阶段结果写成结构化日志，并通过接口同步到 web 展示台的日志面板。

它和 `workflow-archive-report` 的区别是：

- `workflow-log-publish` 负责 **每轮过程日志**
- `workflow-archive-report` 负责 **最终收口归档**

## 适用场景

- 自我优化工作流中的宿主反馈入场日志
- 每轮改造后的 review 结论日志
- 需要把阶段结果实时展示到 web 日志面板时

## 输入

- workflow 标识
- run 标识
- loop 轮次
- 日志阶段：`intake / review / final`
- 宿主问题
- 改造摘要
- review 评分卡
- 当前结论
- 关联产物链接

## 输出

- 日志写入结果
- log_id
- web 展示面板可读摘要
- 接口提交状态

## 接口契约

默认通过以下接口把日志同步到 web 展示台：

- `POST /api/v1/runtime/logs`
- `GET /api/v1/runtime/logs?workflow_id=self_optimization_workflow`

单条日志建议至少包含：

- `workflow_id`
- `run_id`
- `loop_round`
- `phase`
- `host_issue`
- `summary`
- `review_scorecard`
- `decision`
- `artifacts`
- `created_at`

## 规则

- intake 阶段必须至少记录宿主问题与优化目标
- review 阶段必须至少记录评分卡、通过 / 不通过结论和下一轮重点
- final 阶段必须记录最终结论与归档链接
- 不允许只写“已处理”，必须写清楚问题与结论
