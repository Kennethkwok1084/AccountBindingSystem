# 开发文档 - CampusNet Account Management System

## 一、系统概述

本系统旨在帮助校园网络管理员统一管理学生的上网账号，核心功能包括：账号导入、学号绑定、使用状态查询、绑定日志记录以及绑定过期自动释放等。

适用于高校/宿舍场景的账号定期回收与分配。

---

## 二、功能模块说明

### 1. 账号导入模块

- 后端使用 `openpyxl` 解析上传的 Excel 表（第一行为表头）
- 账号、密码导入至 `accounts` 表，已存在账号不重复导入
- 前端通过 `ExcelUpload.vue` 实现上传组件，支持拖拽上传

### 2. 学号绑定模块

- 前端填写账号 + 学号，POST 到绑定接口
- 后端检查该账号未绑定，执行更新字段：
  - `is_bound = True`
  - `student_id = xxx`
  - `bind_time = 当前时间`
- 绑定成功后调用日志模块记录日志

### 3. 自动释放模块（后台任务）

- 每次页面访问或每日调度执行
- 遍历 `accounts` 表中 `is_bound = True` 且 `bind_time` 超过 32 天的数据
- 自动将其：
  - `is_bound = False`
  - `student_id = NULL`
  - `bind_time = NULL`

### 4. 状态查看模块

- 使用 Element Plus 的 `el-table` 实现数据展示
- 支持按绑定状态筛选、分页、模糊搜索
- 数据由 `/api/accounts` 返回 JSON 渲染前端

### 5. 日志记录模块

- 所有绑定操作由后端统一调用日志插入逻辑
- 日志记录信息：账号、学号、时间、操作人
- 展示页支持时间区间搜索、导出日志

### 6. 数据导出模块

- 后端调用 `pandas` 生成 Excel 表格
- 提供 `/export/accounts` 与 `/export/logs` 下载接口
- 文件命名自动含时间戳

---

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

