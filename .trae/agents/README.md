# TRAE Work Agents

这里存放的是 **TRAE Work 可复用的角色定义**，不是项目代码里的 agent runtime。

这次重构以后，`agents/` 不再承担“完整流程说明”的职责。它只负责回答三个问题：

- 这个 agent 是什么角色
- 它负责做什么，不负责做什么
- 它在工作流里通常作为哪一类节点被引用

同时需要注意：一部分原来以 agent 形式存在的能力，现在已经改由 `skills/` 承载。对应 agent 文件保留，但默认仅作为历史说明或迁移参考。

完整流程定义已经上移到：

- `../workflows/`：工作流节点、边、进入条件、回流规则
- `../registry/agent-catalog.yaml`：agent 角色类型与适用范围
- `../policies/orchestration-policy.md`：全局一级选流规则
- `../workflows/`：工作流内部的守门、人工确认、回流与收口规则

## 当前目录结构

```text
.trae/agents/
├── README.md
├── core/
│   └── ceo-orchestrator-agent.md
├── development/
│   ├── technology-minister-agent.md
│   ├── host-acceptance-agent.md
│   ├── host-acceptance-rubric.md
│   ├── senior-backend-engineer-agent.md
│   ├── frontend-engineer-agent.md
│   ├── effect-qa-minister-agent.md
│   └── function-qa-minister-agent.md
├── guard/
│   ├── site-preflight-legacy-agent.md
│   ├── site-session-recovery-legacy-agent.md
│   └── human-confirmation-legacy-agent.md
├── intelligence/
│   └── intelligence-minister-agent.md
├── ecommerce/
│   ├── ecommerce-minister-agent.md
│   ├── catalog-quality-legacy-agent.md
│   ├── product-minister-agent.md
│   ├── product-selection-agent.md
│   ├── supply-chain-minister-agent.md
│   ├── content-material-minister-agent.md
│   ├── listing-readiness-legacy-agent.md
│   ├── customer-risk-minister-agent.md
│   └── archive-minister-agent.md
└── optimization/
    ├── optimization-minister-agent.md
    └── optimization-review-agent.md
```

## 新的理解方式

### 1. `core/` 只保留全局入口

- `ceo-orchestrator-agent`：全局选流与转流

### 2. `development/` 是一条明确的工作流，不是松散的 agent 集合

`development_workflow` 的核心节点是：

1. `technology-minister-agent`
2. `backend-development-agent` / `frontend-development-agent`
3. `ui-ux-review-agent`
4. `regression-validation-agent`
5. `host-acceptance-agent` 做最终宿主验收

最重要的规则是：

- `technology-minister-agent` 明确属于 `development_workflow`
- 它是开发流里的入口评估与分派节点
- `host-acceptance-agent` 是最终宿主验收节点
- 它不是业务流和资讯流的共享入口

### 3. 一部分横切能力已改为 skill 承载

以下能力现在优先由 skill 承载：

- `site-preflight-check`
- `site-session-recovery`
- `human-gate-approval`
- `workflow-archive-report`
- `catalog-import-check`
- `listing-readiness-check`

对应 agent 文件继续保留在：

- `guard/`
- `ecommerce/`

但它们不再是默认执行路径。

例外：`news-digest-agent` 是情报部部长角色，负责 `news_workflow` 的编排；`process-archive-agent` 是经营档案 / 复盘部部长角色，负责归档口径。它们不直接执行采集或报告生成，具体动作分别由 `weread-wechat-digest` 与 `workflow-archive-report` 承载。

### 4. `ecommerce/` 是电商工作流的节点族

`ecommerce-orchestrator-agent` 现在应理解为：

- 电商工作流 controller
- 只在 `ecommerce_workflow` 内部判断阶段和下一跳
- 不承担全局编排

### 5. `optimization/` 是自我优化工作流的节点族

- `self-optimization-agent`：自我优化工作流入口编排角色，围绕宿主不满意点发起诊断、研究、改造与继续 loop
- `optimization-review-agent`：围绕评分卡判定通过 / 不通过，并决定是否继续 loop

## 当前推荐使用方式

### 先选工作流

由 `ceo-orchestrator-agent` 根据任务类型选择：

- `development_workflow`
- `news_workflow`
- `ecommerce_workflow`
- `self_optimization_workflow`

### 再按工作流调用 agent

一旦进入某条 workflow，节点顺序和回流规则以 `workflows/*.yaml` 为准，不再由单个 agent 自由定义整条链路。

### 最后由横切节点收口

跨多个工作流共享的默认 skill 主要是：

- `site-preflight-check`
- `site-session-recovery`
- `human-gate-approval`
- `workflow-archive-report`

## 相关文件

- 顶层说明：`../README.md`
- agent 目录：`../registry/agent-catalog.yaml`
- 工作流定义：`../workflows/`
- 编排策略：`../policies/orchestration-policy.md`
