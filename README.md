# AI Paper Market Dashboard

Educational Streamlit dashboard for six Binance-listed perpetual symbols.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

The app uses read-only public market-data endpoints and never submits orders.
Signals combine a qualitative base score with RSI, momentum, EMA trend, volume ratio and volatility.
