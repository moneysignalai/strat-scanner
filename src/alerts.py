"""Alert formatting and dispatch utilities."""
from datetime import datetime
import logging
from typing import Any, Dict

import requests

from .config import get_settings
from .models import StratSignal

logger = logging.getLogger(__name__)


def signal_to_alert_dict(signal: StratSignal) -> Dict[str, Any]:
    """
    Convert a StratSignal into a canonical alert dict for logging or downstream use.
    """
    now_iso = datetime.utcnow().isoformat() + "Z"
    return {
        "timestamp": now_iso,
        "symbol": signal.symbol,
        "direction": signal.direction,
        "pattern_name": signal.pattern_name,
        "timeframe": signal.timeframe,
        "bias_timeframe": signal.bias_timeframe,
        "entry_level": signal.entry_level,
        "stop_level": signal.stop_level,
        "target_level": signal.target_level,
        "underlying_price": signal.underlying_price,
        "option": {
            "ticker": signal.option_ticker,
            "strike": signal.option_strike,
            "expiration": signal.option_expiration,
            "type": signal.option_type,
            "bid": signal.option_bid,
            "ask": signal.option_ask,
            "iv": signal.option_iv,
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

    opt = alert["option"] or {}
    has_option = opt.get("ticker") is not None

    header = f"⚡ STRAT SIGNAL — {sym}\n📅 {ts}\n"
    core = (
        f"🎯 Pattern: {patt}\n"
        f"🕒 TF: {tf} (Bias: {btf})\n"
        f"📈 Direction: {dirn}\n\n"
        f"📊 Levels\n"
        f"• Entry: {entry:.2f}\n"
        f"• Stop: {stop:.2f}\n"
        f"• Underlying: {under:.2f}\n"
    )

    if target is not None:
        core += f"• Target: {target:.2f}\n"

    if has_option:
        opt_line = (
            f"\n📝 Option Idea\n"
            f"• {opt.get('type', '').upper()} {opt.get('strike'):.2f} exp {opt.get('expiration')}\n"
            f"• Bid/Ask: {opt.get('bid', 0.0):.2f} / {opt.get('ask', 0.0):.2f}\n"
        )
        iv_val = opt.get("iv")
        if iv_val is not None:
            opt_line += f"• IV: {iv_val:.1f}%\n"
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
