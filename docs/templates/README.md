# Excel 模板样例

本目录提供当前实现口径下可直接给业务方使用的模板样例。

## 文件列表

- `account-pool-template.xlsx`
  账号池导入模板，当前最小必填列为 `account / batch_code`
  其余字段由系统自动推导：
  `batch_name = batch_code`、`batch_type = normal`、`priority` 根据批次时间推导、`expire_at` 根据 `batch_code` 推导、`warn_days` 使用系统默认值
- `charge-list-template.xlsx`
  收费清单模板，包含 `student_no / name / charge_time / package_name / fee_amount`
- `full-student-list-template.xlsx`
  完整名单模板，默认工作表为 `Sheet1`，包含 `student_no / name / expire_at / mobile_account`

## 固定导出模板说明

系统导出统一使用以下列顺序：

1. `学号`
2. `移动账户`
3. `移动密码`
4. `联通账户`
5. `联通密码`
6. `电信账户`
7. `电信密码`

其中联通、电信列固定保留但默认留空，便于下游沿用既有 Excel 收集表。
