# 校园网移动运营商账号池管理系统完整项目文档

> 文档导航：为便于开发协作，当前总报告已拆分出一组配套文档，可结合阅读。
>
> - [文档导航](./README.md)
> - [需求基线与业务规则](./product-requirements.md)
> - [系统架构设计](./system-architecture.md)
> - [数据模型与 API 约定](./data-model-and-api.md)
> - [工程澄清与风险清单](./engineering-clarifications.md)
> - [部署、运维与测试](./deployment-testing.md)
>
> 本文档继续作为细节总库，保留完整论证、DDL 草案、API 示例、测试与实施细节。
>
> 当前实现版已经统一采用 PostgreSQL、Alembic 迁移和 Vue 3 自定义中后台界面；若本文历史论证与代码实现存在差异，请以拆分文档和仓库代码为准。

## 执行摘要

本报告给出一套可直接进入设计、开发、联调与上线阶段的“校园网移动运营商账号池管理系统”完整项目文档，目标是在**不偏离已确认业务规则**的前提下，把“移动 PPPoE 账号池管理、收费清单增量处理、批次到期预警、人工确认换绑、Excel 模板导出、台账审计与内网部署”固化为一套稳定、可追溯、便于后续维护的系统方案。系统建议采用**前后端分离**：前端使用 Vue 3，优先使用 Vue 官方推荐的 `<script setup>` 与 Vue Router 组合式 API；后端使用 Flask，按官方推荐的应用工厂与蓝图组织方式进行模块化；调度使用 APScheduler 3.x，并把调度器独立成单独进程/容器以避免重复执行；数据库使用 MySQL InnoDB；部署使用 Docker Compose，并用 `depends_on` 与 healthcheck 管理服务启动顺序。上述栈与组织方式均能在官方文档中找到直接支持。citeturn5view0turn5view1turn5view12turn7view3turn7view4turn7view1turn11search1turn5view4turn5view5

本方案的核心设计是把**当前绑定关系**与**历史台账**彻底分离：`current_binding` 只保存“此刻有效”的学生—移动账号关系，`binding_history` 保存“分配、续费顺延、释放、换绑、禁用、人工修正”等全过程；批量执行采用“**先预览、后执行**”两阶段；执行阶段采用短事务与唯一约束兜底，并在候选账号选择时使用 `SELECT ... FOR UPDATE` 锁定行，避免同一账号被并发抢占。MySQL 官方资料说明 InnoDB 默认隔离级别是 `REPEATABLE READ`，`SELECT ... FOR UPDATE` 会对读取结果加排他锁，因此该方案适合账号分配这类读改写一致性场景。citeturn5view9turn10search0turn10search2

在安全与运维上，本系统按照“**单管理员、内网、最小权限、可备份恢复**”设计。管理员密码不使用可逆加密保存，优先采用 OWASP 推荐的 Argon2id；若环境限制不便引入额外依赖，则使用 Python 标准库可用的 `pbkdf2_hmac` 或 `scrypt` 作为回退方案。数据库逻辑备份采用 `mysqldump`；日志采用 Python 官方 `logging`；Excel 读写采用 pandas 的 `read_excel` / `to_excel`。这些能力均有官方资料支持。citeturn5view8turn8view0turn8view1turn5view11turn7view6turn5view6turn5view7

## 项目背景与范围

### 项目背景与建设目标

当前业务的真实痛点不是“能不能导 Excel”，而是**账号池状态失真、批次到期前无法稳定预警、台账难追溯、人工 Excel 处理容易重复分配或漏分配**。因此，本项目不是一个普通的“导入导出工具”，而是一套围绕移动账号生命周期的**轻量业务中台**。它应当把四条业务主线收口到同一套数据模型中：

1. 移动账号池导入、可用性管理、禁用与恢复。
2. 收费清单增量识别、预览、执行与导出。
3. 完整学生名单导入、有效期校正与到期释放。
4. 批次失效预警、批量换绑预览与执行、以及完整台账审计。

系统上线后的直接目标如下：

| 目标 | 说明 |
|---|---|
| 防止重复分配 | 同一移动账号同一时刻只能绑定一个学号 |
| 保证可追溯 | 任一账号用过谁、任一学号用过什么账号，都可追溯 |
| 降低人工错误 | 收费清单和完整名单都通过模板校验与预览 |
| 支持到期治理 | 批次 D-1 预警、到期释放、人工确认批量换绑 |
| 满足现有后台衔接 | 导出的 Excel 列顺序和命名规则固定，不改变现网操作习惯 |

### 已确认的固定业务规则

以下规则**直接来自已确认业务约束**，应视为第一版不可变更的验收基线：

| 规则项 | 已确认内容 |
|---|---|
| 运营商范围 | 仅管理移动账号 |
| 移动密码 | 统一为 `123123` |
| 批次有效期 | 普通批次默认一年；`0元账号` 视为长期有效 |
| 分配优先级 | 优先新批次分配 |
| 分配顺序 | 按收费时间升序，优先最早开通的 20 人，其余报错 |
| 套餐有效期计算 | 包月按 31 天；包年按 365 天 |
| 校正规则 | 收费记录先推算，完整学生名单为最终校正依据 |
| 自动任务 | 每天凌晨执行 |
| 批次预警 | 提前 1 天预警某批次明天失效 |
| 导出模板固定列 | 学号、移动账户、移动密码、联通账户、联通密码、电信账户、电信密码 |
| 模板空列要求 | 联通/电信列必须存在但必须为空 |
| 导出文件命名 | `移动YYMMDDHHmm` |
| 使用角色 | 单管理员 |
| 部署环境 | Linux 内网 |
| 技术假设 | 前后端分离、MySQL、Flask、Vue3 |

### 范围与不包含项

| 类别 | 包含项 | 不包含项 |
|---|---|---|
| 账号管理 | 移动账号导入、禁用、恢复、状态流转 | 联通/电信账号真实管理 |
| 学生数据 | 收费清单、完整学生名单、当前绑定与历史台账 | 学校收费系统本身 |
| 批量处理 | 收费清单预览执行、批次换绑预览执行 | 直接调用现有后台接口自动入库 |
| 调度 | 批次预警、低库存预警、到期释放 | 实时消息推送到企业微信/短信（未指定） |
| 权限 | 单管理员登录、审计日志 | 多角色 RBAC、SSO（未指定） |
| 文件处理 | `.xlsx` 导入与导出 | OCR、图片识别、PDF 导入 |

### 未指定但必须显式标注的事项

以下细节在现有需求中**未明确给出**，本方案按“可落地默认值”处理，同时保留配置项：

| 未指定项 | 本方案默认值 | 备注 |
|---|---|---|
| 系统时区 | `Asia/Shanghai` | 必须写入 `system_config`；若部署地不同，可调整 |
| 完整名单 Excel Sheet 名 | `Sheet1` | 可配置 |
| 完整名单列名别名 | 采用列名映射配置 | 因源文件列名格式未完全指定 |
| 低库存预警阈值 | 上线前配置 | 需求未指定，不写死 |
| `0元账号` 相对普通新批次的优先级 | 默认低于普通新批次 | 避免长期号被过早耗尽；可在批次优先级中调整 |
| 批次到期后是否自动批量换绑 | 默认“自动预警 + 人工确认执行” | 因“全自动换绑”未最终指定，先采用保守方案 |
| 收费时间完全相同的跨批次水位处理 | 仍按 `> last_processed_charge_time` | 该规则已确认，但建议后续升级为 `(time,row_hash)` 水位 |

## 总体架构与关键设计原则

### 总体技术架构

推荐部署拓扑如下：

| 层级 | 组件 | 作用 |
|---|---|---|
| 接入层 | Nginx | 同域提供前端静态资源，并反向代理 `/api` 到 Flask |
| 前端层 | Vue 3 + Vue Router + Ant Design Vue | 表单、表格、文件上传、预览执行、台账查询 |
| API 层 | Flask + SQLAlchemy | 业务规则、导入校验、分配逻辑、导出生成 |
| 调度层 | APScheduler 3.x 独立进程 | 凌晨自动任务、预警、释放 |
| 数据层 | MySQL InnoDB | 关系数据、约束、索引、事务 |
| 文件层 | 本地挂载卷 | 原始上传文件、导出文件、备份 |

之所以建议 Flask 采用“**应用工厂 + 蓝图**”，是因为 Flask 官方明确建议扩展对象不要在定义时绑定到应用实例，蓝图也正是用于大型应用组件化与公共模式复用；官方还说明生产模式下 Flask 会把异常写入 logger，因此集中错误处理与结构化日志是合理做法。前端方面，Vue 官方明确推荐在 SFC 中使用 `<script setup>`，Vue Router 官方提供了全局守卫和组合式 API 守卫，适合这个系统里“登录态保护”“预览页防误离开”等场景；Ant Design Vue 官方组件库也直接覆盖 Form、Table、Upload 等中后台核心部件。citeturn5view0turn5view1turn5view2turn5view12turn7view3turn7view4turn1search1turn2search0turn3search0

