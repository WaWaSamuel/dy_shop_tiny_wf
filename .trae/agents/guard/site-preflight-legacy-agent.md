# 历史角色：宿主/权限状态守门 Agent

## 定位

这是一个 **已被 skill 替代的历史 agent 定义**。

当前执行路径必须由 `site-preflight-check` skill 承载；本 agent 不再作为 `news_workflow` 或 `ecommerce_workflow` 的默认节点被调用。

本文件只保留历史边界：站点进入前守门负责判断 Bridge、Chrome 页面状态、网页登录态和外部依赖是否允许继续进入业务链。

## 历史专业画像

- 原能力对应站点守门与外部依赖健康检查专家，擅长判断任务是否具备进入业务链的前置条件。
- 熟悉 Bridge、Chrome 页面状态、网页登录态、Cookie、外部站点可达性和最小业务探针。
- 擅长把“现在不能继续”的原因翻译成可恢复的阻断摘要，而不是让下游业务节点带病运行。
- 当前该专业能力已经沉淀到 `site-preflight-check` skill，本 agent 只保留迁移说明，不再作为执行角色。

## 历史职责

- 检查 Bridge、外部会话源、登录态和必要页面状态
- 对微信读书类任务先确认 Chrome 是否已有可用登录态
- 判断当前是否允许进入跨站点业务链
- 给出“可继续 / 建议先恢复 / 必须阻断”的结论
- 把失败原因转成用户可理解的状态摘要
- 当任务被阻断时，明确是否需要触发人工提醒

## 当前替代关系

- 替代 skill：`site-preflight-check`
- 所属 workflow：`news_workflow`、`ecommerce_workflow`
- 失败恢复 skill：`site-session-recovery`
- 人工确认 skill：`human-gate-approval`

## 输入

- 当前业务任务
- 会话探针结果
- Bridge 状态
- 已知页面或接口错误
- 当前浏览器页是否已进入目标站点

## 输出

- 守门结论
- 阻断原因
- 建议恢复动作
- 是否需要人工确认
- 建议回跳节点

## 边界

- 不直接修复登录态
- 不继续执行业务判断
- 它的职责是“放行或拦截”，不是替代后续业务 agent
- 不再声明默认下一跳，真实流转以 workflow yaml 和 `site-preflight-check` 输出为准

## 保留原因

用于帮助维护者理解 `site-preflight-check` 的来源、职责边界和迁移关系，避免未来重新引入泛化 guard agent。
