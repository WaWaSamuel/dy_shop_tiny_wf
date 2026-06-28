# DYShop 项目级智能体指引

本项目是一个“一人公司”工作台。项目级指引只描述 CEO / 总经理在全局入口可见的事实来源、一级工作流、入口角色、流转模板和通用边界。

具体 agent、skill、tool、节点、边、字段、接口和执行细节，不在本文件展开；一律以 `.trae/registry/*.yaml`、`.trae/workflows/*.yaml`、`.trae/policies/orchestration-policy.md` 和对应 agent / skill / tool 文件为准。

## 0. 会话启动前置

读取 `AGENTS.md` 是静默前置步骤，不允许和处理步骤混写。

每一个会话开始时，必须先阅读本文件。只有阅读完成后，才可以理解用户意图、判断 workflow、输出计划或开始处理。

禁止把“我会先读取 AGENTS.md”写成第一句处理计划。可见回复只能从已完成读取后的判断、分流和下一步动作开始。

## 1. 事实来源与防幻觉

事实来源优先级从高到低：

1. 运行期真实数据：接口返回、Excel 内容、Bridge 返回、外部站点真实状态。
2. 结构定义文件：`.trae/registry/*.yaml`、`.trae/workflows/*.yaml`、`.trae/policies/orchestration-policy.md`、`.trae/tools/*/TOOL.md`。
3. 代码与配置：`frontend/`、`backend/`、`bridge/`、`run.sh`、`Makefile`。
4. 本文件的项目级描述。
5. 模型记忆与历史对话。

冲突时高优先级覆盖低优先级。本文件与 registry、workflow 或 orchestration policy 不一致时，以结构定义文件为准，并提示宿主修订本文件。

防幻觉硬约束：

- 不得编造 agent ID、workflow ID、skill ID、tool ID、文件路径、接口路径或字段名。
- 引用具体名称前必须能在事实来源中找到；找不到就先读文件核实。
- 真实数据与 mock / 示例数据必须可区分。
- 不确定就核验或上报，不用自信解释替代真实检查。

## 2. CEO 可见一级工作流

全局入口只做一级选流，不承担任何 workflow 内部阶段判断。一级选流完成后，必须进入目标 workflow 的入口角色，再由 workflow 内部继续递归分派。

| 一级 workflow | 公司职能 | 入口角色 | CEO 可见边界 |
| --- | --- | --- | --- |
| `development_workflow` | 技术开发部门 | `technology-minister-agent` | 页面、接口、联调、问题诊断、修复、回归和验收类任务入口 |
| `news_workflow` | 情报部 | `news-digest-agent` | 资讯采集、整理、摘要和推送类任务入口 |
| `ecommerce_workflow` | 电商部门 | `ecommerce-orchestrator-agent` | 货盘、选品、供应链、素材、上架和异常订单类任务入口 |
| `self_optimization_workflow` | 优化部门 | `self-optimization-agent` | 宿主对规则、职责、路由、闭环或系统结构不满意时的优化入口 |

CEO 只需要知道一级 workflow 与入口角色。workflow 内部有哪些 agent、skill、tool、节点和边，必须进入对应 workflow 文件后再读取，不在本文件维护副本。

## 3. 分流顺序

处理任何项目任务时，按以下顺序执行：

1. 静默读取本文件。
2. 读取并遵守 `.trae/policies/orchestration-policy.md`。
3. 选择唯一一级 workflow。
4. 读取目标 `.trae/workflows/<workflow>.yaml`。
5. 从目标 workflow 的 `workflow_controller`、`minister_role` 或起始节点确认入口角色。
6. 通过 `.trae/registry/agent-catalog.yaml` 或 `.trae/registry/skill-catalog.yaml` 找到入口文件。
7. 读取入口文件后，才允许继续判断下一跳或开始执行。

不得只声明“属于某个 workflow”就直接实现、解释或自行分派。没有加载入口角色时，视为流转不完整。

## 4. 固定流转输出模板

每次发生 workflow 选择、agent / skill 分发、workflow handoff、回流或收口判断时，必须使用以下结构化模板输出或放入 handoff 包。

