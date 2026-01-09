"""Strat pattern detection logic."""
from typing import List, Optional
import logging

from .models import Candle, CandleType, StratSignal

logger = logging.getLogger(__name__)

VOLUME_LOOKBACK_DAYS = 20


def _calculate_pct_to_entry(
    current_price: Optional[float], entry: Optional[float]
) -> Optional[float]:
    if current_price is None or entry in (None, 0):
        return None
    try:
        return ((current_price - entry) / entry) * 100.0
    except (TypeError, ZeroDivisionError):
        return None


def _calculate_risk_reward(
    direction: str,
    entry: Optional[float],
    stop: Optional[float],
    current_price: Optional[float],
) -> Optional[float]:
    if entry is None or stop is None or current_price is None:
        return None
    try:
        risk = abs(entry - stop)
    except TypeError:
        return None
    if risk <= 0:
        return None
    if direction == "CALL":
        reward = max(current_price, entry) - stop
    else:
        reward = entry - min(current_price, entry)
    if reward <= 0:
        return None
    return reward / risk


def _calculate_volume_vs_avg_pct(daily_candles: List[Candle]) -> Optional[float]:
    if len(daily_candles) <= VOLUME_LOOKBACK_DAYS:
        return None
    today = daily_candles[-1]
    if today.volume is None:
        return None
    prior = daily_candles[-(VOLUME_LOOKBACK_DAYS + 1) : -1]
    volumes: List[float] = []
    for candle in prior:
        if candle.volume is None or candle.volume <= 0:
            return None
        volumes.append(candle.volume)
    if len(volumes) < VOLUME_LOOKBACK_DAYS:
        return None
    avg_volume = sum(volumes) / len(volumes)
    if avg_volume <= 0:
        return None
    return ((today.volume - avg_volume) / avg_volume) * 100.0


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
        current_price = underlying_price or c2.close
        pct_to_entry = _calculate_pct_to_entry(current_price, c1.high)
        risk_reward = _calculate_risk_reward("CALL", c1.high, c1.low, current_price)
        volume_vs_avg_pct = _calculate_volume_vs_avg_pct(daily_candles)
        signal = StratSignal(
            symbol=symbol,
            direction="CALL",
            pattern_name="Daily 1-2U continuation",
            timeframe="1D",
            bias_timeframe="1W",
            entry_level=c1.high,
            stop_level=c1.low,
            target_level=None,
            underlying_price=current_price,
            pct_to_entry=pct_to_entry,
            risk_reward=risk_reward,
            volume_vs_avg_pct=volume_vs_avg_pct,
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
        current_price = underlying_price or c2.close
        pct_to_entry = _calculate_pct_to_entry(current_price, c1.low)
        risk_reward = _calculate_risk_reward("PUT", c1.low, c1.high, current_price)
        volume_vs_avg_pct = _calculate_volume_vs_avg_pct(daily_candles)
        signal = StratSignal(
            symbol=symbol,
            direction="PUT",
            pattern_name="Daily 1-2D continuation",
            timeframe="1D",
            bias_timeframe="1W",
            entry_level=c1.low,
            stop_level=c1.high,
            target_level=None,
            underlying_price=current_price,
            pct_to_entry=pct_to_entry,
            risk_reward=risk_reward,
            volume_vs_avg_pct=volume_vs_avg_pct,
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
