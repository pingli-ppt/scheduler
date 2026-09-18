"""SQLite 连接、初始化和表结构。

数据库默认放在本文件同目录的 ``guochu.sqlite3``。该文件已被项目根目录的
``.gitignore`` 忽略。测试或部署时可通过 ``GUOCHU_DB_PATH`` 覆盖路径。
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "guochu.sqlite3"
DATABASE_PATH_ENV = "GUOCHU_DB_PATH"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS foods (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    category            TEXT NOT NULL CHECK (category IN (
                            '谷物根茎薯类', '豆类坚果', '奶类', '肉类', '蛋类',
                            '维生素A丰富蔬果', '其他蔬果'
                        )),
    iron_mg_per_100g     REAL CHECK (iron_mg_per_100g IS NULL OR iron_mg_per_100g >= 0),
    zinc_mg_per_100g     REAL CHECK (zinc_mg_per_100g IS NULL OR zinc_mg_per_100g >= 0),
    nutrient_source     TEXT CHECK (nutrient_source IS NULL OR nutrient_source IN ('animal', 'plant')),
    is_allergen         INTEGER NOT NULL CHECK (is_allergen IN (0, 1)),
    allergen_type       TEXT CHECK (allergen_type IS NULL OR allergen_type IN (
                            '含麸质谷物', '甲壳纲类动物', '鱼类', '蛋类',
                            '花生', '大豆', '乳', '坚果'
                        )),
    min_month           INTEGER NOT NULL CHECK (min_month >= 6),
    texture_stage       INTEGER NOT NULL CHECK (texture_stage IN (1, 2, 3, 4)),
    season_months       TEXT NOT NULL DEFAULT '',
    prep_note           TEXT,
    source              TEXT NOT NULL CHECK (length(trim(source)) > 0),
    avg_price           REAL CHECK (avg_price IS NULL OR avg_price >= 0),
    edible_ratio        REAL CHECK (edible_ratio IS NULL OR (edible_ratio >= 0 AND edible_ratio <= 1))
);

CREATE TABLE IF NOT EXISTS children (
    id                  TEXT PRIMARY KEY,
    nickname            TEXT NOT NULL,
    birth_date          TEXT NOT NULL,
    weaning_start       TEXT NOT NULL,
    known_allergens     TEXT NOT NULL DEFAULT '',
    "group"             TEXT NOT NULL CHECK ("group" IN ('test', 'control')),
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS food_records (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id            TEXT NOT NULL,
    food_id             INTEGER NOT NULL,
    date                TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('planned', 'passed', 'reaction', 'refused')),
    note                TEXT,
    reported_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (child_id) REFERENCES children(id),
    FOREIGN KEY (food_id) REFERENCES foods(id)
);

CREATE TABLE IF NOT EXISTS daily_intake (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id            TEXT NOT NULL,
    date                TEXT NOT NULL,
    categories          TEXT NOT NULL DEFAULT '',
    meal_count          INTEGER NOT NULL CHECK (meal_count >= 0),
    is_breastfed        INTEGER NOT NULL CHECK (is_breastfed IN (0, 1)),
    milk_feeds          INTEGER NOT NULL DEFAULT 0 CHECK (milk_feeds >= 0),
    submitted_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (child_id) REFERENCES children(id),
    UNIQUE (child_id, date)
);

CREATE INDEX IF NOT EXISTS idx_food_records_child_date
    ON food_records (child_id, date, id);

CREATE INDEX IF NOT EXISTS idx_daily_intake_child_date
    ON daily_intake (child_id, date, id);
"""


def resolve_database_path(database_path: str | Path | None = None) -> Path:
    """返回数据库路径；相对路径统一相对于项目根目录解释。"""

    configured = database_path or os.environ.get(DATABASE_PATH_ENV)
    if configured is None:
        return DEFAULT_DATABASE_PATH

    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def get_connection(database_path: str | Path | None = None) -> sqlite3.Connection:
    """创建启用外键约束且以列名访问结果的 SQLite 连接。"""

    path = resolve_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def open_database(
    database_path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """提供会自动提交、回滚并关闭的数据库连接。"""

    connection = get_connection(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database(database_path: str | Path | None = None) -> Path:
    """幂等创建数据层所需的四张核心表，并返回数据库路径。"""

    path = resolve_database_path(database_path)
    with open_database(path) as connection:
        connection.executescript(SCHEMA_SQL)
    return path


if __name__ == "__main__":
    print(init_database())
