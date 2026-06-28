# Workflow Specs

这里存放当前项目的工作流定义文件。

## 当前原则

- workflow 是流程结构的唯一事实来源
- 节点可以引用 `agent`，也可以直接引用 `skill`
- 检查型、动作型、归档型、站点型节点，优先引用 `skill`
- 判断型、策略型、解释型节点，优先引用 `agent`
- 底层执行动作由 skill 显式调用 `tools/` 中登记的 tool，不建议 workflow 直接引用底层 tool

## 文件说明

### 一级 workflow

- `development-workflow.yaml`
  - 开发工作流
  - 明确 `technology-minister-agent` 是开发流内的起点评估节点，`host-acceptance-agent` 是最终宿主验收节点
- `news-workflow.yaml`
  - 资讯摘要工作流
  - 强制守门、恢复、摘要、归档
- `ecommerce-workflow.yaml`
  - 电商工作流
  - 覆盖质检、候选、比价、素材、上架、异常、归档
- `self-optimization-workflow.yaml`
  - 自我优化工作流
  - 覆盖宿主反馈、问题定位、最新范式研究、升级改造、review 评分与继续 loop

### 部门级 SOP workflow

- `ceo-orchestration-workflow.yaml`
  - CEO / 总经理分流工作流
- `product-department-workflow.yaml`
  - 电商商品部工作流
- `supply-chain-department-workflow.yaml`
  - 电商供应链部工作流
- `content-material-department-workflow.yaml`
  - 电商内容与素材部工作流
- `customer-risk-department-workflow.yaml`
  - 电商客服风控部工作流
- `function-qa-workflow.yaml`
  - 技术开发部门功能 QA 工作流
- `effect-qa-workflow.yaml`
  - 技术开发部门效果 QA 工作流
- `archive-department-workflow.yaml`
  - 经营档案 / 复盘部工作流

## 当前层级

一级 workflow：

- `development_workflow`
- `news_workflow`
- `ecommerce_workflow`
- `self_optimization_workflow`

部门级 SOP workflow 不参与全局第一跳选流，而是在一级 workflow 内部作为部门 SOP 被调用。全局第一跳仍只进入上述四条一级 workflow。

## 使用原则

- 工作流文件是流程结构的唯一事实来源
- agent 文件只描述角色，不再单独承担完整流程定义
- skill 文件承载固定动作、检查与归档能力
- tool 文件承载底层执行契约，例如 `im.send_card`
- 每条工作流都应包含：
  - 进入条件
  - 共享状态
  - 节点
  - 边
  - 成功条件
  - 失败与回流策略
