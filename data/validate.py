"""团队数据契约的常量、解析和食物行校验。"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Collection, Mapping


FOOD_COLUMNS = (
    "id",
    "name",
    "category",
    "iron_mg_per_100g",
    "zinc_mg_per_100g",
    "nutrient_source",
    "is_allergen",
    "allergen_type",
    "min_month",
    "texture_stage",
    "season_months",
    "prep_note",
    "source",
    "avg_price",
    "edible_ratio",
)

CATEGORIES = frozenset(
    {
        "谷物根茎薯类",
        "豆类坚果",
        "奶类",
        "肉类",
        "蛋类",
        "维生素A丰富蔬果",
        "其他蔬果",
    }
)

ALLERGEN_TYPES = frozenset(
    {
        "含麸质谷物",
        "甲壳纲类动物",
        "鱼类",
        "蛋类",
        "花生",
        "大豆",
        "乳",
        "坚果",
    }
)

NUTRIENT_SOURCES = frozenset({"animal", "plant"})
RECORD_STATUSES = frozenset({"planned", "passed", "reaction", "refused"})


class DataValidationError(ValueError):
    """输入或数据库中的值不符合团队数据契约。"""


def _location(field_name: str, line_number: int | None = None) -> str:
    if line_number is None:
        return field_name
    return f"第 {line_number} 行的 {field_name}"


def parse_iso_date(value: object, field_name: str = "date") -> date:
    """将 ISO 日期字符串转换为 ``datetime.date``，不吞掉格式错误。"""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{field_name} 必须是 YYYY-MM-DD 格式的日期")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise DataValidationError(
            f"{field_name} 必须是有效的 YYYY-MM-DD 日期，实际为 {value!r}"
        ) from exc


def parse_csv_list(
    value: object,
    field_name: str,
    allowed_values: Collection[str] | None = None,
) -> list[str]:
    """把逗号分隔文本解析成去空白、去重复且保持顺序的字符串列表。"""

    if value is None:
        items: list[object] = []
    elif isinstance(value, str):
        items = value.replace("，", ",").split(",")
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        raise DataValidationError(f"{field_name} 必须是逗号分隔文本或字符串列表")

    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in result:
            continue
        if allowed_values is not None and text not in allowed_values:
            raise DataValidationError(f"{field_name} 包含未约定的值：{text!r}")
        result.append(text)
    return result


def parse_season_months(value: object, field_name: str = "season_months") -> list[int]:
    """把 ``1-12`` 或 ``9,10,11`` 转换为 ``list[int]``。"""

    if value is None or (isinstance(value, str) and not value.strip()):
        return []

    if isinstance(value, str):
        raw_parts: list[object] = value.replace("，", ",").split(",")
    elif isinstance(value, (list, tuple)):
        raw_parts = list(value)
    else:
        raise DataValidationError(f"{field_name} 必须是月份文本或整数列表")

    months: list[int] = []
    for raw_part in raw_parts:
        part = str(raw_part).strip()
        if not part:
            continue
        if "-" in part:
            bounds = [item.strip() for item in part.split("-")]
            if len(bounds) != 2:
                raise DataValidationError(f"{field_name} 的月份范围无效：{part!r}")
            try:
                start, end = (int(item) for item in bounds)
            except ValueError as exc:
                raise DataValidationError(
                    f"{field_name} 的月份范围无效：{part!r}"
                ) from exc
            if start > end:
                raise DataValidationError(f"{field_name} 的月份范围起点不能大于终点")
            candidates = range(start, end + 1)
        else:
            try:
                candidates = (int(part),)
            except ValueError as exc:
                raise DataValidationError(
                    f"{field_name} 包含非整数月份：{part!r}"
                ) from exc

        for month in candidates:
            if month < 1 or month > 12:
                raise DataValidationError(f"{field_name} 的月份必须在 1 到 12 之间")
            if month not in months:
                months.append(month)
    return months


def _required_text(
    value: object,
    field_name: str,
    line_number: int | None,
) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise DataValidationError(f"{_location(field_name, line_number)} 不允许为空")
    return text


def _optional_text(value: object) -> str | None:
    text = "" if value is None else str(value).strip()
    return text or None


def _integer(
    value: object,
    field_name: str,
    line_number: int | None,
) -> int:
    try:
        text = _required_text(value, field_name, line_number)
        number = int(text)
    except ValueError as exc:
        raise DataValidationError(
            f"{_location(field_name, line_number)} 必须是整数"
        ) from exc
    return number


def _optional_float(
    value: object,
    field_name: str,
    line_number: int | None,
) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        number = float(str(value).strip())
    except ValueError as exc:
        raise DataValidationError(
            f"{_location(field_name, line_number)} 必须是数字或留空"
        ) from exc
    if not math.isfinite(number):
        raise DataValidationError(f"{_location(field_name, line_number)} 必须是有限数字")
    if number < 0:
        raise DataValidationError(f"{_location(field_name, line_number)} 不能为负数")
    return number


def validate_food_headers(fieldnames: list[str] | None) -> None:
    """要求食物 CSV 的字段集合与团队契约完全一致。"""

    if fieldnames is None:
        raise DataValidationError("foods.csv 缺少表头")
    actual = {name for name in fieldnames if name is not None}
    expected = set(FOOD_COLUMNS)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    messages = []
    if missing:
        messages.append(f"缺少字段：{', '.join(missing)}")
    if unexpected:
        messages.append(f"存在未约定字段：{', '.join(unexpected)}")
    if messages:
        raise DataValidationError("foods.csv 表头不符合数据契约；" + "；".join(messages))


def normalize_food_row(
    row: Mapping[str, object],
    line_number: int | None = None,
) -> dict[str, object]:
    """校验一行食物数据并转换成可安全写入 SQLite 的值。"""

    food_id = _integer(row.get("id"), "id", line_number)
    if food_id <= 0:
        raise DataValidationError(f"{_location('id', line_number)} 必须大于 0")

    category = _required_text(row.get("category"), "category", line_number)
    if category not in CATEGORIES:
        raise DataValidationError(
            f"{_location('category', line_number)} 不是约定的七类之一：{category!r}"
        )

    nutrient_source = _optional_text(row.get("nutrient_source"))
    if nutrient_source is not None and nutrient_source not in NUTRIENT_SOURCES:
        raise DataValidationError(
            f"{_location('nutrient_source', line_number)} 只能填 animal、plant 或留空"
        )

    is_allergen = _integer(row.get("is_allergen"), "is_allergen", line_number)
    if is_allergen not in (0, 1):
        raise DataValidationError(
            f"{_location('is_allergen', line_number)} 只能填 0 或 1"
        )

    allergen_type = _optional_text(row.get("allergen_type"))
    if allergen_type is not None and allergen_type not in ALLERGEN_TYPES:
        raise DataValidationError(
            f"{_location('allergen_type', line_number)} 不是约定的八类之一：{allergen_type!r}"
        )
    if is_allergen == 1 and allergen_type is None:
        raise DataValidationError(
            f"{_location('allergen_type', line_number)} 在 is_allergen=1 时必须填写"
        )
    if is_allergen == 0 and allergen_type is not None:
        raise DataValidationError(
            f"{_location('allergen_type', line_number)} 在 is_allergen=0 时必须留空"
        )

    min_month = _integer(row.get("min_month"), "min_month", line_number)
    if min_month < 6:
        raise DataValidationError(f"{_location('min_month', line_number)} 不得小于 6")

    texture_stage = _integer(row.get("texture_stage"), "texture_stage", line_number)
    if texture_stage not in (1, 2, 3, 4):
        raise DataValidationError(
            f"{_location('texture_stage', line_number)} 只能填 1、2、3、4"
        )

    months = parse_season_months(
        row.get("season_months"),
        _location("season_months", line_number),
    )
    edible_ratio = _optional_float(row.get("edible_ratio"), "edible_ratio", line_number)
    if edible_ratio is not None and edible_ratio > 1:
        raise DataValidationError(
            f"{_location('edible_ratio', line_number)} 必须在 0 到 1 之间"
        )

    return {
        "id": food_id,
        "name": _required_text(row.get("name"), "name", line_number),
        "category": category,
        "iron_mg_per_100g": _optional_float(
            row.get("iron_mg_per_100g"), "iron_mg_per_100g", line_number
        ),
        "zinc_mg_per_100g": _optional_float(
            row.get("zinc_mg_per_100g"), "zinc_mg_per_100g", line_number
        ),
        "nutrient_source": nutrient_source,
        "is_allergen": is_allergen,
        "allergen_type": allergen_type,
        "min_month": min_month,
        "texture_stage": texture_stage,
        "season_months": ",".join(str(month) for month in months),
        "prep_note": _optional_text(row.get("prep_note")),
        "source": _required_text(row.get("source"), "source", line_number),
        "avg_price": _optional_float(row.get("avg_price"), "avg_price", line_number),
        "edible_ratio": edible_ratio,
    }
