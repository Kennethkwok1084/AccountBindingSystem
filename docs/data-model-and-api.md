# 数据模型与 API 约定

本文档聚焦开发落地所需的数据结构、关键约束、REST 接口和 Excel 契约。完整 DDL 草案与示例响应见 [完整深度研究报告](./deep-research-report.md)。

## 1. 建模原则

- 当前有效绑定与历史台账必须分离。
- 账号分配、续费、释放、换绑都要可追溯。
- 批量操作必须有主表和明细表，方便预览、执行、失败重试和审计。
- 系统参数配置化，不把业务常量散落在代码中。

## 2. 核心表清单

| 表名 | 用途 |
|---|---|
| `admin_user` | 管理员账号 |
| `system_config` | 系统配置 |
| `account_batch` | 批次与优先级 |
| `mobile_account` | 移动账号池 |
| `student` | 学生基础资料与有效期 |
| `current_binding` | 当前有效绑定 |
| `binding_history` | 历史绑定台账 |
| `import_job` / `import_job_error` | 导入任务与逐行错误 |
| `operation_batch` / `operation_batch_detail` | 批量操作主表与明细 |
| `export_job` | 导出任务 |
| `alert_record` | 预警与待办 |
| `audit_log` | 审计日志 |
| `scheduler_run_log` | 调度任务运行日志 |

## 3. 关键数据关系

### 3.1 批次与账号

- 一个 `account_batch` 下有多个 `mobile_account`。
- `account_batch.priority` 决定分配优先级。
- `mobile_account.status` 至少覆盖 `available / assigned / disabled / expired`。

### 3.2 学生与绑定

- 一个学生同一时刻最多只有一个当前绑定。
- 一个移动账号同一时刻最多服务一个学生。
- 当前绑定落在 `current_binding`，历史变更落在 `binding_history`。

### 3.3 批量处理

- `operation_batch` 承载一次业务操作，如收费清单执行、批次换绑、手动换绑。
- `operation_batch_detail` 记录每一行的动作计划、执行结果、失败原因和关联导出信息。

## 4. 关键约束

| 约束 | 目的 |
|---|---|
| `student.student_no` 唯一 | 避免学生重复建档 |
| `mobile_account.account` 唯一 | 避免账号池重复 |
| `current_binding.student_id` 唯一 | 保证一个学生只有一个当前号 |
| `current_binding.mobile_account_id` 唯一 | 保证一个号同一时刻只绑定一个学生 |
| `account_batch.batch_code` 唯一 | 批次唯一识别 |

实现注意：

- 分配候选账号时加行锁。
- 批处理明细记录必须保留失败原因。
- 历史表采取追加写，不做覆盖更新。

## 5. 建议配置项

建议统一放入 `system_config`：

| 配置项 | 示例值 | 用途 |
|---|---|---|
| `system.timezone` | `Asia/Shanghai` | 系统时区 |
| `charge.last_processed_charge_time` | `2026-04-20 09:28:00` | 收费增量水位 |
| `package.month_days` | `31` | 包月顺延天数 |
| `package.year_days` | `365` | 包年顺延天数 |
| `batch.warn_days_default` | `1` | 批次预警提前天数 |
| `inventory.low_stock_threshold` | `50` | 低库存阈值 |
| `charge.max_execute_rows` | `20` | 收费执行人数上限 |
| `full_list.sheet_name` | `Sheet1` | 完整名单默认 Sheet |

## 6. API 通用约定

| 项目 | 约定 |
|---|---|
| 前缀 | `/api/v1` |
| 认证 | 登录后使用同域 Cookie |
| CSRF | 所有写操作要求 `X-CSRF-Token` |
| 幂等 | 执行类接口要求 `X-Idempotency-Key` |
| 成功响应 | `code / message / data / request_id` |
| 错误响应 | `code / message / details / request_id` |

推荐成功响应结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "req_20260420_xxxx"
}
```

## 7. 关键接口分组

### 7.1 认证与配置

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/auth/login` | 登录 |
| `POST` | `/auth/logout` | 登出 |
| `GET` | `/auth/me` | 当前登录态 |
| `PUT` | `/auth/password` | 修改管理员密码 |
| `GET` | `/config` | 查询配置 |
| `PUT` | `/config` | 更新配置 |

### 7.2 收费清单主链路

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/charge-batches/preview` | 上传收费清单并生成预览 |
| `POST` | `/charge-batches/{batch_id}/execute` | 执行收费批次 |
| `GET` | `/charge-batches` | 查询收费批次列表 |
| `GET` | `/operation-batches/{id}` | 查询批次摘要 |
| `GET` | `/operation-batches/{id}/details` | 查询批次明细 |

### 7.3 完整名单导入

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/full-students/import/preview` | 完整名单预览 |
| `POST` | `/full-students/import/{job_id}/execute` | 执行导入 |
| `GET` | `/imports/{job_id}` | 查询导入任务详情 |

### 7.4 换绑与台账

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/batch-rebinds/preview` | 批次换绑预览 |
| `POST` | `/batch-rebinds/{batch_id}/execute` | 批次换绑执行 |
| `POST` | `/bindings/manual-rebind` | 手动换绑 |
| `GET` | `/students/{student_no}` | 学生详情 |
| `GET` | `/students/{student_no}/history` | 学生历史台账 |
| `GET` | `/ledger/accounts/{account}` | 账号台账 |

### 7.5 导出、预警、调度、审计

| 方法 | 端点 | 说明 |
|---|---|---|
| `GET` | `/exports` | 导出记录列表 |
| `GET` | `/exports/{id}/download` | 下载导出文件 |
| `GET` | `/alerts` | 查询预警列表 |
| `PATCH` | `/alerts/{id}/resolve` | 处理预警 |
| `GET` | `/scheduler/jobs` | 查询任务清单 |
| `POST` | `/scheduler/run/{job_name}` | 手工触发任务 |
| `GET` | `/scheduler/runs` | 查询任务运行日志 |
| `GET` | `/audit-logs` | 查询审计日志 |

## 8. Excel 契约

### 8.1 账号池导入

- 用于创建批次与批量导入移动账号。
- 必须能识别账号、批次、批次类型、过期日等关键字段。
- 非法账号、重复账号、缺失批次信息要落导入错误明细。

### 8.2 收费清单导入

- 关键字段至少包括学号、姓名、收费时间、套餐、金额。
- 预览时完成增量识别、排序、分类。
- 执行时沿用预览结果，不重新改变业务口径。

### 8.3 完整学生名单导入

- 用于校正有效期与释放到期绑定。
- 若名单中的账号和系统当前绑定不一致，只生成冲突告警。

### 8.4 固定导出模板

导出列必须固定为：

| 列顺序 | 列名 | 说明 |
|---|---|---|
| 1 | 学号 | 必填 |
| 2 | 移动账户 | 必填 |
| 3 | 移动密码 | 固定为 `123123` |
| 4 | 联通账户 | 必须存在且为空 |
| 5 | 联通密码 | 必须存在且为空 |
| 6 | 电信账户 | 必须存在且为空 |
| 7 | 电信密码 | 必须存在且为空 |

命名规则固定为 `移动YYMMDDHHmm.xlsx`。

## 9. 高风险实现点

- 收费水位若只按时间戳判断，边界场景可能漏单或重单。
- 候选账号选择若不加锁，会产生并发重复分配。
- 若预览与执行使用两套不同规则，联调时会出现“预览对、执行错”。
- 手动换绑若未同时处理旧号状态和历史记录，会造成台账断裂。
- 导出模板只要列顺序变化，就会影响现网后台导入。