### 模块边界与目录建议

后端建议按业务域拆分蓝图：

- `auth`：登录、退出、修改密码、当前用户。
- `dashboard`：统计、待办中心、最近导入导出。
- `accounts`：账号池、批次、禁用与恢复。
- `students`：学生基础资料、当前绑定、历史查询。
- `imports`：账号池导入、收费清单导入、完整名单导入。
- `operations`：收费清单预览执行、批次换绑预览执行、手动换绑。
- `exports`：导出任务、文件下载。
- `alerts`：预警列表、处理状态。
- `scheduler`：任务查询、手工触发、任务运行日志。
- `audit`：审计日志。

前端建议对应路由页面：

- `/login`
- `/dashboard`
- `/accounts`
- `/batches`
- `/imports/account-pool`
- `/imports/full-list`
- `/operations/charge-preview`
- `/operations/batch-rebind`
- `/operations/manual-rebind`
- `/exports`
- `/ledger/students`
- `/ledger/accounts`
- `/alerts`
- `/settings`

### 一致性、并发与幂等性原则

本系统虽然是单管理员，但仍然存在**后台调度器**与**人工操作**并发更新账号状态的可能，因此不能假设“不会并发”。一致性原则如下：

1. `current_binding` 表**只保留当前有效绑定**，并对 `student_id` 与 `mobile_account_id` 都加唯一约束。
2. 所有“账号分配/换绑/释放”都必须写入 `binding_history`。
3. 账号候选获取必须在事务内完成，且对候选行使用 `SELECT ... FOR UPDATE`，避免被并发事务重复抢占。MySQL 官方文档说明该语句会对读取到的行加排他锁。citeturn10search0turn10search2
4. 批处理采用“**预览无副作用，执行有副作用**”模式。
5. 执行端点必须支持幂等键，避免双击提交或浏览器重放导致重复执行。
6. 不使用 `SKIP LOCKED` 做常规账号分配。MySQL 官方文档指出 `SKIP LOCKED` 会返回不一致视图，更适合队列式场景，不适合作为一般事务工作流的默认方案。citeturn12search0turn12search2
7. SQLAlchemy 侧遵循 Session 事务边界与 flush 机制：对象变更在事务中统一发出 SQL，失败即可回滚当前事务。citeturn7view0

### 收费清单处理流程图

下面的流程图用于直接指导“收费清单导入—预览—执行—导出”的开发实现：

```mermaid
flowchart TD
    A[上传收费清单 Excel] --> B[模板与列校验]
    B -->|失败| B1[生成导入错误记录并结束]
    B -->|成功| C[解析行数据]
    C --> D[筛选 charge_time > last_processed_charge_time]
    D --> E[按 charge_time 升序排序]
    E --> F[逐行分类]
    F --> F1{学生是否已有当前绑定?}
    F1 -->|否| G[计划: 新分配]
    F1 -->|是| F2{当前有效期是否覆盖?}
    F2 -->|是| H[计划: 续费顺延，不换账号]
    F2 -->|否| I[计划: 需要换绑]
    G --> J[汇总预览结果]
    H --> J
    I --> J
    J --> K[管理员确认执行]
    K -->|取消| K1[结束，不落业务数据]
    K -->|确认| L[逐行事务执行]
    L --> M{成功?}
    M -->|是| N[写 current_binding / binding_history / export_job明细]
    M -->|否| O[写失败原因]
    N --> P[更新 operation_batch 汇总]
    O --> P
    P --> Q[生成导出Excel]
    Q --> R[更新 last_processed_charge_time]
```

### 定时调度设计原则

APScheduler 官方资料说明：它本质上是一个应用内任务调度库，不是独立守护进程；如果把任务持久化到数据库，则调度器重启后仍可保留任务状态并补跑错过的任务。3.x 文档同时支持 `max_instances`、`misfire_grace_time` 和 `coalesce` 等参数。基于这些能力，本方案建议把调度器单独部署为一个容器或进程，使用 `SQLAlchemyJobStore` 持久化任务，所有计划任务统一配置 `max_instances=1`、合理的 `misfire_grace_time` 和 `coalesce=True`，以避免重启后重复释放或重复创建预警。citeturn7view1turn11search1turn11search3turn11search4

## 详细功能需求与前端交互

### 功能模块总表

| 模块 | 目标 | 主要能力 | 权限 |
|---|---|---|---|
| 登录与系统设置 | 管理员进入系统并维护基础配置 | 登录、退出、改密、查看当前用户、修改系统参数 | 未登录可访问登录；其余仅管理员 |
| 账号池管理 | 管理移动账号库存 | Excel 导入、列表、状态筛选、禁用/恢复、历史查看 | 管理员 |
| 批次管理 | 维护批次与优先级 | 查看批次、状态、优先级、到期时间、账号规模 | 管理员 |
| 完整名单导入 | 校正有效期与当前真实状态 | 上传、校验、预览、执行、冲突记录 | 管理员 |
| 收费清单处理 | 增量识别并生成导入模板 | 上传、预览、执行、导出 | 管理员 |
| 批次换绑 | 处理 D-1 预警批次的后续换绑 | 受影响名单预览、分配新号、导出模板 | 管理员 |
| 手动换绑 | 处理个别账号异常 | 搜索学号、选择新号、原号禁用/释放、单行导出 | 管理员 |
| 台账与审计 | 追溯账号与学生历史 | 当前绑定、历史绑定、导入导出记录、审计日志 | 管理员 |
| 预警与待办 | 管理低库存、批次失效、失败任务 | 未处理预警列表、处理闭环 | 管理员 |

### 前端页面原型与组件建议

前端建议基于 Vue 3 + Vue Router + Ant Design Vue，使用 `<script setup>` 组织页面逻辑；路由层使用全局前置守卫校验登录态，在“导入预览页、手动换绑页”使用 `onBeforeRouteLeave` 阻止未保存离开。Ant Design Vue 的 Form、Table、Upload 组件天然适合本系统的“表单录入 + 表格预览 + 文件上传”场景。citeturn5view12turn7view3turn7view4turn1search1turn2search0turn3search0

| 页面 | 关键组件 | 核心字段 | 交互说明 |
|---|---|---|---|
| 登录页 | `a-form` `a-input-password` `a-button` | 用户名、密码 | 登录成功后跳转首页 |
| 首页/仪表盘 | `a-card` `a-statistic` `a-table` `a-alert` | 可用账号数、已分配数、待办数、最近任务 | 卡片点击进入对应列表 |
| 账号池管理 | `a-upload` `a-table` `a-select` `a-tag` `a-modal` | 账号、批次、状态、禁用原因 | 支持筛选、禁用、恢复、看历史 |
| 批次管理 | `a-table` `a-form` `a-date-picker` `a-input-number` | 批次号、类型、过期日、优先级 | 管理优先级，查看库存分布 |
| 完整名单导入 | `a-upload-dragger` `a-table` `a-result` | 文件、导入摘要、冲突明细 | 上传后预览，确认执行 |
| 收费清单预览 | `a-upload-dragger` `a-table` `a-tabs` `a-button` | 上次水位、本次新增、计划动作、失败原因 | 先预览，后执行，执行后可下载导出文件 |
| 批次换绑预览 | `a-table` `a-descriptions` `a-button` | 受影响学号、旧账号、新账号、失败原因 | 由预警中心跳转进入 |
| 手动换绑 | `a-form` `a-auto-complete` `a-table` `a-drawer` | 学号、当前账号、候选账号、是否禁用旧号 | 支持执行并立即导出单行 Excel |
| 导出记录 | `a-table` `a-button` | 文件名、来源操作批次、行数、下载时间 | 点击即下载 |
| 台账查询 | `a-tabs` `a-form` `a-timeline` `a-table` | 学号/账号、当前状态、历史记录 | 支持按学生与按账号双视角查询 |
| 预警中心 | `a-table` `a-tag` `a-button` | 类型、级别、内容、状态 | 处理后标记已解决 |
| 系统设置 | `a-form` `a-switch` `a-input-number` | 水位时间、低库存阈值、时区、预警天数 | 仅管理员可改 |

### 关键交互流程

#### 收费清单页

1. 上传文件。
2. 后端返回“模板校验结果 + 本次增量识别结果”。
3. 页面用 Tab 展示“新分配 / 续费顺延 / 需换绑 / 失败”四类。
4. 管理员确认执行。
5. 执行成功后自动跳出导出记录卡片，支持下载 Excel。
6. 若执行中有部分失败，页面展示“成功数/失败数/失败原因汇总”。

#### 完整名单导入页

