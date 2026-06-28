---
name: "site-preflight-check"
description: "在进入站点型工作流前，检查登录态、Bridge、页面状态与外部依赖是否可用。"
---

# Site Preflight Check

这个 Skill 用于替代泛化的 `host-permission-guard-agent` 默认执行职责。

它适合承载“检查型、前置型、站点状态型”动作，而不是继续维持一个泛 guard agent 来做所有站点判断。

## 适用场景

- 进入微信读书之前检查会话
- 进入电商外部站点之前检查依赖
- 判断当前页面是否掉回登录页
- 判断 Bridge 是否可用

## 输入

- 目标站点
- 当前浏览器状态
- 会话探针结果
- Bridge 状态
- 工作流上下文

## 输出

- 守门结论：`passed / blocked / recoverable`
- 阻断原因
- 推荐恢复动作
- 是否允许继续进入下一个 workflow 节点

## 规则

- 只做放行、阻断、可恢复判断
- 不替代后续业务推理
- 若检测到会话异常，应把下一跳交给 `site-session-recovery`
