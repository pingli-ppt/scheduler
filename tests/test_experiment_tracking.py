from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from data.database import init_database, open_database
from data.repository import (
    load_daily_intake,
    load_history,
    load_recommendations,
    record_recommendation_engagement,
    record_recommendation_outcome,
    record_reschedule_result,
    save_daily_intake,
    save_recommendation,
    save_recommendations,
)
from data.validate import DataValidationError


class ExperimentTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.sqlite3"
        self.environment = patch.dict(
            os.environ,
            {"GUOCHU_DB_PATH": str(self.database_path)},
        )
        self.environment.start()
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
                    (3, "猪肉", "肉类"),
                ],
            )

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_displayed_recommendations_are_idempotent_and_create_plans(self) -> None:
        plan = [
            {"food_id": 1, "date": date(2026, 7, 20), "reason": "类别缺口"},
            {"food_id": 2, "date": date(2026, 7, 24), "reason": "类别缺口"},
        ]
        first = save_recommendations("C001", plan)
        second = save_recommendations("C001", plan)

        self.assertEqual(first, second)
        self.assertEqual(len(set(first)), 2)
        self.assertEqual(
            [item["status"] for item in load_history("C001")],
            ["planned", "planned"],
        )
        recommendations = load_recommendations("C001")
        self.assertEqual(
            [item["recommendation_id"] for item in recommendations],
            first,
        )
        self.assertIsNone(recommendations[0]["adopted"])
        self.assertIsNone(recommendations[0]["consumed"])

    def test_engagement_and_outcome_link_back_to_recommendation(self) -> None:
        recommendation_id = save_recommendation(
            "C001",
            1,
            date(2026, 7, 20),
        )
        record_recommendation_engagement(
            recommendation_id,
            adopted=True,
            consumed=True,
        )
        deleted = record_recommendation_outcome(
            recommendation_id,
            date(2026, 7, 20),
            "passed",
            "正常摄入",
        )

        self.assertEqual(deleted, 0)
        recommendation = load_recommendations("C001")[0]
        self.assertTrue(recommendation["adopted"])
        self.assertTrue(recommendation["consumed"])
        self.assertEqual(recommendation["outcome"], "passed")
        self.assertEqual(recommendation["outcome_date"], date(2026, 7, 20))
        self.assertIsNotNone(recommendation["outcome_record_id"])

    def test_not_adopted_cannot_be_marked_consumed(self) -> None:
        recommendation_id = save_recommendation("C001", 1, "2026-07-20")
        with self.assertRaises(DataValidationError):
            record_recommendation_engagement(
                recommendation_id,
                adopted=False,
                consumed=True,
            )

        record_recommendation_engagement(
            recommendation_id,
            adopted=False,
        )
        recommendation = load_recommendations("C001")[0]
        self.assertFalse(recommendation["adopted"])
        self.assertFalse(recommendation["consumed"])

    def test_reaction_cancels_future_recommendations_and_tracks_reschedule(self) -> None:
        recommendation_ids = save_recommendations(
            "C001",
            [
                {"food_id": 1, "date": "2026-07-20"},
                {"food_id": 2, "date": "2026-07-24"},
                {"food_id": 3, "date": "2026-07-28"},
            ],
        )
        deleted = record_recommendation_outcome(
            recommendation_ids[0],
            "2026-07-20",
            "reaction",
            "出现不良反应",
        )
        self.assertEqual(deleted, 2)

        recommendations = load_recommendations("C001")
        self.assertEqual(recommendations[0]["outcome"], "reaction")
        self.assertTrue(recommendations[0]["reschedule_triggered"])
        self.assertIsNotNone(recommendations[1]["cancelled_at"])
        self.assertIsNotNone(recommendations[2]["cancelled_at"])
        self.assertIsNone(recommendations[1]["planned_record_id"])
        self.assertIsNone(recommendations[2]["planned_record_id"])

        record_reschedule_result(
            recommendation_ids[0],
            succeeded=True,
            plan_count=8,
        )
        tracked = load_recommendations("C001")[0]
        self.assertTrue(tracked["reschedule_succeeded"])
        self.assertEqual(tracked["reschedule_plan_count"], 8)

        repeated = record_recommendation_outcome(
            recommendation_ids[0],
            "2026-07-20",
            "reaction",
        )
        self.assertEqual(repeated, 0)
        self.assertEqual(
            [item["status"] for item in load_history("C001")],
            ["planned", "reaction"],
        )

    def test_daily_intake_upserts_without_duplicate_days(self) -> None:
        save_daily_intake(
            "C001",
            "2026-07-20",
            ["谷物根茎薯类", "肉类"],
            2,
            True,
            0,
        )
        save_daily_intake(
            "C001",
            "2026-07-20",
            ["谷物根茎薯类", "肉类", "其他蔬果"],
            3,
            1,
            0,
        )

        intake = load_daily_intake("C001")
        self.assertEqual(len(intake), 1)
        self.assertEqual(intake[0]["meal_count"], 3)
        self.assertEqual(
            intake[0]["categories"],
            ["谷物根茎薯类", "肉类", "其他蔬果"],
        )


if __name__ == "__main__":
    unittest.main()
