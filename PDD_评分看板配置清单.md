# 拼多多评分看板配置清单

## 一、项目与版本

- GitHub 仓库：`https://github.com/GuoTeng06/Rating`
- 当前部署分支：`agent/deploy-dashboard-20260810`
- 合并请求：[PR #1](https://github.com/GuoTeng06/Rating/pull/1)
- 生产前端入口：`frontend/index.html`
- 本地预览入口：`frontend/index-preview.html`

## 二、运行环境

- Docker / Docker Compose
- Python 3.11（由 Dockerfile 提供）
- 后端服务：FastAPI + Gunicorn/Uvicorn
- 容器名：`pdd-dashboard`
- 容器网络：`host`
- 服务端口：`8768`

## 三、数据源配置

- MySQL 主机：`192.168.16.38`
- 数据库：`pdd rating`
- 数据库用户名：部署环境变量配置
- 数据库密码：部署环境变量配置
- 数据库连接信息不要提交到 GitHub；建议通过 `docker-compose.yml`、`.env` 或服务器密钥管理注入。

## 四、部署目录与访问地址

- 服务器项目目录：`/home/lingchi/pdd-rating/`
- Docker Compose 文件：`/home/lingchi/pdd-rating/docker-compose.yml`
- 局域网访问：`http://192.168.16.54:8768/`
- 外网访问：`https://pdd_ratting.tyler-personnal.top/`
- 外网方式：Cloudflare Tunnel（如果隧道配置仍指向 8768 端口，则无需修改看板代码）

## 五、常用部署命令

```bash
cd /home/lingchi/pdd-rating
docker compose build pdd-dashboard
docker compose up -d pdd-dashboard
docker ps --filter name=pdd-dashboard
curl -I http://127.0.0.1:8768/
```

## 六、发布前检查

- [ ] 确认 `frontend/index.html` 为正式生产入口，不含预览横幅。
- [ ] 确认 MySQL 可连接，接口能返回店铺、商品和趋势数据。
- [ ] 确认 `pdd-dashboard` 容器状态为 `Up`。
- [ ] 确认 8768 端口未被其他服务占用。
- [ ] 确认外网域名和 Cloudflare Tunnel 可访问。
- [ ] 确认移动端浏览器能打开核心页面。
- [ ] 确认 GitHub 中没有提交数据库密码、SSH 私钥、Cookie 或 Token。

## 七、回滚方式

本次部署前服务器已保留旧前端备份：

`/home/lingchi/pdd-rating/frontend/index.html.backup-20260810-deploy`

如需回滚：

```bash
cd /home/lingchi/pdd-rating
cp frontend/index.html.backup-20260810-deploy frontend/index.html
docker compose build pdd-dashboard
docker compose up -d pdd-dashboard
```

## 八、登录与权限待确认项

- [ ] 钉钉登录应用 AppKey / AppSecret（仅配置在服务器，不提交仓库）。
- [ ] 钉钉回调地址及允许域名。
- [ ] 允许访问的钉钉部门、职位或角色。
- [ ] iframe 嵌入来源白名单。
- [ ] 是否需要中台代理 API，以及代理地址和鉴权方式。

