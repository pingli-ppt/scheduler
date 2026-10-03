from __future__ import annotations

import csv
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from data.database import init_database, open_database
from data.import_foods import import_foods
from data.repository import (
    ChildNotFoundError,
    FoodNotFoundError,
    load_child,
    load_daily_intake,
    load_foods,
    load_history,
    save_record,
)
from data.validate import FOOD_COLUMNS, DataValidationError


class DataLayerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.sqlite3"
        self.environment = patch.dict(
            os.environ,
            {"GUOCHU_DB_PATH": str(self.database_path)},
        )
        self.environment.start()
        init_database()
        self._seed_database()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    def _seed_database(self) -> None:
        with open_database() as connection:
            connection.execute(
                """
                INSERT INTO foods (
                    id, name, category, iron_mg_per_100g, zinc_mg_per_100g,
                    nutrient_source, is_allergen, allergen_type, min_month,
                    texture_stage, season_months, prep_note, source,
                    avg_price, edible_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "猪肉",
                    "肉类",
                    3.0,
                    2.99,
                    "animal",
                    0,
                    None,
                    6,
                    1,
                    "1-12",
                    "煮熟后打成泥",
                    "中国食物成分表",
                    None,
                    None,
                ),
            )
            connection.execute(
                """
                INSERT INTO children (
                    id, nickname, birth_date, weaning_start,
                    known_allergens, "group", created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "C002",
                    "空记录宝宝",
                    "2026-02-01",
                    "2026-08-01",
                    "",
                    "control",
                    "2026-09-15 10:00:00",
                ),
            )
            connection.execute(
                """
                INSERT INTO children (
                    id, nickname, birth_date, weaning_start,
                    known_allergens, "group", created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "C001",
                    "测试宝宝",
                    "2026-01-15",
                    "2026-07-15",
                    "蛋类,花生",
                    "test",
                    "2026-09-15 09:00:00",
                ),
            )
            connection.executemany(
                """
                INSERT INTO food_records (child_id, food_id, date, status, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("C001", 1, "2026-07-20", "passed", ""),
                    ("C001", 1, "2026-07-18", "planned", ""),
                ],
            )
            connection.executemany(
                """
                INSERT INTO daily_intake (
                    child_id, date, categories, meal_count,
                    is_breastfed, milk_feeds
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("C001", "2026-07-20", "肉类,其他蔬果", 2, 1, 0),
                    ("C001", "2026-07-19", "谷物根茎薯类", 2, 1, 0),
                ],
            )

    def test_database_initialization_is_idempotent(self) -> None:
        init_database()
        with open_database() as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue({"foods", "children", "food_records", "daily_intake"} <= tables)

    def test_load_foods_preserves_fields_and_parses_season_months(self) -> None:
        foods = load_foods()
        self.assertEqual(list(foods[0].keys()), list(FOOD_COLUMNS))
        self.assertEqual(foods[0]["season_months"], list(range(1, 13)))

    def test_load_child_parses_dates_and_allergens(self) -> None:
        child = load_child("C001")
        self.assertEqual(child["birth_date"], date(2026, 1, 15))
        self.assertEqual(child["weaning_start"], date(2026, 7, 15))
        self.assertEqual(child["known_allergens"], ["蛋类", "花生"])

    def test_history_is_ordered_and_has_fixed_keys(self) -> None:
        history = load_history("C001")
        self.assertEqual(
            [item["date"] for item in history],
            [date(2026, 7, 18), date(2026, 7, 20)],
        )
        self.assertEqual(set(history[0]), {"food_id", "date", "status"})

    def test_daily_intake_is_ordered_and_parses_categories(self) -> None:
        intake = load_daily_intake("C001")
        self.assertEqual(
            [item["date"] for item in intake],
            [date(2026, 7, 19), date(2026, 7, 20)],
        )
        self.assertEqual(intake[1]["categories"], ["肉类", "其他蔬果"])
        self.assertEqual(
            set(intake[0]),
            {"date", "categories", "meal_count", "is_breastfed", "milk_feeds"},
        )

    def test_save_record_accepts_date_and_returns_none(self) -> None:
        result = save_record("C001", 1, date(2026, 7, 21), "refused", "暂时不吃")
        self.assertIsNone(result)
        self.assertEqual(load_history("C001")[-1]["status"], "refused")

    def test_empty_allergens_history_intake_and_categories_are_explicit(self) -> None:
        self.assertEqual(load_child("C002")["known_allergens"], [])
        self.assertEqual(load_history("C002"), [])
        self.assertEqual(load_daily_intake("C002"), [])

        with open_database() as connection:
            connection.execute(
                """
                INSERT INTO daily_intake (
                    child_id, date, categories, meal_count,
                    is_breastfed, milk_feeds
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("C002", "2026-08-02", "", 0, 0, 2),
            )
        self.assertEqual(load_daily_intake("C002")[0]["categories"], [])

    def test_invalid_stored_date_is_not_silently_ignored(self) -> None:
        with open_database() as connection:
            connection.execute(
                """
                INSERT INTO food_records (child_id, food_id, date, status, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("C002", 1, "2026-02-30", "planned", ""),
            )
        with self.assertRaises(DataValidationError):
            load_history("C002")

    def test_unknown_ids_and_invalid_status_raise_clear_errors(self) -> None:
        with self.assertRaises(ChildNotFoundError):
            load_child("C999")
        with self.assertRaises(ChildNotFoundError):
            load_history("C999")
        with self.assertRaises(FoodNotFoundError):
            save_record("C001", 999, date(2026, 7, 21), "passed", "")
        with self.assertRaises(DataValidationError):
            save_record("C001", 1, date(2026, 7, 21), "unknown", "")

    def test_food_import_inserts_then_updates_by_id(self) -> None:
        csv_path = Path(self.temporary_directory.name) / "foods.csv"
        row = {
            "id": "2",
            "name": "南瓜",
            "category": "维生素A丰富蔬果",
            "iron_mg_per_100g": "0.4",
            "zinc_mg_per_100g": "0.14",
            "nutrient_source": "plant",
            "is_allergen": "0",
            "allergen_type": "",
            "min_month": "6",
            "texture_stage": "1",
            "season_months": "9,10,11",
            "prep_note": "蒸熟后打泥",
            "source": "中国食物成分表",
            "avg_price": "",
            "edible_ratio": "",
            "auto_recommend": "1",
        }
        with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=FOOD_COLUMNS)
            writer.writeheader()
            writer.writerow(row)

        first = import_foods(csv_path)
        self.assertEqual((first.inserted, first.updated), (1, 0))
        self.assertEqual(load_foods()[1]["season_months"], [9, 10, 11])

        row["name"] = "贝贝南瓜"
        row["auto_recommend"] = "0"
        with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=FOOD_COLUMNS)
            writer.writeheader()
            writer.writerow(row)

        second = import_foods(csv_path)
        self.assertEqual((second.inserted, second.updated), (0, 1))
        self.assertEqual(load_foods()[1]["name"], "贝贝南瓜")
        self.assertEqual(load_foods()[1]["auto_recommend"], 0)


if __name__ == "__main__":
    unittest.main()