```text
【流转留痕】
当前层级：<一级选流 / workflow入口 / workflow节点 / QA-review / archive>
事实来源：<orchestration-policy / workflow yaml / registry / 入口角色文件 / 运行期数据>
流转动作：<from workflow/node/agent/skill> -> <to workflow/node/agent/skill>
触发条件：<命中的 entry rule / edge condition / guard / review / failure policy>
传递上下文：<任务摘要、关键输入、风险、阻断项、保留事实>
能力边界：<当前节点不做什么、必须交给谁>

【节点状态】
acting_agent：<当前执行 agent，若是 skill 则写 acting_skill>
current_node：<当前 workflow node key>
workflow_edge：<from -> to>
next_required_node：<下一必经节点>
target_agent_or_skill：<下一跳目标>
target_file：<registry 中确认的文件路径>
target_loaded：<true / false>

【完成态来源】
pass_flags：<本节点可写状态>
node_completion_sources：<每个 *_passed / *_completed 的产出来源>
handoff_required：<true / false>
archive_allowed：<true / false>
```

规则：

- 模板是可审计摘要，不是模型内部隐式推理。
- `*_passed`、`*_completed`、`acceptance_passed`、`development_workflow_completed` 等完成态必须有明确来源。
- 动作名不能替代角色执行。可见摘要里出现 QA、review、验收、归档等阶段动作时，必须同时显示对应执行者、节点、目标文件和可写状态。
- 上游角色只能生成 handoff 包，不能代写下游节点的通过态。

## 5. 一级分流边界

以下是 CEO 层只用于一级选流的粗边界，细则以 `.trae/policies/orchestration-policy.md` 为准：

- 新增或修复 Web 页面、接口、路由、样式、布局、联调、数据展示、浏览器可见 bug：进入 `development_workflow`。
- 资讯采集、微信读书、公众号、日报、摘要整理：进入 `news_workflow`。
- 货盘、选品、供应商、素材、上架、异常订单：进入 `ecommerce_workflow`。
- 宿主质疑规则、职责边界、路由结果、闭环完整性、workflow / agent / registry 一致性，或明确表达系统性不满意：进入 `self_optimization_workflow`。

普通页面视觉错乱、CSS、布局遮挡、图片或文字重叠、路由页面展示异常，默认是 `development_workflow` 的问题诊断与修复任务，不得因为用户说“不满意”就自动升级为自优化影响面审计。

## 6. 能力边界

可以做：

- 读取本地文件、接口返回、Bridge 返回和运行期真实状态。
- 按 workflow 文件进入对应入口角色。
- 改本项目页面、接口、脚本和 `.trae` 编排资产。
- 生成结构化 handoff、review、归档输入。

不能做 / 必须先确认：

- 不直接执行真实下单、真实上架、真实发货、真实退款、删除数据或对外群发。
- 不在项目代码内维护应用内 Agent Runtime。
- 不直连外部数据库；外部数据只经既有导入、Bridge 或接口链路。
- 不用解释替代复测、QA、验收或 review。
- 不跳过 workflow 内部 guard、人工确认、QA、review 或 archive。

## 7. `.trae` 变更契约

修改 `.trae/` 下的 registry、workflow、agent、skill、tool 或 policy 时，必须保持：

- registry 中的 ID 唯一，且文件路径真实存在。
- workflow 节点只能引用已登记的 agent 或 skill。
- workflow edge 只能连接同一 workflow 内已声明节点。
- 被删除或改名的 ID 不得在 registry、workflow、policy、agent 文档、后端展示接口或报告文件中残留。
- 改完后必须自查 YAML 可解析、引用不悬空、旧 ID 无残留。

若改动影响后端测试入口或公共依赖，运行：

```bash
make test
```

## 8. 允许 / 禁止 LLM 判断的范围

LLM 可以在 workflow 内部做局部分流和表达压缩。

以下动作不允许完全交给自由 LLM 决策：

- 全局选流。
- 是否跳过 workflow 入口角色。
- 是否绕过 guard、人工确认、QA、review 或 archive。
- 是否提前收口。
- 是否编造数据、名称、路径或外部状态。
