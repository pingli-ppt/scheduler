from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from data.database import init_database
from data.import_foods import import_foods, read_food_rows
from data.repository import save_child, save_daily_intake
from data.validate import DataValidationError


FIXTURES = Path(__file__).resolve().parent


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "api.sqlite3"
        self.environment = patch.dict(
            os.environ,
            {
                "GUOCHU_DB_PATH": str(self.database_path),
                "GUOCHU_EXPERIMENT_PHASE": "active",
            },
        )
        self.environment.start()
        init_database()
        import_foods(FIXTURES / "foods_test.csv")
        self._import_children()
        self._import_daily_intake()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    def _read_csv(self, name: str) -> list[dict[str, str]]:
        with (FIXTURES / name).open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    def _import_children(self) -> None:
        for row in self._read_csv("children_test.csv"):
            save_child(
                row["id"],
                row["nickname"],
                row["birth_date"],
                row["weaning_start"],
                row["known_allergens"],
                row["group"],
            )

    def _import_daily_intake(self) -> None:
        for row in self._read_csv("daily_intake_test.csv"):
            save_daily_intake(
                row["child_id"],
                row["date"],
                row["categories"],
                row["meal_count"],
                row["is_breastfed"] == "1",
                row["milk_feeds"],
            )

    def _create_schedule(self) -> dict:
        response = self.client.post(
            "/children/C002/schedule",
            json={"weeks": 2, "today": "2026-10-07"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_docs_include_chinese_interface_help_and_parameter_descriptions(self) -> None:
        docs = self.client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn("在线测试", docs.text)
        self.assertIn("发送请求", docs.text)
        self.assertIn("服务器返回", docs.text)

        spec = self.client.get("/openapi.json").json()
        child_parameters = spec["paths"]["/children/{child_id}"]["get"]["parameters"]
        self.assertEqual(child_parameters[0]["description"], "儿童编号，例如 C002")
        recommendation_parameters = spec["paths"][
            "/recommendations/{recommendation_id}/outcome"
        ]["post"]["parameters"]
        self.assertIn("唯一推荐编号", recommendation_parameters[0]["description"])

    def test_family_h5_contains_all_six_pages_and_assets(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("宝宝档案", page.text)
        for name in ("profile", "daily", "schedule", "report", "history", "share"):
            self.assertIn(f'data-page="{name}"', page.text)

        styles = self.client.get("/styles.css")
        script = self.client.get("/app.js")
        self.assertEqual(styles.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertIn("刷新成功", script.text)
        self.assertIn("evidenceByScore", script.text)

    def test_yang_zi_yue_food_fixture_is_used_and_invalid_row_is_rejected(self) -> None:
        foods = self.client.get("/foods")
        self.assertEqual(foods.status_code, 200)
        self.assertEqual(len(foods.json()), 17)
        self.assertTrue(all(item["name"].startswith("测试-") for item in foods.json()))
        with self.assertRaises(DataValidationError):
            read_food_rows(FIXTURES / "foods_invalid_test.csv")

    def test_child_and_daily_intake_endpoints_return_fixture_data(self) -> None:
        child = self.client.get("/children/C002")
        self.assertEqual(child.status_code, 200)
        self.assertEqual(child.json()["known_allergens"], ["蛋类"])

        intake = self.client.get("/children/C002/daily-intake")
        self.assertEqual(intake.status_code, 200)
        self.assertEqual(len(intake.json()), 6)
        self.assertEqual(len(intake.json()[3]["categories"]), 4)

        created = self.client.put(
            "/children/C005",
            json={
                "nickname": "接口测试宝宝",
                "birth_date": "2026-03-01",
                "weaning_start": "2026-09-01",
                "known_allergens": ["乳"],
                "group": "test",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["known_allergens"], ["乳"])

        saved_intake = self.client.put(
            "/children/C005/daily-intake",
            json={
                "date": "2026-10-01",
                "categories": ["谷物根茎薯类", "肉类"],
                "meal_count": 2,
                "is_breastfed": True,
                "milk_feeds": 0,
            },
        )
        self.assertEqual(saved_intake.status_code, 200, saved_intake.text)
        self.assertEqual(saved_intake.json()["categories"], ["谷物根茎薯类", "肉类"])

    def test_schedule_is_saved_with_display_snapshot_and_engagement(self) -> None:
        schedule = self._create_schedule()
        self.assertGreater(schedule["count"], 0)
        self.assertTrue(
            all("recommendation_id" in item for item in schedule["recommendations"])
        )
        self.assertTrue(
            all(item["food_id"] not in {6, 7} for item in schedule["recommendations"])
        )

        stored = self.client.get("/children/C002/recommendations").json()
        self.assertEqual(len(stored), schedule["count"])
        self.assertEqual(stored[0]["reason"], schedule["recommendations"][0]["reason"])
        self.assertEqual(stored[0]["source"], schedule["recommendations"][0]["source"])

        repeated = self._create_schedule()
        self.assertEqual(repeated["count"], schedule["count"])
        self.assertEqual(
            [item["recommendation_id"] for item in repeated["recommendations"]],
            [item["recommendation_id"] for item in schedule["recommendations"]],
        )

        recommendation_id = schedule["recommendations"][0]["recommendation_id"]
        engagement = self.client.patch(
            f"/recommendations/{recommendation_id}/engagement",
            json={"adopted": True, "consumed": True},
        )
        self.assertEqual(engagement.status_code, 200)
        self.assertIs(engagement.json()["adopted"], True)
        self.assertIs(engagement.json()["consumed"], True)

    def test_reaction_cancels_future_plan_and_records_reschedule(self) -> None:
        schedule = self._create_schedule()
        first = schedule["recommendations"][0]
        response = self.client.post(
            f"/recommendations/{first['recommendation_id']}/outcome",
            json={
                "date": first["date"],
                "status": "reaction",
                "note": "测试反应",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["recommendation"]["outcome"], "reaction")
        self.assertIs(result["recommendation"]["reschedule_triggered"], True)
        self.assertIs(result["recommendation"]["reschedule_succeeded"], True)
        self.assertEqual(
            result["recommendation"]["reschedule_plan_count"],
            len(result["rescheduled"]),
        )

    def test_control_group_and_baseline_do_not_receive_schedule(self) -> None:
        control = self.client.post(
            "/children/C004/schedule",
            json={"weeks": 1, "today": "2026-10-07"},
        )
        self.assertEqual(control.status_code, 403)

        with patch.dict(os.environ, {"GUOCHU_EXPERIMENT_PHASE": "baseline"}):
            baseline = self.client.post(
                "/children/C002/schedule",
                json={"weeks": 1, "today": "2026-10-07"},
            )
        self.assertEqual(baseline.status_code, 409)


if __name__ == "__main__":
    unittest.main()
