from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

import pandas as pd

from .config_service import get_config_value
from .date_service import normalize_date, normalize_datetime


ACCOUNT_PATTERN = re.compile(r"^[A-Za-z0-9_.@-]+$")


@dataclass(frozen=True)
class TemplateColumn:
    name: str
    kind: str = "string"
    required: bool = True
    allow_blank: bool = False
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemplateDefinition:
    name: str
    columns: tuple[TemplateColumn, ...]
    duplicate_keys: tuple[str, ...] = ()
    sheet_name: str | None = None
    sheet_name_config_key: str | None = None


@dataclass(frozen=True)
class ValidationIssue:
    row_no: int
    field_name: str | None
    error_code: str
    error_message: str
    raw_data: dict = field(default_factory=dict)


@dataclass
class TemplateParseResult:
    template: TemplateDefinition
    sheet_name: str | None
    rows: list[dict]
    issues: list[ValidationIssue]
    available_columns: set[str]

    @property
    def has_fatal_errors(self) -> bool:
        return any(issue.row_no == 0 for issue in self.issues)


ACCOUNT_POOL_TEMPLATE = TemplateDefinition(
    name="account_pool",
    columns=(
        TemplateColumn("account"),
        TemplateColumn("batch_code"),
        TemplateColumn("batch_name", required=False),
        TemplateColumn("batch_type", required=False, choices=("normal", "free", "recycle", "special")),
        TemplateColumn("priority", kind="integer", required=False),
        TemplateColumn("expire_at", kind="date", required=False),
        TemplateColumn("warn_days", kind="integer", required=False),
    ),
    duplicate_keys=("account",),
)

CHARGE_LIST_TEMPLATE = TemplateDefinition(
    name="charge_list",
    columns=(
        TemplateColumn("student_no"),
        TemplateColumn("name"),
        TemplateColumn("charge_time", kind="datetime"),
        TemplateColumn("package_name"),
        TemplateColumn("fee_amount", kind="decimal"),
    ),
    duplicate_keys=("student_no", "charge_time", "package_name"),
)

FULL_STUDENT_TEMPLATE = TemplateDefinition(
    name="full_student_list",
    columns=(
        TemplateColumn("student_no"),
        TemplateColumn("name"),
        TemplateColumn("expire_at", kind="date"),
        TemplateColumn("mobile_account", required=False),
    ),
    duplicate_keys=("student_no",),
    sheet_name_config_key="full_list.sheet_name",
)


TEMPLATES = {
    ACCOUNT_POOL_TEMPLATE.name: ACCOUNT_POOL_TEMPLATE,
    CHARGE_LIST_TEMPLATE.name: CHARGE_LIST_TEMPLATE,
    FULL_STUDENT_TEMPLATE.name: FULL_STUDENT_TEMPLATE,
}


def get_template(template_name: str) -> TemplateDefinition:
    try:
        return TEMPLATES[template_name]
    except KeyError as exc:
        raise ValueError(f"未知模板：{template_name}") from exc


