"""果初前后端联调 API。"""

from __future__ import annotations

import os
from datetime import date as Date, timedelta
from pathlib import Path as FilePath
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.docs import chinese_swagger_ui
from algo.scheduler import generate_schedule
from data.repository import (
    ChildNotFoundError,
    FoodNotFoundError,
    RecommendationNotFoundError,
    load_child,
    load_daily_intake,
    load_foods,
    load_history,
    load_recommendation,
    load_recommendations,
    record_recommendation_engagement,
    record_recommendation_outcome,
    record_reschedule_result,
    save_child,
    save_daily_intake,
    save_recommendations,
)
from data.validate import DataValidationError


EXPERIMENT_PHASE_ENV = "GUOCHU_EXPERIMENT_PHASE"
CORS_ORIGINS_ENV = "GUOCHU_CORS_ORIGINS"
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


def _cors_origins() -> list[str]:
    configured = os.environ.get(CORS_ORIGINS_ENV)
    if configured is None:
        return list(DEFAULT_CORS_ORIGINS)
    return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]

OPENAPI_TAGS = [
    {
        "name": "系统状态",
        "description": "检查本机接口服务是否正常运行。",
    },
    {
        "name": "儿童档案",
        "description": "新增、更新和查询儿童档案。",
    },
    {
        "name": "食物数据",
        "description": "查询当前食物库。",
    },
    {
        "name": "辅食推荐",
        "description": "生成推荐，并追踪展示、采纳、摄入、结果和不良反应后的重排。",
    },
    {
        "name": "家庭记录",
        "description": "查询辅食历史并保存每日膳食。",
    },
]

