"""命令行排程演示。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from data.validate import parse_iso_date

from .scheduler import build_schedule, generate_schedule


def _demo_food(food_id: int, name: str, category: str, **overrides) -> dict:
    food = {
        "id": food_id,
        "name": name,
        "category": category,
        "iron_mg_per_100g": 1.0,
        "zinc_mg_per_100g": 1.0,
        "nutrient_source": "plant",
        "is_allergen": 0,
        "allergen_type": None,
        "min_month": 6,
        "texture_stage": 1,
        "season_months": [],
        "prep_note": None,
        "source": "演示数据",
        "avg_price": None,
        "edible_ratio": None,
    }
    food.update(overrides)
    return food


def _demo_schedule(start: date, weeks: int) -> list[dict]:
    child = {
        "id": "C-DEMO",
        "nickname": "演示宝宝",
        "birth_date": date(2026, 1, 1),
        "weaning_start": date(2026, 7, 1),
        "known_allergens": [],
        "group": "test",
    }
    foods = [
        _demo_food(
            1,
            "牛肉",
            "肉类",
            iron_mg_per_100g=4.5,
            zinc_mg_per_100g=4.5,
            nutrient_source="animal",
        ),
        _demo_food(2, "南瓜", "维生素A丰富蔬果"),
        _demo_food(3, "西兰花", "维生素A丰富蔬果"),
        _demo_food(4, "大米", "谷物根茎薯类", nutrient_source=None),
        _demo_food(5, "土豆", "谷物根茎薯类", nutrient_source=None),
        _demo_food(6, "豆腐", "豆类坚果", allergen_type="大豆", is_allergen=1),
        _demo_food(
            7,
            "鸡蛋",
            "蛋类",
            iron_mg_per_100g=2.0,
            zinc_mg_per_100g=1.0,
            nutrient_source="animal",
            allergen_type="蛋类",
            is_allergen=1,
        ),
        _demo_food(
            8,
            "鳕鱼",
            "肉类",
            iron_mg_per_100g=1.0,
            zinc_mg_per_100g=1.0,
            nutrient_source="animal",
            allergen_type="鱼类",
            is_allergen=1,
        ),
        _demo_food(9, "香蕉", "其他蔬果"),
        _demo_food(
            10,
            "小麦面糊",
            "谷物根茎薯类",
            allergen_type="含麸质谷物",
            is_allergen=1,
        ),
        _demo_food(
            11,
            "猪肝",
            "肉类",
            iron_mg_per_100g=20.0,
            zinc_mg_per_100g=5.0,
            nutrient_source="animal",
        ),
    ]
    return build_schedule(child, foods, [], weeks=weeks, start_date=start)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="生成果初辅食引入计划")
    parser.add_argument("child_id", nargs="?", help="数据库中的儿童编号")
    parser.add_argument("--weeks", type=int, default=6, help="计划周数，默认 6")
    parser.add_argument("--today", help="计划起始日，格式 YYYY-MM-DD")
    parser.add_argument("--demo", action="store_true", help="使用内置匿名模拟数据")
    args = parser.parse_args()

    start = parse_iso_date(args.today, "today") if args.today else date.today()
    if args.demo:
        plan = _demo_schedule(start, args.weeks)
    else:
        if not args.child_id:
            parser.error("非演示模式必须提供 child_id")
        plan = generate_schedule(args.child_id, weeks=args.weeks, today=start)
    print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