1. 上传完整名单。
2. 展示“可校正记录数、到期释放数、冲突数”。
3. 点击执行后，系统写入 `student.source_expire_at`、释放到期账号、生成冲突预警。
4. 若存在系统绑定与名单绑定不一致，只生成冲突，不自动覆盖当前绑定。

#### 手动换绑页

1. 输入学号。
2. 拉取当前绑定、有效期、所属批次、候选新账号。
3. 选择新账号，并指定旧号处理方式：**禁用**或**释放**。
4. 执行后即生成单行导出文件，供后台导入。

## 数据库与后端接口

### 数据库设计说明

本设计以 MySQL 8.x 的 InnoDB 为基础，依赖其事务能力、唯一索引、外键与行锁机制；约束命名也遵从 MySQL `CREATE TABLE` 语义。账号分配路径使用短事务与 `FOR UPDATE` 锁行；日志与历史记录采用追加写入，避免回写覆盖。citeturn5view10turn5view9turn10search0

### 数据库表清单

| 表名 | 作用 |
|---|---|
| `admin_user` | 单管理员账户 |
| `system_config` | 系统配置键值表 |
| `account_batch` | 账号批次与优先级 |
| `import_job` | 文件导入任务主表 |
| `import_job_error` | 导入逐行错误 |
| `student` | 学生基础信息与有效期 |
| `mobile_account` | 移动账号池 |
| `operation_batch` | 业务执行批次主表，承载收费处理/批次换绑/手动换绑 |
| `operation_batch_detail` | 业务执行批次明细 |
| `current_binding` | 当前有效绑定关系 |
| `binding_history` | 历史台账 |
| `export_job` | 导出文件任务 |
| `alert_record` | 预警与待办 |
| `audit_log` | 审计日志 |
| `scheduler_run_log` | 调度任务运行日志 |

### 关键表字段说明

#### `account_batch`

| 字段 | 类型 | 约束/索引 | 说明 | 示例 |
|---|---|---|---|---|
| `id` | BIGINT | PK | 主键 | `1` |
| `batch_code` | VARCHAR(32) | UNIQUE | 批次号 | `202509` |
| `batch_type` | ENUM | idx | `normal/zero` | `normal` |
| `priority` | INT | idx | 分配优先级，值越大越优先 | `100` |
| `expire_at` | DATE | idx | 到期日；长期批次可空 | `2026-09-30` |
| `warn_days` | INT |  | 预警提前天数 | `1` |
| `status` | ENUM | idx | `active/expired/disabled` | `active` |

#### `mobile_account`

| 字段 | 类型 | 约束/索引 | 说明 | 示例 |
|---|---|---|---|---|
| `id` | BIGINT | PK | 主键 | `1001` |
| `account` | VARCHAR(64) | UNIQUE | 移动账号 | `yd001234` |
| `password` | VARCHAR(64) |  | 固定为 `123123` | `123123` |
| `batch_id` | BIGINT | FK + idx | 所属批次 | `1` |
| `status` | ENUM | idx | `available/assigned/disabled/expired` | `available` |
| `disabled_reason` | VARCHAR(255) |  | 禁用原因 | `拨号不可用` |
| `last_assigned_at` | DATETIME |  | 最近分配时间 | `2026-04-20 09:30:00` |

#### `student`

| 字段 | 类型 | 约束/索引 | 说明 | 示例 |
|---|---|---|---|---|
| `id` | BIGINT | PK | 主键 | `5001` |
| `student_no` | VARCHAR(32) | UNIQUE | 学号 | `2023001001` |
| `name` | VARCHAR(64) | idx | 姓名 | `张三` |
| `current_package_name` | VARCHAR(128) |  | 当前套餐 | `30元移动包月75M` |
| `current_fee_amount` | DECIMAL(10,2) |  | 当前金额 | `30.00` |
| `expected_expire_at` | DATE | idx | 按收费记录推算的到期日 | `2026-05-20` |
| `source_expire_at` | DATE | idx | 按完整名单校正的到期日 | `2026-05-18` |
| `last_charge_time` | DATETIME | idx | 最近收费时间 | `2026-04-20 09:10:00` |

#### `current_binding`

| 字段 | 类型 | 约束/索引 | 说明 | 示例 |
|---|---|---|---|---|
| `id` | BIGINT | PK | 主键 | `8001` |
| `student_id` | BIGINT | UNIQUE + FK | 当前学生 | `5001` |
| `mobile_account_id` | BIGINT | UNIQUE + FK | 当前账号 | `1001` |
| `bind_source` | ENUM | idx | `initial/charge_import/batch_rebind/manual/reconcile` | `charge_import` |
| `bind_type` | ENUM |  | `allocate/rebind/manual_fix` | `allocate` |
| `bind_at` | DATETIME | idx | 绑定时间 | `2026-04-20 09:32:00` |
| `expire_at` | DATE | idx | 当前生效到期日 | `2026-05-20` |

#### `binding_history`

| 字段 | 类型 | 约束/索引 | 说明 | 示例 |
|---|---|---|---|---|
| `id` | BIGINT | PK | 主键 | `9001` |
| `student_id` | BIGINT | FK + idx | 学生 | `5001` |
| `old_mobile_account_id` | BIGINT | FK | 旧账号 | `1000` |
| `new_mobile_account_id` | BIGINT | FK | 新账号 | `1001` |
| `action_type` | ENUM | idx | `allocate/renew/release/rebind/disable/enable/manual_fix` | `rebind` |
| `old_expire_at` | DATE |  | 旧到期日 | `2026-04-30` |
| `new_expire_at` | DATE |  | 新到期日 | `2026-05-31` |
| `detail_json` | JSON |  | 额外上下文 | `{"reason":"batch_expire"}` |
| `created_at` | DATETIME | idx | 记录时间 | `2026-04-20 09:35:00` |

### 数据库 DDL SQL 脚本草案

下面的 DDL 脚本草案可直接作为 MySQL 8.x 起始版本。它假定使用 InnoDB、UTF8MB4、追加式历史表、当前绑定唯一约束，以及用于批次与导入导出的日志表。citeturn5view9turn5view10turn10search0

