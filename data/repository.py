"""供算法层调用的稳定数据接口。"""

from __future__ import annotations

from typing import Iterable, Mapping

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


class RecommendationNotFoundError(LookupError):
    """指定的推荐编号不存在。"""


def _ensure_child_exists(connection, child_id: str) -> None:
    row = connection.execute(
        "SELECT 1 FROM children WHERE id = ?",
        (child_id,),
    ).fetchone()
    if row is None:
        raise ChildNotFoundError(f"儿童编号不存在：{child_id}")


def _ensure_food_exists(connection, food_id: int) -> None:
    row = connection.execute(
        "SELECT 1 FROM foods WHERE id = ?",
        (food_id,),
    ).fetchone()
    if row is None:
        raise FoodNotFoundError(f"食物编号不存在：{food_id}")


def _positive_int(value, field_name: str) -> int:
    if isinstance(value, bool):
        raise DataValidationError(f"{field_name} 必须是正整数")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise DataValidationError(f"{field_name} 必须是正整数") from exc
    if number <= 0:
        raise DataValidationError(f"{field_name} 必须是正整数")
    return number


def _nonnegative_int(value, field_name: str) -> int:
    if isinstance(value, bool):
        raise DataValidationError(f"{field_name} 必须是非负整数")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise DataValidationError(f"{field_name} 必须是非负整数") from exc
    if number < 0:
        raise DataValidationError(f"{field_name} 必须是非负整数")
    return number


def _flag(value, field_name: str) -> int:
    if isinstance(value, bool):
        return int(value)
    if value in (0, 1):
        return int(value)
    raise DataValidationError(f"{field_name} 必须是布尔值或 0/1")


def _load_recommendation_row(connection, recommendation_id: int):
    row = connection.execute(
        """
        SELECT r.*, outcome.status AS outcome_status
        FROM recommendations AS r
        LEFT JOIN food_records AS outcome ON outcome.id = r.outcome_record_id
        WHERE r.id = ?
        """,
        (recommendation_id,),
    ).fetchone()
    if row is None:
        raise RecommendationNotFoundError(f"推荐编号不存在：{recommendation_id}")
    return row


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


def save_child(
    child_id,
    nickname,
    birth_date,
    weaning_start,
    known_allergens,
    group,
) -> None:
    """新增或更新儿童档案。"""

    normalized_id = str(child_id).strip()
    normalized_nickname = str(nickname).strip()
    if not normalized_id:
        raise DataValidationError("child_id 不允许为空")
    if not normalized_nickname:
        raise DataValidationError("nickname 不允许为空")
    normalized_birth_date = parse_iso_date(birth_date, "birth_date")
    normalized_weaning_start = parse_iso_date(weaning_start, "weaning_start")
    if normalized_weaning_start < normalized_birth_date:
        raise DataValidationError("weaning_start 不能早于 birth_date")
    normalized_allergens = parse_csv_list(
        known_allergens,
        "known_allergens",
        ALLERGEN_TYPES,
    )
    if group not in {"test", "control"}:
        raise DataValidationError("group 只能是 test 或 control")

    init_database()
    with open_database() as connection:
        connection.execute(
            """
            INSERT INTO children (
                id, nickname, birth_date, weaning_start,
                known_allergens, "group"
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                nickname = excluded.nickname,
                birth_date = excluded.birth_date,
                weaning_start = excluded.weaning_start,
                known_allergens = excluded.known_allergens,
                "group" = excluded."group"
            """,
            (
                normalized_id,
                normalized_nickname,
                normalized_birth_date.isoformat(),
                normalized_weaning_start.isoformat(),
                ",".join(normalized_allergens),
                group,
            ),
        )


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


def save_daily_intake(
    child_id,
    date,
    categories,
    meal_count,
    is_breastfed,
    milk_feeds,
) -> None:
    """新增或覆盖某个儿童一天的膳食记录。"""

    intake_date = parse_iso_date(date, "date")
    normalized_categories = parse_csv_list(categories, "categories", CATEGORIES)
    normalized_meal_count = _nonnegative_int(meal_count, "meal_count")
    normalized_is_breastfed = _flag(is_breastfed, "is_breastfed")
    normalized_milk_feeds = _nonnegative_int(milk_feeds, "milk_feeds")

    init_database()
    with open_database() as connection:
        _ensure_child_exists(connection, child_id)
        connection.execute(
            """
            INSERT INTO daily_intake (
                child_id, date, categories, meal_count,
                is_breastfed, milk_feeds
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(child_id, date) DO UPDATE SET
                categories = excluded.categories,
                meal_count = excluded.meal_count,
                is_breastfed = excluded.is_breastfed,
                milk_feeds = excluded.milk_feeds,
                submitted_at = CURRENT_TIMESTAMP
            """,
            (
                child_id,
                intake_date.isoformat(),
                ",".join(normalized_categories),
                normalized_meal_count,
                normalized_is_breastfed,
                normalized_milk_feeds,
            ),
        )


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


