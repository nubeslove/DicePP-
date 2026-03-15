# nonebot-dicepp

基于Python的DND骰娘机器人, 可作为机器人项目 NoneBot 的插件使用。

请加入交流群 861919492 获取整合包和部署指南。

V2.0.5 更新内容：

- 修复部分 bug
- 优化 log 代码，新增外部接口

## Linux 部署与反向 WebSocket Token 设置

本项目使用 NoneBot2 + OneBot v11 适配器，默认提供反向 WebSocket 接入：`/onebot/v11/ws`。

### 设置 13 位 Token

如果你的 OneBot/QQ 代理（如 go-cqhttp、Lagrange.OneBot、NapCat 等）要求反向连接必须带一个 13 位 token：

1. 在项目根目录创建或编辑环境文件 `.env`（或直接在启动前临时设置环境变量）添加：

```env
ACCESS_TOKEN=1699999999999  # 13 位示例，可用当前时间戳或随机数
SECRET=                     # 若不需要可留空
HOST=0.0.0.0                # 需要外部访问时建议这样设置
PORT=8080                   # 与代理配置的反向地址端口一致
```

1. 代理端配置对应字段（可能叫 `access_token`、`token`，或通过请求头 `Authorization: Bearer <ACCESS_TOKEN>` 发送，视代理实现而定）。
1. 启动后代理以带 token 的反向 WS 方式连接：`ws://<你的服务器>:8080/onebot/v11/ws`。

### Linux 启动方式概览

1. 直接 Python 方式（推荐调试）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

1. Docker 方式（稳定部署）

```bash
docker build -t dicepp:latest .
docker run -d --name dicepp_bot -p 8080:8080 --env-file .env dicepp:latest
```

或使用 `docker-compose.yml`：

```bash
docker compose up -d --build
```

1. nb-cli 方式（可选）

```bash
nb run
```

### 数据持久化

Docker Compose 已挂载 `./src/plugins/DicePP/data` 到容器内部，长期运行请保持该目录持久化以保存牌堆/日志等数据。

### 常见问题

- 连接失败且日志提示 WebSocket 被关闭：检查 token 是否一致、端口/防火墙是否开放。
- 多账号同时连接：保持 `MAX_WORKERS=1`（Compose 已设置）并在代理端区分不同 `self_id`。
- 需外网访问：`HOST` 设为 `0.0.0.0` 并在服务器开放 8080 端口。

---

如有进一步问题请在群内或 issue 反馈。
