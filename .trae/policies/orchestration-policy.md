# 编排策略

## 目标

把“选哪条工作流”和“工作流里怎么流转”拆开，避免单个 agent 同时承担全局编排、局部分流和具体执行。

## 总原则

1. 全局只保留少量 orchestrator
   - `ceo-orchestrator-agent`

2. 工作流 controller 不等于全局 orchestrator
   - `ecommerce-orchestrator-agent` 是 `ecommerce_workflow` 的 controller

3. 工作流结构优先于 agent 直觉
   - 先看 `workflows/*.yaml`
   - 再决定调用对应节点 agent 或 skill
   - 不允许由单个 agent 自由定义整条链路
   - 一级选流只进入 `development_workflow` / `news_workflow` / `ecommerce_workflow` / `self_optimization_workflow`
   - 部门级 workflow 是一级流内部的二级 SOP，不作为全局第一跳
   - 一级 workflow 被选中后，必须立刻读取该 workflow yaml，并按 `workflow_controller` / `minister_role` / 起始节点加载入口 agent 或 skill
   - 二级及以下 workflow 必须以独立 workflow handoff 进入；不允许把子 workflow 的 `minister_role` 伪装成父 workflow 的普通节点直接执行
   - 不允许只输出“属于某 workflow”后跳过入口角色直接执行
   - 跨 workflow 或跨 agent handoff 必须遵守 `.trae/policies/context-isolation-policy.md`，上游只传压缩 `handoff_packet`，下游只回传结构化 `result_packet`
   - 所有跨 workflow、父子 workflow handoff 和 result 回流，都必须调用 `agents-log` 留痕；不能只在聊天里显示 `【流转留痕】`

4. `technology-minister-agent` 明确属于开发工作流
   - 它是 `development_workflow` 的起点评估节点
   - 它不是业务主链和资讯链的共享入口

## 一级选流后的强制入口动作

`ceo-orchestrator-agent` 只完成一级选流，不承担流内阶段判断。选中一级 workflow 后，下一步必须进入该 workflow 的入口角色：

固定执行顺序如下：

1. 静默读取 `AGENTS.md`。
2. 读取 `.trae/policies/orchestration-policy.md`。
3. 读取 `.trae/policies/context-isolation-policy.md`。
4. 选择唯一一级 workflow。
5. 读取目标 workflow yaml。
6. 从 workflow 的 `workflow_controller`、`minister_role` 或起始节点确认入口角色。
7. 通过 registry 找到并读取入口角色文件。
8. 生成或接收压缩 `handoff_packet`，再交给入口角色继续处理。

- `development_workflow` → 读取 `workflows/development-workflow.yaml`，加载 `technology-minister-agent`
- `news_workflow` → 读取 `workflows/news-workflow.yaml`，加载 `news-digest-agent`
- `ecommerce_workflow` → 读取 `workflows/ecommerce-workflow.yaml`，加载 `ecommerce-orchestrator-agent`
- `self_optimization_workflow` → 读取 `workflows/self-optimization-workflow.yaml`，加载 `self-optimization-agent`

可见流转说明只写极简 `【流转留痕】`：`动作`、`依据`、`上下文`、`边界`。已选 workflow、已读取 workflow yaml、已加载入口角色、下一跳入口等细节必须进入内部 packet / workflow state / 日志。如果缺少入口角色加载，本次分流未完成。

进入入口角色前，必须生成或接收符合 `context-isolation-policy.md` 的 `handoff_packet`。入口角色只能消费该 packet 中的结构化字段、引用和约束；workflow 结束后必须返回 `result_packet` 给上一级，供上一级继续判断、回流或收口。

父 workflow 进入二级或以下 workflow 时，必须把 `target_workflow` 明确写成目标子 workflow ID，并先完成 handoff 日志记录。子 workflow 返回时，也必须把结果压缩为 `result_packet`，并记录 result 回流日志。

## 选流规则

### `entry_rules` 写法约定

所有 workflow 的 `entry_rules` 不应只写成关键词命中列表。统一采用三段式：

```yaml
entry_rules:
  semantic_intent:
    allowed: true
    classifier_agent: <workflow入口agent>
    output_required:
      - intent_type
      - workflow_match
      - routing_confidence
      - hard_exclusion_hit
    rule: <允许 LLM 做语义分类，但必须结构化输出>
  hard_triggers:
    - rule: <强触发条件>
      route: <target_workflow>
  hard_exclusions:
    - rule: <强排除条件>
      route: <fallback_workflow>
```

