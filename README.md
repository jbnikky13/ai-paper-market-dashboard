# AI Market Intelligence v4.4

Complete dashboard + independent Telegram market reporter.

## Architecture

`telegram_bot.py` does **not** import `app.py`.

Therefore the Telegram worker can continue operating even if the Streamlit dashboard is offline.

### Files

- `app.py` — Streamlit dashboard
- `telegram_bot.py` — independent Telegram worker
- `requirements.txt` — dependencies
- `.gitignore` — protects local secrets/data

## Secrets

### Streamlit

Add these to Streamlit Secrets:

```toml
TELEGRAM_BOT_TOKEN = "..."
TELEGRAM_CHANNEL_ID = "@yourchannel"
NGXPULSE_API_KEY = "..."
COINGECKO_DEMO_API_KEY = "..."
```

### Telegram worker

Expose the same values as environment variables:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHANNEL_ID
NGXPULSE_API_KEY
COINGECKO_DEMO_API_KEY
```

Never commit tokens to GitHub.

## Test locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

For Telegram:

```bash
python telegram_bot.py
```

## Cloud operation

The dashboard and Telegram worker should be deployed separately.

A cloud scheduler/cron service should execute:

```bash
python telegram_bot.py
```

at the desired interval.

Because the worker fetches market data directly, the Streamlit site does not need to be online for Telegram updates.

## Data sources

- CoinGecko — crypto
- Yahoo Finance chart endpoint — listed assets
- NGX Pulse — NGX, when configured

## Paper history

The dashboard stores snapshots in:

`.market_data/paper_trades.csv`

Local filesystem persistence depends on the hosting provider. For durable cloud storage, move this later to a database or external storage.

## Scope

This project is informational/paper analysis only. It does not execute trades or recommend a risk amount.