```sql
CREATE DATABASE IF NOT EXISTS campus_mobile_pool
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE campus_mobile_pool;

DROP TABLE IF EXISTS scheduler_run_log;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS alert_record;
DROP TABLE IF EXISTS export_job;
DROP TABLE IF EXISTS binding_history;
DROP TABLE IF EXISTS current_binding;
DROP TABLE IF EXISTS operation_batch_detail;
DROP TABLE IF EXISTS operation_batch;
DROP TABLE IF EXISTS mobile_account;
DROP TABLE IF EXISTS student;
DROP TABLE IF EXISTS import_job_error;
DROP TABLE IF EXISTS import_job;
DROP TABLE IF EXISTS account_batch;
DROP TABLE IF EXISTS system_config;
DROP TABLE IF EXISTS admin_user;

CREATE TABLE admin_user (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    password_algo VARCHAR(32) NOT NULL DEFAULT 'argon2id',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_admin_user_username UNIQUE (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE system_config (
    config_key VARCHAR(64) PRIMARY KEY,
    config_value JSON NOT NULL,
    remark VARCHAR(255) NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE account_batch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    batch_code VARCHAR(32) NOT NULL,
    batch_name VARCHAR(64) NULL,
    batch_type ENUM('normal', 'zero') NOT NULL DEFAULT 'normal',
    priority INT NOT NULL DEFAULT 100,
    expire_at DATE NULL,
    warn_days INT NOT NULL DEFAULT 1,
    status ENUM('active', 'expired', 'disabled') NOT NULL DEFAULT 'active',
    remark VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_account_batch_code UNIQUE (batch_code),
    INDEX idx_account_batch_status_expire (status, expire_at),
    INDEX idx_account_batch_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE import_job (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    job_type ENUM('account_pool', 'charge_list', 'full_student_list') NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_path VARCHAR(255) NOT NULL,
    file_checksum VARCHAR(64) NULL,
    sheet_name VARCHAR(64) NULL,
    mapping_json JSON NULL,
    status ENUM('uploaded', 'validating', 'validated', 'executing', 'success', 'partial_success', 'failed') NOT NULL DEFAULT 'uploaded',
    total_rows INT NOT NULL DEFAULT 0,
    success_rows INT NOT NULL DEFAULT 0,
    failed_rows INT NOT NULL DEFAULT 0,
    error_summary VARCHAR(500) NULL,
    operator_id BIGINT NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_import_job_operator FOREIGN KEY (operator_id) REFERENCES admin_user(id),
    INDEX idx_import_job_type_status (job_type, status),
    INDEX idx_import_job_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE import_job_error (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    import_job_id BIGINT NOT NULL,
    row_no INT NOT NULL,
    field_name VARCHAR(64) NULL,
    error_code VARCHAR(64) NOT NULL,
    error_message VARCHAR(255) NOT NULL,
    raw_data JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_import_job_error_job FOREIGN KEY (import_job_id) REFERENCES import_job(id) ON DELETE CASCADE,
    INDEX idx_import_job_error_job_row (import_job_id, row_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE student (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    student_no VARCHAR(32) NOT NULL,
    name VARCHAR(64) NOT NULL,
    current_package_name VARCHAR(128) NULL,
    current_fee_amount DECIMAL(10,2) NULL,
    expected_expire_at DATE NULL,
    source_expire_at DATE NULL,
    last_charge_time DATETIME NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    remark VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_no UNIQUE (student_no),
    INDEX idx_student_name (name),
    INDEX idx_student_source_expire (source_expire_at),
    INDEX idx_student_expected_expire (expected_expire_at),
    INDEX idx_student_last_charge_time (last_charge_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE mobile_account (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    account VARCHAR(64) NOT NULL,
    password VARCHAR(64) NOT NULL DEFAULT '123123',
    batch_id BIGINT NOT NULL,
    status ENUM('available', 'assigned', 'disabled', 'expired') NOT NULL DEFAULT 'available',
    disabled_reason VARCHAR(255) NULL,
    source_import_job_id BIGINT NULL,
    last_assigned_at DATETIME NULL,
    last_released_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_mobile_account_account UNIQUE (account),
    CONSTRAINT fk_mobile_account_batch FOREIGN KEY (batch_id) REFERENCES account_batch(id),
    CONSTRAINT fk_mobile_account_import_job FOREIGN KEY (source_import_job_id) REFERENCES import_job(id) ON DELETE SET NULL,
    INDEX idx_mobile_account_batch_status (batch_id, status),
    INDEX idx_mobile_account_status_batch (status, batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE operation_batch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    batch_no VARCHAR(40) NOT NULL,
    operation_type ENUM('charge_import', 'batch_rebind', 'manual_rebind', 'full_reconcile') NOT NULL,
    related_batch_id BIGINT NULL,
    import_job_id BIGINT NULL,
    last_processed_charge_time_before DATETIME NULL,
    last_processed_charge_time_after DATETIME NULL,
    preview_rows INT NOT NULL DEFAULT 0,
    to_allocate_count INT NOT NULL DEFAULT 0,
    to_renew_count INT NOT NULL DEFAULT 0,
    to_rebind_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    fail_count INT NOT NULL DEFAULT 0,
    status ENUM('previewed', 'executing', 'executed', 'partial_success', 'failed', 'cancelled') NOT NULL DEFAULT 'previewed',
    operator_id BIGINT NOT NULL,
    remark VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_operation_batch_no UNIQUE (batch_no),
    CONSTRAINT fk_operation_batch_related_batch FOREIGN KEY (related_batch_id) REFERENCES account_batch(id) ON DELETE SET NULL,
    CONSTRAINT fk_operation_batch_import_job FOREIGN KEY (import_job_id) REFERENCES import_job(id) ON DELETE SET NULL,
    CONSTRAINT fk_operation_batch_operator FOREIGN KEY (operator_id) REFERENCES admin_user(id),
    INDEX idx_operation_batch_type_status (operation_type, status),
    INDEX idx_operation_batch_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE current_binding (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    student_id BIGINT NOT NULL,
    mobile_account_id BIGINT NOT NULL,
    bind_source ENUM('initial', 'charge_import', 'batch_rebind', 'manual', 'reconcile') NOT NULL,
    bind_type ENUM('allocate', 'rebind', 'manual_fix') NOT NULL,
    bind_at DATETIME NOT NULL,
    expire_at DATE NULL,
    remark VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_current_binding_student FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE CASCADE,
    CONSTRAINT fk_current_binding_mobile_account FOREIGN KEY (mobile_account_id) REFERENCES mobile_account(id) ON DELETE CASCADE,
    CONSTRAINT uq_current_binding_student UNIQUE (student_id),
    CONSTRAINT uq_current_binding_mobile_account UNIQUE (mobile_account_id),
    INDEX idx_current_binding_expire (expire_at),
    INDEX idx_current_binding_bind_at (bind_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE operation_batch_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    operation_batch_id BIGINT NOT NULL,
    row_no INT NOT NULL,
    student_id BIGINT NULL,
    student_no VARCHAR(32) NOT NULL,
    name VARCHAR(64) NULL,
    package_name VARCHAR(128) NULL,
    fee_amount DECIMAL(10,2) NULL,
    charge_time DATETIME NULL,
    action_plan ENUM('allocate', 'renew', 'rebind', 'skip', 'fail') NOT NULL,
    old_mobile_account_id BIGINT NULL,
    new_mobile_account_id BIGINT NULL,
    result_status ENUM('pending', 'success', 'failed', 'skipped') NOT NULL DEFAULT 'pending',
    result_code VARCHAR(64) NULL,
    result_message VARCHAR(255) NULL,
    source_row_json JSON NULL,
    extra_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_operation_batch_detail_batch FOREIGN KEY (operation_batch_id) REFERENCES operation_batch(id) ON DELETE CASCADE,
    CONSTRAINT fk_operation_batch_detail_student FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE SET NULL,
    CONSTRAINT fk_operation_batch_detail_old_account FOREIGN KEY (old_mobile_account_id) REFERENCES mobile_account(id) ON DELETE SET NULL,
    CONSTRAINT fk_operation_batch_detail_new_account FOREIGN KEY (new_mobile_account_id) REFERENCES mobile_account(id) ON DELETE SET NULL,
    CONSTRAINT uq_operation_batch_detail_row UNIQUE (operation_batch_id, row_no),
    INDEX idx_operation_batch_detail_student_no (student_no),
    INDEX idx_operation_batch_detail_action (action_plan, result_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE binding_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    student_id BIGINT NOT NULL,
    old_mobile_account_id BIGINT NULL,
    new_mobile_account_id BIGINT NULL,
    action_type ENUM('allocate', 'renew', 'release', 'rebind', 'disable', 'enable', 'manual_fix') NOT NULL,
    package_name VARCHAR(128) NULL,
    charge_time DATETIME NULL,
    old_expire_at DATE NULL,
    new_expire_at DATE NULL,
    source ENUM('charge_list', 'full_list', 'scheduler', 'manual', 'system') NOT NULL,
    operation_batch_id BIGINT NULL,
    import_job_id BIGINT NULL,
    operator_id BIGINT NULL,
    detail_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_binding_history_student FOREIGN KEY (student_id) REFERENCES student(id),
    CONSTRAINT fk_binding_history_old_account FOREIGN KEY (old_mobile_account_id) REFERENCES mobile_account(id) ON DELETE SET NULL,
    CONSTRAINT fk_binding_history_new_account FOREIGN KEY (new_mobile_account_id) REFERENCES mobile_account(id) ON DELETE SET NULL,
    CONSTRAINT fk_binding_history_operation_batch FOREIGN KEY (operation_batch_id) REFERENCES operation_batch(id) ON DELETE SET NULL,
    CONSTRAINT fk_binding_history_import_job FOREIGN KEY (import_job_id) REFERENCES import_job(id) ON DELETE SET NULL,
    CONSTRAINT fk_binding_history_operator FOREIGN KEY (operator_id) REFERENCES admin_user(id) ON DELETE SET NULL,
    INDEX idx_binding_history_student_time (student_id, created_at),
    INDEX idx_binding_history_new_account_time (new_mobile_account_id, created_at),
    INDEX idx_binding_history_old_account_time (old_mobile_account_id, created_at),
    INDEX idx_binding_history_action (action_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE export_job (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    export_type ENUM('batch', 'single') NOT NULL,
    operation_batch_id BIGINT NULL,
    student_id BIGINT NULL,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    status ENUM('generated', 'downloaded', 'failed') NOT NULL DEFAULT 'generated',
    operator_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    downloaded_at DATETIME NULL,
    CONSTRAINT fk_export_job_operation_batch FOREIGN KEY (operation_batch_id) REFERENCES operation_batch(id) ON DELETE SET NULL,
    CONSTRAINT fk_export_job_student FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE SET NULL,
    CONSTRAINT fk_export_job_operator FOREIGN KEY (operator_id) REFERENCES admin_user(id),
    INDEX idx_export_job_created (created_at),
    INDEX idx_export_job_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE alert_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    alert_type ENUM('batch_expire', 'low_account', 'import_fail', 'export_fail', 'allocation_fail', 'reconcile_conflict', 'expired_batch_still_assigned') NOT NULL,
    level ENUM('info', 'warning', 'critical') NOT NULL,
    title VARCHAR(128) NOT NULL,
    content VARCHAR(500) NOT NULL,
    related_batch_id BIGINT NULL,
    related_import_job_id BIGINT NULL,
    related_operation_batch_id BIGINT NULL,
    detail_json JSON NULL,
    is_resolved TINYINT(1) NOT NULL DEFAULT 0,
    resolved_at DATETIME NULL,
    resolved_by BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_record_batch FOREIGN KEY (related_batch_id) REFERENCES account_batch(id) ON DELETE SET NULL,
    CONSTRAINT fk_alert_record_import_job FOREIGN KEY (related_import_job_id) REFERENCES import_job(id) ON DELETE SET NULL,
    CONSTRAINT fk_alert_record_operation_batch FOREIGN KEY (related_operation_batch_id) REFERENCES operation_batch(id) ON DELETE SET NULL,
    CONSTRAINT fk_alert_record_resolved_by FOREIGN KEY (resolved_by) REFERENCES admin_user(id) ON DELETE SET NULL,
    INDEX idx_alert_record_open (is_resolved, level, created_at),
    INDEX idx_alert_record_type (alert_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE audit_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    operator_id BIGINT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(64) NULL,
    request_method VARCHAR(16) NOT NULL,
    request_path VARCHAR(255) NOT NULL,
    request_ip VARCHAR(64) NULL,
    result_status ENUM('success', 'failed') NOT NULL,
    message VARCHAR(255) NULL,
    detail_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_log_operator FOREIGN KEY (operator_id) REFERENCES admin_user(id) ON DELETE SET NULL,
    INDEX idx_audit_log_resource (resource_type, resource_id),
    INDEX idx_audit_log_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE scheduler_run_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    job_name VARCHAR(64) NOT NULL,
    scheduled_at DATETIME NOT NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    status ENUM('success', 'failed', 'skipped') NOT NULL,
    affected_rows INT NOT NULL DEFAULT 0,
    message VARCHAR(255) NULL,
    detail_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_scheduler_run_log_job_time (job_name, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 示例数据草案

```sql
INSERT INTO admin_user (username, password_hash, password_algo)
VALUES ('admin', '$argon2id$v=19$m=19456,t=2,p=1$example$examplehash', 'argon2id');

