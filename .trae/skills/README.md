# TRAE Work Skills

这里存放的是 **比 agent 更适合模板化、检查型、工具型、可复用动作型** 的能力定义。

当前判断标准：

- 需要策略判断、开放式权衡、对不完全信息做解释：优先用 `agent`
- 输入输出稳定、工具调用强、动作边界清晰、可反复复用：优先用 `skill`
- 真实执行底层动作（发送 IM、调用 SDK、跑命令、访问底层 API）：归入 `tools/`，由 skill 显式调用

## 当前 skills

- `weread-wechat-digest`
  - 微信读书公众号文章采集与摘要
- `human-gate-approval`
  - 通用人工确认与等待决策
- `workflow-archive-report`
  - 统一归档、汇总与可视化收口
- `site-preflight-check`
  - 站点登录态 / Bridge / 页面前置检查
- `site-session-recovery`
  - 站点会话恢复与复测条件说明
- `catalog-import-check`
  - 货盘导入质量检查
- `listing-readiness-check`
  - 上架准备度检查
- `change-surface-audit`
  - 扫描 prompt、workflow、skill、代码、接口与展示层的影响面
- `latest-pattern-research`
  - 围绕当前问题联网研究最新范式与可落地建议
- `workflow-log-publish`
  - 将宿主问题与阶段结论通过接口同步到 web 日志面板

## 当前约定

- workflow 节点若主要承担“检查、确认、归档、恢复、固定站点动作”，应优先引用 skill
- 自我优化 loop 中的“影响面扫描”和“最新范式研究”默认优先由 skill 承载
- 自我优化 loop 中的“阶段日志同步到 web”默认优先由 skill 承载
- 被 skill 替代的 agent 文件保留在 `agents/` 中，但应标记为 `legacy` 或 `replaced_by_skill`
- 若某能力需要“部长角色 + 工具执行”两层表达，agent 保留为 active 角色，skill 只作为工具能力，不写 `replaces_agents`
- `registry/` 同时维护 agent catalog、skill catalog 与 tool catalog，避免 workflow / skill 继续默认引用旧能力
- 需要发送 IM 消息的 skill 必须显式调用 `im.send_card`，不要直接调用飞书 SDK
