from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PRODUCTS_CSV = BASE_DIR / "data" / "products_verified.csv"
DEFAULT_REVIEWS_CSV = BASE_DIR / "data" / "review_summaries.csv"
DEFAULT_JSON_DB = BASE_DIR / "data" / "sample_products.json"
DEFAULT_SQLITE_PATH = BASE_DIR / "data" / "k_beauty_agent.sqlite3"


def database_url() -> str:
    return os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")


def sqlite_path_from_url(url: str | None = None) -> Path:
    value = url or database_url()
    if value.startswith("sqlite:///"):
        return Path(value.removeprefix("sqlite:///"))
    if value.startswith("sqlite://"):
        return Path(value.removeprefix("sqlite://"))
    return Path(value)


def admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "change-me")


def openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


def session_secret() -> str:
    return os.getenv("SESSION_SECRET", "dev-session-secret-change-me")
