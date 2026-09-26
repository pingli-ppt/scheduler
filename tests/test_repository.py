from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from data.database import init_database, open_database
from data.repository import load_history, record_reaction_and_delete_future_plans
from algo.scheduler import generate_schedule


class ReactionRepositoryTests(unittest.TestCase):
    def test_generate_schedule_uses_repository_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "integration.sqlite3"
            with patch.dict(os.environ, {"GUOCHU_DB_PATH": str(database_path)}):
                init_database()
                with open_database() as connection:
                    connection.execute(
                        """
                        INSERT INTO children (
                            id, nickname, birth_date, weaning_start,
                            known_allergens, "group"
                        ) VALUES ('C001', '测试宝宝', '2026-01-01',
                                  '2026-07-01', '', 'test')
                        """
                    )
                    connection.executemany(
                        """
                        INSERT INTO foods (
                            id, name, category, is_allergen, min_month,
                            texture_stage, season_months, source
                        ) VALUES (?, ?, ?, 0, 6, 1, '', '测试来源')
                        """,
                        [
                            (1, "南瓜", "维生素A丰富蔬果"),
                            (2, "大米", "谷物根茎薯类"),
                        ],
                    )

                plan = generate_schedule(
                    "C001", weeks=1, today=date(2026, 7, 1)
                )
                self.assertEqual([item["date"] for item in plan], [
                    date(2026, 7, 1),
                    date(2026, 7, 5),
                ])

    def test_reaction_and_future_plan_deletion_are_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "test.sqlite3"
            with patch.dict(os.environ, {"GUOCHU_DB_PATH": str(database_path)}):
                init_database()
                with open_database() as connection:
                    connection.execute(
                        """
                        INSERT INTO foods (
                            id, name, category, is_allergen, min_month,
                            texture_stage, season_months, source
                        ) VALUES (1, '测试食物', '其他蔬果', 0, 6, 1, '', '测试来源')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO children (
                            id, nickname, birth_date, weaning_start,
                            known_allergens, "group"
                        ) VALUES ('C001', '测试宝宝', '2026-01-01', '2026-07-01', '', 'test')
                        """
                    )
                    connection.executemany(
                        """
                        INSERT INTO food_records (child_id, food_id, date, status)
                        VALUES ('C001', 1, ?, 'planned')
                        """,
                        [("2026-07-20",), ("2026-07-24",), ("2026-07-28",)],
                    )

                deleted = record_reaction_and_delete_future_plans(
                    "C001", 1, date(2026, 7, 20), "测试记录"
                )
                self.assertEqual(deleted, 2)
                history = load_history("C001")
                self.assertEqual(
                    [(item["date"], item["status"]) for item in history],
                    [
                        (date(2026, 7, 20), "planned"),
                        (date(2026, 7, 20), "reaction"),
                    ],
                )


if __name__ == "__main__":
    unittest.main()
