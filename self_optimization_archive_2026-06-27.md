# self_optimization archive

## 问题定义

本轮按周自动巡检 DYShop 仓库，重点检查代码冗余、重复实现、过时资产、低价值抽象、规范漂移，以及 web / backend 数据传输不一致。最终收敛为两类问题：

- 可自动落地的低风险问题：`runtime` 日志接口读写故障、仓库忽略规则漂移、`bridge` 文档入口漂移、可再生临时产物残留。
- 暂缓处理的跨模块问题：`runtime` capability catalog 在容器内为空，根因是 `.trae` 未挂载进 Python 服务容器。

## 根因判断

- `GET /api/v1/runtime/logs` 使用了 `(:param IS NULL OR field = :param)` 形式；在 `asyncpg` 下空参数会触发类型推断歧义，直接报 `AmbiguousParameterError`。
- `POST /api/v1/runtime/logs` 直接把 Python `dict/list` 作为 JSONB 绑定参数传入，`asyncpg` 在当前写法下无法编码，触发 `dict has no attribute encode`。
- `.gitignore` 未覆盖 `.venv-bridge/`、`.tmp_asset_sheets/`、`backend/celerybeat-schedule`，导致本地运行产物容易再次污染工作树。
- `bridge/README.md` 仍沿用旧的独立启动叙述，与当前 `./run.sh dev` 统一入口规范不一致。
- `runtime` catalog 为空的根因不是扫描器，而是 `docker-compose.yml` 只把 `./backend` 挂进 Python 容器，容器内不存在项目级 `.trae`。

## change-surface-audit

### 必须改

- `backend/app/services/runtime_center.py`
- `.gitignore`
- `bridge/README.md`
- 运行产物：`.tmp_asset_sheets/`、`backend/celerybeat-schedule`

### 建议改

- 为 `runtime` catalog 读取引入显式根路径配置，而不是依赖文件层级推导。
- 后续把前后端契约收敛到 OpenAPI 单一来源，减少手写 `types` 与 `services` 漂移。

### 可暂缓

- 从版本控制中彻底移除 `.venv-bridge/`。该目录确属低价值产物，但会影响当前本机调试环境，本轮先只补忽略规则，不直接清掉。
- 为 `backend` / `celery-*` 服务补充 `.trae` 挂载并修复 runtime catalog 空态。此项涉及容器边界，已下沉为候选开发请求。

## latest-pattern-research

- 可采用：把后端 OpenAPI 作为前后端契约单一来源，并生成 TypeScript client / types，减少手写接口漂移。[1][2]
- 可采用：继续把 Vite 构建产物视为部署产物，保留 `dist` 作为发布结果而不是长期纳入源码管理。[3]
- 可采用：把虚拟环境视为可重建的本地环境目录，不应纳入 Git；因此补充 `.venv-bridge/` 忽略规则是合理收口。[4]
- 不建议本轮采用：直接引入完整代码生成链、容器挂载重构或 runtime catalog 路径重设计。这些都超出“每周低风险自动优化”边界。

## 已执行改造

- 修复 `runtime` 查询：改为动态拼装筛选条件，只绑定实际存在的参数，消除空参数触发的 `asyncpg` 类型歧义。
- 修复 `runtime` 写入：JSONB 字段统一序列化并显式 `CAST(... AS JSONB)`，恢复 `workflow-log-publish` 对应的兼容写入接口。
- 更新 `.gitignore`：新增 `.venv-bridge/`、`.tmp_asset_sheets/`、`backend/celerybeat-schedule`。
- 清理运行产物：删除 `.tmp_asset_sheets/` 与 `backend/celerybeat-schedule`。
- 修正文档漂移：`bridge/README.md` 改为以 `./run.sh dev` 为默认入口，并保留 bridge 单独调试方式。

## 验证结果

- `GET /api/v1/runtime/overview` 返回 `200`
- `GET /api/v1/runtime/logs?workflow_id=self_optimization_workflow` 返回 `200`
- `POST /api/v1/runtime/logs` 返回 `201`
- 新写入的 intake 日志可立即通过 `GET /api/v1/runtime/logs?workflow_id=self_optimization_workflow` 读回

## review 评分卡

| 维度 | 分数 | 说明 |
|---|---:|---|
| 宿主要求对齐度 | 4.7 | 命中了低风险高收益边界，先做问题定义、影响面与范式研究，再执行小范围改造 |
| 根因覆盖度 | 4.6 | 覆盖了 runtime 读写两条根因、忽略规则漂移与文档漂移 |
| 改造范围完整度 | 4.2 | 已覆盖 backend、仓库规范、文档和运行产物；容器挂载问题已识别但按规则暂缓 |
| 最新范式吸收度 | 4.1 | 结合 OpenAPI 单一来源、Vite 构建产物边界、虚拟环境边界给出落地建议 |
| 实现质量与风险控制 | 4.5 | 改动集中且已用真实接口完成回归验证 |
| 回归影响可接受度 | 4.6 | 没有直接触碰高风险运行环境，只修复故障点与仓库卫生项 |

- 平均分：`4.45`
- 结论：`passed`

## 暂缓项

- 候选开发请求：`self_optimization_candidate_request_runtime-catalog-mount_2026-06-27.md`
- 说明：`runtime` catalog 为空的根因是 Python 容器未挂载项目级 `.trae`，属于跨模块运行环境问题，本轮不直接做大改。

## 最终状态

- `optimized`
- 本轮存在明确可执行的低风险优化项，已完成自动落地并通过验证。

## 产物索引

- `self_optimization_development_request_2026-06-27.md`
- `self_optimization_candidate_request_runtime-catalog-mount_2026-06-27.md`
- `self_optimization_archive_2026-06-27.md`

## Sources

1. [FastAPI: Generating SDKs](https://fastapi.tiangolo.com/advanced/generate-clients/)
2. [openapi-typescript Introduction](https://openapi-ts.dev/introduction)
3. [Vite: Deploying a Static Site](https://vite.dev/guide/static-deploy)
4. [Python docs: `venv` — Creation of virtual environments](https://docs.python.org/3/library/venv.html)
