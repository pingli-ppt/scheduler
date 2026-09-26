"""六周辅食引入排程器。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta

from data.repository import load_child, load_foods, load_history

from .constants import N_OBSERVE, TEXTURE_DESC
from .constraints import age_in_months, has_record_on_date, is_food_eligible
from .scoring import build_reason, build_source, score_food


def _last_new_food_date(history: Iterable[Mapping]) -> date | None:
    dates = [
        item["date"]
        for item in history
        if item["status"] in {"passed", "planned", "reaction"}
    ]
    return max(dates, default=None)


def build_schedule(
    child: Mapping,
    foods: Iterable[Mapping],
    history: Iterable[Mapping],
    weeks: int = 6,
    start_date: date | None = None,
) -> list[dict]:
    """使用已经加载的数据生成计划，不执行数据库写入。"""

    if weeks <= 0:
        return []
    start = start_date or date.today()
    if age_in_months(child["birth_date"], start) < 6:
        return []

    food_list = list(foods)
    history_list = list(history)
    food_by_id = {int(food["id"]): food for food in food_list}
    end = start + timedelta(days=weeks * 7)
    last_new = _last_new_food_date(history_list)
    plan: list[dict] = []
    planned_food_ids: set[int] = set()

    target = start
    while target < end:
        if has_record_on_date(history_list, target):
            target += timedelta(days=1)
            continue
        if last_new is not None and (target - last_new).days < N_OBSERVE:
            target += timedelta(days=1)
            continue

        candidates = [
            food
            for food in food_list
            if is_food_eligible(
                food,
                child,
                target,
                history_list,
                planned_food_ids,
            )
        ]
        if not candidates:
            target += timedelta(days=1)
            continue

        scored = [
            (
                score_food(food, child, target, food_by_id, history_list, plan),
                food,
            )
            for food in candidates
        ]
        result, best = min(
            scored,
            key=lambda item: (-item[0].total, int(item[1]["id"])),
        )
        food_id = int(best["id"])
        plan.append(
            {
                "date": target,
                "food_id": food_id,
                "food_name": str(best["name"]),
                "texture": int(best["texture_stage"]),
                "texture_desc": TEXTURE_DESC[int(best["texture_stage"])],
                "reason": build_reason(
                    result.dominant,
                    best,
                    target,
                    food_by_id,
                    history_list,
                    plan,
                ),
                "source": build_source(best, result.dominant),
            }
        )
        planned_food_ids.add(food_id)
        last_new = target
        target += timedelta(days=1)

    return plan


def generate_schedule(
    child_id: str,
    weeks: int = 6,
    today: date | None = None,
) -> list[dict]:
    """从稳定数据接口读取输入并生成计划。"""

    return build_schedule(
        child=load_child(child_id),
        foods=load_foods(),
        history=load_history(child_id),
        weeks=weeks,
        start_date=today,
    )
