# self_optimization development_request

## 背景问题

- 每周自动巡检发现当前仓库存在一组低风险但高收益的问题：
- `runtime` 执行记录接口的 `GET /api/v1/runtime/logs` 在筛选参数为空时触发 PostgreSQL `AmbiguousParameterError`，导致执行记录中心与 `workflow-log-publish` 的展示闭环不稳定。
- 仓库忽略规则与实际运行产物存在漂移，缺失对 `.venv-bridge/`、`.tmp_asset_sheets/`、`backend/celerybeat-schedule` 的边界约束。
- `bridge/README.md` 仍保留“手动启动 bridge + make start”的旧叙述，没有体现当前项目以 `./run.sh dev` 为统一入口的规范。
- 仓库内存在明显低价值运行产物：`.tmp_asset_sheets/` 与 `backend/celerybeat-schedule`。

## 目标行为

- `GET /api/v1/runtime/logs` 与执行中心页面在筛选为空或部分为空时稳定返回，不再因空参数绑定导致 500。
- 仓库忽略规则明确覆盖本地虚拟环境、临时资产切片和 Celery 本地调度状态文件，减少后续重复污染。
- 清理明确无业务价值且可再生的运行产物，但不直接触碰可能影响当前开发环境的大体量目录。
- `bridge/README.md` 与当前 `run.sh` 统一入口保持一致，仅把手动 bridge 启动保留为调试场景。

## 涉及页面或接口

- 后端接口：`/api/v1/runtime/logs`
- 后端服务：`backend/app/services/runtime_center.py`
- 前端展示页：`frontend/src/pages/runtime/ExecutionCenter.tsx`
- 仓库规范文件：`.gitignore`
- 文档：`bridge/README.md`

## 验收标准

- 调用 `GET /api/v1/runtime/logs?workflow_id=self_optimization_workflow` 返回 `200`，JSON 可正常解析。
- 执行记录中心依赖的 `getRuntimeOverview()` / `getRuntimeLogs()` 链路不再因空筛选触发后端 500。
- `.gitignore` 新增对 `.venv-bridge/`、`.tmp_asset_sheets/`、`backend/celerybeat-schedule` 的忽略规则。
- `.tmp_asset_sheets/` 与 `backend/celerybeat-schedule` 从工作树中移除。
- `bridge/README.md` 明确 `./run.sh dev` 为主入口，并把手动 bridge 启动标为可选调试方式。

## 回归风险

- `runtime` 查询 SQL 若改动不当，可能影响执行中心筛选结果或排序。
- 忽略规则新增若写错，可能误伤需要纳管的正式资产。
- 文档更新若过度删减，可能影响独立调试 bridge 的可读性。
- 本轮不直接删除 `.venv-bridge/`，避免对当前本机调试环境造成不必要扰动；该项仅记录为后续候选清理事项。
