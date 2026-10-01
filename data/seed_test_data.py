"""把杨紫玥 0930 版测试数据导入独立的本地联调数据库。"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from data.database import PROJECT_ROOT, init_database, resolve_database_path
from data.import_foods import import_foods
from data.repository import save_child, save_daily_intake


FIXTURES = PROJECT_ROOT / "tests"
DEFAULT_DATABASE = PROJECT_ROOT / "tmp" / "guochu-test.sqlite3"


def _read_csv(name: str) -> list[dict[str, str]]:
    with (FIXTURES / name).open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def seed(database_path: str | Path) -> Path:
    path = resolve_database_path(database_path)
    os.environ["GUOCHU_DB_PATH"] = str(path)
    init_database(path)
    food_summary = import_foods(FIXTURES / "foods_test.csv", path)

    children = _read_csv("children_test.csv")
    for row in children:
        save_child(
            row["id"],
            row["nickname"],
            row["birth_date"],
            row["weaning_start"],
            row["known_allergens"],
            row["group"],
        )

    intake = _read_csv("daily_intake_test.csv")
    for row in intake:
        save_daily_intake(
            row["child_id"],
            row["date"],
            row["categories"],
            row["meal_count"],
            row["is_breastfed"] == "1",
            row["milk_feeds"],
        )

    print(
        f"测试库已准备：{path}（食物 {food_summary.total} 条，"
        f"儿童 {len(children)} 条，每日膳食 {len(intake)} 条）"
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="准备果初 API 本地联调测试库")
    parser.add_argument("database", nargs="?", default=DEFAULT_DATABASE)
    args = parser.parse_args()
    seed(args.database)


if __name__ == "__main__":
    main()
