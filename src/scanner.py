"""Scanner orchestration for Strat signals."""
from typing import Optional, Set, Dict
import logging
import random
from datetime import datetime, date
from zoneinfo import ZoneInfo

from .config import get_settings
from .data_providers import MassiveClient
from .models import StratSignal
from .strat_logic import detect_daily_strat_signals
from .options_picker import pick_option_for_signal
from .alerts import send_signal_alert

logger = logging.getLogger(__name__)


class Scanner:
    """
    Orchestrates fetching data, detecting Strat signals, selecting options, and sending alerts.
    """

    def __init__(self, client: MassiveClient) -> None:
        self.client = client
        self.settings = get_settings()
        self._seen_signals: Set[str] = set()
        self._current_seen_date: Optional[date] = None
        self._symbol_last_alert_date: Dict[str, date] = {}

    def _current_et_date(self) -> date:
        return datetime.now(ZoneInfo("America/New_York")).date()

    def _signal_key(self, signal: StratSignal, today: date) -> str:
        return (
            f"{signal.symbol}:{signal.pattern_name}:{signal.direction}:"
            f"{signal.entry_level}:{today.isoformat()}"
        )

    def scan_once(self) -> None:
        """
        Run a single full scan over all configured tickers.
        """
        tickers_str = self.settings.SCAN_TICKERS or ""
        tickers = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
        random.shuffle(tickers)
        tickers_scanned = 0
        signals_detected = 0
        signals_alerted = 0
        errors = 0
        all_signals: list[StratSignal] = []
        cooldown_days = self.settings.ALERT_COOLDOWN_DAYS
        symbols_alerted_this_scan: Set[str] = set()

        today = self._current_et_date()
        if self._current_seen_date != today:
            self._seen_signals.clear()
            self._current_seen_date = today
            logger.info(
                "Resetting seen signals for new trading day",
                extra={"date": today.isoformat()},
            )

        logger.info(
            "Scan starting",
            extra={
                "ticker_count": len(tickers),
                "first_tickers": tickers[:5],
                "last_tickers": tickers[-5:],
            },
        )
        max_alerts_logged = False

        for ticker in tickers:
            if signals_alerted >= self.settings.MAX_SIGNALS_PER_SCAN:
                if not max_alerts_logged:
                    logger.warning(
                        "Max signals per scan reached; breaking ticker loop",
                        extra={"max": self.settings.MAX_SIGNALS_PER_SCAN},
                    )
                    max_alerts_logged = True
                break
            tickers_scanned += 1
            try:
                logger.info("Scanning ticker", extra={"ticker": ticker})

                daily = self.client.get_stock_aggs_daily(
                    ticker, self.settings.TIMEFRAME_DAYS_LOOKBACK
                )
                if len(daily) < 4:
                    logger.debug(
                        "Not enough daily candles for Strat logic",
                        extra={"ticker": ticker, "candles": len(daily)},
                    )
                    continue

                weekly = self.client.get_stock_aggs_weekly(ticker, weeks_back=12)

                last_price = self.client.get_last_trade_price(ticker)
                if last_price is None and daily:
                    last_price = daily[-1].close
                if last_price is None:
                    logger.warning(
                        "No price available for ticker", extra={"ticker": ticker}
                    )
                    continue

                signals = detect_daily_strat_signals(ticker, daily, weekly, last_price)
                all_signals.extend(signals)

                if signals:
                    logger.info(
                        "Signals detected for ticker",
                        extra={"ticker": ticker, "signals_found": len(signals)},
                    )
                else:
                    logger.debug("No signals for ticker", extra={"ticker": ticker})

                for signal in signals:
                    if signals_alerted >= self.settings.MAX_SIGNALS_PER_SCAN:
                        if not max_alerts_logged:
                            logger.warning(
                                "Max signals per scan reached; breaking ticker loop",
                                extra={"max": self.settings.MAX_SIGNALS_PER_SCAN},
                            )
                            max_alerts_logged = True
                        break

                    symbol = signal.symbol
                    if symbol in symbols_alerted_this_scan:
                        logger.debug(
                            "Skipping signal because symbol already alerted this scan",
                            extra={
                                "symbol": symbol,
                                "pattern_name": signal.pattern_name,
                            },
                        )
                        continue
                    if cooldown_days > 0:
                        last_date = self._symbol_last_alert_date.get(symbol)
                        if last_date is not None:
                            days_since = (today - last_date).days
                            if days_since < cooldown_days:
                                logger.debug(
                                    "Skipping signal due to symbol cooldown",
                                    extra={
                                        "symbol": symbol,
                                        "last_alert_date": last_date.isoformat(),
                                        "today": today.isoformat(),
                                        "cooldown_days": cooldown_days,
                                        "days_since": days_since,
                                    },
                                )
                                continue

                    key = self._signal_key(signal, today)
                    if key in self._seen_signals:
                        logger.debug(
                            "Skipping duplicate signal for day",
                            extra={
                                "ticker": symbol,
                                "pattern": signal.pattern_name,
                                "direction": signal.direction,
                            },
                        )
                        continue

                    chain = self.client.get_options_chain_snapshot(ticker)
                    signal = pick_option_for_signal(signal, chain)

                    send_signal_alert(signal)
                    self._seen_signals.add(key)
                    signals_alerted += 1
                    signals_detected += 1
                    self._symbol_last_alert_date[symbol] = today
                    symbols_alerted_this_scan.add(symbol)

            except Exception:
                errors += 1
                logger.exception("Error scanning ticker", extra={"ticker": ticker})

        logger.info(
            "Scan completed",
            extra={
                "ticker_count": len(tickers),
                "signals_count": len(all_signals),
                "signal_tickers": sorted({s.symbol for s in all_signals}),
                "unique_signal_ticker_count": len({s.symbol for s in all_signals}),
                "unique_signal_tickers": len({s.symbol for s in all_signals}),
                "patterns_used": sorted({s.pattern_name for s in all_signals}),
                "tickers_scanned": tickers_scanned,
                "signals_detected": signals_detected,
                "signals_alerted": signals_alerted,
                "signals_alerted_by_day_seen_cache_size": len(self._seen_signals),
                "cooldown_days": cooldown_days,
                "errors": errors,
            },
        )
