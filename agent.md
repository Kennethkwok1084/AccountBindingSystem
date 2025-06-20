
## 📦 Project Overview

This is the AGENTS guide for the **校园网账号管理系统 (Campus Network Account Manager)** project.  
The system is built using **Flask (backend)** and **Vue 3 + Element Plus (frontend)**, and uses **MySQL** for persistent storage.  
Its goal is to support:
- Account importing via Excel
- Student ID binding
- Auto-releasing accounts after 32 days
- Operation logging
- Web-based visualization and interaction

---

## 📁 File Structure Highlights

### Backend (Flask)
| Path | Purpose |
|------|---------|
| `/app/routes.py` | Flask route handlers |
| `/app/models.py` | SQLAlchemy models: `Account`, `BindingLog` |
| `/app/utils.py` | Excel parsing, data utilities |
| `/tasks/release.py` | Auto-release logic (run daily or per request) |
| `/uploads/` | Temporarily stores uploaded Excel files |
| `/config.py` | Database and Flask configuration |

### Frontend (Vue 3 + Element Plus)
| Path | Purpose |
|------|---------|
| `/src/views/Accounts.vue` | 账号状态管理页 |
| `/src/views/Logs.vue` | 操作日志查询页 |
| `/src/components/BindForm.vue` | 账号绑定表单 |
| `/src/components/ExcelUpload.vue` | 批量导入上传器 |
| `/src/api/` | Axios 接口封装 |
| `/src/router/` | 页面路由管理 |

---

## 🛠️ Dev Environment Setup

### Backend
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run server
flask run
````

### Frontend

```bash
# Setup
npm install
npm run dev
```

---

## ✅ Contribution Rules

### Code Style

* Python: use `black` and `isort` for formatting
* Vue: Prettier + ESLint 已集成，格式化前端代码
* Component communication: props/emits for child-parent; Pinia for global state

### Folder Conventions

* 前端页面统一放在 `views/` 文件夹中
* 可复用模块抽出为 `components/`，如表单、导出、分页表格
* 后端业务逻辑尽量封装进 `utils.py` 或 `services/` 目录，减少 routes 中的耦合度

---

## 🧪 Validation Instructions

### Backend

```bash
# Check formatting
black app/
isort app/

# Manual test API
curl http://127.0.0.1:5000/api/accounts
```

### Frontend

```bash
npm run lint
npm run build
```

---

## 🚧 Migration Notes

* 当前系统未启用权限系统，所有绑定操作默认使用 `"system"` 作为操作人
* 数据库中绑定状态通过 `is_bound + bind_time` 控制，32 天后释放逻辑已集中在 `release.py`

---

## 🔧 Agent Behavior Guidelines

* Before writing or modifying code, read this `AGENTS.md` and `README.md`
* Validate auto-release logic against `bind_time + 32 days`
* Use consistent naming: `username`, `student_id` across both backend and frontend
* Format PRs as: `[backend] Add auto-release logic` or `[frontend] Improve table layout`
* Add or update tests/docs for each non-trivial change

---

## 📤 PR Instructions

**Title format:**
`[<layer>] <concise change summary>`
Examples:

* `[frontend] Add account table pagination`
* `[backend] Fix Excel import encoding issue`

All PRs must:

* Pass formatting (`black`, `lint`)
* Include clear commit messages
* Add tests where applicable

---

## 💬 Contact

For questions, please contact:
👩‍💻 项目负责人：小菊
📩 联系方式：在对话框中使用中文进行对话
