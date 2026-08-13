
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone

st.set_page_config(page_title="AI Paper Market Dashboard", page_icon="📊", layout="wide")

ASSETS = {
    "ZHONGJIUSDT": {"name":"ZhongJi InnoLight", "ref":"HKEX 3308", "theme":"AI optical infrastructure"},
    "HANMIUSDT": {"name":"Hanmi Semiconductor", "ref":"KRX 042700", "theme":"HBM / semiconductor equipment"},
    "SAMSUNGEMUSDT": {"name":"Samsung Electro-Mechanics", "ref":"KRX 009150", "theme":"AI components / MLCC"},
    "LGELECTRONICSUSDT": {"name":"LG Electronics", "ref":"KRX 066570", "theme":"electronics / data-center cooling"},
    "NAVERUSDT": {"name":"NAVER", "ref":"KRX 035420", "theme":"AI / cloud / internet"},
    "KODEX200USDT": {"name":"Samsung KODEX 200 ETF", "ref":"KRX 069500", "theme":"Korean large-cap index"},
}

STARTING_SCORE = {
    "ZHONGJIUSDT": 68, "HANMIUSDT": 74, "SAMSUNGEMUSDT": 72,
    "LGELECTRONICSUSDT": 63, "NAVERUSDT": 58, "KODEX200USDT": 55
}

@st.cache_data(ttl=30)
def get_klines(symbol, interval="5m", limit=200):
    url = "https://fapi.binance.com/fapi/v1/klines"
    r = requests.get(url, params={"symbol":symbol, "interval":interval, "limit":limit}, timeout=10)
    r.raise_for_status()
    data = r.json()
    cols = ["open_time","open","high","low","close","volume","close_time","quote_volume",
            "trades","taker_base","taker_quote","ignore"]
    df = pd.DataFrame(data, columns=cols)
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df

def indicators(df):
    close = df["close"]
    ret = close.pct_change()
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(20).mean().iloc[-1]
    momentum = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0
    trend = (ema_fast.iloc[-1] / ema_slow.iloc[-1] - 1) * 100
    volatility = ret.rolling(20).std().iloc[-1] * 100
    return float(rsi.iloc[-1]), float(vol_ratio), float(momentum), float(trend), float(volatility)

def signal_from_indicators(rsi, vol_ratio, momentum, trend, volatility, base):
    score = base
    score += np.clip(momentum * 2.0, -10, 10)
    score += np.clip(trend * 80, -8, 8)
    if 50 <= rsi <= 70: score += 4
    elif rsi > 75: score -= 5
    elif rsi < 30: score += 3
    if vol_ratio > 1.5 and momentum > 0: score += 4
    if volatility > 3: score -= 4
    score = int(np.clip(score, 0, 100))
    if score >= 68: sig = "Bullish"
    elif score <= 42: sig = "Bearish"
    else: sig = "Neutral"
    return sig, score

def init_state():
    if "paper_trades" not in st.session_state:
        st.session_state.paper_trades = []

init_state()

st.title("📊 AI Paper-Trading Market Dashboard")
st.caption("Educational simulation only • No real orders • Confidence is a model score, not a probability of profit.")

with st.sidebar:
    st.header("Controls")
    interval = st.selectbox("Candle interval", ["1m","5m","15m","1h"], index=1)
    refresh = st.slider("Refresh interval (seconds)", 10, 300, 30)
    st.info("Market data is read-only. The dashboard never sends trading orders.")
    if st.button("Clear paper-trade log"):
        st.session_state.paper_trades = []
        st.rerun()

rows = []
raw = {}
for symbol, meta in ASSETS.items():
    try:
        df = get_klines(symbol, interval)
        raw[symbol] = df
        rsi, vr, mom, trend, vol = indicators(df)
        sig, conf = signal_from_indicators(rsi, vr, mom, trend, vol, STARTING_SCORE[symbol])
        rows.append([symbol, meta["name"], meta["ref"], df["close"].iloc[-1], sig, conf, rsi, mom, vr, vol])
    except Exception as e:
        rows.append([symbol, meta["name"], meta["ref"], np.nan, "Unavailable", 0, np.nan, np.nan, np.nan, np.nan])

dashboard = pd.DataFrame(rows, columns=["Symbol","Asset","Reference","Price","Signal","Confidence","RSI","Momentum %","Volume ratio","Volatility %"])

st.subheader("Live signal board")
st.dataframe(
    dashboard.style.format({
        "Price":"{:.4f}", "Confidence":"{:.0f}%", "RSI":"{:.1f}",
        "Momentum %":"{:.2f}", "Volume ratio":"{:.2f}", "Volatility %":"{:.2f}"
    }),
    use_container_width=True, hide_index=True
)

selected = st.selectbox("Inspect asset", list(ASSETS.keys()))
d = raw.get(selected)

if d is not None:
    rsi, vr, mom, trend, vol = indicators(d)
    sig, conf = signal_from_indicators(rsi, vr, mom, trend, vol, STARTING_SCORE[selected])
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Signal", sig)
    c2.metric("Confidence score", f"{conf}%")
    c3.metric("RSI", f"{rsi:.1f}")
    c4.metric("Momentum", f"{mom:.2f}%")
    c5.metric("Volatility", f"{vol:.2f}%")

    st.line_chart(d.set_index("time")["close"], height=320)
    st.caption(f"Theme: {ASSETS[selected]['theme']} • Reference: {ASSETS[selected]['ref']}")

    st.subheader("Paper-trade simulator")
    st.write("This records hypothetical observations only; it does not submit orders.")
    direction = st.radio("Hypothetical direction", ["Bullish signal", "Bearish signal"], horizontal=True)
    note = st.text_input("Reason / note", placeholder="e.g. momentum + volume confirmation")
    if st.button("Record paper observation"):
        st.session_state.paper_trades.append({
            "Time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "Symbol": selected,
            "Price": float(d["close"].iloc[-1]),
            "Signal": sig,
            "Confidence": conf,
            "Observation": direction,
            "Note": note
        })
        st.success("Paper observation recorded.")

st.subheader("Paper-trade history")
if st.session_state.paper_trades:
    st.dataframe(pd.DataFrame(st.session_state.paper_trades), use_container_width=True, hide_index=True)
else:
    st.info("No paper observations recorded yet.")

st.caption("Last refresh: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
