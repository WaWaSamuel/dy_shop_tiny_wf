# Personal Studio - Makefile
# 常用命令快捷方式

.PHONY: help start stop clean logs migrate test lint install-bridge dev-bridge

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ==================== Docker 启动 ====================

start: ## Docker 启动所有服务
	@chmod +x run.sh stop.sh && ./run.sh dev

stop: ## 停止所有服务
	./run.sh stop

clean: ## 清理所有数据 (慎用)
	./run.sh clean

restart: ## 重启所有服务
	docker compose restart

rebuild: ## 重新构建并启动
	docker compose up --build -d

logs: ## 查看所有日志
	docker compose logs -f

logs-backend: ## 查看后端日志
	docker compose logs -f backend

logs-frontend: ## 查看前端日志
	docker compose logs -f frontend

logs-celery: ## 查看 Celery 日志
	docker compose logs -f celery-worker

# ==================== 本地开发 ====================

local: ## 本地启动 (无 Docker，需要本地 PG + Redis)
	@chmod +x start-local.sh && ./start-local.sh

install-backend: ## 安装后端依赖
	cd backend && pip install -r requirements.txt

install-frontend: ## 安装前端依赖
	cd frontend && npm install

dev-backend: ## 启动后端 (开发模式)
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend: ## 启动前端 (开发模式)
	cd frontend && npm run dev

install-bridge: ## 安装宿主机 bridge 依赖
	python3 -m venv .venv-bridge
	./.venv-bridge/bin/pip install -r bridge/requirements.txt

dev-bridge: ## 启动宿主机 bridge
	./.venv-bridge/bin/uvicorn bridge.app:app --host 127.0.0.1 --port 8765 --reload

# ==================== 数据库 ====================

migrate: ## 运行数据库迁移
	cd backend && alembic upgrade head

migrate-create: ## 创建新迁移 (用法: make migrate-create MSG="add xxx table")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

migrate-rollback: ## 回滚最近一次迁移
	cd backend && alembic downgrade -1

db-shell: ## 进入数据库 Shell
	docker compose exec postgres psql -U studio -d studio_main

redis-shell: ## 进入 Redis Shell
	docker compose exec redis redis-cli

# ==================== 测试 ====================

test: ## 运行后端测试
	cd backend && pytest -v

test-cov: ## 运行测试 (含覆盖率)
	cd backend && pytest --cov=app --cov-report=html

# ==================== 代码质量 ====================

lint: ## 代码检查
	cd backend && ruff check .
	cd frontend && npm run lint

format: ## 代码格式化
	cd backend && ruff format .
	cd frontend && npm run format
