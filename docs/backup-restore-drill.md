# 备份恢复演练记录

本文档用于记录 PostgreSQL 备份恢复演练，避免“只有脚本，没有演练产物”。

## 1. 演练目标

- 验证 `pg_dump` 备份可用。
- 验证上传目录和导出目录可恢复。
- 验证恢复后关键业务表与文件可正常读取。

## 2. 演练环境

| 项目 | 记录 |
|---|---|
| 演练日期 | 2026-04-20 |
| 执行人 | 待填写 |
| 环境 | Docker Compose / PostgreSQL |
| 备份文件 | 待填写 |
| 文件卷快照 | 待填写 |

## 3. 演练步骤

1. 停止 `backend` 与 `scheduler`。
2. 执行数据库恢复脚本：
   `./scripts/restore_postgres.sh backup/your_dump.sql`
3. 恢复 `storage/uploads` 与 `storage/exports`。
4. 启动 `postgres`，检查 migration 版本与关键表计数。
5. 启动 `backend` 与 `scheduler`。
6. 验证登录、导出下载、台账查询、调度日志。

## 4. 验证记录

| 检查项 | 结果 | 备注 |
|---|---|---|
| PostgreSQL 可启动 | 待填写 | |
| Alembic 版本正确 | 待填写 | |
| `current_binding` 计数正确 | 待填写 | |
| `binding_history` 可查询 | 待填写 | |
| 导出文件可下载 | 待填写 | |
| 调度日志可查看 | 待填写 | |

## 5. 结论

- 是否通过：待填写
- 风险与后续动作：待填写
