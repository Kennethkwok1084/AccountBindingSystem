# AccountBindSystem

校园网移动账号池管理系统实现版仓库。

当前实现口径：

- 后端：Flask + SQLAlchemy + Alembic
- 前端：Vue 3 + Vue Router + 自定义中后台界面
- 数据库：PostgreSQL
- 部署：Docker Compose + Nginx
- 调度：独立 `scheduler` 进程

## 目录结构

| 路径 | 说明 |
|---|---|
| `backend/` | Flask API、迁移、业务服务、测试 |
| `frontend/` | Vue 前端页面 |
| `deploy/nginx/` | Nginx 构建与代理配置 |
| `docs/` | 需求、架构、API、部署、模板、上线清单 |
| `scripts/` | PostgreSQL 备份与恢复脚本 |

## 已实现能力

- 管理员登录、会话、CSRF
- Alembic 基线迁移与 `init-db` 初始化
- 系统配置查询/更新
- 移动账号池导入与导入任务详情
- 批次列表、新建、更新
- 收费清单预览与执行
- 完整名单预览与执行
- 手动换绑、批次换绑
- 导出任务生成与下载
- 账号/学生台账
- 预警中心、调度任务、审计日志

## 本地开发

### 后端

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/flask --app wsgi:app init-db
DEFAULT_ADMIN_PASSWORD=your_password ../.venv/bin/flask --app wsgi:app seed-admin
../.venv/bin/gunicorn --bind 0.0.0.0:5000 wsgi:app
```

默认本地开发数据库可用 SQLite；Compose 部署使用 PostgreSQL。

### 前端

```bash
cd frontend
npm install
npm run dev
```

## Docker Compose 启动

先准备环境变量：

```bash
cp .env.example .env
```

再启动：

```bash
docker compose up --build
```

如果需要在宿主机直接执行后端初始化命令，不要使用 Compose 容器内部的主机名 `postgres`。
请改用映射出来的本地端口：

```bash
cd backend
export DATABASE_URL="postgresql+psycopg://${ABS_DB_USER}:${ABS_DB_PASSWORD}@localhost:${ABS_POSTGRES_PORT:-5432}/${ABS_DB_NAME}"
../.venv/bin/flask --app wsgi:app init-db
```

如果你希望沿用 Compose 默认的 `postgres` 主机名，请在容器内执行：

```bash
docker compose exec backend flask --app wsgi:app init-db
docker compose exec backend flask --app wsgi:app seed-admin --password your_password
```

启动后访问：

- 前端：`http://localhost:8080`
- PostgreSQL：`localhost:5432`

## 认证模式

默认 `ABS_AUTH_MODE=local`，继续使用系统内置管理员账号密码登录。

如果前面已经由雷池统一登录保护，可以改为：

- `ABS_AUTH_MODE=disabled`：关闭本系统登录页，所有请求通过后端后使用 `ABS_AUTH_DISABLED_USERNAME` 作为内部审计用户。
- `ABS_AUTH_MODE=proxy`：关闭本系统登录页，并从反向代理注入的请求头读取用户名。默认读取 `X-Remote-User,X-Forwarded-User,Remote-User,X-Auth-Request-User`，可用 `ABS_AUTH_PROXY_USER_HEADERS` 调整。

`proxy` 模式下，后端会按统一登录用户名自动创建内部 `admin_user`，用于继续满足导入、导出、审计日志等外键关系。建议只允许雷池访问本系统 Nginx/Backend；如雷池可注入固定密钥头，可同时配置 `ABS_AUTH_PROXY_REQUIRED_SECRET_HEADER` 和 `ABS_AUTH_PROXY_REQUIRED_SECRET`，避免客户端伪造身份头。

## 测试

```bash
.venv/bin/pytest backend/tests -q
cd frontend && npm run build
```

## 模板与文档

- 模板样例位于 `docs/templates/`
- 架构与部署说明见 `docs/`

## 备份与恢复

```bash
./scripts/backup_postgres.sh
./scripts/restore_postgres.sh backup/your_dump.sql
```
