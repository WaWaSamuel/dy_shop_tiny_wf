---
name: "workflow-archive-report"
description: "统一整理工作流结果、产物、决策和终态，输出归档记录或可视化收口结果。"
---

# Workflow Archive Report

这个 Skill 用于执行 `process-archive-agent` 定义好的归档动作。

它的职责是把一条 workflow 的终态沉淀成结构化资产，而不是继续参与业务判断。

## 适用场景

- workflow 正常完成
- workflow 暂停
- workflow 被人工取消
- workflow 因守门失败或登录问题被阻断
- 自我优化 loop 达到通过、未解决收口或轮次耗尽
- workflow 需要生成可回看的摘要与产物索引

## 输入

- workflow 标识
- run 状态
- 节点结果
- 关键 artifact
- 人工决策
- 终止原因或完成原因

## 输出

- 归档摘要
- 产物索引
- 最终状态
- 可视化报告材料

## 规则

- 不重跑业务动作
- 不引入新判断链路
- 所有暂停、取消、失败、完成都应有统一归档结构
