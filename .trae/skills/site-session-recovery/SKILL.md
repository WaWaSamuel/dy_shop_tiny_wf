---
name: "site-session-recovery"
description: "针对站点登录态、Cookie、会话失效等问题，生成恢复动作和复测条件。"
---

# Site Session Recovery

这个 Skill 用于替代 `external-login-recovery-agent` 默认执行职责。

它把“恢复说明、人工动作、复测条件”收敛成稳定动作，不再继续让一个泛 recovery agent 占据默认链路。

## 适用场景

- 微信读书未登录
- Cookie 失效
- 页面跳回登录页
- Session 过期

## 输入

- 站点标识
- 阻断原因
- 当前页面状态
- 会话异常信息

## 输出

- 恢复步骤
- 需要人工完成的动作
- 复测条件
- 建议回跳节点

## 显式调用 tool

当会话恢复需要通知宿主完成登录、扫码、Cookie 同步或手动恢复动作时，必须调用 cmd/runtime tool：

- tool：`im.send_card`
- 契约文件：`.trae/tools/im-send-card/TOOL.md`
- 后端入口：`POST /api/v1/tools/invoke`

调用示例：

```json
{
  "name": "im.send_card",
  "args": {
    "title": "站点会话需要恢复",
    "lines": [
      "站点：<站点名称>",
      "阻断原因：<登录态失效 / Cookie 过期 / 页面回退登录页>",
      "请完成恢复动作后，回到 preflight 节点重新检查。",
      "复测条件：<明确的复测条件>"
    ],
    "template": "orange",
    "open_id": "<宿主飞书 open_id，可选>"
  }
}
```

发送成功不等于恢复成功。恢复完成后必须回到 `site-preflight-check` 重新检查。

## 规则

- 不直接推进业务链
- 恢复完成后应回到 preflight 重新检查
- 如果用户放弃恢复，应交给归档 skill 收口
