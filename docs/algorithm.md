# 排程算法交接说明

更新日期：2026-09-26

## 公共接口

```python
from algo import generate_schedule, report_reaction

plan = generate_schedule("C001", weeks=6)
new_plan = report_reaction("C001", food_id=12, reaction_date=date(2026, 10, 1))
```

`generate_schedule` 只计算并返回计划，不自动保存 `planned` 记录。API 层在用户确认
计划后负责保存，避免预览操作污染历史数据。

返回条目严格包含 `date`、`food_id`、`food_name`、`texture`、
`texture_desc`、`reason`、`source` 七个字段；其中 `date` 是 Python `date`。

`report_reaction` 会在同一个 SQLite 事务中记录 `reaction` 并删除反应日期之后的
`planned` 记录，然后从反应日加 4 天开始重新生成六周计划。

## 实现约定

- C5 只按 `allergen_type` 与儿童的过敏类别比较；`known_allergens` 不存食物编号。
- `passed` 和已有 `planned` 食物不再作为新食物；`reaction` 食物冷却 90 天后允许重试。
- `refused` 不计入摄入或类别覆盖，累计三次后排除。
- 类别缺口使用目标日前七天的食物历史与本次计划，不使用 `daily_intake`；后者只供
  MDD、MMF、MAD 等分析指标计算。
- 推荐理由取加权贡献最大的评分项。贡献相同时固定按 iron、zinc、gap、season、
  allergen_early 决胜，保证输出稳定。
- 历史记录与新计划发生同日冲突时历史优先，当天不新增安排。

## 运行与验证

无需数据库即可运行匿名模拟演示：

```powershell
python -m algo.cli --demo --today 2026-09-26 --weeks 6
```

使用本地数据库：

```powershell
python -m algo.cli C001 --today 2026-09-26 --weeks 6
```

运行全部测试：

```powershell
python -m unittest discover -s tests -v
```

