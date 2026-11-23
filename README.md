# AI Market Intelligence — Telegram Reporting

Telegram is the project's sole reporting and alert-delivery channel. The Streamlit app is a separate optional research interface; it is not part of the reporting pipeline.

## Architecture

`telegram_bot.py` does **not** import `app.py`.

Therefore the Telegram worker can continue operating even if the Streamlit dashboard is offline.

### Files

- `telegram_bot.py` — primary hourly Telegram market/news reporter
- `business_news.py` — Infera Business Topic integration and Telegram news formatting
- `ng_ipo_bot.py` / `ng_ipo_scanner.py` — Nigeria IPO/public-offer Telegram alerts
- `quarterly_financial_bot.py` / `financials.py` — quarterly financial Telegram alerts
- `app.py` — optional Streamlit research interface (not a reporting channel)
- `pages/2_Quarterly_Financials.py` — interactive quarter-by-quarter financial analysis
- `financials.py` — public-data financial/filing intelligence engine
- `telegram_bot.py` — independent market/news Telegram worker
- `quarterly_financial_bot.py` — automatic Telegram quarterly filing reporter
- `.github/workflows/telegram.yml` — scheduled hourly market/news Telegram report
- `.github/workflows/telegram-research-reports.yml` — scheduled IPO and quarterly financial Telegram reports
- `requirements.txt` — dependencies
- `.gitignore` — protects local secrets/data

## Quarterly financial intelligence

For supported listed companies, the system tracks, by quarter:

- revenue
- reported profit / profit after tax where the public feed exposes it
- operating cash flow
- debt
- expansion costs / capital expenditure
- refining-margin language when present in a filing
- crude-supply / supply-agreement language when present
- use of proceeds / how money raised is intended to be used when present
- filing/source URL and filing status

The dashboard deliberately distinguishes **reported quarterly profit** from **audited annual profit**. Quarterly 10-Q/interim reports are normally unaudited; annual 10-K results are marked audited when the source identifies them as such.

Missing values remain `N/A`. The system does not estimate or invent financial figures or financing uses.

### Sources

- SEC Company Facts + SEC filings — U.S. issuers where CIKs are configured
- Yahoo Finance fundamentals — quarterly machine-readable fundamentals for supported listed symbols
- Official issuer filings are surfaced as the narrative source where available through SEC

NGX issuers that do not expose machine-readable quarterly fundamentals through the configured public feeds are not fabricated; they remain candidates for a dedicated issuer-report connector.

## Secrets

### Streamlit

Add these to Streamlit Secrets:

```toml
TELEGRAM_BOT_TOKEN = "..."
TELEGRAM_CHANNEL_ID = "@yourchannel"
NGXPULSE_API_KEY = "..."
COINGECKO_DEMO_API_KEY = "..."
GNEWS_API_KEY = "..."
```

### GitHub Actions

The workflow expects these repository secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHANNEL_ID
NGXPULSE_API_KEY
COINGECKO_DEMO_API_KEY
GNEWS_API_KEY
```

Never commit tokens to GitHub.

## Test locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

For Telegram market/news:

```bash
python telegram_bot.py
```

For quarterly financial updates:

```bash
python quarterly_financial_bot.py
```

## Cloud operation

GitHub Actions sends the main market/news report to Telegram every hour. A separate Telegram-only workflow checks for Nigeria IPO/public-offer documents daily and quarterly financial filings weekly. The reporting workers write delivery state only after Telegram acknowledges successful delivery, so failed sends remain eligible for retry.

Telegram is the only reporting channel. The optional Streamlit interface is not used to deliver alerts or reports.

## Data sources

- CoinGecko — crypto
- Yahoo Finance — listed market data and supported quarterly fundamentals
- SEC — U.S. filings and Company Facts
- NGX Pulse — NGX market prices, when configured

## Paper history

The dashboard stores snapshots in:

`.market_data/paper_trades.csv`

Local filesystem persistence depends on the hosting provider. For durable cloud storage, move this later to a database or external storage.

## Scope

This project is informational/paper analysis only. It does not execute trades or recommend a risk amount.
