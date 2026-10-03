# 数据层结构说明

更新日期：2026-09-28

## 核心表

- `foods`：食物基础资料；`auto_recommend` 为 `0` 时不进入自动推荐候选池。
- `children`：儿童档案及 `test` / `control` 分组。
- `food_records`：`planned`、`passed`、`refused`、`reaction` 记录。
- `daily_intake`：按儿童和日期唯一的每日膳食记录。

## 推荐追踪表 `recommendations`

该表用于实验分析，不改变算法读取 `food_records` 的既有契约。

一条推荐实际展示给家庭时创建记录，主键 `id` 即对外使用的
`recommendation_id`。同一儿童、食物和安排日期的有效推荐重复保存时返回原编号，
避免页面刷新产生重复记录。

主要字段：

| 字段 | 含义 |
|---|---|
| `child_id` / `food_id` / `scheduled_date` | 推荐对象与安排日期 |
| `recommended_at` | 推荐实际展示并写入数据库的时间 |
| `planned_record_id` | 对应的 `food_records.planned` 记录 |
| `adopted` | 家长是否实际提供该食物；未上报时为 `NULL` |
| `consumed` | 宝宝是否实际吃进去；未上报时为 `NULL` |
| `outcome_record_id` | 对应的 `passed`、`refused` 或 `reaction` 记录 |
| `cancelled_at` / `cancellation_reason` | 推荐因重排等原因失效的时间和原因 |
| `reschedule_*` | 反应是否触发重排、重排是否成功及新计划条数 |

数据链为：

```text
recommendation_id → adopted → consumed → passed/refused/reaction → reschedule
```

## 数据接口

- `save_recommendations()`：保存实际展示的一批推荐并返回编号。
- `record_recommendation_engagement()`：保存采纳与摄入情况。
- `record_recommendation_outcome()`：保存最终结果并关联原推荐。
- `record_reschedule_result()`：保存反应后的重排结果。
- `load_recommendations()`：读取可供页面或导出使用的完整追踪数据。
- `save_daily_intake()`：按儿童和日期新增或覆盖每日膳食记录。
