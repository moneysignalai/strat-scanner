"""Data provider integrations for Massive.com."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from massive.rest import RESTClient

from .config import get_settings
from .models import Candle

logger = logging.getLogger(__name__)


def _parse_timestamp(value: object) -> datetime:
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            return datetime.utcfromtimestamp(value / 1000)
        return datetime.utcfromtimestamp(value)
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def _candle_from_agg(row: dict) -> Candle:
    return Candle(
        timestamp=_parse_timestamp(row.get("t") or row.get("timestamp")),
        open=float(row.get("o") or row.get("open") or 0.0),
        high=float(row.get("h") or row.get("high") or 0.0),
        low=float(row.get("l") or row.get("low") or 0.0),
        close=float(row.get("c") or row.get("close") or 0.0),
        volume=(
            float(row.get("v") or row.get("volume"))
            if row.get("v") is not None or row.get("volume") is not None
            else None
        ),
    )


class MassiveClient:
    """
    Lightweight wrapper around the Massive REST client for the data we need.
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.MASSIVE_API_KEY:
            raise RuntimeError("MASSIVE_API_KEY is not set")
        self.client = RESTClient(api_key=settings.MASSIVE_API_KEY)

    def get_stock_aggs_daily(self, ticker: str, days_back: int) -> List[Candle]:
        """Fetch daily OHLC aggregates for a ticker."""
        logger.info("Requesting daily aggregates", extra={"ticker": ticker})
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days_back)
            results = self.client.list_aggs(
                ticker,
                1,
                "day",
                start_date,
                end_date,
                limit=days_back + 5,
            )
            rows = list(results) if results else []
            if not rows:
                logger.warning(
                    "No daily aggregates returned", extra={"ticker": ticker}
                )
                return []
            candles = [_candle_from_agg(row) for row in rows]
            return sorted(candles, key=lambda c: c.timestamp)
        except Exception:
            logger.exception("Failed to fetch daily aggregates", extra={"ticker": ticker})
            return []

    def get_stock_aggs_weekly(self, ticker: str, weeks_back: int) -> List[Candle]:
        """Fetch weekly OHLC aggregates for a ticker."""
        logger.info("Requesting weekly aggregates", extra={"ticker": ticker})
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(weeks=weeks_back)
            results = self.client.list_aggs(
                ticker,
                1,
                "week",
                start_date,
                end_date,
                limit=weeks_back + 5,
            )
            rows = list(results) if results else []
            if not rows:
                logger.warning(
                    "No weekly aggregates returned", extra={"ticker": ticker}
                )
                return []
            candles = [_candle_from_agg(row) for row in rows]
            return sorted(candles, key=lambda c: c.timestamp)
        except Exception:
            logger.exception("Failed to fetch weekly aggregates", extra={"ticker": ticker})
            return []

    def get_last_trade_price(self, ticker: str) -> Optional[float]:
        """Fetch the last trade price for a ticker."""
        logger.info("Requesting last trade", extra={"ticker": ticker})
        try:
            trade = self.client.get_last_trade(ticker)
            if trade is None:
                logger.warning("No last trade returned", extra={"ticker": ticker})
                return None
            if isinstance(trade, dict):
                for key in ("price", "p", "last", "last_price"):
                    if key in trade and trade[key] is not None:
                        return float(trade[key])
            price = getattr(trade, "price", None) or getattr(trade, "p", None)
            return float(price) if price is not None else None
        except Exception:
            logger.exception("Failed to fetch last trade", extra={"ticker": ticker})
            return None

    def get_options_chain_snapshot(self, ticker: str) -> List[dict]:
        """Fetch options chain snapshot for a ticker."""
        logger.info("Requesting options chain snapshot", extra={"ticker": ticker})
        try:
            response = self.client.get_options_chain_snapshot(ticker)
            if response is None:
                logger.warning(
                    "No options chain snapshot returned", extra={"ticker": ticker}
                )
                return []
            if isinstance(response, dict):
                results = response.get("results") or response.get("data") or []
            elif isinstance(response, list):
                results = response
            else:
                results = list(response)
            if not results:
                logger.warning(
                    "Empty options chain snapshot", extra={"ticker": ticker}
                )
            return results
        except Exception:
            logger.exception("Failed to fetch options chain snapshot", extra={"ticker": ticker})
            return []


# Example snippets for manual testing (do not run automatically)
#
# from .data_providers import MassiveClient
# client = MassiveClient()
# daily_candles = client.get_stock_aggs_daily("SPY", days_back=60)
# print(daily_candles[-5:])
#
# from .models import Candle
# from .strat_logic import detect_daily_122_signals
# fake_daily = [
#     Candle(timestamp=datetime.utcnow(), open=100, high=105, low=95, close=104),
#     Candle(timestamp=datetime.utcnow(), open=104, high=108, low=100, close=107),
#     Candle(timestamp=datetime.utcnow(), open=107, high=109, low=106, close=108),
#     Candle(timestamp=datetime.utcnow(), open=108, high=110, low=107, close=109),
# ]
# fake_weekly = [
#     Candle(timestamp=datetime.utcnow(), open=100, high=110, low=90, close=105)
# ]
# signals = detect_daily_122_signals("SPY", fake_daily, fake_weekly, 109)
# print(signals)
