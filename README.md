# DYShop / Personal Studio

基于 `Docker Compose` 的一键启动方案，适合在 macOS 上快速拉起前端、后端、PostgreSQL、Redis 和 Celery 服务。

## 1. 环境准备

本项目推荐直接使用 **Docker Desktop for Mac**，不要用 `brew` 安装 Docker 相关组件。

下载地址：

`https://www.docker.com/products/docker-desktop/`

下载后打开 Settings（齿轮图标）→ Resources → Advanced：
```bash
配置项	建议设置	说明
CPUs	4	你的项目 5 个容器并行
Memory	6 GB	PG + Redis + Python + Node 同时跑
Swap	2 GB	防止内存溢出
Disk image size	30 GB	镜像 + 数据存储
```

点 Apply & Restart。

配置镜像加速（国内网络必须）Settings → Docker Engine，将 JSON 修改为：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.nju.edu.cn"
  ]
}
```
点 Apply & Restart。

打开终端执行：

```bash
docker --version
# Docker version 27.x.x

docker compose version
# Docker Compose version v2.x.x

docker run hello-world
# 看到 "Hello from Docker!" 即成功
```

## 2. 项目结构

当前项目通过 `docker-compose.yml` 编排以下服务：

- `frontend`：Vite + React 前端
- `backend`：FastAPI 后端
- `postgres`：PostgreSQL 16
- `redis`：Redis 7
- `celery-worker`：异步任务 Worker
- `celery-beat`：定时任务

## 3. 快速启动

进入项目根目录：

```bash
cd /Users/bytedance/StickerProductive/DYShop
```

给启动脚本执行权限并启动：

```bash
chmod +x start.sh
./start.sh dev
```

也可以使用 `Makefile`：

```bash
make start
```

首次启动会自动执行：

1. 检查本机 Docker 环境
2. 拉取基础镜像
3. 构建前后端镜像
4. 启动数据库、缓存、后端、前端和 Celery 服务
5. 轮询 `http://localhost:8000/health`，确认后端可用

首次构建时间会明显更长，属于正常现象。

## 4. 启动成功后访问地址

- 前端页面：`http://localhost:5174`
- 后端 API：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`

## 5. 常用命令

启动全部服务：

```bash
./start.sh dev
```

查看全部日志：

```bash
./start.sh logs
```

查看后端日志：

```bash
./start.sh logs backend
```

停止服务：

```bash
./start.sh stop
```

清理服务和数据卷：

```bash
./start.sh clean
```

直接使用 Compose：

```bash
docker compose up --build -d
docker compose logs -f
docker compose down
docker compose down -v
```

## 6. 配置说明

项目当前的容器内配置已经写在 `docker-compose.yml` 中，默认会注入：

- PostgreSQL 连接
- Redis 连接
- Celery Broker / Backend
- 前端代理目标 `VITE_PROXY_TARGET=http://backend:8000`

后端示例环境变量文件位于：

```bash
backend/.env.example
```

前端示例环境变量文件位于：

```bash
frontend/.env.example
```

如果只是本地用 Docker Compose 启动，通常不需要额外手动创建 `.env` 文件。

## 7. 常见问题

### 7.1 `docker: command not found`

说明 Docker Desktop 尚未安装，直接从官网下载安装：

`https://www.docker.com/products/docker-desktop/`

### 7.2 `Cannot connect to the Docker daemon`

说明 Docker Desktop 还没启动完成。请先打开 Docker Desktop，并等待状态变为 Running，再重新执行：

```bash
./start.sh dev
```

### 7.3 端口被占用

本项目默认使用这些端口：

- `5174`
- `8000`
- `5432`
- `6379`

如果端口冲突，请先停止本机已有服务，或修改 `docker-compose.yml` 里的端口映射。

### 7.4 首次启动较慢

首次启动会下载镜像并构建依赖，速度取决于网络环境和本机性能。后续启动会快很多。

## 8. 推荐启动方式

在 macOS 上，推荐直接使用下面这套流程：

1. 安装 Docker Desktop for Mac
2. 打开 Docker Desktop，确认已运行
3. 在项目根目录执行 `./start.sh dev`
4. 打开 `http://localhost:5174`

这也是当前项目最直接、维护成本最低的启动方式。
