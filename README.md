# Strat Scanner

A lightweight worker that scans selected tickers for Strat **daily 1-2-2 continuation** patterns, enriches signals with a liquid options contract idea, and delivers alerts via Telegram. It is designed to run continuously as a background worker (e.g., on Render).

## Features

- **Strat pattern detection** for daily 1-2-2 continuation setups with weekly bias confirmation.
- **Options contract selection** based on expiration window, moneyness, open interest, and spread filters.
- **Telegram alerts** with a clean, human-readable message format.
- **Configurable scan loop** (tickers, intervals, lookback window, signal cap).
- **Massive.com data integration** for equities and options snapshots.

## Architecture Overview

The scanner is organized as a small pipeline that runs on an interval:

1. **Fetch market data** for each ticker via Massive.com.
2. **Detect Strat signals** using daily candles with weekly bias context.
3. **Select an options contract** that matches the signal direction and liquidity criteria.
4. **Send alerts** to Telegram and log the signal payload.

Key components:

- **Data providers**: `src/data_providers.py` (Massive REST client + options snapshot endpoint)
- **Pattern logic**: `src/strat_logic.py` (candle classification + 1-2-2 detection)
- **Options filtering**: `src/options_picker.py` (expiration, moneyness, OI, spread)
- **Alerts**: `src/alerts.py` (message formatting + Telegram delivery)
- **Scanner orchestration**: `src/scanner.py` (loop over tickers and track duplicates)
- **Worker entrypoint**: `src/worker.py` (long-running loop)

## Requirements

- Python 3.10+
- Massive.com API access
- Optional Telegram bot credentials (for notifications)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The worker is configured entirely through environment variables. In development, setting `ENVIRONMENT=dev` enables `.env` loading via `python-dotenv`.

### Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MASSIVE_API_KEY` | ✅ | — | API key for Massive.com data. |
| `SCAN_TICKERS` | ❌ | `SPY,QQQ,IWM,NVDA,TSLA,AAPL,MSFT,AMZN,META,AMD,AVGO` | Comma-separated tickers to scan. |
| `TIMEFRAME_DAYS_LOOKBACK` | ❌ | `60` | Daily candles lookback window. |
| `SCAN_INTERVAL_SECONDS` | ❌ | `300` | Delay between scan cycles. |
| `MAX_SIGNALS_PER_SCAN` | ❌ | `50` | Hard cap on alerts per scan cycle. |
| `TELEGRAM_BOT_TOKEN` | ❌ | — | Bot token for Telegram alert delivery. |
| `TELEGRAM_CHAT_ID` | ❌ | — | Chat ID for Telegram alert delivery. |
| `LOG_LEVEL` | ❌ | `INFO` | Logging verbosity. |
| `DEBUG_MODE` | ❌ | `false` | Enables verbose log format. |
| `ENVIRONMENT` | ❌ | `prod` | Use `dev` to load `.env`. |

### Example `.env`

```bash
MASSIVE_API_KEY=your_api_key
SCAN_TICKERS=SPY,QQQ,MSFT
TIMEFRAME_DAYS_LOOKBACK=60
SCAN_INTERVAL_SECONDS=300
MAX_SIGNALS_PER_SCAN=50
TELEGRAM_BOT_TOKEN=123456:ABCDEF
TELEGRAM_CHAT_ID=123456789
LOG_LEVEL=INFO
DEBUG_MODE=false
ENVIRONMENT=dev
```

## Running Locally

Run a single worker process from the repo root:

```bash
python -m src.worker
```

The worker runs indefinitely, sleeping between scan cycles based on `SCAN_INTERVAL_SECONDS`.

## Signal Detection Logic (Summary)

The scanner detects **daily 1-2-2 continuation** setups with a weekly bias filter:

- **Bullish (CALL)**
  - Daily candles: `2U` → `1` → breakout above the inside bar
  - Weekly bias: current weekly candle is **up**

- **Bearish (PUT)**
  - Daily candles: `2D` → `1` → breakdown below the inside bar
  - Weekly bias: current weekly candle is **down**

If a signal is detected, the options picker chooses a contract that:

- Matches direction (call/put)
- Expires within the next 14 days
- Has acceptable liquidity (open interest ≥ 50)
- Has a tight spread (≤ 20%)
- Is not deep ITM (call strikes ≥ underlying, put strikes ≤ underlying)

## Alert Format

Alerts include:

- Timestamp in **US/Eastern**
- Symbol, pattern name, timeframes, and direction
- Entry/stop/underlying price
- Optional option idea (strike, expiration, bid/ask, IV)

If no suitable option passes filters, the alert includes a note suggesting a manual selection.

## Deployment (Render)

This project includes a `render.yaml` worker definition that:

- Installs dependencies via `pip install -r requirements.txt`
- Starts the worker with `python -m src.worker`
- Expects configuration via environment variables

Render or any similar worker platform can run the scanner continuously.

## Project Structure

```
.
├── README.md
├── render.yaml
├── requirements.txt
└── src/
    ├── alerts.py
    ├── config.py
    ├── data_providers.py
    ├── logging_utils.py
    ├── models.py
    ├── options_picker.py
    ├── scanner.py
    ├── strat_logic.py
    └── worker.py
```

## Notes

- The scanner is designed for **alerting**, not automated trading.
- API rate limits and data availability depend on your Massive.com plan.
- Telegram credentials are optional—if omitted, alerts are logged only.

## License

No license file is included in this repository. If you plan to distribute or commercialize this project, add a license that matches your intended usage.
