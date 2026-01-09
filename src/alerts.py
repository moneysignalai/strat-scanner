"""Alert formatting and dispatch utilities."""
from datetime import datetime, timezone
import logging
from typing import Any, Dict
from zoneinfo import ZoneInfo  # <-- added for EST timezone handling

import requests

from .config import get_settings
from .models import StratSignal

logger = logging.getLogger(__name__)


def signal_to_alert_dict(signal: StratSignal) -> Dict[str, Any]:
    """
    Convert a StratSignal into a canonical alert dict for logging or downstream use.
    Timestamp is formatted in US/Eastern (America/New_York).
    """
    et = ZoneInfo("America/New_York")
    now_pretty = datetime.now(timezone.utc).astimezone(et).strftime("%m-%d-%Y · %I:%M %p ET")

    return {
        "timestamp": now_pretty,
        "symbol": signal.symbol,
        "direction": signal.direction,
        "pattern_name": signal.pattern_name,
        "timeframe": signal.timeframe,
        "bias_timeframe": signal.bias_timeframe,
        "entry_level": signal.entry_level,
        "stop_level": signal.stop_level,
        "target_level": signal.target_level,
        "underlying_price": signal.underlying_price,
        "pct_to_entry": signal.pct_to_entry,
        "risk_reward": signal.risk_reward,
        "volume_vs_avg_pct": signal.volume_vs_avg_pct,
        "option": {
            "ticker": signal.option_ticker,
            "strike": signal.option_strike,
            "expiration": signal.option_expiration,
            "type": signal.option_type,
            "bid": signal.option_bid,
            "ask": signal.option_ask,
            "iv": signal.option_iv,
            "open_interest": signal.option_open_interest,
            "volume": signal.option_volume,
            "delta": signal.option_delta,
            "iv_pct": signal.option_iv_pct,
        },
    }


def send_telegram_message(text: str) -> None:
    """Send a message to Telegram if configured."""
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured; skipping message send")
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(
                "Telegram sendMessage returned non-200",
                extra={
                    "status_code": resp.status_code,
                    "body": resp.text[:500],
                },
            )
    except Exception:
        logger.exception("Error sending Telegram message")


def format_signal_message(signal: StratSignal) -> str:
    """
    Format a StratSignal into a human-readable multi-line alert string.
    Designed for Telegram but can be reused elsewhere.
    """
    alert = signal_to_alert_dict(signal)
    ts = alert["timestamp"]
    sym = alert["symbol"]
    dirn = alert["direction"]
    patt = alert["pattern_name"]
    tf = alert["timeframe"]
    btf = alert["bias_timeframe"]
    entry = alert["entry_level"]
    stop = alert["stop_level"]
    target = alert["target_level"]
    under = alert["underlying_price"]
    pct_to_entry = alert.get("pct_to_entry")
    risk_reward = alert.get("risk_reward")
    volume_vs_avg_pct = alert.get("volume_vs_avg_pct")

    opt = alert["option"] or {}
    has_option = opt.get("ticker") is not None

    header = f"⚡ STRAT SIGNAL — {sym}\n📅 {ts}\n"
    core = (
        f"🎯 Pattern: {patt}\n"
        f"🕒 TF: {tf} (Bias: {btf})\n"
        f"📈 Direction: {dirn}\n\n"
        f"📊 Price Action\n"
        f"• Current $: {under:.2f}"
    )
    if pct_to_entry is not None:
        pct_sign = "−" if pct_to_entry < 0 else "+"
        core += f" ({pct_sign}{abs(pct_to_entry):.2f}% from entry)"
    core += (
        "\n"
        f"• Entry: {entry:.2f}\n"
        f"• Stop: {stop:.2f}\n"
    )

    if target is not None:
        core += f"• Target: {target:.2f}\n"

    if risk_reward is not None and risk_reward > 0:
        rr_display = min(max(risk_reward, 0.1), 10.0)
        core += f"• R/R: {rr_display:.1f} : 1\n"

    if volume_vs_avg_pct is None:
        volume_text = "n/a"
    else:
        volume_sign = "−" if volume_vs_avg_pct < 0 else "+"
        volume_direction = "below" if volume_vs_avg_pct < 0 else "above"
        volume_text = f"{volume_sign}{abs(volume_vs_avg_pct):.0f}% {volume_direction} avg"
    core += f"• Volume: {volume_text}\n"

    if has_option:
        exp = opt.get("expiration")
        formatted_exp = (
            datetime.fromisoformat(exp).strftime("%m-%d-%Y") if exp else exp
        )
        strike = opt.get("strike")
        strike_text = f"{strike:.2f}" if isinstance(strike, (int, float)) else "n/a"
        bid = opt.get("bid") or 0.0
        ask = opt.get("ask") or 0.0
        opt_line = (
            f"\n📝 Option Idea\n"
            f"• {opt.get('type', '').upper()} {strike_text} exp {formatted_exp}\n"
            f"• Bid/Ask: {bid:.2f} / {ask:.2f}\n"
        )
        oi_val = opt.get("open_interest")
        vol_val = opt.get("volume")
        delta_val = opt.get("delta")
        iv_val = opt.get("iv_pct")
        if iv_val is None:
            iv_val = opt.get("iv")
            if iv_val is not None and iv_val <= 1:
                iv_val = iv_val * 100
        if any(value is not None for value in (oi_val, vol_val, delta_val, iv_val)):
            oi_text = str(oi_val) if oi_val is not None else "n/a"
            vol_text = str(vol_val) if vol_val is not None else "n/a"
            delta_text = f"{delta_val:.2f}" if delta_val is not None else "n/a"
            iv_text = f"{iv_val:.1f}%" if iv_val is not None else "n/a"
            opt_line += f"• OI: {oi_text} | Vol: {vol_text}\n"
            opt_line += f"• Delta: {delta_text} | IV: {iv_text}\n"
    else:
        opt_line = (
            "\n📝 Option Idea\n"
            "• No suitable liquid contract found. Consider ATM weekly manually.\n"
        )

    return header + core + opt_line


def send_signal_alert(signal: StratSignal) -> None:
    """
    Convert a StratSignal into an alert dict, log it, and send a Telegram message (if configured).
    """
    alert_dict = signal_to_alert_dict(signal)
    logger.info(
        "Signal alert generated",
        extra={
            "symbol": alert_dict["symbol"],
            "direction": alert_dict["direction"],
            "pattern": alert_dict["pattern_name"],
        },
    )
    logger.debug("Signal alert payload", extra={"alert": alert_dict})
    message = format_signal_message(signal)
    send_telegram_message(message)