INSERT INTO system_config (config_key, config_value, remark) VALUES
('timezone', JSON_OBJECT('value', 'Asia/Shanghai'), '系统时区'),
('monthly_extend_days', JSON_OBJECT('value', 31), '包月顺延天数'),
('yearly_extend_days', JSON_OBJECT('value', 365), '包年顺延天数'),
('batch_warn_days', JSON_OBJECT('value', 1), '批次预警天数'),
('allocation_priority_limit', JSON_OBJECT('value', 20), '最早优先人数上限'),
('last_processed_charge_time', JSON_OBJECT('value', NULL), '收费清单处理水位'),
('low_account_threshold', JSON_OBJECT('value', 50), '低库存阈值');

INSERT INTO account_batch (batch_code, batch_name, batch_type, priority, expire_at, warn_days, status, remark)
VALUES
('202509', '2025年09批次', 'normal', 100, '2026-09-30', 1, 'active', '普通批次'),
('0元账号', '长期账号批次', 'zero', 10, NULL, 1, 'active', '长期有效');

INSERT INTO mobile_account (account, password, batch_id, status)
VALUES
('yd0001', '123123', 1, 'available'),
('yd0002', '123123', 1, 'available'),
('yd9001', '123123', 2, 'available');

INSERT INTO student (student_no, name, current_package_name, current_fee_amount, expected_expire_at, source_expire_at, last_charge_time)
VALUES
('2023001001', '张三', '30元移动包月75M', 30.00, '2026-05-21', '2026-05-20', '2026-04-20 09:10:00');
```

### 后端 API 设计约定

#### 通用约定

- 前缀：`/api/v1`
- 认证：登录成功后设定同域 `HttpOnly` 会话 Cookie；所有写操作要求带 `X-CSRF-Token`
- 响应格式统一：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "req_20260420_xxxx"
}
```

- 错误格式统一：

```json
{
  "code": "IMP001",
  "message": "缺少必填列：学号",
  "details": [
    {"row_no": 1, "field": "学号", "reason": "missing"}
  ],
  "request_id": "req_20260420_xxxx"
}
```

#### 通用状态码

| 状态码 | 含义 | 典型场景 |
|---|---|---|
| `200` | 成功 | 查询、执行成功 |
| `201` | 创建成功 | 预览批次、导出任务生成 |
| `400` | 请求错误 | 参数缺失、格式错误 |
| `401` | 未认证 | 未登录或会话失效 |
| `403` | 禁止访问 | 非管理员 |
| `404` | 资源不存在 | 学号/批次/任务不存在 |
| `409` | 状态冲突 | 批次已执行、账号已被占用 |
| `422` | 业务校验失败 | 无可用账号、列名合法但业务不合法 |
| `500` | 服务内部错误 | 未处理异常 |

### 关键后端 API 列表

#### 认证与系统配置

| 方法 | 端点 | 输入 | 输出 | 错误处理 | 权限 |
|---|---|---|---|---|---|
| `POST` | `/auth/login` | `username,password` | 用户信息、会话建立 | 用户名或密码错误 `401` | 匿名 |
| `POST` | `/auth/logout` | 无 | 登出成功 | 会话不存在仍返回成功 | 管理员 |
| `GET` | `/auth/me` | 无 | 当前用户、会话状态 | 未登录 `401` | 管理员 |
| `PUT` | `/auth/password` | `old_password,new_password` | 修改成功 | 原密码错误 `422` | 管理员 |
| `GET` | `/config` | 无 | 所有配置项 | 无 | 管理员 |
| `PUT` | `/config` | 配置 JSON | 更新后的配置 | 非法配置 `422` | 管理员 |

#### 仪表盘与预警

| 方法 | 端点 | 输入 | 输出 | 错误处理 | 权限 |
|---|---|---|---|---|---|
| `GET` | `/dashboard` | 查询参数可选 | 统计卡片、最近任务、待办列表 | 无 | 管理员 |
| `GET` | `/alerts` | `type,level,is_resolved,page,size` | 预警分页列表 | 无 | 管理员 |
| `PATCH` | `/alerts/{id}/resolve` | `resolution_note` | 处理结果 | 预警不存在 `404` | 管理员 |

#### 账号池与批次

| 方法 | 端点 | 输入 | 输出 | 错误处理 | 权限 |
|---|---|---|---|---|---|
| `POST` | `/mobile-accounts/import` | Excel 文件 | 导入任务 ID、摘要 | 文件格式/列缺失 `400/422` | 管理员 |
| `GET` | `/mobile-accounts` | `status,batch_code,page,size` | 账号分页列表 | 无 | 管理员 |
| `GET` | `/mobile-accounts/{id}` | 无 | 账号详情 | 不存在 `404` | 管理员 |
| `GET` | `/mobile-accounts/{id}/history` | 无 | 账号历史绑定 | 不存在 `404` | 管理员 |
| `PATCH` | `/mobile-accounts/{id}/disable` | `reason` | 状态更新 | 已失效/已禁用 `409` | 管理员 |
| `PATCH` | `/mobile-accounts/{id}/enable` | 无 | 状态更新 | 不可恢复 `409` | 管理员 |
| `GET` | `/batches` | `status,page,size` | 批次列表 | 无 | 管理员 |
| `POST` | `/batches` | `batch_code,batch_type,priority,expire_at` | 新建批次 | 批次号重复 `409` | 管理员 |
| `PUT` | `/batches/{id}` | 批次更新字段 | 更新结果 | 不存在 `404` | 管理员 |

#### 完整名单导入

| 方法 | 端点 | 输入 | 输出 | 错误处理 | 权限 |
|---|---|---|---|---|---|
| `POST` | `/full-students/import/preview` | Excel 文件 | 导入任务摘要、冲突列表、预计释放数 | 模板错误 `422` | 管理员 |
| `POST` | `/full-students/import/{job_id}/execute` | `idempotency_key` | 执行结果 | 已执行 `409` | 管理员 |
| `GET` | `/imports/{job_id}` | 无 | 导入任务详情 | 不存在 `404` | 管理员 |

#### 收费清单处理

| 方法 | 端点 | 输入 | 输出 | 错误处理 | 权限 |
|---|---|---|---|---|---|
| `POST` | `/charge-batches/preview` | Excel 文件 | 预览批次、分类结果、失败明细 | 模板错误 `422` | 管理员 |
| `POST` | `/charge-batches/{batch_id}/execute` | `idempotency_key` | 执行结果、导出任务信息 | 已执行 `409`、无号 `422` | 管理员 |
| `GET` | `/charge-batches` | 分页参数 | 批次列表 | 无 | 管理员 |
| `GET` | `/operation-batches/{id}` | 无 | 批次摘要 | 不存在 `404` | 管理员 |
| `GET` | `/operation-batches/{id}/details` | `result_status,page,size` | 明细分页 | 不存在 `404` | 管理员 |

#### 批次换绑与手动换绑

