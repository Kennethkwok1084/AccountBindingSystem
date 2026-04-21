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

启动后访问：

- 前端：`http://localhost:8080`
- PostgreSQL：`localhost:5432`

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
