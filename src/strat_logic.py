"""Strat pattern detection logic."""
from typing import List
import logging

from .models import Candle, CandleType, StratSignal

logger = logging.getLogger(__name__)


def classify_candle_type(current: Candle, previous: Candle) -> CandleType:
    """
    Classify the current candle relative to the previous one using The Strat conventions.
    """
    if current.high <= previous.high and current.low >= previous.low:
        return CandleType.INSIDE

    if current.high >= previous.high and current.low <= previous.low:
        return CandleType.OUTSIDE

    took_high = current.high > previous.high
    took_low = current.low < previous.low

    if took_high and not took_low:
        return CandleType.TWO_UP
    if took_low and not took_high:
        return CandleType.TWO_DOWN

    return CandleType.OUTSIDE


def get_weekly_bias(weekly_candles: List[Candle]) -> str:
    """
    Returns 'up', 'down', or 'neutral' based on the current weekly bar.
    """
    if not weekly_candles:
        return "neutral"
    current = weekly_candles[-1]
    if current.close > current.open:
        return "up"
    if current.close < current.open:
        return "down"
    return "neutral"


def detect_daily_122_signals(
    symbol: str,
    daily_candles: List[Candle],
    weekly_candles: List[Candle],
    underlying_price: float,
) -> List[StratSignal]:
    """
    Detect bullish and bearish daily 1-2-2 continuation patterns with weekly bias.
    """
    if len(daily_candles) < 4:
        logger.debug(
            "Not enough candles for 1-2-2 detection",
            extra={"symbol": symbol, "candles": len(daily_candles)},
        )
        return []

    c0 = daily_candles[-3]
    c1 = daily_candles[-2]
    c2 = daily_candles[-1]

    t0_type = classify_candle_type(c0, daily_candles[-4])
    t1_type = classify_candle_type(c1, c0)
    weekly_bias = get_weekly_bias(weekly_candles)

    signals: List[StratSignal] = []

    if (
        t0_type == CandleType.TWO_UP
        and t1_type == CandleType.INSIDE
        and weekly_bias == "up"
        and c2.high > c1.high
    ):
        signal = StratSignal(
            symbol=symbol,
            direction="CALL",
            pattern_name="Daily 1-2U continuation",
            timeframe="1D",
            bias_timeframe="1W",
            entry_level=c1.high,
            stop_level=c1.low,
            target_level=None,
            underlying_price=underlying_price or c2.close,
        )
        logger.debug(
            "Strat signal detected",
            extra={
                "symbol": symbol,
                "pattern": signal.pattern_name,
                "direction": signal.direction,
                "entry": signal.entry_level,
                "stop": signal.stop_level,
            },
        )
        signals.append(signal)

    if (
        t0_type == CandleType.TWO_DOWN
        and t1_type == CandleType.INSIDE
        and weekly_bias == "down"
        and c2.low < c1.low
    ):
        signal = StratSignal(
            symbol=symbol,
            direction="PUT",
            pattern_name="Daily 1-2D continuation",
            timeframe="1D",
            bias_timeframe="1W",
            entry_level=c1.low,
            stop_level=c1.high,
            target_level=None,
            underlying_price=underlying_price or c2.close,
        )
        logger.debug(
            "Strat signal detected",
            extra={
                "symbol": symbol,
                "pattern": signal.pattern_name,
                "direction": signal.direction,
                "entry": signal.entry_level,
                "stop": signal.stop_level,
            },
        )
        signals.append(signal)

    return signals
