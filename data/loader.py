"""兼容仓库预留的 loader 入口。

新代码建议从 ``data.repository`` 导入；已有代码若使用 ``data.loader``，仍可
访问原有接口以及新增的实验记录接口。
"""

from .repository import (
    ChildNotFoundError,
    FoodNotFoundError,
    RecommendationNotFoundError,
    load_child,
    load_daily_intake,
    load_foods,
    load_history,
    load_recommendations,
    record_recommendation_engagement,
    record_recommendation_outcome,
    record_reaction_and_delete_future_plans,
    record_reschedule_result,
    save_daily_intake,
    save_recommendation,
    save_recommendations,
    save_record,
)

__all__ = [
    "ChildNotFoundError",
    "FoodNotFoundError",
    "RecommendationNotFoundError",
    "load_foods",
    "load_child",
    "load_history",
    "load_daily_intake",
    "load_recommendations",
    "save_record",
    "save_daily_intake",
    "save_recommendation",
    "save_recommendations",
    "record_recommendation_engagement",
    "record_recommendation_outcome",
    "record_reaction_and_delete_future_plans",
    "record_reschedule_result",
]
