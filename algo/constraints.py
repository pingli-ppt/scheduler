"""候选食物硬性约束 C1～C6。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from .constants import D_COOLDOWN, MAX_REFUSE


def age_in_months(birth_date: date, target_date: date) -> int:
    """计算目标日期时的完整月龄，不进位。"""

    months = (target_date.year - birth_date.year) * 12
    months += target_date.month - birth_date.month
    if target_date.day < birth_date.day:
        months -= 1
    return months


def allowed_texture_stage(month_age: int) -> int:
    """返回月龄允许的最高食物形态阶段。"""

    if month_age < 6:
        return 0
    if month_age == 6:
        return 1
    if month_age <= 8:
        return 2
    if month_age <= 11:
        return 3
    return 4


def has_record_on_date(history: Iterable[Mapping], target_date: date) -> bool:
    """历史记录优先：当天已有记录时，不再安排另一种新食物。"""

    return any(item["date"] == target_date for item in history)


def is_food_eligible(
    food: Mapping,
    child: Mapping,
    target_date: date,
    history: Iterable[Mapping],
    planned_food_ids: set[int] | None = None,
) -> bool:
    """判断食物在指定日期是否通过 C2～C6。"""

    source = str(food.get("source") or "").strip()
    if not source:
        return False

    month_age = age_in_months(child["birth_date"], target_date)
    if month_age < int(food["min_month"]):
        return False
    if int(food["texture_stage"]) > allowed_texture_stage(month_age):
        return False

    allergen_type = food.get("allergen_type")
    if allergen_type and allergen_type in set(child.get("known_allergens") or []):
        return False

    food_id = int(food["id"])
    if planned_food_ids and food_id in planned_food_ids:
        return False

    refused_count = 0
    for item in history:
        if int(item["food_id"]) != food_id:
            continue
        status = item["status"]
        if status in {"passed", "planned"}:
            return False
        if status == "refused":
            refused_count += 1
        elif status == "reaction":
            elapsed = (target_date - item["date"]).days
            if 0 <= elapsed < D_COOLDOWN:
                return False

    return refused_count < MAX_REFUSE