| 方法 | 端点 | 输入 | 输出 | 错误处理 | 权限 |
|---|---|---|---|---|---|
| `POST` | `/batch-rebinds/preview` | `batch_id` | 受影响学生、拟分配新号、失败明细 | 批次不存在 `404`、无可用新号 `422` | 管理员 |
| `POST` | `/batch-rebinds/{batch_id}/execute` | `idempotency_key` | 换绑结果、导出任务 | 已执行 `409` | 管理员 |
| `POST` | `/bindings/manual-rebind` | `student_no,new_account_id,old_account_action` | 换绑结果、单行导出任务 | 学号/账号不存在 `404`；账号已占用 `409` | 管理员 |

#### 学生、台账、导出、调度

| 方法 | 端点 | 输入 | 输出 | 错误处理 | 权限 |
|---|---|---|---|---|---|
| `GET` | `/students/{student_no}` | 无 | 学生详情、当前绑定 | 不存在 `404` | 管理员 |
| `GET` | `/students/{student_no}/history` | 无 | 学生历史台账 | 不存在 `404` | 管理员 |
| `GET` | `/ledger/accounts/{account}` | 无 | 账号当前状态与历史 | 不存在 `404` | 管理员 |
| `GET` | `/exports` | `page,size` | 导出记录分页 | 无 | 管理员 |
| `GET` | `/exports/{id}/download` | 无 | 文件流 | 文件不存在 `404` | 管理员 |
| `GET` | `/scheduler/jobs` | 无 | 任务清单 | 无 | 管理员 |
| `POST` | `/scheduler/run/{job_name}` | 无 | 手动触发结果 | 正在执行 `409` | 管理员 |
| `GET` | `/scheduler/runs` | `job_name,page,size` | 任务运行日志 | 无 | 管理员 |
| `GET` | `/audit-logs` | `action,resource_type,page,size` | 审计日志分页 | 无 | 管理员 |

### 关键 API 示例

#### 登录

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "YourStrongPassword"
}
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user": {
      "id": 1,
      "username": "admin"
    },
    "csrf_token": "csrf_xxx"
  },
  "request_id": "req_20260420_0001"
}
```

#### 收费清单预览

```http
POST /api/v1/charge-batches/preview
Content-Type: multipart/form-data
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "operation_batch_id": 101,
    "last_processed_charge_time_before": "2026-04-13 23:59:59",
    "preview_rows": 38,
    "to_allocate_count": 12,
    "to_renew_count": 18,
    "to_rebind_count": 5,
    "fail_count": 3,
    "details": [
      {
        "row_no": 1,
        "student_no": "2023001001",
        "name": "张三",
        "action_plan": "renew",
        "result_message": "当前账号仍有效，顺延31天"
      },
      {
        "row_no": 2,
        "student_no": "2023001002",
        "name": "李四",
        "action_plan": "allocate",
        "new_mobile_account": "yd0001"
      }
    ]
  },
  "request_id": "req_20260420_0101"
}
```

#### 收费清单执行

```http
POST /api/v1/charge-batches/101/execute
Content-Type: application/json
X-Idempotency-Key: idem_20260420_101

{
  "confirm": true
}
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "operation_batch_id": 101,
    "status": "partial_success",
    "success_count": 35,
    "fail_count": 3,
    "export_job": {
      "id": 88,
      "filename": "移动2604200930.xlsx",
      "row_count": 17
    },
    "last_processed_charge_time_after": "2026-04-20 09:28:00"
  },
  "request_id": "req_20260420_0102"
}
```

#### 手动换绑

```http
POST /api/v1/bindings/manual-rebind
Content-Type: application/json
X-Idempotency-Key: idem_20260420_manual_01

{
  "student_no": "2023001001",
  "new_account_id": 1002,
  "old_account_action": "disable",
  "remark": "原账号拨号不可用"
}
```

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "student_no": "2023001001",
    "old_account": "yd0001",
    "new_account": "yd0002",
    "export_job": {
      "id": 89,
      "filename": "移动2604200945.xlsx",
      "row_count": 1
    }
  },
  "request_id": "req_20260420_0103"
}
```

## 定时任务、Excel、批量处理与台账审计

### APScheduler 任务设计

APScheduler 3.x 文档支持通过作业存储、`max_instances`、`misfire_grace_time` 和 `coalesce` 控制计划任务的持久化、并发和错过触发后的行为；SQLAlchemyJobStore 可以把作业保存到数据库表中，调度器重启后仍保留作业状态。基于此，本系统建议使用一个**独立 scheduler 容器**，而不是把调度器绑进 Web Worker。citeturn7view1turn11search1turn11search3turn11search4

| 任务名 | 触发时间 | 作用 | 幂等性策略 | 失败处理 |
|---|---|---|---|---|
| `batch_expire_warning_job` | 每天 00:05 | 找出 `expire_at = tomorrow` 的批次并生成预警 | 若同一批次同一天已有未解决预警，则不重复创建 | 记 `scheduler_run_log` + `alert_record(import_fail)` |
| `low_account_warning_job` | 每天 00:10 | 检查可用账号数是否低于阈值 | 同日同类型预警去重 | 记录失败日志 |
| `release_expired_binding_job` | 每天 00:15 | 依据 `student.source_expire_at` 释放已到期绑定 | 只处理仍存在于 `current_binding` 且 `expire_at < today` 的记录 | 单条失败不影响其他条，写历史和预警 |
| `mark_batch_expired_job` | 每天 00:20 | 将过期批次状态改为 `expired` | 仅从 `active -> expired` 变更一次 | 若批次仍有当前绑定，生成 `expired_batch_still_assigned` 预警 |
| `cleanup_old_exports_job` | 每周日 02:00 | 清理过旧导出文件（可选） | 依据保留期限清理 | 清理失败写日志，不影响业务 |

### Excel 导入格式、映射与校验规则

pandas 官方文档说明 `read_excel()` 可以读取多种 Excel 格式，`to_excel()` 可以直接写回 `.xlsx` 文件；不过为了减少运维复杂度，本项目产品级规范**只接受 `.xlsx`**。这样做不是因为工具不支持更多格式，而是为了降低模板失真与引擎兼容问题。citeturn5view6turn5view7

#### 移动账号池导入模板

| 列名 | 必填 | 类型 | 规则 |
|---|---|---|---|
| 移动账户 | 是 | 文本 | 唯一，非空 |
| 密码 | 是 | 文本 | 必须为 `123123`；非该值报错 |
| 批次 | 是 | 文本 | 若不存在则创建批次或报错，取决于配置 |
| 备注 | 否 | 文本 | 可空 |

样例：

| 移动账户 | 密码 | 批次 | 备注 |
|---|---|---|---|
| yd0001 | 123123 | 202509 | 第一批 |
| yd0002 | 123123 | 202509 | 第一批 |
| yd9001 | 123123 | 0元账号 | 长期号 |

#### 收费清单导入模板

| 列名 | 必填 | 类型 | 规则 |
|---|---|---|---|
| 学号 | 是 | 文本 | 非空 |
| 姓名 | 是 | 文本 | 非空 |
| 收费金额 | 是 | 数值 | 仅允许 `30` 或 `300`；其余报错 |
| 办理套餐 | 是 | 文本 | 用于校验“包月/包年” |
| 收费时间 | 是 | 日期时间 | 必须能解析；仅处理 `>` 上次水位的记录 |

样例：

| 学号 | 姓名 | 收费金额 | 办理套餐 | 收费时间 |
|---|---|---|---|---|
| 2023001001 | 张三 | 30 | 30元移动包月75M | 2026-04-20 09:10:00 |
| 2023001002 | 李四 | 300 | 300元移动包年75M | 2026-04-20 09:12:00 |

校验规则：

- `收费金额=30` 且套餐名不含“包月”时，报 `IMP_PACKAGE_MISMATCH`。
- `收费金额=300` 且套餐名不含“包年”时，报 `IMP_PACKAGE_MISMATCH`。
- 同一文件内学号重复时，按现规则理论不应出现；若出现，整行报错。
- 收费时间若小于等于当前水位，不参与本次预览。

#### 完整学生名单导入模板

| 列名 | 必填 | 类型 | 规则 |
|---|---|---|---|
| 学号 | 是 | 文本 | 非空 |
| 姓名 | 是 | 文本 | 非空 |
| 当前套餐 | 是 | 文本 | 作为 `current_package_name` |
| 套餐有效期 | 是 | 日期 | 作为 `source_expire_at` |
| 移动账户 | 否 | 文本 | 若为空表示当前无移动绑定 |
| 联通账户 | 否 | 文本 | 仅保留原始信息，不参与运算 |
| 电信账户 | 否 | 文本 | 仅保留原始信息，不参与运算 |

样例：

