---
name: "change-surface-audit"
description: "根据宿主反馈扫描提示词、workflow、skill、代码、接口和展示层的影响面，输出必须检查与必须改动的范围。"
---

# Change Surface Audit

这个 Skill 用于承载“优化前先扫清影响面”的固定动作。

自我优化最容易犯的错误，是只盯着当前看到的一个点去改，结果 prompt、workflow、skill、代码、接口、web 展示之间没有一起收口。这个 Skill 的目的就是把必须检查、必须同步、可延后处理的范围先梳理清楚。

## 适用场景

- 宿主提出系统级不满意点时
- 问题可能横跨 `.trae`、prompt、workflow、skill、代码与 web
- 进入自我优化 loop 的每一轮开始前

## 输入

- 宿主不满意点
- 当前行为表现
- 现有系统结构
- 历史 review 打回意见

## 输出

- 影响面清单
- 高概率根因区域
- 必须同步修改的文件 / 模块类别
- 可延后处理项

## 规则

- 优先输出结构化范围，不直接输出完整解决方案
- 必须显式区分 `必须改`、`建议改`、`可暂缓`
- 需要覆盖 prompt、workflow、skill、agent、代码、接口、web 展示这些面
