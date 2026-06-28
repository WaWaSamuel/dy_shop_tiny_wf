---
name: "human-gate-approval"
description: "暂停当前工作流，生成结构化确认事项，等待人工选择继续、暂缓、取消或换方案。"
---

# Human Gate Approval

这个 Skill 用于承载原来 `im-confirmation-agent` 负责的动作型能力。

它不是业务判断 agent，而是一个显式的 **human-in-the-loop runtime step**。

## 适用场景

- 候选品需要人工拍板
- 供应商选择需要人工确认
- 上架前需要最终确认
- 异常订单需要人工决定处理方式
- 资讯链需要发送登录提醒或确认是否继续重试

## 输入

- 当前工作对象
- 上游结论
- 风险点
- 备选项
- 推荐选项

## 输出

- 待确认事项
- 选项说明
- 推荐动作
- 暂停状态：`waiting_human`
- 恢复条件

## 显式调用 tool

当本 skill 需要把确认事项发送给宿主时，必须调用 cmd/runtime tool：

- tool：`im.send_card`
- 契约文件：`.trae/tools/im-send-card/TOOL.md`
- 后端入口：`POST /api/v1/tools/invoke`

调用示例：

```json
{
  "name": "im.send_card",
  "args": {
    "title": "人工确认待处理",
    "lines": [
      "事项：<当前需要确认的业务事项>",
      "风险：<关键风险点>",
      "推荐：<推荐动作>",
      "选项：继续 / 暂缓 / 取消 / 换方案"
    ],
    "template": "orange",
    "open_id": "<宿主飞书 open_id，可选>"
  }
}
```

调用成功只代表“消息已发送”，不代表“人工已确认”。本 skill 必须继续输出 `waiting_human`，并把恢复条件写入工作流状态。

## 规则

- 只负责把事项整理清楚，不替用户做决定
- “已提醒”不等于“已确认”
- 决策结果必须进入工作流状态和归档记录