| 学号 | 姓名 | 当前套餐 | 套餐有效期 | 移动账户 | 联通账户 | 电信账户 |
|---|---|---|---|---|---|---|
| 2023001001 | 张三 | 30元移动包月75M | 2026-05-20 | yd0001 |  |  |
| 2023001009 | 王五 | 联通包月 | 2026-05-18 |  | lt123 |  |

#### 固定导出模板

导出格式是本系统与现有后台衔接的最硬约束之一，应被视为**强验收项**：

| 列名 | 值来源 |
|---|---|
| 学号 | 学生学号 |
| 移动账户 | 新分配或换绑后的移动账号 |
| 移动密码 | 固定 `123123` |
| 联通账户 | 空字符串 |
| 联通密码 | 空字符串 |
| 电信账户 | 空字符串 |
| 电信密码 | 空字符串 |

样例：

| 学号 | 移动账户 | 移动密码 | 联通账户 | 联通密码 | 电信账户 | 电信密码 |
|---|---|---|---|---|---|---|
| 2023001002 | yd0001 | 123123 |  |  |  |  |
| 2023001008 | yd0009 | 123123 |  |  |  |  |

文件名规则：

- 采用系统时区当前时间拼接。
- 格式：`移动YYMMDDHHmm.xlsx`
- 例：`移动2604200930.xlsx`

### 批量处理与回滚策略

#### 收费清单批处理

收费批处理必须严格区分“**预览**”与“**执行**”：

- 预览阶段：
  - 解析文件；
  - 校验模板；
  - 识别增量；
  - 分类为 `allocate/renew/rebind/fail`；
  - 写入 `operation_batch` 和 `operation_batch_detail`；
  - **不改业务数据**。

- 执行阶段：
  - 遍历明细，按 `charge_time ASC, row_no ASC` 排序；
  - 仅处理优先的前 20 人，其余标记失败；
  - 每行使用短事务；
  - 成功后提交当前行；
  - 失败仅回滚当前行，保留整批汇总与失败明细；
  - 整体批次允许 `partial_success`。

该策略的原因很直接：你的业务已确认“优先最早开通的 20 人，其余报错”，因此**批次整体原子回滚并不符合业务**；系统正确行为应当是“部分成功 + 完整失败名单 + 明确导出结果”。

#### 完整名单导入

完整名单导入建议采用“**整批校验、整批执行**”：

- 若模板列错误、日期大量无法解析，则整批失败回滚。
- 若仅存在少量账号冲突，则整批仍可执行学生有效期校正，但冲突写入预警，不自动修复当前绑定。
- 所有到期释放动作写入 `binding_history(action_type=release, source=full_list)`。

#### 批次换绑

批次换绑不建议默认自动执行，而应当：

1. 由预警任务创建“明天失效批次”的待办。
2. 管理员打开待办执行“换绑预览”。
3. 系统寻找可用新号并生成预览。
4. 管理员确认后再执行并生成导出文件。

这样既满足“提前换绑”的业务要求，又不会在未确认库存与名单时自动改绑，风险更低。

### 台账与审计设计

台账分三层：

| 层级 | 表 | 含义 |
|---|---|---|
| 当前态 | `current_binding` | 谁正在用哪个移动号 |
| 业务历史 | `binding_history` | 发生过什么业务动作 |
| 技术审计 | `audit_log` / `scheduler_run_log` | 谁在什么时候通过哪个接口做了什么；调度器做了什么 |

审计日志建议至少记录：

- `request_id`
- 操作人
- 请求路径/方法
- IP
- 资源类型与 ID
- 结果状态
- 错误信息
- 关键参数快照（脱敏后）

Python 官方文档把 `logging` 定义为“跟踪软件运行时发生事件的手段”；因此项目中不应只依赖数据库日志，还应保留结构化应用日志，尤其是导入失败、调度失败、下载失败等事件。citeturn7view6turn7view5

### 预警与待办中心规则

| 预警类型 | 触发条件 | 级别 | 是否自动生成 | 解决方式 |
|---|---|---|---|---|
| 批次失效预警 | 存在 `expire_at = tomorrow` 的批次 | warning | 是 | 预览并执行批次换绑，或确认忽略 |
| 库存不足预警 | `available` 账号数低于阈值 | warning/critical | 是 | 导入新账号池或调整阈值 |
| 收费处理失败预警 | 批处理失败数 > 0 | warning | 是 | 查看失败明细并补处理 |
| 完整名单冲突预警 | 名单移动账号与系统当前绑定不一致 | warning | 是 | 手工修正 |
| 过期批次仍在用预警 | 批次已过期但账号仍处于当前绑定 | critical | 是 | 立即人工换绑 |
| 导出失败预警 | 文件写入失败 | critical | 是 | 重试导出/检查磁盘 |

待办中心默认展示：

1. 未解决 critical
2. 未解决 warning
3. 最近一次收费批处理失败
4. 最近一次完整名单冲突
5. 明天到期的批次数量
6. 当前可绑定账号数

## 部署、安全、运维、测试与实施

### Linux 内网部署方案

Docker Compose 官方资料说明：Compose Specification 是当前推荐的 Compose 文件格式；Compose 以单一 YAML 编排 services、networks、volumes；`depends_on` 能控制依赖启动顺序。基于此，本系统适合用 4 个服务部署：`mysql`、`backend`、`scheduler`、`nginx`。其中 `scheduler` 与 `backend` 共享同一代码镜像，但 `command` 不同。citeturn5view4turn5view5turn9search3turn9search7

#### 部署依赖建议

| 服务 | 推荐说明 |
|---|---|
| MySQL | 8.0+，建议 InnoDB、utf8mb4 |
| Python | 3.11 或 3.12 |
| Flask | 3.x |
| SQLAlchemy | 2.x |
| APScheduler | 3.11.x |
| pandas | 2.x/3.x 皆可，锁定一个主版本 |
| Vue | 3.x |
| Vue Router | 4.x |
| Ant Design Vue | 4.x |
| Nginx | 稳定版 |

#### Docker Compose 示例

```yaml
services:
  mysql:
    image: mysql:8.4
    container_name: campus_mysql
    environment:
      MYSQL_ROOT_PASSWORD: root_password
      MYSQL_DATABASE: campus_mobile_pool
      MYSQL_USER: campus_user
      MYSQL_PASSWORD: campus_password
      TZ: Asia/Shanghai
    command: >
      --default-authentication-plugin=mysql_native_password
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_0900_ai_ci
    volumes:
      - ./data/mysql:/var/lib/mysql
      - ./backup:/backup
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h 127.0.0.1 -uroot -proot_password || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 12
    restart: unless-stopped

  backend:
    build: ./backend
    container_name: campus_backend
    environment:
      APP_ENV: production
      TZ: Asia/Shanghai
      DATABASE_URL: mysql+pymysql://campus_user:campus_password@mysql:3306/campus_mobile_pool?charset=utf8mb4
      SECRET_KEY: change_me
      STORAGE_ROOT: /app/storage
    depends_on:
      mysql:
        condition: service_healthy
    volumes:
      - ./storage:/app/storage
    restart: unless-stopped

  scheduler:
    build: ./backend
    container_name: campus_scheduler
    command: ["python", "scheduler_runner.py"]
    environment:
      APP_ENV: production
      TZ: Asia/Shanghai
      DATABASE_URL: mysql+pymysql://campus_user:campus_password@mysql:3306/campus_mobile_pool?charset=utf8mb4
      SECRET_KEY: change_me
      STORAGE_ROOT: /app/storage
    depends_on:
      mysql:
        condition: service_healthy
    volumes:
      - ./storage:/app/storage
    restart: unless-stopped

  nginx:
    image: nginx:stable
    container_name: campus_nginx
    depends_on:
      - backend
    ports:
      - "8080:80"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./frontend/dist:/usr/share/nginx/html:ro
      - ./storage:/usr/share/nginx/storage:ro
    restart: unless-stopped
```

### 安全与权限设计

#### 认证与权限

本项目只有一个管理员角色，因此权限模型可以极简：

| 角色 | 权限 |
|---|---|
| 匿名 | 仅可访问登录接口 |
| 管理员 | 全部页面与全部接口 |

建议采用**同域部署**，让 Nginx 同时提供前端页面和 `/api` 代理，这样浏览器可直接使用 `HttpOnly` 会话 Cookie，不需要暴露跨域 token 存储。若必须分域，则需要额外配置 CORS 和 Cookie 策略。

#### 密码存储策略

OWASP 的 Password Storage Cheat Sheet 明确建议优先使用 Argon2id；若不可用，再选择 scrypt；对于历史兼容场景再考虑 bcrypt。Python 标准库提供 `pbkdf2_hmac` 与 `scrypt`。因此建议：

1. **优先**：`argon2-cffi` + Argon2id；
2. **回退**：`hashlib.scrypt()`；
3. **再次回退**：`hashlib.pbkdf2_hmac('sha256', ..., iterations>=500000)`。

