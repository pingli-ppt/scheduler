"""排程规则中的固定参数和固定文案。"""

N_OBSERVE = 4
D_COOLDOWN = 90
MAX_REFUSE = 3
NUTRIENT_RICH_THRESHOLD = 4.5
PLANT_NUTRIENT_FACTOR = 0.5
RECENT_CATEGORY_DAYS = 7

WEIGHTS = {
    "iron": 0.25,
    "zinc": 0.15,
    "gap": 0.30,
    "allergen_early": 0.10,
    "season": 0.20,
}

# 贡献相同时使用固定顺序，保证推荐理由可复现。
REASON_PRIORITY = ("iron", "zinc", "gap", "season", "allergen_early")

TEXTURE_DESC = {
    1: "细腻泥糊状",
    2: "碎末状",
    3: "碎块状、可手抓的指状食物",
    4: "块状、指状、小块软饭",
}

REACTION_MESSAGE = "停止添加这种食物；记录时间和具体表现；如果反应严重，请及时就医。"