def validate_excel(path: str, template_name: str) -> TemplateParseResult:
    template = get_template(template_name)
    sheet_name = _resolve_sheet_name(template)
    issues: list[ValidationIssue] = []
    target_path = Path(path)

    try:
        workbook = pd.ExcelFile(target_path)
    except ValueError as exc:
        return TemplateParseResult(
            template=template,
            sheet_name=sheet_name,
            rows=[],
            issues=[
                ValidationIssue(
                    row_no=0,
                    field_name=None,
                    error_code="invalid_workbook",
                    error_message=str(exc),
                    raw_data={"path": str(target_path)},
                )
            ],
            available_columns=set(),
        )

    selected_sheet = sheet_name or workbook.sheet_names[0]
    if selected_sheet not in workbook.sheet_names:
        return TemplateParseResult(
            template=template,
            sheet_name=selected_sheet,
            rows=[],
            issues=[
                ValidationIssue(
                    row_no=0,
                    field_name="sheet_name",
                    error_code="invalid_sheet_name",
                    error_message=f"模板要求工作表 {selected_sheet}，实际存在 {', '.join(workbook.sheet_names)}",
                    raw_data={"sheet_names": workbook.sheet_names},
                )
            ],
            available_columns=set(),
        )

    dataframe = pd.read_excel(target_path, sheet_name=selected_sheet)
    dataframe = dataframe.where(pd.notnull(dataframe), None)
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    available_columns = set(dataframe.columns)

    expected_columns = {column.name for column in template.columns}
    missing_columns = [column.name for column in template.columns if column.required and column.name not in available_columns]
    if missing_columns:
        return TemplateParseResult(
            template=template,
            sheet_name=selected_sheet,
            rows=[],
            issues=[
                ValidationIssue(
                    row_no=0,
                    field_name=column_name,
                    error_code="missing_required_column",
                    error_message=f"缺少必填列：{column_name}",
                    raw_data={"available_columns": sorted(available_columns)},
                )
                for column_name in missing_columns
            ],
            available_columns=available_columns,
        )

    duplicate_seen: set[tuple[object, ...]] = set()
    rows: list[dict] = []
    for row_no, raw_row in enumerate(dataframe.to_dict(orient="records"), start=2):
        normalized = {column_name: raw_row.get(column_name) for column_name in expected_columns if column_name in available_columns}
        row_issues = _validate_row(template, row_no, normalized)
        if template.duplicate_keys and not row_issues:
            duplicate_key = tuple(normalized.get(key) for key in template.duplicate_keys)
            if all(value not in (None, "") for value in duplicate_key):
                if duplicate_key in duplicate_seen:
                    row_issues.append(
                        ValidationIssue(
                            row_no=row_no,
                            field_name=",".join(template.duplicate_keys),
                            error_code="duplicate_row",
                            error_message="文件中存在重复记录",
                            raw_data=dict(normalized),
                        )
                    )
                else:
                    duplicate_seen.add(duplicate_key)
        if row_issues:
            issues.extend(row_issues)
            continue
        rows.append(normalized)

    return TemplateParseResult(
        template=template,
        sheet_name=selected_sheet,
        rows=rows,
        issues=issues,
        available_columns=available_columns,
    )


def _resolve_sheet_name(template: TemplateDefinition) -> str | None:
    if template.sheet_name_config_key:
        value = get_config_value(template.sheet_name_config_key)
        if value:
            return str(value)
    return template.sheet_name


def _validate_row(template: TemplateDefinition, row_no: int, row: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for column in template.columns:
        if column.name not in row:
            continue
        value = row.get(column.name)
        if _is_blank(value):
            row[column.name] = None
            if column.required and not column.allow_blank:
                issues.append(
                    ValidationIssue(
                        row_no=row_no,
                        field_name=column.name,
                        error_code="missing_required_value",
                        error_message=f"{column.name} 不能为空",
                        raw_data=dict(row),
                    )
                )
            continue
        try:
            row[column.name] = _normalize_value(column, value)
        except (TypeError, ValueError, InvalidOperation) as exc:
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field_name=column.name,
                    error_code="invalid_value",
                    error_message=str(exc),
                    raw_data=dict(row),
                )
            )
            continue
        if column.choices and row[column.name] not in column.choices:
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field_name=column.name,
                    error_code="invalid_choice",
                    error_message=f"{column.name} 必须为 {', '.join(column.choices)} 之一",
                    raw_data=dict(row),
                )
            )

    account_value = row.get("account")
    if account_value and not ACCOUNT_PATTERN.match(account_value):
        issues.append(
            ValidationIssue(
                row_no=row_no,
                field_name="account",
                error_code="invalid_account_format",
                error_message="account 格式不合法",
                raw_data=dict(row),
            )
        )
    mobile_account_value = row.get("mobile_account")
    if mobile_account_value and not ACCOUNT_PATTERN.match(mobile_account_value):
        issues.append(
            ValidationIssue(
                row_no=row_no,
                field_name="mobile_account",
                error_code="invalid_account_format",
                error_message="mobile_account 格式不合法",
                raw_data=dict(row),
            )
        )
    return issues


def _normalize_value(column: TemplateColumn, value):
    if column.kind == "string":
        return str(value).strip()
    if column.kind == "integer":
        number = Decimal(str(value))
        if number != number.to_integral_value():
            raise ValueError(f"{column.name} 必须为整数")
        number = int(number)
        if number < 0:
            raise ValueError(f"{column.name} 不能为负数")
        return number
    if column.kind == "decimal":
        number = Decimal(str(value))
        if number < 0:
            raise ValueError(f"{column.name} 不能为负数")
        return number
    if column.kind == "date":
        normalized = normalize_date(value)
        if normalized is None:
            raise ValueError(f"{column.name} 不是有效日期")
        return normalized
    if column.kind == "datetime":
        normalized = normalize_datetime(value)
        if normalized is None:
            raise ValueError(f"{column.name} 不是有效时间")
        return normalized
    raise ValueError(f"未支持的字段类型：{column.kind}")


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass
    return False
