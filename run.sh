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
        ;;
    "prod")
        echo -e "${YELLOW}🚀 生产模式启动...${NC}"
        echo ""
        docker compose -f docker-compose.yml up --build -d
        ;;
    "stop")
        echo -e "${YELLOW}🛑 停止所有服务...${NC}"
        docker compose down
        echo -e "${GREEN}✓ 已停止${NC}"
        exit 0
        ;;
    "clean")
        echo -e "${RED}🗑️  清理所有数据（包括数据库）...${NC}"
        read -p "确认删除所有数据? (y/N): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            docker compose down -v
            echo -e "${GREEN}✓ 已清理${NC}"
        fi
        exit 0
        ;;
    "logs")
        docker compose logs -f ${2:-""}
        exit 0
        ;;
    *)
        echo "用法: ./start.sh [dev|prod|stop|clean|logs]"
        echo ""
        echo "  dev   - 开发模式启动 (默认)"
        echo "  prod  - 生产模式启动"
        echo "  stop  - 停止所有服务"
        echo "  clean - 清理所有数据"
        echo "  logs  - 查看日志 (可跟服务名)"
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
        echo -e "${RED}❌ 后端启动超时，请检查日志: ./start.sh logs backend${NC}"
        exit 1
    fi
    sleep 2
done

echo -e "${GREEN}✓ 后端 API 就绪${NC}     → http://localhost:8000"
echo -e "${GREEN}✓ API 文档${NC}           → http://localhost:8000/docs"
echo -e "${GREEN}✓ 前端页面${NC}           → http://localhost:5174"
echo -e "${GREEN}✓ PostgreSQL${NC}         → localhost:5432"
echo -e "${GREEN}✓ Redis${NC}              → localhost:6379"
echo ""
echo "============================================"
echo -e "${GREEN}  🎉 所有服务已启动！${NC}"
echo "============================================"
echo ""
echo "常用命令:"
echo "  ./run.sh logs           # 查看全部日志"
echo "  ./run.sh logs backend   # 查看后端日志"
echo "  ./run.sh stop           # 停止服务"
echo "  ./run.sh clean          # 清理数据"
echo ""
