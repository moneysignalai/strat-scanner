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
    # Patterns are intentionally strict; most tickers will not trigger on a given day.
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

    logger.debug(
        "Strat pattern context",
        extra={
            "symbol": symbol,
            "daily_candles_count": len(daily_candles),
            "t0_type": t0_type.value,
            "t1_type": t1_type.value,
            "weekly_bias": weekly_bias,
            "c1_high": c1.high,
            "c1_low": c1.low,
            "c2_high": c2.high,
            "c2_low": c2.low,
            "underlying_price": underlying_price,
        },
    )

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


def detect_daily_212_signals(
    symbol: str,
    daily_candles: List[Candle],
    weekly_candles: List[Candle],
    underlying_price: float,
) -> List[StratSignal]:
    """
    Detect bullish and bearish daily 2-1-2 continuation patterns with weekly bias.
    """
    if len(daily_candles) < 4:
        logger.debug(
            "Not enough candles for 2-1-2 detection",
            extra={"symbol": symbol, "candles": len(daily_candles)},
        )
        return []

    c0 = daily_candles[-3]
    c1 = daily_candles[-2]
    c2 = daily_candles[-1]

    t0_type = classify_candle_type(c0, daily_candles[-4])
    t1_type = classify_candle_type(c1, c0)
    t2_type = classify_candle_type(c2, c1)
    weekly_bias = get_weekly_bias(weekly_candles)

    signals: List[StratSignal] = []

    logger.debug(
        "Strat pattern context",
        extra={
            "symbol": symbol,
            "daily_candles_count": len(daily_candles),
            "t0_type": t0_type.value,
            "t1_type": t1_type.value,
            "t2_type": t2_type.value,
            "weekly_bias": weekly_bias,
            "c0_high": c0.high,
            "c0_low": c0.low,
            "c2_high": c2.high,
            "c2_low": c2.low,
            "underlying_price": underlying_price,
        },
    )

    if (
        t0_type == CandleType.TWO_UP
        and t1_type == CandleType.INSIDE
        and t2_type == CandleType.TWO_UP
        and weekly_bias == "up"
        and c2.high > c0.high
    ):
        current_price = underlying_price or c2.close
        pct_to_entry = _calculate_pct_to_entry(current_price, c2.high)
        risk_reward = _calculate_risk_reward("CALL", c2.high, c1.low, current_price)
        volume_vs_avg_pct = _calculate_volume_vs_avg_pct(daily_candles)
        signal = StratSignal(
            symbol=symbol,
            direction="CALL",
            pattern_name="Daily 2-1-2 continuation",
            timeframe="1D",
            bias_timeframe="1W",
            entry_level=c2.high,
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
        and t2_type == CandleType.TWO_DOWN
        and weekly_bias == "down"
        and c2.low < c0.low
    ):
        current_price = underlying_price or c2.close
        pct_to_entry = _calculate_pct_to_entry(current_price, c2.low)
        risk_reward = _calculate_risk_reward("PUT", c2.low, c1.high, current_price)
        volume_vs_avg_pct = _calculate_volume_vs_avg_pct(daily_candles)
        signal = StratSignal(
            symbol=symbol,
            direction="PUT",
            pattern_name="Daily 2-1-2 continuation",
            timeframe="1D",
            bias_timeframe="1W",
            entry_level=c2.low,
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


def detect_daily_strat_signals(
    symbol: str,
    daily_candles: List[Candle],
    weekly_candles: List[Candle],
    underlying_price: float,
) -> List[StratSignal]:
    """
    Detect all supported daily Strat signals (1-2-2 continuation, 2-1-2 continuation, etc.)
    for a single symbol. This is the unified entry point used by the Scanner.

    Currently includes:
    - Daily 1-2-2 continuation (existing logic)
    - Daily 2-1-2 continuation (new logic)
    """
    signals: List[StratSignal] = []

    signals.extend(
        detect_daily_122_signals(
            symbol=symbol,
            daily_candles=daily_candles,
            weekly_candles=weekly_candles,
            underlying_price=underlying_price,
        )
    )

    signals.extend(
        detect_daily_212_signals(
            symbol=symbol,
            daily_candles=daily_candles,
            weekly_candles=weekly_candles,
            underlying_price=underlying_price,
        )
    )

    return signals


# TODO: Add additional Strat detectors (e.g., detect_daily_inside_breakout_signals)
# detect_daily_122_signals from scanner.py when ready.
