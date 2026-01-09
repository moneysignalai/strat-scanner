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
    logger.info(
        "Evaluating options for signal",
        extra={
            "ticker": signal.symbol,
            "direction": signal.direction,
            "chain_size": len(options_chain),
        },
    )
    if not options_chain:
        logger.warning(
            "No options chain data available", extra={"symbol": signal.symbol}
        )
        return signal

    now = datetime.utcnow().date()
    max_exp = now + timedelta(days=21)
    desired_type = "call" if signal.direction == "CALL" else "put"

    after_type: List[dict] = []
    for contract in options_chain:
        contract_type = contract.get("contract_type")
        if not contract_type:
            continue
        if str(contract_type).lower() != desired_type:
            continue
        after_type.append(contract)
    logger.debug(
        "Options after contract_type filter",
        extra={"ticker": signal.symbol, "count": len(after_type)},
    )

    after_expiry: List[dict] = []
    for contract in after_type:
        expiration_value = contract.get("expiration_date")
        expiration = _parse_expiration(expiration_value)
        if not expiration:
            continue
        expiration_date = expiration.date()
        if expiration_date < now or expiration_date > max_exp:
            continue
        contract["_parsed_expiration"] = expiration_date
        contract["_parsed_dte"] = (expiration_date - now).days
        after_expiry.append(contract)
    logger.debug(
        "Options after expiry filter",
        extra={"ticker": signal.symbol, "count": len(after_expiry)},
    )

    after_moneyness: List[dict] = []
    lower_call = signal.underlying_price * 0.97
    upper_put = signal.underlying_price * 1.03
    for contract in after_expiry:
        strike = contract.get("strike_price")
        if strike is None:
            continue
        try:
            strike_val = float(strike)
        except (TypeError, ValueError):
            continue
        if desired_type == "call" and strike_val < lower_call:
            continue
        if desired_type == "put" and strike_val > upper_put:
            continue
        contract["_parsed_strike"] = strike_val
        after_moneyness.append(contract)
    logger.debug(
        "Options after moneyness filter",
        extra={"ticker": signal.symbol, "count": len(after_moneyness)},
    )

    filtered: List[dict] = []
    for contract in after_moneyness:
        open_interest = contract.get("open_interest")
        try:
            oi_val = int(open_interest or 0)
        except (TypeError, ValueError):
            oi_val = 0
        if oi_val < 50:
            continue

        bid = contract.get("bid_price")
        ask = contract.get("ask_price")
        try:
            bid_val = float(bid or 0)
            ask_val = float(ask or 0)
        except (TypeError, ValueError):
            continue
        if ask_val <= 0:
            continue
        spread_pct = (ask_val - bid_val) / ask_val
        if spread_pct > 0.25:
            continue

        contract["_parsed_bid"] = bid_val
        contract["_parsed_ask"] = ask_val
        contract["_parsed_oi"] = oi_val
        filtered.append(contract)
    logger.debug(
        "Options after liquidity filter",
        extra={"ticker": signal.symbol, "count": len(filtered)},
    )

    if not filtered and options_chain:
        logger.debug(
            "Using relaxed fallback filters for options",
            extra={"ticker": signal.symbol},
        )
        relaxed: List[dict] = []
        lower_bound = signal.underlying_price * 0.95
        upper_bound = signal.underlying_price * 1.05
        for contract in after_expiry:
            strike_val = contract.get("_parsed_strike")
            if strike_val is None:
                strike = contract.get("strike_price")
                if strike is None:
                    continue
                try:
                    strike_val = float(strike)
                except (TypeError, ValueError):
                    continue
                contract["_parsed_strike"] = strike_val
            if strike_val < lower_bound or strike_val > upper_bound:
                continue

            open_interest = contract.get("open_interest")
            try:
                oi_val = int(open_interest or 0)
            except (TypeError, ValueError):
                oi_val = 0
            if oi_val < 10:
                continue

            bid = contract.get("bid_price")
            ask = contract.get("ask_price")
            try:
                bid_val = float(bid or 0)
                ask_val = float(ask or 0)
            except (TypeError, ValueError):
                continue
            if ask_val <= 0:
                continue
            spread_pct = (ask_val - bid_val) / ask_val
            if spread_pct > 0.35:
                continue

            contract["_parsed_bid"] = bid_val
            contract["_parsed_ask"] = ask_val
            contract["_parsed_oi"] = oi_val
            relaxed.append(contract)
        if relaxed:
            filtered = relaxed

    if not filtered:
        logger.warning(
            "No option contracts passed filters", extra={"symbol": signal.symbol}
        )
        return signal

    filtered.sort(
        key=lambda c: (
            c["_parsed_dte"],
            abs(c["_parsed_strike"] - signal.entry_level),
        )
    )

    chosen = filtered[0]
    signal.option_ticker = chosen.get("symbol")
    signal.option_strike = chosen.get("_parsed_strike")
    expiration = chosen.get("_parsed_expiration")
    signal.option_expiration = expiration.isoformat() if expiration else None
    signal.option_type = desired_type
    signal.option_bid = chosen.get("_parsed_bid")
    signal.option_ask = chosen.get("_parsed_ask")
    signal.option_iv = (
        float(chosen.get("implied_vol"))
        if chosen.get("implied_vol") is not None
        else None
    )

    logger.info(
        "Option contract selected",
        extra={
            "ticker": signal.symbol,
            "option_symbol": signal.option_ticker,
            "side": signal.option_type.upper() if signal.option_type else None,
            "strike": signal.option_strike,
            "expiration": signal.option_expiration,
            "bid": signal.option_bid,
            "ask": signal.option_ask,
            "oi": chosen.get("_parsed_oi"),
        },
    )

    return signal
