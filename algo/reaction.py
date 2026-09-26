"""不良反应上报后的整段重排。"""

from __future__ import annotations

from datetime import date, timedelta

from data.repository import record_reaction_and_delete_future_plans

from .constants import N_OBSERVE
from .scheduler import generate_schedule


def report_reaction(
    child_id: str,
    food_id: int,
    reaction_date: date,
) -> list[dict]:
    """记录反应、丢弃后续计划，并从观察期结束日起重排六周。"""

    if not isinstance(reaction_date, date):
        raise TypeError("reaction_date 必须是 datetime.date")
    record_reaction_and_delete_future_plans(
        child_id,
        food_id,
        reaction_date,
        None,
    )
    return generate_schedule(
        child_id,
        weeks=6,
        today=reaction_date + timedelta(days=N_OBSERVE),
    )
