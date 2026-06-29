# TRAE Work Runtime Specs

这里存放的是 **TRAE Work 在当前项目里的运行规范**，而不是项目代码中的 agent runtime。

从这次重构开始，`.trae/` 采用四层结构：

```text
.trae/
├── README.md
├── agents/       # 角色定义：每个 agent 的职责、边界、输入、输出
├── skills/       # 动作定义：检查、确认、归档、站点动作等可复用技能
├── tools/        # 底层执行工具契约：由 skill 显式调用的 cmd/runtime tools
├── workflows/    # 工作流定义：节点、边、状态、回流与收口规则
├── registry/     # agent / skill / tool 元数据目录：角色类型、适用范围、替代关系
├── policies/     # 全局一级选流规则；工作流内部规则写在 workflows/ 或入口 agent 中
```

## 当前原则

- `agents/` 只描述 **角色能力**，不直接等于一条完整流程。
- `skills/` 描述 **检查型、动作型、归档型、站点型** 的可复用技能。
- `tools/` 描述 **底层执行工具**，例如 IM 卡片发送；skill 必须显式调用 tool，不直接碰底层 SDK。
- `workflows/` 才是 **流程结构的唯一事实来源**，同时包含一级 workflow 和部门级 SOP workflow。
- `registry/` 负责把现有 agent、skill 和 tool 归类为不同层级，并记录 `replaced_by_skill` / tool 调用关系。
- `policies/` 只保留全局一级选流规则；guard、人工确认、恢复等规则归属于具体 workflow。
- 自我优化 loop 规则归属于 `self-optimization-agent` 与 `self_optimization_workflow`。
- TRAE Work 在执行任务时，应优先读取 `policies/orchestration-policy.md` 完成一级选流，再读取对应一级 workflow、部门 SOP workflow 与入口角色。

## 新的分层方式

### 全局编排层

- `ceo-orchestrator-agent`

这一层只负责：

- 识别任务属于哪条工作流
- 决定是否进入开发流、资讯流、电商流
- 决定是否进入自我优化流
- 处理暂停、恢复、升级与转流

### 工作流控制层 / 部门部长层

- `ecommerce-orchestrator-agent`
- `technology-minister-agent`
- `self-optimization-agent`
- 各部门 SOP 中声明的 `minister_role`

这一层负责进入一级流后的部门 SOP 编排。当前默认框架里，一级选流不直接跳到末端 worker，而是先进入对应 workflow 或部门 SOP 的部长角色。

### 工作流节点层

- 开发工作流节点：
  - `technology-minister-agent`
  - `backend-development-agent`
  - `frontend-development-agent`
  - `effect-qa-agent`
  - `function-qa-agent`
- 资讯工作流节点：
  - `news-digest-agent`
  - `weread-wechat-digest`（skill）
- 电商工作流节点：
  - `product-minister-agent`
  - `candidate-discovery-agent`
  - `supplier-lookup-agent`
  - `creative-strategy-agent`
  - `exception-order-agent`
- 归档工作流节点：
  - `process-archive-agent`
  - `workflow-archive-report`（skill）
- 自我优化工作流节点：
  - `self-optimization-agent`
  - `optimization-review-agent`

### 横切 skill 层

- `site-preflight-check`
- `site-session-recovery`
- `human-gate-approval`
- `workflow-archive-report`
- `catalog-import-check`
- `listing-readiness-check`
- `change-surface-audit`
- `latest-pattern-research`
- `workflow-log-publish`

这些 skill 可以被多个工作流复用，但它们不是全局编排层。

### 底层 tool 层

- `im.send_card`

这一层负责真实执行底层动作。需要发送 IM 消息的 skill 必须显式调用 `im.send_card`，不要直接调用飞书 SDK 或临时拼接口。

## 当前工作流清单

一级 workflow：

- `development_workflow`
- `news_workflow`
- `ecommerce_workflow`
- `self_optimization_workflow`

部门级 SOP workflow：

- `ceo_orchestration_workflow`
- `product_department_workflow`
- `supply_chain_department_workflow`
- `content_material_department_workflow`
- `customer_risk_department_workflow`
- `archive_department_workflow`

每条工作流的节点、边和成功条件，见 `workflows/` 下对应文件。

## 最重要的改动

- `technology-minister-agent` 已明确归入 `development_workflow`，不再视为全局共享节点。
- `business_workflow` 与历史业务编排角色已被移除，`development_workflow`、`news_workflow`、`ecommerce_workflow`、`self_optimization_workflow` 现在是同一级。
- `ceo-orchestrator-agent` 直接把任务选流到一级 workflow，不再先经过“业务总层”。
- `im-confirmation-agent`、`host-permission-guard-agent`、`external-login-recovery-agent`、`catalog-quality-agent`、`listing-readiness-agent` 已转为默认由 skill 承载。
- `news-digest-agent` 与 `process-archive-agent` 保留为部门部长角色，具体执行动作分别由 `weread-wechat-digest` 与 `workflow-archive-report` 承载。
- 新增 `self_optimization_workflow`，用于围绕宿主不满意点触发“诊断 -> 范式研究 -> 按需 handoff 开发流 -> review -> 继续 loop”的升级闭环。
- 自我优化工作流默认通过主动输入触发字眼启动，并要求每轮把宿主问题与改造结论通过接口同步到 web 日志面板。
- 现有 agent、skill 与 tool 由 `registry/agent-catalog.yaml`、`registry/skill-catalog.yaml` 和 `registry/tool-catalog.yaml` 统一归位。
