"""将 foods.csv 幂等导入 SQLite；同一 id 再次导入时更新原记录。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from .database import init_database, open_database
from .validate import (
    FOOD_COLUMNS,
    DataValidationError,
    normalize_food_row,
    validate_food_headers,
)


DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "foods.csv"

UPSERT_SQL = f"""
INSERT INTO foods ({', '.join(FOOD_COLUMNS)})
VALUES ({', '.join('?' for _ in FOOD_COLUMNS)})
ON CONFLICT(id) DO UPDATE SET
    name = excluded.name,
    category = excluded.category,
    iron_mg_per_100g = excluded.iron_mg_per_100g,
    zinc_mg_per_100g = excluded.zinc_mg_per_100g,
    nutrient_source = excluded.nutrient_source,
    is_allergen = excluded.is_allergen,
    allergen_type = excluded.allergen_type,
    min_month = excluded.min_month,
    texture_stage = excluded.texture_stage,
    season_months = excluded.season_months,
    prep_note = excluded.prep_note,
    source = excluded.source,
    avg_price = excluded.avg_price,
    edible_ratio = excluded.edible_ratio
"""


@dataclass(frozen=True)
class ImportSummary:
    inserted: int
    updated: int

    @property
    def total(self) -> int:
        return self.inserted + self.updated


def read_food_rows(csv_path: str | Path = DEFAULT_CSV_PATH) -> list[dict[str, object]]:
    """一次性读取并校验 CSV，任一行错误时不写入数据库。"""

    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"找不到食物库文件：{path}")

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        validate_food_headers(reader.fieldnames)
        rows = [
            normalize_food_row(row, line_number=line_number)
            for line_number, row in enumerate(reader, start=2)
        ]

    seen_ids: set[int] = set()
    for row in rows:
        food_id = int(row["id"])
        if food_id in seen_ids:
            raise DataValidationError(f"foods.csv 中出现重复 id：{food_id}")
        seen_ids.add(food_id)
    return rows


def import_foods(
    csv_path: str | Path = DEFAULT_CSV_PATH,
    database_path: str | Path | None = None,
) -> ImportSummary:
    """导入食物库，按 ``id`` 新增或更新，并返回本次统计。"""

    rows = read_food_rows(csv_path)
    init_database(database_path)
    ids = {int(row["id"]) for row in rows}

    with open_database(database_path) as connection:
        existing_ids = {
            int(row["id"])
            for row in connection.execute("SELECT id FROM foods").fetchall()
            if int(row["id"]) in ids
        }
        connection.executemany(
            UPSERT_SQL,
            [tuple(row[column] for column in FOOD_COLUMNS) for row in rows],
        )

    return ImportSummary(
        inserted=len(ids - existing_ids),
        updated=len(ids & existing_ids),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="校验并导入果初食物库")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=DEFAULT_CSV_PATH,
        help="foods.csv 路径（默认 data/foods.csv）",
    )
    parser.add_argument(
        "--database",
        dest="database_path",
        help="SQLite 文件路径（默认 data/guochu.sqlite3）",
    )
    args = parser.parse_args()
    summary = import_foods(args.csv_path, args.database_path)
    print(
        f"导入完成：新增 {summary.inserted} 条，更新 {summary.updated} 条，"
        f"共处理 {summary.total} 条。"
    )


if __name__ == "__main__":
    main()
