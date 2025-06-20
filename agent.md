
# 👩‍💻 Codex Agent 使用指南 - 校园账号管理系统

## 📦 项目结构说明（Monorepo）

本项目采用前后端分离结构，使用 Vue + Element Plus 构建前端，Flask + SQLAlchemy 实现后端接口逻辑。项目结构如下：

```

account-manager/
├── frontend/         # Vue 3 + Element Plus 开发的前端页面
├── backend/          # Flask + SQLAlchemy 构建的 REST API 后端
├── setup.sh          # 任务开始时执行的安装脚本
├── AGENTS.md         # 当前说明文件，提供 Codex 工作指引
└── README.md

```

---

## 🗂️ 数据库结构

### `accounts` 表：用于管理所有可绑定的校园网账号

| 字段名        | 类型       | 描述                             |
|---------------|------------|----------------------------------|
| id            | INT        | 自增主键                         |
| username      | VARCHAR    | 账号（唯一）                     |
| password      | VARCHAR    | 明文密码                         |
| is_bound      | BOOLEAN    | 是否绑定                         |
| student_id    | VARCHAR    | 绑定的学号，未绑定则为 NULL     |
| bind_time     | DATETIME   | 最后一次绑定时间                 |
| create_time   | DATETIME   | 初始导入时间 ✅（用于溯源管理） |

> ✅ 每个账号最多只能绑定一个学号；超过 32 天自动释放。

---

### `binding_logs` 表：记录所有绑定操作及自动释放日志

| 字段名        | 类型       | 描述                                        |
|---------------|------------|---------------------------------------------|
| id            | INT        | 自增主键                                     |
| username      | VARCHAR    | 被操作的账号                                 |
| student_id    | VARCHAR    | 绑定或解绑时的学号                           |
| bind_time     | DATETIME   | 操作时间                                     |
| operator      | VARCHAR    | 操作人，默认值为 "system"，也可为管理员账号    |
| action        | VARCHAR    | 操作类型，如 `"bind"`、`"auto_release"` 等 ✅ |

> ✅ 所有绑定/解绑行为都需记录日志，便于审核和溯源。

---

## 📋 业务逻辑要求

- 用户账号可被“绑定”到一个学号，成功后 `is_bound=True` 并更新 `student_id`、`bind_time`
- 一个学号只允许绑定一个账号（需唯一性检查）
- 超过 32 天未更新 `bind_time` 的账号应自动释放为未绑定状态
- 所有操作都记录入 `binding_logs` 表
- 支持 Excel（.xlsx）批量导入账号信息（字段：username, password）

---

## ✅ 测试规范与代码格式

- 后端测试工具：`pytest`
- 前端测试工具：`vitest`
- 格式化工具：
  - Python 使用 `black` + `isort`
  - Vue 使用 `prettier` + `eslint`

---

## 🚀 可执行任务示例

- 编写 `/api/bind` 接口处理账号绑定请求
- 编写定时任务自动释放超时账号并记录日志
- 编写 `/api/import_accounts` 接口，支持 xlsx 文件批量导入
- 增加 `/api/logs` 接口，用于查询 `binding_logs`
- 实现前端绑定页面，提供输入框（账号、学号）+ 成功提示
- 补充接口的测试用例，覆盖绑定失败、绑定成功、重复绑定等情况

---

## 💬 提示 Codex 的最佳实践

- 请优先关注 `backend/models.py`、`backend/routes/*.py` 和 `frontend/views/Bind.vue`
- 建议在 PR 中说明所影响的数据库结构、测试覆盖内容
- 若需要扩展字段，请通过 Alembic 生成迁移脚本，不直接改表结构
- 请先将develop.md编写成需要实现的模块步骤，并且每次编写的时候标记完成的模块

---

## 📥 PR 提交流程

- 通过测试（pytest + vitest）
- 通过格式化检查（black + prettier）
- 使用如下 PR 标题格式：
```

\[backend] 添加账号绑定接口
\[frontend] 新增绑定页面逻辑

