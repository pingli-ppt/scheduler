"""兼容仓库预留的 loader 入口。

新代码建议从 ``data.repository`` 导入；已有代码若使用 ``data.loader``，得到的
是完全相同的五个数据接口。
"""

from .repository import (
    ChildNotFoundError,
    FoodNotFoundError,
    load_child,
    load_daily_intake,
    load_foods,
    load_history,
    save_record,
)

__all__ = [
    "ChildNotFoundError",
    "FoodNotFoundError",
    "load_foods",
    "load_child",
    "load_history",
    "load_daily_intake",
    "save_record",
]