管理员密码哈希存储于 `admin_user.password_hash`；绝不做可逆加密；绝不与移动账号的业务固定密码混用。citeturn5view8turn8view0turn8view1

#### 文件与接口安全

- 仅允许 `.xlsx` 上传。
- 上传文件大小限制建议 10MB。
- 文件名服务端重命名，禁止直接使用原文件名存储。
- 下载接口必须鉴权。
- 审计日志记录下载行为。
- Nginx 禁止目录浏览。
- 生产模式关闭 Flask Debug。
- 所有异常返回统一 JSON，不回显堆栈。

### 运维、备份与恢复

MySQL 官方文档说明 `mysqldump` 是逻辑备份工具，会生成可重建对象定义与数据的 SQL 语句。因此建议使用“**数据库逻辑备份 + 文件卷备份**”双重措施。citeturn5view11

#### 备份策略

| 类别 | 频率 | 方式 | 保留 |
|---|---|---|---|
| 数据库全量备份 | 每天凌晨 | `mysqldump` | 7~30 天 |
| 上传文件备份 | 每天 | rsync/卷快照 | 7~30 天 |
| 导出文件备份 | 每天 | rsync/卷快照 | 7~30 天 |
| 配置文件备份 | 变更后 | Git/只读备份 | 永久 |

#### 恢复流程

1. 停止 `backend` 与 `scheduler`。
2. 恢复最近一份数据库 dump。
3. 恢复 `/storage/uploads` 与 `/storage/exports`。
4. 启动 `mysql`，检查表结构与关键计数。
5. 启动 `backend` 与 `scheduler`。
6. 验证：
   - 最新 `current_binding` 数量；
   - 最近一条 `binding_history`；
   - 最近导出文件可下载；
   - 调度器任务状态正常。

### 测试用例设计

#### 单元测试示例

| 用例 | 输入 | 预期 |
|---|---|---|
| 包月顺延 | 当前有效期 `2026-05-20`，收费时间 `2026-04-20` | 新预计到期日 `2026-06-20` 左右（按 31 天） |
| 包年顺延 | 当前有效期 `2026-09-01`，收费时间 `2026-04-20` | 新预计到期日 = 当前有效期 + 365 天 |
| 0元批次排序 | 正常批次 + 0元批次都有可用号 | 默认先选正常批次 |
| 导出文件名 | 当前时间 `2026-04-20 09:30` | `移动2604200930.xlsx` |
| 导出模板空列 | 生成导出 | 联通/电信 4 列全部存在且为空 |

#### 集成测试示例

| 用例 | 步骤 | 预期 |
|---|---|---|
| 账号池导入成功 | 上传合法账号池文件 | 建立批次与账号记录 |
| 收费清单预览 | 上传混合数据 | 正确分类 allocate/renew/rebind/fail |
| 收费清单执行部分成功 | 待处理 25 人，规则仅前 20 | 成功 20，失败 5，失败原因明确 |
| 完整名单释放 | 导入有效期已过期名单 | 自动释放到期绑定 |
| 批次预警生成 | 存在明天到期批次 | alert_record 生成 warning |
| 批次换绑执行 | 对到期批次执行预览与执行 | 旧号释放/禁用，新号绑定，生成导出 |

#### 端到端测试示例

| 用例 | 流程 | 预期 |
|---|---|---|
| 新办学生全链路 | 登录 → 导入账号池 → 导入收费清单 → 预览 → 执行 → 下载导出模板 | 全链路成功 |
| 个别异常账号换绑 | 登录 → 搜索学号 → 手动换绑 → 单行导出 | 旧号禁用，新号绑定，单行文件可下载 |
| 批次到期治理 | 调度生成预警 → 打开待办 → 批次换绑预览 → 执行 | 受影响学生完成换绑 |

### 迁移与升级注意事项

| 类别 | 注意事项 |
|---|---|
| 数据库迁移 | 先备份，再执行 DDL；新增字段优先 nullable；大表加索引要走预生产验证 |
| 调度升级 | 锁定 APScheduler 主版本；升级前验证 `misfire/coalesce/max_instances` 配置兼容性 |
| 前端升级 | 锁定 Vue / Ant Design Vue 主版本；预览上传组件的行为差异要回归测试 |
| 文件格式升级 | 变更导入模板时必须提升模板版本并兼容旧模板至少一个周期 |
| 业务规则变更 | 若未来取消“最早 20 人”规则，应优先改配置，不直接改 SQL |

### 项目实施计划

#### 人员角色建议

| 角色 | 责任 |
|---|---|
| 业务负责人 | 确认模板、验收规则、试运行反馈 |
| 后端开发 | 数据模型、接口、调度、导入导出、台账 |
| 前端开发 | 页面、预览、交互、下载、待办中心 |
| 测试/实施 | 测试用例、UAT、上线演练 |
| 运维 | Compose、备份、监控、恢复演练 |

#### 里程碑与估时

| 里程碑 | 主要产出 | 估时 |
|---|---|---|
| 需求冻结 | 本文档、字段映射确认、模板样例冻结 | 2~3 天 |
| 数据与后端骨架 | DDL、基础模型、认证、配置、账号池接口 | 3~5 天 |
| 导入导出主链路 | 收费清单预览执行、完整名单导入、导出任务 | 5~7 天 |
| 调度与预警 | APScheduler、待办中心、批次预警、到期释放 | 3~4 天 |
| 前端联调 | 全部主要页面、接口联调、交互优化 | 5~7 天 |
| 测试与修复 | 单元/集成/E2E/UAT | 4~6 天 |
| 上线与观察 | 生产部署、首周观察、问题修复 | 2~3 天 |

若由 1 名前后端全栈工程师完成，实际排期建议 **4~6 周**；若前后端并行，则 **2~3 周**可出首版。

#### 风险与缓解

| 风险 | 说明 | 缓解措施 |
|---|---|---|
| 完整名单列名不稳定 | 不同周导出的列名可能变化 | 做列名映射配置与模板校验 |
| 收费时间水位漏单 | 同一时间戳跨批次文件可能造成边界问题 | 第一版按既定规则实现，同时记录风险并准备升级水位方案 |
| 0元账号被过度消耗 | 若优先级处理不当，长期号会先被发掉 | 通过 `account_batch.priority` 显式控制 |
| 批量执行重复提交 | 浏览器双击、网络重试 | 执行接口要求 `X-Idempotency-Key` |
| 调度重复执行 | Web 与 scheduler 都起定时器 | scheduler 独立容器，Web 不启动调度器 |
| 导入模板被手工改坏 | 列顺序、日期格式被 Excel 改写 | 强校验 + 错误明细反馈 |

### 可直接用于开发的交付物清单

| 交付物 | 内容 |
|---|---|
| 需求规格说明书 | 即本报告，可作为需求冻结版本 |
| 数据库 DDL 草案 | 上述 SQL 脚本 |
| API 规格表 | 上述 REST 端点、状态码、示例 |
| 前端页面清单 | 页面路由、组件、字段、交互说明 |
| Excel 模板样例 | 账号池导入、收费清单、完整名单、固定导出模板 |
| 调度任务清单 | 任务名、Cron、幂等策略、失败策略 |
| 测试清单 | 单元、集成、端到端场景 |
| 部署清单 | Docker Compose、环境变量、目录结构 |
| 验收清单 | 下列验收标准 |

### 验收标准

| 验收项 | 标准 |
|---|---|
| 账号唯一性 | 任意时刻同一移动账号不能绑定给两个学号 |
| 历史可追溯 | 能查任一学号历史账号、任一账号历史学号 |
| 收费预览正确 | 增量筛选、分类结果与人工核对一致 |
| 执行规则正确 | 严格按收费时间升序优先处理最早 20 人，其余报错 |
| 有效期规则正确 | 包月 31 天、包年 365 天；完整名单可覆盖校正 |
| 自动任务正确 | 每天凌晨执行，生成批次失效预警并释放到期绑定 |
| 导出模板正确 | 列顺序与命名完全匹配；联通/电信列存在且为空 |
| 导出命名正确 | `移动YYMMDDHHmm.xlsx` |
| 手动换绑可用 | 能完成换绑并生成单行导出 |
| 审计闭环可用 | 导入、导出、执行、失败、调度都可被查询 |
| 备份恢复可用 | 完成一次演练并通过恢复验证 |
| 部署可复现 | 在 Linux 内网通过 Compose 一键启动 |

以上方案把**需求边界、数据结构、接口、前端交互、调度、Excel、部署、安全、测试与实施**完整打通，并尽量把未指定点显式暴露为配置项或风险项。对当前业务而言，最关键的不是技术炫技，而是把“现有人工 Excel 工作流”稳定迁移到“有状态、有约束、有台账”的系统中；只要严格按本文档落地，第一版就已经能够替代绝大多数人工表格操作，并为后续批次换绑、容量预测与规则演进留出足够空间。
