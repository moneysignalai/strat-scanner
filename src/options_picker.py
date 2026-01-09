"""Option selection logic for Strat signals."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
import logging

from .models import StratSignal

logger = logging.getLogger(__name__)


def _parse_expiration(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        cleaned = value.replace("Z", "")
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def pick_option_for_signal(
    signal: StratSignal,
    options_chain: List[dict],
) -> StratSignal:
    """
    Select a single liquid option contract for a given signal based on
    moneyness, expiration window, and liquidity filters.
    """
    if not options_chain:
        logger.warning(
            "No options chain data available", extra={"symbol": signal.symbol}
        )
        return signal

    now = datetime.utcnow()
    max_exp = now + timedelta(days=14)
    desired_type = "call" if signal.direction == "CALL" else "put"

    filtered: List[dict] = []
    for contract in options_chain:
        contract_type = (
            contract.get("contract_type")
            or contract.get("type")
            or contract.get("option_type")
        )
        if not contract_type:
            continue
        if str(contract_type).lower() != desired_type:
            continue

        expiration_value = contract.get("expiration_date") or contract.get(
            "expiration"
        )
        expiration = _parse_expiration(expiration_value)
        if not expiration:
            continue
        if expiration.date() < now.date() or expiration > max_exp:
            continue

        strike = contract.get("strike_price") or contract.get("strike")
        if strike is None:
            continue
        try:
            strike_val = float(strike)
        except (TypeError, ValueError):
            continue

        if desired_type == "call" and strike_val < signal.underlying_price:
            continue
        if desired_type == "put" and strike_val > signal.underlying_price:
            continue

        open_interest = contract.get("open_interest") or contract.get("oi")
        try:
            oi_val = int(open_interest or 0)
        except (TypeError, ValueError):
            oi_val = 0
        if oi_val < 50:
            continue

        bid = contract.get("bid_price") or contract.get("bid")
        ask = contract.get("ask_price") or contract.get("ask")
        try:
            bid_val = float(bid or 0)
            ask_val = float(ask or 0)
        except (TypeError, ValueError):
            continue
        if ask_val <= 0:
            continue
        spread_pct = (ask_val - bid_val) / ask_val
        if spread_pct > 0.20:
            continue

        contract["_parsed_expiration"] = expiration
        contract["_parsed_strike"] = strike_val
        contract["_parsed_bid"] = bid_val
        contract["_parsed_ask"] = ask_val
        filtered.append(contract)

    if not filtered:
        logger.warning(
            "No option contracts passed filters", extra={"symbol": signal.symbol}
        )
        return signal

    if desired_type == "call":
        filtered.sort(
            key=lambda c: (c["_parsed_expiration"], c["_parsed_strike"])
        )
    else:
        filtered.sort(
            key=lambda c: (c["_parsed_expiration"], -c["_parsed_strike"])
        )

    chosen = filtered[0]
    signal.option_ticker = (
        chosen.get("symbol")
        or chosen.get("contract_symbol")
        or chosen.get("ticker")
    )
    signal.option_strike = chosen.get("_parsed_strike")
    expiration = chosen.get("_parsed_expiration")
    signal.option_expiration = expiration.date().isoformat() if expiration else None
    signal.option_type = desired_type
    signal.option_bid = chosen.get("_parsed_bid")
    signal.option_ask = chosen.get("_parsed_ask")
    signal.option_iv = (
        float(chosen.get("implied_volatility"))
        if chosen.get("implied_volatility") is not None
        else None
    )

    logger.info(
        "Option contract selected for signal",
        extra={
            "symbol": signal.symbol,
            "direction": signal.direction,
            "option_ticker": signal.option_ticker,
            "strike": signal.option_strike,
            "expiration": signal.option_expiration,
        },
    )

    return signal