解释：

- `semantic_intent` 是入口角色的语义分类契约，不是自由发挥许可。
- `hard_triggers` 是可审计的兜底触发条件。
- `hard_exclusions` 优先级高于普通语义命中，用来避免误入错误 workflow。
- LLM 可以理解“用户到底想干什么”，但必须输出 `intent_type`、`workflow_match`、`routing_confidence`、`hard_exclusion_hit` 等结构化字段。
- workflow edge、guard 和后续节点只能消费这些结构化字段与硬规则，不得消费“我感觉应该走某流”这类自然语言解释。

### 进入 `development_workflow`

当任务主要涉及：

- 新增 Web 页面、导航入口、可视化面板、管理台或展示台能力
- 使用前端技术实现功能，例如 React、ReactFlow、Ant Design、Vite、TypeScript、图表、节点图、交互页面
- 页面改造
- 页面视觉错乱、CSS、布局、遮挡、图片或文字重叠、路由页面展示异常、浏览器可见 UI bug
- 接口改造
- 页面 / 接口 / 功能异常、bug、报错、问题排查或技术归因
- 数据读取接口、聚合接口、展示接口或前后端联调
- 联调
- 回归
- 测评
- 上线前功能确认

即使任务内容提到 `.trae`、agent、workflow、skill、tool、registry、编排关系等系统资产，只要用户目标是“在 Web 上新增 / 修改 / 查看 / 可视化一个功能或入口”，一级选流仍应优先进入 `development_workflow`。

典型例子：

- “我想要一个可视化查看当前 `.trae` 下所有 agent、workflow、skill、tool 编排情况的工具，在 Web 上增加入口，用 ReactFlow 实现节点 graph。”
  - 一级选流：`development_workflow`
  - 理由：用户目标是新增 Web 可视化功能，`.trae` 只是该功能读取和展示的数据来源。

### 进入 `news_workflow`

当任务主要涉及：

- 微信读书
- 公众号文章
- 热点摘要
- 日报整理

### 进入 `ecommerce_workflow`

当任务主要涉及：

- 货盘
- 选品
- 比价
- 素材
- 上架
- 异常订单

### 进入 `self_optimization_workflow`

当任务主要涉及：

- 宿主明确指出当前方案不满意
- 需要继续优化、升级、重构
- 需要围绕最新热点范式重新设计
- 需要同时改 prompt、workflow、skill、代码或接口
- 触发语通常来自宿主主动输入，例如：`不满意`、`有问题`、`再优化`、`继续改`、`优化一下`、`重构一下`
- 宿主在描述“痛点”“体验问题”“为什么没按预期工作”“为什么没有按规则执行”这类系统性不满意点
- 宿主指出 registry、workflow、agent、skill、tool、prompt 的定义、规则执行、闭环或展示源与真实定义不一致，例如“角色不存在但仍展示”“刷新没用”“旧 ID 还在”“registry 和页面读取源不一致”“编排资产不准”

注意：用户描述“想要一个新功能 / 页面 / 工具 / 入口 / 可视化面板”，不自动等同于自我优化。只有当用户明确表达对现有系统行为、路由结果、规则执行、角色边界、闭环质量或方案效果不满意时，才按自我优化入口处理。

注意：用户只反馈 Web 页面视觉错乱、CSS、布局、遮挡、图片或文字重叠、路由页面展示异常、浏览器可见 UI bug 时，默认进入 `development_workflow`，不得直接进入自优化影响面审计。

### `self_optimization_workflow` 优先级

- 只要宿主表达的是“痛点 / 不满意 / 路由错误 / 闭环没走完 / 没按规则执行”，即使话里同时包含明确开发目标，也必须优先进入 `self_optimization_workflow`
- 不允许因为任务里出现“做一个页面”“补一个接口”“加一个功能”这类开发措辞，就提前把任务直接落到 `development_workflow`
- `self_optimization_workflow` 的职责不是替代开发，而是先约束问题定义、影响面、loop 与 review，再决定是否 handoff 给 `development_workflow`
- 若后续判断确实需要改代码，必须先进入 `self_optimization_workflow` 做问题定义与约束收紧，再 handoff 开发流
- 反过来，如果用户只是提出新的产品功能，且没有表达系统性不满意或路由失败，则不得因为任务提到 `.trae`、agent、workflow、skill、tool、prompt 或编排资产就误入 `self_optimization_workflow`

