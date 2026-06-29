# DYShop 项目级智能体指引

## 0. 项目定位

DYShop 是一个“一人公司”工作台。`AGENTS.md` 只描述全局入口、运行规范、事实来源、一级工作流和通用边界。

子工作流的节点、边、字段、agent、skill、tool、接口和执行细节不在本文件维护；一律以下列事实来源为准：

- `.trae/policies/orchestration-policy.md`
- `.trae/policies/context-isolation-policy.md`
- `.trae/workflows/*.yaml`
- `.trae/registry/*.yaml`
- 对应 agent / skill / tool 文件

## 1. 会话入口

每次处理项目任务前，必须静默读取本文件。读取完成后，才允许理解用户意图、判断 workflow、输出计划或开始处理。

全局入口是 `ceo-orchestrator-agent`。

## 2. 一级工作流

CEO 层只需要知道一级 workflow 与入口角色：

| 一级 workflow | 公司职能 | 入口角色 |
| --- | --- | --- |
| `development_workflow` | 技术开发部门 | `technology-minister-agent` |
| `news_workflow` | 情报部 | `news-digest-agent` |
| `ecommerce_workflow` | 电商部门 | `ecommerce-orchestrator-agent` |
| `self_optimization_workflow` | 优化部门 | `self-optimization-agent` |

一级选流细则、硬触发、硬排除和优先级，以 `.trae/policies/orchestration-policy.md` 为准。进入某个一级 workflow 后，必须读取对应 workflow yaml 和入口角色文件，再由入口角色继续递归分派。

## 3. 事实来源

事实来源优先级从高到低：

1. 运行期真实数据：接口返回、Excel 内容、Bridge 返回、外部站点真实状态。
2. 结构定义文件：`.trae/policies/*.md`、`.trae/workflows/*.yaml`、`.trae/registry/*.yaml`、`.trae/tools/*/TOOL.md`。
3. 代码与配置：`frontend/`、`backend/`、`bridge/`、`run.sh`、`Makefile`。
4. 本文件。
5. 模型记忆与历史对话。

冲突时高优先级覆盖低优先级。本文件与 policy、registry 或 workflow 不一致时，以结构定义文件为准，并提示宿主修订本文件。

## 4. 入口约束

项目任务只能按 `.trae/policies/orchestration-policy.md` 完成一级选流、入口加载和后续 handoff。

不得只声明“属于某 workflow”就直接实现、解释或自行分派。没有完成目标 workflow、入口角色和 `handoff_packet` 的确认时，视为流转不完整。

## 5. 可见流转

每次发生 workflow 选择、agent / skill 分发、workflow handoff、回流或收口判断时，对外只输出极简 `【流转留痕】`：

```text
【流转留痕】
动作：<from> -> <to>
依据：<命中的 policy / rule / edge / guard / review>
上下文：<任务摘要 + 必要保留事实 / packet refs>
边界：<当前节点不做什么 / 下一步交给谁>
```

细节如节点状态、完成态来源、`entry_rule_type`、事实来源、可写字段等，只进入内部 packet、workflow state、日志或归档；默认不在聊天回复展开。

## 6. 上下文隔离

跨 workflow 或跨 agent 传递上下文时，必须遵守 `.trae/policies/context-isolation-policy.md`：

- 上游只给下游压缩后的 `handoff_packet`。
- 下游结束后只回传结构化 `result_packet`。
- 不转发完整聊天记录、完整日志、原始大文件、Cookie、Token、密钥或未脱敏外部数据。
- 日志只记录 packet 引用、摘要和状态，不记录完整 packet。

## 7. 防幻觉与边界

- 不得编造 agent ID、workflow ID、skill ID、tool ID、文件路径、接口路径或字段名。
- 引用具体名称前必须能在事实来源中找到；找不到就先读文件核实。
- 真实数据与 mock / 示例数据必须可区分。
- 不确定就核验或上报，不用自信解释替代真实检查。
- 不跳过 workflow 入口角色、guard、人工确认、QA、review 或 archive。
- 不用解释替代复测、QA、验收或 review。
- 不直接执行真实下单、真实上架、真实发货、真实退款、删除数据或对外群发。
- 不直连外部数据库；外部数据只经既有导入、Bridge 或接口链路。
- 不在项目代码内维护应用内 Agent Runtime。

## 8. `.trae` 变更契约

修改 `.trae/` 下的 registry、workflow、agent、skill、tool 或 policy 时，必须保持：

- registry 中的 ID 唯一，且文件路径真实存在。
- workflow 节点只能引用已登记的 agent 或 skill。
- workflow edge 只能连接同一 workflow 内已声明节点。
- 被删除或改名的 ID 不得在 registry、workflow、policy、agent 文档、后端展示接口或报告文件中残留。
- 改完后必须自查 YAML 可解析、引用不悬空、旧 ID 无残留。

若改动影响后端测试入口或公共依赖，运行 `make test`。
