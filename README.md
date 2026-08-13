# AI Market Intelligence Dashboard v3

A Streamlit paper-trading research dashboard.

## Features
- Six new Binance TradFi perpetuals with automatic pre-launch fallback to their HKEX/KRX underlying
- Crypto watchlist
- US stocks
- ETFs/indexes
- Custom symbol scanner/watchlist
- RSI, momentum, EMA trend, volume ratio and volatility features
- Hypothetical Bullish / Neutral / Bearish signals
- Confidence scores
- Interactive price charts
- Paper-observation history
- Automatic accuracy scoring when current data is available
- CSV export of paper history
- No order execution

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment
Push `app.py`, `requirements.txt`, and `README.md` to GitHub and deploy the repository with Streamlit Community Cloud.

## Data
Binance public market-data endpoints are used for Binance symbols. Yahoo Finance's public chart endpoint is used for stock/ETF and pre-launch underlying data.

## Important
The confidence value is a model score, not a probability of profit. This project is for research and paper trading only.
