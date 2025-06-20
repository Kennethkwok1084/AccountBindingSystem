
# CampusNet Account Management System (CNAMS)

本系统为校园网账号管理提供一站式解决方案，支持账号批量导入、学号绑定、绑定状态管理、自动释放机制及日志记录。

## 📦 功能模块

- ✅ 支持通过 Excel 批量导入校园网账号（账号 + 密码）
- ✅ 学号绑定功能，记录账号绑定关系
- ✅ 前端基于 Vue3 + Element Plus，美观实用
- ✅ 绑定状态可视化查询，分页+筛选
- ✅ 自动释放功能：绑定满 32 天后自动重置为未使用状态
- ✅ 日志记录功能：记录所有绑定操作（时间 + 学号 + 账号）
- ✅ 导出账号与日志为 Excel 文件

## 📁 项目结构

```

backend/
├── app/
│   ├── models.py
│   ├── routes.py
│   ├── utils.py
├── tasks/
│   └── release.py
├── uploads/
├── config.py
├── run.py

frontend/
├── src/
│   ├── views/
│   ├── components/
│   ├── api/
│   ├── App.vue
│   └── main.js

````

## 🔧 技术栈

- 后端：Flask + SQLAlchemy
- 数据库：MySQL
- 前端：Vue3 + Element Plus
- 代码规范：使用 ESLint v9，配置文件为 `eslint.config.js`
- 解析导入：openpyxl
- 导出支持：pandas + xlsxwriter

## 🚀 快速启动

### 后端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run
````

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 🗂️ 数据库结构


### `accounts`

| 字段名          | 类型       | 描述             |
| ------------ | -------- | -------------- |
| id           | INT      | 自增主键           |
| username     | VARCHAR  | 账号             |
| password     | VARCHAR  | 明文密码           |
| is\_bound    | BOOLEAN  | 是否绑定           |
| student\_id  | VARCHAR  | 绑定学号（为空表示未绑定）  |
| bind\_time   | DATETIME | 上次绑定时间         |
| create\_time | DATETIME | 账号导入时间 ✅（建议新增） |

---

### `binding_logs`

| 字段名         | 类型       | 描述                                |
| ----------- | -------- | --------------------------------- |
| id          | INT      | 自增主键                              |
| username    | VARCHAR  | 操作对象账号                            |
| student\_id | VARCHAR  | 对应学号                              |
| bind\_time  | DATETIME | 操作时间                              |
| operator    | VARCHAR  | 操作者，默认 system                     |
| action      | VARCHAR  | 操作类型（如 bind、auto\_release）✅（建议新增） |

## 📋 开发说明请见 develop.md
