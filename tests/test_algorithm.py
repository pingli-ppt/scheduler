from __future__ import annotations

import unittest
from datetime import date, timedelta
from unittest.mock import patch

from algo.constants import N_OBSERVE
from algo.constraints import age_in_months, allowed_texture_stage, is_food_eligible
from algo.reaction import report_reaction
from algo.scheduler import build_schedule
from algo.scoring import score_food


def make_child(**overrides) -> dict:
    child = {
        "id": "C001",
        "nickname": "测试宝宝",
        "birth_date": date(2026, 1, 15),
        "weaning_start": date(2026, 7, 15),
        "known_allergens": [],
        "group": "test",
    }
    child.update(overrides)
    return child


def make_food(food_id: int, **overrides) -> dict:
    food = {
        "id": food_id,
        "name": f"食物{food_id}",
        "category": "其他蔬果",
        "iron_mg_per_100g": 0.0,
        "zinc_mg_per_100g": 0.0,
        "nutrient_source": None,
        "is_allergen": 0,
        "allergen_type": None,
        "min_month": 6,
        "texture_stage": 1,
        "season_months": [],
        "prep_note": None,
        "source": "测试来源",
        "avg_price": None,
        "edible_ratio": None,
    }
    food.update(overrides)
    return food


class ConstraintTests(unittest.TestCase):
    def test_age_uses_complete_months(self) -> None:
        birth = date(2026, 1, 15)
        self.assertEqual(age_in_months(birth, date(2026, 7, 14)), 5)
        self.assertEqual(age_in_months(birth, date(2026, 7, 15)), 6)

    def test_texture_stage_boundaries(self) -> None:
        self.assertEqual(
            [allowed_texture_stage(i) for i in (5, 6, 7, 9, 12)],
            [0, 1, 2, 3, 4],
        )

    def test_known_allergen_is_excluded_by_category(self) -> None:
        child = make_child(known_allergens=["蛋类"])
        food = make_food(1, allergen_type="蛋类", is_allergen=1)
        self.assertFalse(is_food_eligible(food, child, date(2026, 7, 15), []))

    def test_reaction_cooldown_ends_on_day_90(self) -> None:
        child = make_child()
        food = make_food(1)
        reaction = {"food_id": 1, "date": date(2026, 7, 15), "status": "reaction"}
        self.assertFalse(
            is_food_eligible(food, child, date(2026, 10, 12), [reaction])
        )
        self.assertTrue(
            is_food_eligible(food, child, date(2026, 10, 13), [reaction])
        )

    def test_third_refusal_excludes_food(self) -> None:
        child = make_child()
        food = make_food(1)
        history = [
            {
                "food_id": 1,
                "date": date(2026, 7, 15) + timedelta(days=i),
                "status": "refused",
            }
            for i in range(3)
        ]
        self.assertFalse(is_food_eligible(food, child, date(2026, 8, 1), history))

    def test_blank_source_is_excluded(self) -> None:
        self.assertFalse(
            is_food_eligible(
                make_food(1, source=" "),
                make_child(),
                date(2026, 7, 15),
                [],
            )
        )


class ScoringTests(unittest.TestCase):
    def test_plant_nutrients_are_discounted(self) -> None:
        food = make_food(
            1,
            iron_mg_per_100g=4.5,
            zinc_mg_per_100g=4.5,
            nutrient_source="plant",
        )
        result = score_food(
            food, make_child(), date(2026, 7, 15), {1: food}, [], []
        )
        self.assertEqual(result.components["iron"], 0.5)
        self.assertEqual(result.components["zinc"], 0.5)

    def test_score_is_rounded_and_dominant_is_deterministic(self) -> None:
        food = make_food(
            1,
            category="肉类",
            iron_mg_per_100g=4.5,
            zinc_mg_per_100g=4.5,
            nutrient_source="animal",
        )
        result = score_food(
            food, make_child(), date(2026, 7, 15), {1: food}, [], []
        )
        self.assertEqual(result.total, 0.9)
        self.assertEqual(result.dominant, "gap")


class SchedulerTests(unittest.TestCase):
    def test_under_six_months_and_nonpositive_weeks_return_empty(self) -> None:
        foods = [make_food(1)]
        self.assertEqual(
            build_schedule(make_child(), foods, [], start_date=date(2026, 7, 14)),
            [],
        )
        self.assertEqual(
            build_schedule(
                make_child(), foods, [], weeks=0, start_date=date(2026, 7, 15)
            ),
            [],
        )

    def test_schedule_uses_four_day_spacing_and_exact_output_contract(self) -> None:
        categories = ["肉类", "蛋类", "豆类坚果", "其他蔬果", "谷物根茎薯类"]
        foods = [
            make_food(i, category=category)
            for i, category in enumerate(categories, 1)
        ]
        plan = build_schedule(
            make_child(), foods, [], weeks=3, start_date=date(2026, 7, 15)
        )
        self.assertEqual(len(plan), 5)
        self.assertTrue(
            all(
                (right["date"] - left["date"]).days == N_OBSERVE
                for left, right in zip(plan, plan[1:])
            )
        )
        self.assertEqual(
            set(plan[0]),
            {
                "date",
                "food_id",
                "food_name",
                "texture",
                "texture_desc",
                "reason",
                "source",
            },
        )
        self.assertIsInstance(plan[0]["date"], date)

    def test_tie_is_broken_by_food_id(self) -> None:
        foods = [make_food(9), make_food(2)]
        plan = build_schedule(
            make_child(), foods, [], weeks=1, start_date=date(2026, 7, 15)
        )
        self.assertEqual(plan[0]["food_id"], 2)

    def test_age_boundary_is_rechecked_each_day(self) -> None:
        food = make_food(1, min_month=7, texture_stage=2)
        plan = build_schedule(
            make_child(), [food], [], weeks=1, start_date=date(2026, 8, 14)
        )
        self.assertEqual(plan[0]["date"], date(2026, 8, 15))

    def test_existing_record_wins_on_same_day(self) -> None:
        history = [{"food_id": 99, "date": date(2026, 7, 15), "status": "refused"}]
        plan = build_schedule(
            make_child(),
            [make_food(1)],
            history,
            weeks=1,
            start_date=date(2026, 7, 15),
        )
        self.assertEqual(plan[0]["date"], date(2026, 7, 16))

    def test_no_candidates_skips_without_placeholder(self) -> None:
        food = make_food(1, source="")
        self.assertEqual(
            build_schedule(
                make_child(), [food], [], start_date=date(2026, 7, 15)
            ),
            [],
        )


class ReactionTests(unittest.TestCase):
    @patch("algo.reaction.generate_schedule", return_value=[{"ok": True}])
    @patch("algo.reaction.record_reaction_and_delete_future_plans")
    def test_reaction_is_recorded_then_rescheduled_from_day_four(
        self, record, generate
    ) -> None:
        reaction_day = date(2026, 7, 20)
        result = report_reaction("C001", 7, reaction_day)
        record.assert_called_once()
        generate.assert_called_once_with("C001", weeks=6, today=date(2026, 7, 24))
        self.assertEqual(result, [{"ok": True}])


if __name__ == "__main__":
    unittest.main()
