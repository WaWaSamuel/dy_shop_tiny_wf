#!/bin/bash
set -e

echo "============================================"
echo "  Personal Studio - 一键启动"
echo "============================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

BRIDGE_HOST=${BRIDGE_HOST:-127.0.0.1}
BRIDGE_PORT=${BRIDGE_PORT:-8765}
BRIDGE_URL="http://${BRIDGE_HOST}:${BRIDGE_PORT}/health"
BRIDGE_VENV=".venv-bridge"
BRIDGE_PID_FILE=".run/bridge.pid"
BRIDGE_LOG_FILE=".run/bridge.log"

ensure_runtime_dir() {
    mkdir -p .run
}

is_bridge_healthy() {
    curl -s "${BRIDGE_URL}" > /dev/null 2>&1
}

is_bridge_running() {
    if [ -f "${BRIDGE_PID_FILE}" ]; then
        local pid
        pid=$(cat "${BRIDGE_PID_FILE}")
        if kill -0 "${pid}" > /dev/null 2>&1; then
            return 0
        fi
        rm -f "${BRIDGE_PID_FILE}"
    fi
    return 1
}

ensure_bridge_dependencies() {
    if [ ! -x "${BRIDGE_VENV}/bin/uvicorn" ]; then
        echo -e "${YELLOW}📦 初始化宿主机 bridge 运行环境...${NC}"
        python3 -m venv "${BRIDGE_VENV}"
        "${BRIDGE_VENV}/bin/pip" install -r bridge/requirements.txt
    fi
}

start_bridge() {
    ensure_runtime_dir

    if is_bridge_healthy; then
        echo -e "${GREEN}✓ Bridge 已在运行${NC}      → http://${BRIDGE_HOST}:${BRIDGE_PORT}"
        return 0
    fi

    ensure_bridge_dependencies

    echo -e "${YELLOW}🌉 启动宿主机 bridge...${NC}"
    nohup "${BRIDGE_VENV}/bin/uvicorn" bridge.app:app --host "${BRIDGE_HOST}" --port "${BRIDGE_PORT}" > "${BRIDGE_LOG_FILE}" 2>&1 &
    local bridge_pid=$!
    echo "${bridge_pid}" > "${BRIDGE_PID_FILE}"

    local retry=0
    local max_retries=20
    until is_bridge_healthy; do
        retry=$((retry + 1))
        if [ ${retry} -ge ${max_retries} ]; then
            echo -e "${RED}❌ Bridge 启动超时，请检查日志: ./run.sh bridge-logs${NC}"
            return 1
        fi
        sleep 1
    done

    echo -e "${GREEN}✓ Bridge 就绪${NC}         → http://${BRIDGE_HOST}:${BRIDGE_PORT}"
}

stop_bridge() {
    ensure_runtime_dir

    if is_bridge_running; then
        local pid
        pid=$(cat "${BRIDGE_PID_FILE}")
        echo -e "${YELLOW}🛑 停止宿主机 bridge...${NC}"
        kill "${pid}" > /dev/null 2>&1 || true
        rm -f "${BRIDGE_PID_FILE}"
        echo -e "${GREEN}✓ Bridge 已停止${NC}"
        return 0
    fi

    if is_bridge_healthy; then
        local pid
        pid=$(lsof -ti tcp:"${BRIDGE_PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1)
        if [ -n "${pid}" ]; then
            echo -e "${YELLOW}🛑 停止宿主机 bridge...${NC}"
            kill "${pid}" > /dev/null 2>&1 || true
            echo -e "${GREEN}✓ Bridge 已停止${NC}"
            return 0
        fi
    fi

    echo -e "${YELLOW}ℹ️  Bridge 未运行${NC}"
}

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装，请先安装 Docker Desktop${NC}"
    echo "   下载地址: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker 环境检查通过${NC}"
echo ""

# 启动模式选择
MODE=${1:-"dev"}

case $MODE in
    "dev")
        echo -e "${YELLOW}🚀 开发模式启动...${NC}"
        echo ""
        docker compose up --build -d
        start_bridge
        ;;
    "prod")
        echo -e "${YELLOW}🚀 生产模式启动...${NC}"
        echo ""
        docker compose -f docker-compose.yml up --build -d
        start_bridge
        ;;
    "stop")
        echo -e "${YELLOW}🛑 停止所有服务...${NC}"
        docker compose down
        stop_bridge
        echo -e "${GREEN}✓ 已停止${NC}"
        exit 0
        ;;
    "clean")
        echo -e "${RED}🗑️  清理所有数据（包括数据库）...${NC}"
        read -p "确认删除所有数据? (y/N): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            docker compose down -v
            stop_bridge
            echo -e "${GREEN}✓ 已清理${NC}"
        fi
        exit 0
        ;;
    "bridge-start")
        start_bridge
        exit 0
        ;;
    "bridge-stop")
        stop_bridge
        exit 0
        ;;
    "bridge-logs")
        ensure_runtime_dir
        if [ -f "${BRIDGE_LOG_FILE}" ]; then
            tail -f "${BRIDGE_LOG_FILE}"
        else
            echo -e "${YELLOW}ℹ️  还没有 bridge 日志${NC}"
        fi
        exit 0
        ;;
    "logs")
        docker compose logs -f ${2:-""}
        exit 0
        ;;
    *)
        echo "用法: ./run.sh [dev|prod|stop|clean|logs|bridge-start|bridge-stop|bridge-logs]"
        echo ""
        echo "  dev   - 开发模式启动 (默认)"
        echo "  prod  - 生产模式启动"
        echo "  stop  - 停止所有服务"
        echo "  clean - 清理所有数据"
        echo "  logs  - 查看日志 (可跟服务名)"
        echo "  bridge-start - 启动宿主机 bridge"
        echo "  bridge-stop  - 停止宿主机 bridge"
        echo "  bridge-logs  - 查看 bridge 日志"
        exit 0
        ;;
esac

# 等待服务就绪
echo ""
echo -e "${YELLOW}⏳ 等待服务就绪...${NC}"
echo ""

# 等待后端
MAX_RETRIES=30
RETRY=0
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ 后端启动超时，请检查日志: ./run.sh logs backend${NC}"
        exit 1
    fi
    sleep 2
done

echo -e "${GREEN}✓ 后端 API 就绪${NC}     → http://localhost:8000"
echo -e "${GREEN}✓ API 文档${NC}           → http://localhost:8000/docs"
echo -e "${GREEN}✓ 前端页面${NC}           → http://localhost:5174"
echo -e "${GREEN}✓ PostgreSQL${NC}         → localhost:5432"
echo -e "${GREEN}✓ Redis${NC}              → localhost:6379"
echo -e "${GREEN}✓ Session Bridge${NC}     → http://${BRIDGE_HOST}:${BRIDGE_PORT}"
echo ""
echo "============================================"
echo -e "${GREEN}  🎉 所有服务已启动！${NC}"
echo "============================================"
echo ""
echo "常用命令:"
echo "  ./run.sh logs           # 查看全部日志"
echo "  ./run.sh logs backend   # 查看后端日志"
echo "  ./run.sh bridge-logs    # 查看 bridge 日志"
echo "  ./run.sh stop           # 停止服务"
echo "  ./run.sh clean          # 清理数据"
echo ""