### 开发需求与自我优化的裁决边界

- “我要新增 / 修改 / 实现一个 Web 功能、页面入口、可视化工具、接口或联调能力” → `development_workflow`
- “页面视觉错乱、CSS 样式坏了、布局遮挡、图片或文字重叠、路由页面打开异常、浏览器里看起来不对” → `development_workflow`
- “为什么没有按规则走、为什么没进正确部门、这个机制不合理、这个职责边界有问题、我对当前方案不满意” → `self_optimization_workflow`
- “为什么还展示不存在的 agent / workflow / skill / tool，刷新也没用，registry / workflow / agent / skill / tool 与展示源不一致” → `self_optimization_workflow`
- “帮我优化刚才那个 Web 功能的体验 / 页面 / 交互” → 通常是 `development_workflow`，除非用户明确上升为系统性规则、workflow、agent、skill、tool 或闭环问题
- “帮我优化 agent / workflow / skill / tool 的职责、规则、分流、提示词或组织结构” → `self_optimization_workflow`
- “读取 `.trae` 配置并在 Web 上展示、搜索、可视化、分析” → `development_workflow`

## 工作流内部路由规则归属

本 policy 只负责全局一级选流与跨 workflow 进入规则，不承载工作流内部 SOP。

- 开发流内部 evaluation / frontend / backend / UI/UX review / regression / recheck 闭环，见 `workflows/development-workflow.yaml` 与 `agents/development/*`。
- 资讯流内部守门、恢复、摘要、人工确认和归档，见 `workflows/news-workflow.yaml`。
- 电商流内部守门、货盘质检、候选、供应链、素材、上架准备、异常订单和人工确认，见 `workflows/ecommerce-workflow.yaml` 及部门 SOP。
- 自我优化 loop 的 intake、影响面扫描、最新范式、handoff、review 和继续 loop，见 `workflows/self-optimization-workflow.yaml` 与 `agents/optimization/optimization-minister-agent.md`。
- 二级及以下 workflow 的入口规则、回流规则和局部日志节点，以对应 workflow yaml 为准；父 workflow 只负责 handoff，不直接代替子 workflow 入口角色执行。

任何 agent 不允许把本 policy 当作跳过 workflow yaml 的依据；进入一级 workflow 后，必须按对应 workflow 的节点与边继续推进。

## 软上下文隔离归属

软上下文隔离的字段、压缩规则、禁止项和入口角色职责，以 `.trae/policies/context-isolation-policy.md` 为唯一事实来源。

- workflow yaml 只声明自身 `context_policy`、入口职责和 state 字段，不复写完整 packet 字段解释。
- 入口角色负责把 `handoff_packet` 展开成本 workflow 可消费 state，并在结束时压缩为 `result_packet`。
- 上一级 workflow 只能根据 `result_packet.status`、`state_delta`、`pass_flags`、`node_completion_sources`、`next_recommendation` 和 `packet_refs` 继续判断。
- 日志系统只记录 packet 引用和摘要，不记录完整 packet。

## 何时允许 LLM 路由

允许 LLM 做“语义分类”，但不允许做不可审计的自由路由。

允许范围：

- 一级选流时，`ceo-orchestrator-agent` 可以把用户意图分类成结构化字段，再由 policy 和 workflow 契约裁决。
- 进入 workflow 后，入口角色可以根据 `entry_rules.semantic_intent.output_required` 产出结构化 intent 字段。
- 工作流内部的局部分流，例如：

- 候选品排序后的建议说明
- 异常订单的建议处理方式
- 资讯摘要的压缩表达

强制要求：

- LLM 语义判断必须落成结构化字段。
- 硬排除条件优先级高于语义命中。
- 可见流转说明默认只输出 `【流转留痕】` 极简段；`entry_rule_type`、事实来源、节点层级等细节进入内部 packet / workflow state / 日志。
- `acting_agent`、`current_node`、`node_completion_sources`、`pass_flags` 等细粒度状态必须进入内部 handoff / workflow state；除非宿主要求排查证据，否则不在普通聊天回复里展开。

不允许把以下动作完全交给自由 LLM 决策：

- 全局选流
- 是否跳过 guard 节点
- 是否绕过人工确认
- 是否提前收口
- 是否跳过自我优化 loop 中的 review 节点
