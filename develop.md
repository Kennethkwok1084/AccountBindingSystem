# 开发文档 - CampusNet Account Management System

## 一、系统概述

本系统旨在帮助校园网络管理员统一管理学生的上网账号，核心功能包括：账号导入、学号绑定、使用状态查询、绑定日志记录以及绑定过期自动释放等。

适用于高校/宿舍场景的账号定期回收与分配。

---

## 二、模块拆解

下表展示了系统的主要功能模块及其拆解步骤，后续实现时可逐项对照：

### 1. 账号导入模块

1. 实现接口 `/api/accounts/import`，使用 `openpyxl` 解析上传的 Excel（首行表头）
2. 将账号、密码写入 `accounts` 表，已存在账号跳过导入
3. 编写单元测试验证导入结果
4. 开发 `ExcelUpload.vue` 组件，支持拖拽上传

### 2. 学号绑定模块

1. 前端填写账号与学号，POST 到 `/api/accounts/bind`
2. 后端检查账号未被绑定，更新字段：
   - `is_bound = True`
   - `student_id = 学号`
   - `bind_time = 当前时间`
3. 写入 `binding_logs` 表记录操作人及时间
4. 为成功与失败场景编写测试用例

### 3. 自动释放模块（后台任务）

1. 每日调度或手动触发 `/api/auto-release` 接口
2. 查询 `accounts` 表中 `is_bound=True` 且 `bind_time` 超过 32 天的记录
3. 将其重置为未绑定状态：
   - `is_bound = False`
   - `student_id = NULL`
   - `bind_time = NULL`
4. 在 `binding_logs` 表记录 `auto_release` 动作
5. 编写任务脚本并补充测试

### 4. 状态查看模块

1. 在前端使用 Element Plus 的 `el-table` 展示账号列表
2. 支持按绑定状态筛选、分页与模糊搜索
3. 列表数据由 `/api/accounts` 返回的 JSON 渲染
4. 编写接口单元测试与前端页面测试

### 5. 日志记录模块

1. 在后端封装统一的日志插入函数
2. 记录账号、学号、时间、操作人及动作类型
3. 提供日志查询接口和导出功能
4. 开发前端日志列表页，可按时间区间搜索

### 6. 数据导出模块

1. 后端使用 `pandas` 生成 Excel 表格
2. 提供 `/export/accounts` 与 `/export/logs` 下载接口
3. 文件命名自动带时间戳
4. 编写导出相关测试

---

### 7. 模块进度追踪

| 模块 | 状态 | 备注 |
| ---- | ---- | ---- |
| 项目初始化 | ✅ 已完成，`pytest` 与 `vitest` 均通过 | 基础目录结构建立 |
| 账号导入模块 | ✅ 已完成 | `/accounts/import` 接口已实现 |
| 学号绑定模块 | ✅ 已完成 | `/accounts/bind` 接口已实现 |
| 自动释放模块 | ✅ 已完成 | `/auto-release` 接口已实现 |
| 状态查看模块 | ⬜ 未开始 | |
| 日志记录模块 | ⬜ 未开始 | |
| 数据导出模块 | ⬜ 未开始 | |

## 三、接口定义（节选）

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/accounts/import` | POST | Excel 导入账号 |
| `/api/accounts/bind` | POST | 绑定账号与学号 |
| `/api/accounts` | GET | 获取账号列表 |
| `/api/logs` | GET | 获取日志记录 |
| `/api/auto-release` | POST | 手动触发账号释放 |
| `/export/accounts` | GET | 导出账号 Excel |
| `/export/logs` | GET | 导出日志 Excel |

---

## 四、开发注意事项

- 所有绑定操作必须校验账号状态，避免重复绑定
- 导入功能必须支持重复上传同一文件不出错
- 日志中操作人默认为 system，后续可拓展为用户系统
- Excel 模板字段固定为 `username, password`
- 前端代码需使用 ESLint v9，配置文件为 `eslint.config.js`

---

## 五、自动任务建议

推荐使用 `APScheduler` 或系统级定时任务：

```bash
# 每天凌晨 3 点自动清理绑定超期账号
0 3 * * * /usr/bin/python3 /path/to/release.py
````

---

## 六、后续可扩展方向

* 账号分组功能（学号段/班级）
* 权限系统：支持不同操作人登录
* 批量绑定（前端选择多个账号绑定一批学号）
* WebSocket 实时更新绑定状态

