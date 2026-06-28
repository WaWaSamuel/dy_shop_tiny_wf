# self_optimization candidate development_request

## 背景问题

- `GET /api/v1/runtime/overview` 现在已恢复可访问，但返回的 `catalog` 为空。
- 根因不是扫描逻辑本身，而是当前 `backend` / `celery-*` 容器仅挂载 `./backend:/app`，容器内不存在项目级 `.trae` 目录。
- `runtime_center.py` 依赖 `REPO_ROOT/.trae` 扫描 workflows / agents / skills，因此运行时只能拿到日志表，无法拿到登记目录。

## 目标行为

- 后端运行时能稳定读取项目级 `.trae` 目录，`runtime` 概览页同时展示 capability catalog 与执行记录。
- `backend`、`celery-worker`、`celery-beat` 三个服务对 `.trae` 的访问路径保持一致，避免环境分叉。

## 涉及页面或接口

- 后端服务：`backend/app/services/runtime_center.py`
- 容器编排：`docker-compose.yml`
- 如需收敛路径，还可能涉及 `backend/Dockerfile`
- 前端展示页：`frontend/src/pages/runtime/ExecutionCenter.tsx`

## 候选方案

1. 在 `docker-compose.yml` 中为相关 Python 服务补充只读挂载，把项目级 `.trae` 暴露到容器内固定路径。
2. 将 `runtime_center.py` 的扫描根目录改为显式配置，例如 `RUNTIME_CATALOG_ROOT`，避免依赖当前文件层级推导。
3. 若后续需要更强隔离，再把 `.trae` 编译为独立 catalog 产物，由 backend 只读取产物文件。

## 验收标准

- `GET /api/v1/runtime/overview` 返回的 `catalog` 非空，至少包含 workflows / agents / skills 的登记项。
- `frontend/src/pages/runtime/ExecutionCenter.tsx` 首屏能看到能力目录，而不是仅有空态日志面板。
- Python 服务在本地开发与容器环境下对 catalog 的读取路径一致。

## 回归风险

- 涉及 `docker-compose.yml` 多服务挂载，属于跨模块运行环境改造。
- 若路径设计不当，可能引入本地 / 容器环境不一致，或把不必要目录暴露进运行容器。
- 若直接修改扫描根逻辑而不补配置，可能掩盖环境边界问题，后续仍会在其他服务中复发。
