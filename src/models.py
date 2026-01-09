"""Domain models for Strat scanner."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Optional


class CandleType(str, Enum):
    INSIDE = "1"
    TWO_UP = "2U"
    TWO_DOWN = "2D"
    OUTSIDE = "3"


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


@dataclass
class StratSignal:
    """
    Represents a Strat trading signal on the underlying, plus (optional) mapped option contract.
    """

    symbol: str
    direction: Literal["CALL", "PUT"]
    pattern_name: str
    timeframe: str
    bias_timeframe: str
    entry_level: float
    stop_level: float
    target_level: Optional[float]
    underlying_price: float

    option_ticker: Optional[str] = None
    option_strike: Optional[float] = None
    option_expiration: Optional[str] = None
    option_type: Optional[Literal["call", "put"]] = None
    option_bid: Optional[float] = None
    option_ask: Optional[float] = None
    option_iv: Optional[float] = None
