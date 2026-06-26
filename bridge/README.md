# Session Bridge

宿主机侧登录态桥接服务。

用途：

- 读取 macOS 本机 Chrome 登录态
- 把指定站点的 `Cookie` 同步回 Docker 内的 backend
- 让前端仍然只访问 backend，不直接碰宿主机浏览器

当前已接入：

- `weread` / 微信读书

## 启动

在仓库根目录执行：

```bash
python3 -m venv .venv-bridge
source .venv-bridge/bin/activate
pip install -r bridge/requirements.txt
uvicorn bridge.app:app --host 127.0.0.1 --port 8765 --reload
```

主工程仍然正常启动：

```bash
make start
```

也就是两部分：

1. Docker 内主工程
2. 宿主机本地 bridge

## 环境变量

- `BRIDGE_HOST`，默认 `127.0.0.1`
- `BRIDGE_PORT`，默认 `8765`
- `BRIDGE_BACKEND_API_BASE_URL`，默认 `http://127.0.0.1:8000/api/v1`
- `BRIDGE_CHROME_PROFILE_NAME`，默认 `Default`
- `BRIDGE_CHROME_COOKIES_PATH`，默认空，优先自动探测
- `BRIDGE_CHROME_SAFE_STORAGE_NAME`，默认 `Chrome Safe Storage`
- `BRIDGE_REQUEST_TIMEOUT_SECONDS`，默认 `20`

## 接口

- `GET /health`
- `GET /sources`
- `POST /sync/{source_id}`

## 使用方式

1. 启动 Docker 主工程
2. 启动宿主机 bridge
3. 打开首页
4. 如果微信读书是红灯，点击进入微信读书完成登录
5. 回到首页点击右侧刷新按钮
6. frontend -> backend -> bridge -> Chrome Cookie -> backend probe，状态更新为绿灯

## 说明

首次读取 Chrome 登录态时，macOS 可能弹 Keychain 提示，询问是否允许访问 `Chrome Safe Storage`。这是因为 Chrome Cookie 需要先用 Keychain 中保存的密钥解密。