def save_recommendations(
    child_id: str,
    recommendations: Iterable[Mapping[str, object]],
) -> list[int]:
    """保存实际展示给家庭的一批推荐，并返回对应的推荐编号。

    展示字段会一并保存，保证刷新页面后仍能还原当时实际展示的内容。相同儿童、
    食物和安排日期的有效推荐重复保存时会返回原编号，避免页面刷新造成重复记录。
    """

    normalized: list[tuple[int, object, dict[str, object | None]]] = []
    for index, item in enumerate(recommendations, start=1):
        if not isinstance(item, Mapping):
            raise DataValidationError(f"第 {index} 条推荐必须是包含 food_id 和 date 的映射")
        food_id = _positive_int(item.get("food_id"), f"第 {index} 条推荐的 food_id")
        scheduled_date = parse_iso_date(item.get("date"), f"第 {index} 条推荐的 date")
        display = {
            "food_name": None if item.get("food_name") is None else str(item["food_name"]),
            "texture": (
                None
                if item.get("texture") is None
                else _positive_int(item.get("texture"), f"第 {index} 条推荐的 texture")
            ),
            "texture_desc": (
                None if item.get("texture_desc") is None else str(item["texture_desc"])
            ),
            "reason": None if item.get("reason") is None else str(item["reason"]),
            "display_source": (
                None if item.get("source") is None else str(item["source"])
            ),
        }
        if display["texture"] is not None and int(display["texture"]) not in {1, 2, 3, 4}:
            raise DataValidationError(f"第 {index} 条推荐的 texture 必须在 1 到 4 之间")
        normalized.append((food_id, scheduled_date, display))

    init_database()
    recommendation_ids: list[int] = []
    with open_database() as connection:
        _ensure_child_exists(connection, child_id)
        for food_id, scheduled_date, display in normalized:
            _ensure_food_exists(connection, food_id)
            date_text = scheduled_date.isoformat()
            existing = connection.execute(
                """
                SELECT id
                FROM recommendations
                WHERE child_id = ? AND food_id = ? AND scheduled_date = ?
                  AND cancelled_at IS NULL
                """,
                (child_id, food_id, date_text),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    """
                    UPDATE recommendations
                    SET food_name = COALESCE(food_name, ?),
                        texture = COALESCE(texture, ?),
                        texture_desc = COALESCE(texture_desc, ?),
                        reason = COALESCE(reason, ?),
                        display_source = COALESCE(display_source, ?)
                    WHERE id = ?
                    """,
                    (
                        display["food_name"],
                        display["texture"],
                        display["texture_desc"],
                        display["reason"],
                        display["display_source"],
                        existing["id"],
                    ),
                )
                recommendation_ids.append(int(existing["id"]))
                continue

            planned = connection.execute(
                """
                INSERT INTO food_records (child_id, food_id, date, status, note)
                VALUES (?, ?, ?, 'planned', NULL)
                """,
                (child_id, food_id, date_text),
            )
            recommendation = connection.execute(
                """
                INSERT INTO recommendations (
                    child_id, food_id, scheduled_date,
                    food_name, texture, texture_desc, reason, display_source,
                    planned_record_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    child_id,
                    food_id,
                    date_text,
                    display["food_name"],
                    display["texture"],
                    display["texture_desc"],
                    display["reason"],
                    display["display_source"],
                    planned.lastrowid,
                ),
            )
            recommendation_ids.append(int(recommendation.lastrowid))

    return recommendation_ids


def save_recommendation(child_id, food_id, date) -> int:
    """保存一条实际展示的推荐，并返回 ``recommendation_id``。"""

    return save_recommendations(
        child_id,
        [{"food_id": food_id, "date": date}],
    )[0]


def load_recommendations(child_id: str) -> list[dict]:
    """按安排日期返回推荐、采纳、摄入、结果与重排状态。"""

    init_database()
    with open_database() as connection:
        _ensure_child_exists(connection, child_id)
        rows = connection.execute(
            """
            SELECT
                r.id AS recommendation_id,
                r.child_id,
                r.food_id,
                COALESCE(r.food_name, food.name) AS food_name,
                COALESCE(r.texture, food.texture_stage) AS texture,
                r.texture_desc,
                r.reason,
                r.display_source AS source,
                r.scheduled_date AS date,
                r.recommended_at,
                r.planned_record_id,
                r.adopted,
                r.adopted_at,
                r.consumed,
                r.consumed_at,
                outcome.status AS outcome,
                outcome.date AS outcome_date,
                outcome.note AS outcome_note,
                r.outcome_record_id,
                r.cancelled_at,
                r.cancellation_reason,
                r.reschedule_triggered,
                r.reschedule_succeeded,
                r.reschedule_plan_count,
                r.rescheduled_at
            FROM recommendations AS r
            JOIN foods AS food ON food.id = r.food_id
            LEFT JOIN food_records AS outcome ON outcome.id = r.outcome_record_id
            WHERE r.child_id = ?
            ORDER BY r.scheduled_date ASC, r.id ASC
            """,
            (child_id,),
        ).fetchall()

    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["date"] = parse_iso_date(item["date"], "recommendations.scheduled_date")
        if item["outcome_date"] is not None:
            item["outcome_date"] = parse_iso_date(
                item["outcome_date"],
                "food_records.date",
            )
        for field in (
            "adopted",
            "consumed",
            "reschedule_succeeded",
        ):
            if item[field] is not None:
                item[field] = bool(item[field])
        item["reschedule_triggered"] = bool(item["reschedule_triggered"])
        result.append(item)
    return result


def load_recommendation(recommendation_id) -> dict:
    """按推荐编号返回一条完整的推荐追踪记录。"""

    normalized_id = _positive_int(recommendation_id, "recommendation_id")
    init_database()
    with open_database() as connection:
        row = connection.execute(
            "SELECT child_id FROM recommendations WHERE id = ?",
            (normalized_id,),
        ).fetchone()
    if row is None:
        raise RecommendationNotFoundError(f"推荐编号不存在：{normalized_id}")
    for item in load_recommendations(str(row["child_id"])):
        if item["recommendation_id"] == normalized_id:
            return item
    raise RecommendationNotFoundError(f"推荐编号不存在：{normalized_id}")


def record_recommendation_engagement(
    recommendation_id,
    *,
    adopted,
    consumed=None,
) -> None:
    """记录家长是否采纳，以及宝宝是否实际摄入。"""

    normalized_id = _positive_int(recommendation_id, "recommendation_id")
    normalized_adopted = _flag(adopted, "adopted")
    normalized_consumed = None if consumed is None else _flag(consumed, "consumed")
    if normalized_adopted == 0:
        if normalized_consumed == 1:
            raise DataValidationError("未采纳的推荐不能记录为已摄入")
        normalized_consumed = 0

    init_database()
    with open_database() as connection:
        row = _load_recommendation_row(connection, normalized_id)
        if row["cancelled_at"] is not None:
            raise DataValidationError("已取消的推荐不能再记录采纳或摄入")
        if row["outcome_record_id"] is not None:
            raise DataValidationError("已有最终结果的推荐不能再修改采纳或摄入")
        connection.execute(
            """
            UPDATE recommendations
            SET adopted = ?,
                adopted_at = CURRENT_TIMESTAMP,
                consumed = COALESCE(?, consumed),
                consumed_at = CASE
                    WHEN ? IS NULL THEN consumed_at
                    ELSE CURRENT_TIMESTAMP
                END
            WHERE id = ?
            """,
            (
                normalized_adopted,
                normalized_consumed,
                normalized_consumed,
                normalized_id,
            ),
        )


def record_reaction_and_delete_future_plans(
    child_id,
    food_id,
    date,
    note=None,
    *,
    recommendation_id=None,
) -> int:
    """原子记录一次不良反应，并删除该日期之后的未执行计划。

    返回删除的 ``planned`` 记录数。把两个动作放在同一事务中，可以避免只写入
    反应记录、却因后续异常保留旧计划的中间状态。
    """

    reaction_date = parse_iso_date(date, "date")
    normalized_food_id = _positive_int(food_id, "food_id")
    normalized_recommendation_id = (
        None
        if recommendation_id is None
        else _positive_int(recommendation_id, "recommendation_id")
    )

    init_database()
    with open_database() as connection:
        _ensure_child_exists(connection, child_id)
        _ensure_food_exists(connection, normalized_food_id)

        recommendation = None
        if normalized_recommendation_id is not None:
            recommendation = _load_recommendation_row(
                connection,
                normalized_recommendation_id,
            )
            if (
                recommendation["child_id"] != child_id
                or int(recommendation["food_id"]) != normalized_food_id
            ):
                raise DataValidationError("推荐编号与儿童或食物不匹配")
            if recommendation["cancelled_at"] is not None:
                raise DataValidationError("已取消的推荐不能上报结果")
            if recommendation["outcome_record_id"] is not None:
                if recommendation["outcome_status"] == "reaction":
                    return 0
                raise DataValidationError("该推荐已经记录了其他最终结果")

        reaction = connection.execute(
            """
            INSERT INTO food_records (child_id, food_id, date, status, note)
            VALUES (?, ?, ?, 'reaction', ?)
            """,
            (
                child_id,
                normalized_food_id,
                reaction_date.isoformat(),
                None if note is None else str(note),
            ),
        )
        if normalized_recommendation_id is not None:
            connection.execute(
                """
                UPDATE recommendations
                SET adopted = 1,
                    adopted_at = COALESCE(adopted_at, CURRENT_TIMESTAMP),
                    consumed = 1,
                    consumed_at = COALESCE(consumed_at, CURRENT_TIMESTAMP),
                    outcome_record_id = ?,
                    reschedule_triggered = 1
                WHERE id = ?
                """,
                (reaction.lastrowid, normalized_recommendation_id),
            )

        cancel_sql = """
            UPDATE recommendations
            SET cancelled_at = CURRENT_TIMESTAMP,
                cancellation_reason = 'reaction_replan'
            WHERE child_id = ? AND scheduled_date > ?
              AND cancelled_at IS NULL AND outcome_record_id IS NULL
        """
        cancel_params: list[object] = [child_id, reaction_date.isoformat()]
        if normalized_recommendation_id is not None:
            cancel_sql += " AND id <> ?"
            cancel_params.append(normalized_recommendation_id)
        connection.execute(cancel_sql, cancel_params)

        cursor = connection.execute(
            """
            DELETE FROM food_records
            WHERE child_id = ? AND status = 'planned' AND date > ?
            """,
            (child_id, reaction_date.isoformat()),
        )
        return cursor.rowcount


def record_recommendation_outcome(
    recommendation_id,
    date,
    status,
    note=None,
) -> int:
    """记录推荐的最终结果；反应结果同时取消后续旧计划。

    返回因反应而删除的未来 ``planned`` 记录数；其他结果返回 0。
    """

    normalized_id = _positive_int(recommendation_id, "recommendation_id")
    if status not in {"passed", "refused", "reaction"}:
        raise DataValidationError("推荐结果只能是 passed、refused 或 reaction")
    outcome_date = parse_iso_date(date, "date")

    init_database()
    with open_database() as connection:
        row = _load_recommendation_row(connection, normalized_id)
        if row["cancelled_at"] is not None:
            raise DataValidationError("已取消的推荐不能上报结果")
        if row["outcome_record_id"] is not None:
            if row["outcome_status"] == status:
                return 0
            raise DataValidationError("该推荐已经记录了其他最终结果")
        child_id = str(row["child_id"])
        food_id = int(row["food_id"])

    if status == "reaction":
        return record_reaction_and_delete_future_plans(
            child_id,
            food_id,
            outcome_date,
            note,
            recommendation_id=normalized_id,
        )

    consumed = 1 if status == "passed" else 0
    with open_database() as connection:
        row = _load_recommendation_row(connection, normalized_id)
        if row["cancelled_at"] is not None:
            raise DataValidationError("已取消的推荐不能上报结果")
        if row["outcome_record_id"] is not None:
            if row["outcome_status"] == status:
                return 0
            raise DataValidationError("该推荐已经记录了其他最终结果")
        outcome = connection.execute(
            """
            INSERT INTO food_records (child_id, food_id, date, status, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                child_id,
                food_id,
                outcome_date.isoformat(),
                status,
                None if note is None else str(note),
            ),
        )
        connection.execute(
            """
            UPDATE recommendations
            SET adopted = 1,
                adopted_at = COALESCE(adopted_at, CURRENT_TIMESTAMP),
                consumed = ?,
                consumed_at = COALESCE(consumed_at, CURRENT_TIMESTAMP),
                outcome_record_id = ?
            WHERE id = ?
            """,
            (consumed, outcome.lastrowid, normalized_id),
        )
    return 0


def record_reschedule_result(
    recommendation_id,
    *,
    succeeded,
    plan_count,
) -> None:
    """记录一次反应触发的重排是否完成，以及新计划条目数。"""

    normalized_id = _positive_int(recommendation_id, "recommendation_id")
    normalized_succeeded = _flag(succeeded, "succeeded")
    normalized_plan_count = _nonnegative_int(plan_count, "plan_count")

    init_database()
    with open_database() as connection:
        row = _load_recommendation_row(connection, normalized_id)
        if row["reschedule_triggered"] != 1:
            raise DataValidationError("该推荐没有触发重排")
        connection.execute(
            """
            UPDATE recommendations
            SET reschedule_succeeded = ?,
                reschedule_plan_count = ?,
                rescheduled_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized_succeeded, normalized_plan_count, normalized_id),
        )
