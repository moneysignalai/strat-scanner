"""Scanner orchestration for Strat signals."""
from typing import Set
import logging
from datetime import datetime

from .config import get_settings
from .data_providers import MassiveClient
from .models import StratSignal
from .strat_logic import detect_daily_122_signals
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

    def _signal_key(self, signal: StratSignal) -> str:
        today = datetime.utcnow().date().isoformat()
        return f"{signal.symbol}:{signal.pattern_name}:{signal.direction}:{today}"

    def scan_once(self) -> None:
        """
        Run a single full scan over all configured tickers.
        """
        tickers_str = self.settings.SCAN_TICKERS or ""
        tickers = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
        tickers_scanned = 0
        signals_detected = 0
        signals_alerted = 0
        errors = 0

        for ticker in tickers:
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

                signals = detect_daily_122_signals(ticker, daily, weekly, last_price)
                signals_detected += len(signals)

                for signal in signals:
                    if signals_alerted >= self.settings.MAX_SIGNALS_PER_SCAN:
                        logger.warning(
                            "Max signals per scan reached; skipping remaining",
                            extra={"max": self.settings.MAX_SIGNALS_PER_SCAN},
                        )
                        break

                    key = self._signal_key(signal)
                    if key in self._seen_signals:
                        logger.debug(
                            "Skipping duplicate signal for day",
                            extra={
                                "ticker": signal.symbol,
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

            except Exception:
                errors += 1
                logger.exception("Error scanning ticker", extra={"ticker": ticker})

        logger.info(
            "Scan completed",
            extra={
                "tickers_scanned": tickers_scanned,
                "signals_detected": signals_detected,
                "signals_alerted": signals_alerted,
                "errors": errors,
            },
        )
