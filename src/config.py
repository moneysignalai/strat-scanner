"""Configuration management for the Strat scanner."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _env_int(value: Optional[str], default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Container for environment-based configuration."""

    MASSIVE_API_KEY: str
    SCAN_TICKERS: str = (
        "SPY,QQQ,IWM,NVDA,TSLA,AAPL,MSFT,AMZN,META,AMD,AVGO"
    )
    TIMEFRAME_DAYS_LOOKBACK: int = 60
    SCAN_INTERVAL_SECONDS: int = 300
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    DEBUG_MODE: bool = False
    MAX_SIGNALS_PER_SCAN: int = 50
    ENVIRONMENT: str = "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings object loaded from environment variables."""
    if os.getenv("ENVIRONMENT", "prod").lower() == "dev":
        load_dotenv()

    return Settings(
        MASSIVE_API_KEY=os.getenv("MASSIVE_API_KEY", "").strip(),
        SCAN_TICKERS=os.getenv(
            "SCAN_TICKERS",
            "SPY,QQQ,IWM,NVDA,TSLA,AAPL,MSFT,AMZN,META,AMD,AVGO",
        ),
        TIMEFRAME_DAYS_LOOKBACK=_env_int(
            os.getenv("TIMEFRAME_DAYS_LOOKBACK"), 60
        ),
        SCAN_INTERVAL_SECONDS=_env_int(
            os.getenv("SCAN_INTERVAL_SECONDS"), 300
        ),
        TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        TELEGRAM_CHAT_ID=os.getenv("TELEGRAM_CHAT_ID") or None,
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        DEBUG_MODE=_env_bool(os.getenv("DEBUG_MODE"), False),
        MAX_SIGNALS_PER_SCAN=_env_int(
            os.getenv("MAX_SIGNALS_PER_SCAN"), 50
        ),
        ENVIRONMENT=os.getenv("ENVIRONMENT", "prod"),
    )