app = FastAPI(
    title="果初接口文档",
    version="0.1.0",
    description=(
        "用于婴幼儿辅食推荐、家庭反馈和实验记录。本文档以中文说明为主；"
        "路径、字段名以及 `test`、`control` 等固定取值保留英文，以便程序调用。\n\n"
        "测试方法：展开一个接口，点击“在线测试”，填写标有“必填”的内容，"
        "再点击“发送请求”，最后在“服务器返回”中查看结果。\n\n"
        "常用字段：`child_id` 是儿童编号，`recommendation_id` 是推荐编号，"
        "`status` 是结果状态。页面中的文本、整数、列表和是/否分别对应程序里的 "
        "string、integer、array 和 boolean。"
    ),
    openapi_tags=OPENAPI_TAGS,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

ChildId = Annotated[
    str,
    Path(description="儿童编号，例如 C002"),
]
RecommendationId = Annotated[
    int,
    Path(gt=0, description="系统保存推荐时生成的唯一推荐编号"),
]


class ChildInput(BaseModel):
    nickname: str = Field(min_length=1, description="儿童昵称")
    birth_date: Date = Field(description="出生日期，格式为 YYYY-MM-DD")
    weaning_start: Date = Field(description="开始添加辅食的日期，格式为 YYYY-MM-DD")
    known_allergens: list[str] = Field(
        default_factory=list,
        description="已知致敏物质类别，例如蛋类、乳、大豆",
    )
    group: Literal["test", "control"] = Field(
        description="实验分组：test 表示实验组，control 表示对照组"
    )


class ScheduleInput(BaseModel):
    weeks: int = Field(default=6, ge=1, le=12, description="生成计划的周数，允许 1～12 周")
    today: Date | None = Field(
        default=None,
        description="排程起始日期；留空时使用当天日期",
    )


class EngagementInput(BaseModel):
    adopted: bool = Field(description="家长是否实际按照推荐提供了该食物")
    consumed: bool | None = Field(
        default=None,
        description="宝宝是否实际吃进去了一些；尚未确认时可以留空",
    )


class OutcomeInput(BaseModel):
    date: Date = Field(description="结果发生日期，格式为 YYYY-MM-DD")
    status: Literal["passed", "refused", "reaction"] = Field(
        description="结果状态：passed 表示通过，refused 表示拒食，reaction 表示不良反应"
    )
    note: str | None = Field(default=None, description="补充说明；没有时可以留空")


class DailyIntakeInput(BaseModel):
    date: Date = Field(description="膳食记录日期，格式为 YYYY-MM-DD")
    categories: list[str] = Field(
        default_factory=list,
        description="当天吃到的食物类别",
    )
    meal_count: int = Field(ge=0, description="当天辅食餐数")
    is_breastfed: bool = Field(description="当天是否进行母乳喂养")
    milk_feeds: int = Field(default=0, ge=0, description="当天配方奶喂养次数")


@app.get("/docs", include_in_schema=False)
def api_docs() -> HTMLResponse:
    return chinese_swagger_ui(app.openapi_url, "果初接口文档")


@app.exception_handler(ChildNotFoundError)
@app.exception_handler(FoodNotFoundError)
@app.exception_handler(RecommendationNotFoundError)
async def not_found_handler(_request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DataValidationError)
async def validation_handler(_request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def _current_experiment_phase() -> str:
    phase = os.environ.get(EXPERIMENT_PHASE_ENV, "active").strip().lower()
    if phase not in {"baseline", "active"}:
        raise RuntimeError(
            f"{EXPERIMENT_PHASE_ENV} 只能设置为 baseline 或 active"
        )
    return phase


def _save_displayed_schedule(child_id: str, plan: list[dict]) -> list[dict]:
    ids = save_recommendations(child_id, plan)
    return [
        {"recommendation_id": recommendation_id, **item}
        for recommendation_id, item in zip(ids, plan)
    ]


@app.get(
    "/health",
    tags=["系统状态"],
    summary="检查接口是否正常运行",
    description="返回正常状态时，说明本机接口服务已经启动。",
)
def health() -> dict:
    return {"status": "ok"}


@app.put(
    "/children/{child_id}",
    tags=["儿童档案"],
    summary="新增或更新儿童档案",
)
def put_child(child_id: ChildId, body: ChildInput) -> dict:
    save_child(
        child_id,
        body.nickname,
        body.birth_date,
        body.weaning_start,
        body.known_allergens,
        body.group,
    )
    return load_child(child_id)


@app.get(
    "/children/{child_id}",
    tags=["儿童档案"],
    summary="查询儿童档案",
)
def get_child(child_id: ChildId) -> dict:
    return load_child(child_id)


@app.get(
    "/foods",
    tags=["食物数据"],
    summary="查询食物库",
)
def get_foods() -> list[dict]:
    return load_foods()


@app.post(
    "/children/{child_id}/schedule",
    tags=["辅食推荐"],
    summary="生成并保存辅食推荐",
    description="只向实验组生成推荐；推荐在展示时立即保存，用于后续采纳率统计。",
)
def create_schedule(child_id: ChildId, body: ScheduleInput) -> dict:
    child = load_child(child_id)
    if _current_experiment_phase() == "baseline":
        raise HTTPException(status_code=409, detail="基线期不生成个性化推荐")
    if child["group"] != "test":
        raise HTTPException(status_code=403, detail="对照组不生成个性化推荐")

    start = body.today or Date.today()
    end = start + timedelta(days=body.weeks * 7)
    existing = [
        item
        for item in load_recommendations(child_id)
        if item["cancelled_at"] is None
        and item["outcome"] is None
        and start <= item["date"] < end
    ]
    if existing:
        return {
            "child_id": child_id,
            "count": len(existing),
            "recommendations": existing,
        }

    plan = generate_schedule(child_id, weeks=body.weeks, today=body.today)
    displayed = _save_displayed_schedule(child_id, plan)
    return {
        "child_id": child_id,
        "count": len(displayed),
        "recommendations": displayed,
    }


@app.get(
    "/children/{child_id}/recommendations",
    tags=["辅食推荐"],
    summary="查询推荐追踪记录",
)
def get_recommendations(
    child_id: ChildId,
    include_cancelled: bool = Query(
        default=True,
        description="是否包含已经取消的推荐",
    ),
) -> list[dict]:
    recommendations = load_recommendations(child_id)
    if include_cancelled:
        return recommendations
    return [item for item in recommendations if item["cancelled_at"] is None]


@app.patch(
    "/recommendations/{recommendation_id}/engagement",
    tags=["辅食推荐"],
    summary="记录家长采纳和宝宝实际摄入",
)
def update_engagement(recommendation_id: RecommendationId, body: EngagementInput) -> dict:
    record_recommendation_engagement(
        recommendation_id,
        adopted=body.adopted,
        consumed=body.consumed,
    )
    return load_recommendation(recommendation_id)


@app.post(
    "/recommendations/{recommendation_id}/outcome",
    tags=["辅食推荐"],
    summary="上报推荐结果",
    description="上报不良反应时，会取消后续旧计划并自动重新排程。",
)
def report_outcome(recommendation_id: RecommendationId, body: OutcomeInput) -> dict:
    recommendation = load_recommendation(recommendation_id)
    if recommendation["outcome"] == body.status:
        return {
            "recommendation": recommendation,
            "deleted_future_plans": 0,
            "rescheduled": [],
        }
    deleted_plans = record_recommendation_outcome(
        recommendation_id,
        body.date,
        body.status,
        body.note,
    )
    rescheduled: list[dict] = []

    if body.status == "reaction":
        try:
            plan = generate_schedule(
                recommendation["child_id"],
                weeks=6,
                today=body.date,
            )
            rescheduled = _save_displayed_schedule(
                recommendation["child_id"],
                plan,
            )
        except Exception:
            record_reschedule_result(
                recommendation_id,
                succeeded=False,
                plan_count=0,
            )
            raise
        record_reschedule_result(
            recommendation_id,
            succeeded=True,
            plan_count=len(rescheduled),
        )

    return {
        "recommendation": load_recommendation(recommendation_id),
        "deleted_future_plans": deleted_plans,
        "rescheduled": rescheduled,
    }


@app.get(
    "/children/{child_id}/history",
    tags=["家庭记录"],
    summary="查询辅食历史",
)
def get_history(child_id: ChildId) -> list[dict]:
    return load_history(child_id)


@app.get(
    "/children/{child_id}/daily-intake",
    tags=["家庭记录"],
    summary="查询每日膳食记录",
)
def get_daily_intake(child_id: ChildId) -> list[dict]:
    return load_daily_intake(child_id)


@app.put(
    "/children/{child_id}/daily-intake",
    tags=["家庭记录"],
    summary="保存每日膳食记录",
)
def put_daily_intake(child_id: ChildId, body: DailyIntakeInput) -> dict:
    save_daily_intake(
        child_id,
        body.date,
        body.categories,
        body.meal_count,
        body.is_breastfed,
        body.milk_feeds,
    )
    item = next(
        item for item in load_daily_intake(child_id) if item["date"] == body.date
    )
    return item


WEB_DIRECTORY = FilePath(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIRECTORY, html=True), name="家庭网页")
