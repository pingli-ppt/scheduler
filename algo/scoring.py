"""候选食物评分、推荐理由和来源说明。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from .constants import (
    NUTRIENT_RICH_THRESHOLD,
    PLANT_NUTRIENT_FACTOR,
    REASON_PRIORITY,
    RECENT_CATEGORY_DAYS,
    WEIGHTS,
)
from .constraints import age_in_months


@dataclass(frozen=True)
class ScoreResult:
    """一次评分的原始子分、加权贡献、总分及主导项。"""

    total: float
    components: dict[str, float]
    contributions: dict[str, float]
    dominant: str


def _number(value: object) -> float:
    return 0.0 if value is None else float(value)


def _nutrient_score(food: Mapping, field: str) -> float:
    source_factor = (
        1.0
        if food.get("nutrient_source") == "animal"
        else PLANT_NUTRIENT_FACTOR
    )
    amount = max(_number(food.get(field)), 0.0)
    return min(amount / NUTRIENT_RICH_THRESHOLD, 1.0) * source_factor


def _counted_records(history: Iterable[Mapping]) -> Iterable[Mapping]:
    """拒食表示未摄入，不计入类别覆盖或营养间隔。"""

    return (item for item in history if item["status"] != "refused")


def recent_categories(
    target_date: date,
    food_by_id: Mapping[int, Mapping],
    history: Iterable[Mapping],
    plan: Iterable[Mapping],
) -> set[str]:
    """返回目标日前 7 天内历史与本次计划覆盖的食物类别。"""

    start = target_date - timedelta(days=RECENT_CATEGORY_DAYS)
    categories: set[str] = set()
    for item in _counted_records(history):
        if start <= item["date"] < target_date:
            food = food_by_id.get(int(item["food_id"]))
            if food:
                categories.add(str(food["category"]))
    for item in plan:
        if start <= item["date"] < target_date:
            food = food_by_id.get(int(item["food_id"]))
            if food:
                categories.add(str(food["category"]))
    return categories


def score_food(
    food: Mapping,
    child: Mapping,
    target_date: date,
    food_by_id: Mapping[int, Mapping],
    history: Iterable[Mapping],
    plan: Iterable[Mapping],
) -> ScoreResult:
    """按规则计算五项子分与总分。"""

    covered = recent_categories(target_date, food_by_id, history, plan)
    months = age_in_months(child["birth_date"], target_date)
    season_months = list(food.get("season_months") or [])
    components = {
        "iron": _nutrient_score(food, "iron_mg_per_100g"),
        "zinc": _nutrient_score(food, "zinc_mg_per_100g"),
        "gap": 1.0 if food["category"] not in covered else 0.0,
        "allergen_early": (
            1.0 if food.get("allergen_type") and months < 12 else 0.0
        ),
        "season": (
            1.0
            if not season_months or target_date.month in season_months
            else 0.0
        ),
    }
    contributions = {name: components[name] * WEIGHTS[name] for name in WEIGHTS}
    total = round(sum(contributions.values()), 6)
    dominant = max(
        REASON_PRIORITY,
        key=lambda name: (contributions[name], -REASON_PRIORITY.index(name)),
    )
    return ScoreResult(total, components, contributions, dominant)


def _is_rich(food: Mapping, nutrient: str) -> bool:
    if nutrient == "iron" and food.get("category") == "肉类":
        return True
    return _number(food.get(f"{nutrient}_mg_per_100g")) >= NUTRIENT_RICH_THRESHOLD


def _days_without_nutrient(
    nutrient: str,
    target_date: date,
    food_by_id: Mapping[int, Mapping],
    history: Iterable[Mapping],
    plan: Iterable[Mapping],
) -> int:
    relevant_dates: list[date] = []
    for item in _counted_records(history):
        food = food_by_id.get(int(item["food_id"]))
        if item["date"] < target_date and food and _is_rich(food, nutrient):
            relevant_dates.append(item["date"])
    for item in plan:
        food = food_by_id.get(int(item["food_id"]))
        if item["date"] < target_date and food and _is_rich(food, nutrient):
            relevant_dates.append(item["date"])
    if not relevant_dates:
        return RECENT_CATEGORY_DAYS
    return min((target_date - max(relevant_dates)).days, RECENT_CATEGORY_DAYS)


def build_reason(
    dominant: str,
    food: Mapping,
    target_date: date,
    food_by_id: Mapping[int, Mapping],
    history: Iterable[Mapping],
    plan: Iterable[Mapping],
) -> str:
    """按主导评分项生成受控文案。"""

    if dominant == "iron":
        days = _days_without_nutrient("iron", target_date, food_by_id, history, plan)
        return (
            f"本周已 {days} 天未安排富铁食物。"
            "6 个月后母乳仅能提供约 5% 的铁需要量，其余需从辅食补充。"
        )
    if dominant == "zinc":
        days = _days_without_nutrient("zinc", target_date, food_by_id, history, plan)
        return (
            f"本周已 {days} 天未安排富锌食物。"
            "全国调查显示 6～11 月龄婴儿辅食的锌密度偏低。"
        )
    if dominant == "gap":
        return (
            f"七类食物中的「{food['category']}」本周尚未覆盖。"
            "国家标准要求每天摄入七类中的四类及以上。"
        )
    if dominant == "season":
        return f"{target_date.month} 月正当季。"
    return "此为八大致敏物质之一，建议在 12 月龄前引入并观察。"


def build_source(food: Mapping, dominant: str) -> str:
    """把食物资料来源与触发的评分规则放在同一字段中。"""

    return f"{str(food['source']).strip()}（评分-{dominant}）"
