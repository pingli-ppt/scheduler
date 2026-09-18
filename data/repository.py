"""供算法层调用的稳定数据接口。"""

from __future__ import annotations

from .database import init_database, open_database
from .validate import (
    ALLERGEN_TYPES,
    CATEGORIES,
    FOOD_COLUMNS,
    RECORD_STATUSES,
    DataValidationError,
    parse_csv_list,
    parse_iso_date,
    parse_season_months,
)


class ChildNotFoundError(LookupError):
    """指定的儿童编号不存在。"""


class FoodNotFoundError(LookupError):
    """指定的食物编号不存在。"""


def _ensure_child_exists(connection, child_id: str) -> None:
    row = connection.execute(
        "SELECT 1 FROM children WHERE id = ?",
        (child_id,),
    ).fetchone()
    if row is None:
        raise ChildNotFoundError(f"儿童编号不存在：{child_id}")


def load_foods() -> list[dict]:
    """读取全部食物，字段名与 foods.csv 一致。"""

    init_database()
    columns = ", ".join(FOOD_COLUMNS)
    with open_database() as connection:
        rows = connection.execute(
            f"SELECT {columns} FROM foods ORDER BY id"  # 列名来自固定契约常量
        ).fetchall()

    foods: list[dict] = []
    for row in rows:
        food = dict(row)
        food["season_months"] = parse_season_months(food["season_months"])
        foods.append(food)
    return foods


def load_child(child_id: str) -> dict:
    """读取儿童档案，并将日期和已知过敏类别转换为约定类型。"""

    init_database()
    with open_database() as connection:
        row = connection.execute(
            """
            SELECT id, nickname, birth_date, weaning_start,
                   known_allergens, "group", created_at
            FROM children
            WHERE id = ?
            """,
            (child_id,),
        ).fetchone()

    if row is None:
        raise ChildNotFoundError(f"儿童编号不存在：{child_id}")

    child = dict(row)
    child["birth_date"] = parse_iso_date(child["birth_date"], "birth_date")
    child["weaning_start"] = parse_iso_date(child["weaning_start"], "weaning_start")
    child["known_allergens"] = parse_csv_list(
        child["known_allergens"],
        "known_allergens",
        ALLERGEN_TYPES,
    )
    return child


def load_history(child_id: str) -> list[dict]:
    """按日期升序返回食物历史；每条记录只暴露契约约定的三个字段。"""

    init_database()
    with open_database() as connection:
        _ensure_child_exists(connection, child_id)
        rows = connection.execute(
            """
            SELECT food_id, date, status
            FROM food_records
            WHERE child_id = ?
            ORDER BY date ASC, id ASC
            """,
            (child_id,),
        ).fetchall()

    history: list[dict] = []
    for row in rows:
        item = dict(row)
        item["date"] = parse_iso_date(item["date"], "food_records.date")
        history.append(item)
    return history


def load_daily_intake(child_id: str) -> list[dict]:
    """按日期升序返回每日膳食类别记录。"""

    init_database()
    with open_database() as connection:
        _ensure_child_exists(connection, child_id)
        rows = connection.execute(
            """
            SELECT date, categories, meal_count, is_breastfed, milk_feeds
            FROM daily_intake
            WHERE child_id = ?
            ORDER BY date ASC, id ASC
            """,
            (child_id,),
        ).fetchall()

    intake: list[dict] = []
    for row in rows:
        item = dict(row)
        item["date"] = parse_iso_date(item["date"], "daily_intake.date")
        item["categories"] = parse_csv_list(
            item["categories"],
            "categories",
            CATEGORIES,
        )
        intake.append(item)
    return intake


def save_record(
    child_id,
    food_id,
    date,
    status,
    note,
) -> None:
    """保存一次计划或上报记录。"""

    if status not in RECORD_STATUSES:
        allowed = ", ".join(sorted(RECORD_STATUSES))
        raise DataValidationError(f"status 必须是以下值之一：{allowed}")
    record_date = parse_iso_date(date, "date")
    try:
        normalized_food_id = int(food_id)
    except (TypeError, ValueError) as exc:
        raise DataValidationError("food_id 必须是整数") from exc

    init_database()
    with open_database() as connection:
        _ensure_child_exists(connection, child_id)
        food = connection.execute(
            "SELECT 1 FROM foods WHERE id = ?",
            (normalized_food_id,),
        ).fetchone()
        if food is None:
            raise FoodNotFoundError(f"食物编号不存在：{normalized_food_id}")

        connection.execute(
            """
            INSERT INTO food_records (child_id, food_id, date, status, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                child_id,
                normalized_food_id,
                record_date.isoformat(),
                status,
                None if note is None else str(note),
            ),
        )
