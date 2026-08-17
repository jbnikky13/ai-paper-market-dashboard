"""
AI Market Intelligence Dashboard v4.4
Standalone Streamlit dashboard.

Telegram is optional. The dashboard and Telegram worker are independent.
No real trades are executed.
"""

import os
import html
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="AI Market Intelligence v4.4", page_icon="📊", layout="wide")

APP_VERSION = "v4.4"
DASHBOARD_URL = "https://ai-paper-market-dashboard.streamlit.app/"
DATA_DIR = Path(os.getenv("MARKET_DATA_DIR", ".market_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
PAPER_FILE = DATA_DIR / "paper_trades.csv"

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
NGXPULSE_BASE = "https://www.ngxpulse.ng"

CRYPTO = {
    "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL",
    "binancecoin": "BNB", "ripple": "XRP", "dogecoin": "DOGE",
    "chainlink": "LINK", "avalanche-2": "AVAX",
}
US_ASSETS = {
    "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom",
    "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon",
    "META": "Meta", "TSLA": "Tesla", "AAPL": "Apple",
    "QQQ": "Nasdaq-100 ETF", "SPY": "S&P 500 ETF",
}
NGX_ASSETS = {
    "DANGCEM": "Dangote Cement", "GTCO": "GTCO", "ZENITHBANK": "Zenith Bank",
    "ACCESSCORP": "Access Holdings", "UBA": "UBA", "FIRSTHOLDCO": "First HoldCo",
    "MTNN": "MTN Nigeria", "AIRTELAFRI": "Airtel Africa", "BUAFOODS": "BUA Foods",
    "BUACEMENT": "BUA Cement", "SEPLAT": "Seplat Energy", "ARADEL": "Aradel Holdings",
    "PRESCO": "Presco", "NB": "Nigerian Breweries", "FLOURMILL": "Flour Mills",
}
SIX_ASSETS = {
    "3308.HK": "ZhongJi InnoLight", "042700.KS": "Hanmi Semiconductor",
    "009150.KS": "Samsung Electro-Mechanics", "066570.KS": "LG Electronics",
    "035420.KS": "NAVER", "069500.KS": "KODEX 200 ETF",
}

def secret(name, default=""):
    try:
        value = st.secrets.get(name, None)
        if value is not None:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)

TELEGRAM_BOT_TOKEN = secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = secret("TELEGRAM_CHANNEL_ID")
NGXPULSE_API_KEY = secret("NGXPULSE_API_KEY")
COINGECKO_DEMO_API_KEY = secret("COINGECKO_DEMO_API_KEY")

def api_get(url, *, params=None, headers=None, timeout=15):
    started = time.time()
    try:
        response = requests.get(
            url, params=params,
            headers=headers or {"User-Agent": "AI-Market-Intelligence-v4.4"},
            timeout=timeout,
        )
        return response, round(time.time() - started, 2), None
    except Exception as exc:
        return None, round(time.time() - started, 2), str(exc)

@st.cache_data(ttl=300, show_spinner=False)
def get_crypto():
    headers = {"x-cg-demo-api-key": COINGECKO_DEMO_API_KEY} if COINGECKO_DEMO_API_KEY else {}
    response, elapsed, error = api_get(
        f"{COINGECKO_BASE}/simple/price",
        params={
            "ids": ",".join(CRYPTO.keys()),
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
        },
        headers=headers,
    )
    status = response.status_code if response is not None else None
    diag = {"status": status, "elapsed": elapsed, "error": error}
    if response is None:
        return {}, diag
    if not response.ok:
        diag["error"] = response.text[:500]
        return {}, diag
    return response.json(), diag

@st.cache_data(ttl=120, show_spinner=False)
def get_yahoo(symbol):
    response, elapsed, error = api_get(
        f"{YAHOO_BASE}/{symbol}",
        params={"range": "5d", "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0"},
    )
    diag = {"status": response.status_code if response is not None else None,
            "elapsed": elapsed, "error": error}
    if response is None or not response.ok:
        if response is not None:
            diag["error"] = response.text[:500]
        return None, diag
    try:
        result = response.json()["chart"]["result"]
        if not result:
            diag["error"] = "Yahoo returned no result."
            return None, diag
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        previous = meta.get("previousClose")
        quote = result[0].get("indicators", {}).get("quote", [{}])[0]
        closes = [x for x in quote.get("close", []) if x is not None]
        if price is None and closes:
            price = closes[-1]
        if previous is None and len(closes) > 1:
            previous = closes[-2]
        if price is None or previous in (None, 0):
            diag["error"] = "Price/previous close unavailable."
            return None, diag
        change = ((float(price) / float(previous)) - 1) * 100
        return {"price": float(price), "change": float(change)}, diag
    except Exception as exc:
        diag["error"] = str(exc)
        return None, diag

@st.cache_data(ttl=300, show_spinner=False)
def get_ngx(symbol):
    if not NGXPULSE_API_KEY:
        return None, {"status": None, "elapsed": 0, "error": "NGXPULSE_API_KEY is not configured."}
    response, elapsed, error = api_get(
        f"{NGXPULSE_BASE}/api/ngxdata/prices/{symbol}",
        params={"days": 5},
        headers={"X-API-Key": NGXPULSE_API_KEY, "User-Agent": "AI-Market-Intelligence-v4.4"},
    )
    diag = {"status": response.status_code if response is not None else None,
            "elapsed": elapsed, "error": error}
    if response is None or not response.ok:
        if response is not None:
            diag["error"] = response.text[:500]
        return None, diag
    try:
        data = response.json()
        history = (data.get("history") or data.get("data") or []) if isinstance(data, dict) else data
        df = pd.DataFrame(history)
        if df.empty:
            diag["error"] = "NGX returned no rows."
            return None, diag
        col = next((c for c in ["close", "current_price", "price", "close_price"] if c in df.columns), None)
        if col is None:
            diag["error"] = "No recognised price column in NGX response."
            return None, diag
        prices = pd.to_numeric(df[col], errors="coerce").dropna()
        if prices.empty:
            diag["error"] = "No numeric NGX prices."
            return None, diag
        current = float(prices.iloc[-1])
        previous = float(prices.iloc[-2]) if len(prices) > 1 else current
        change = ((current / previous) - 1) * 100 if previous else 0
        return {"price": current, "change": change}, diag
    except Exception as exc:
        diag["error"] = str(exc)
        return None, diag

def signal_from_change(change):
    if change is None or pd.isna(change):
        return "NO DATA", 0
    change = float(change)
    if change >= 2:
        return "BULLISH", min(95, round(55 + abs(change) * 5))
    if change <= -2:
        return "BEARISH", min(95, round(55 + abs(change) * 5))
    return "NEUTRAL", max(50, min(75, round(60 + abs(change) * 2)))

def movement_icon(change):
    if change is None or pd.isna(change): return "⚪"
    if change > 1: return "🟢"
    if change < -1: return "🔴"
    return "🟡"

def fmt_price(price, currency="$"):
    if price is None or pd.isna(price): return "N/A"
    if currency == "₦": return f"₦{price:,.2f}"
    if price < 1: return f"${price:.6f}"
    return f"${price:,.2f}"

def load_paper_history():
    columns = ["timestamp", "asset", "source", "price", "change_pct", "signal", "confidence", "status"]
    if not PAPER_FILE.exists():
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(PAPER_FILE)
        for c in columns:
            if c not in df.columns: df[c] = ""
        return df[columns]
    except Exception:
        return pd.DataFrame(columns=columns)

def save_paper_history(df):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(PAPER_FILE, index=False)

def record_snapshot(rows):
    if not rows: return
    combined = pd.concat([load_paper_history(), pd.DataFrame(rows)], ignore_index=True)
    save_paper_history(combined.tail(5000))

def send_telegram_message(message, silent=False):
    if not TELEGRAM_BOT_TOKEN: return False, "TELEGRAM_BOT_TOKEN is not configured."
    if not TELEGRAM_CHANNEL_ID: return False, "TELEGRAM_CHANNEL_ID is not configured."
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(endpoint, json={
            "chat_id": TELEGRAM_CHANNEL_ID, "text": message,
            "parse_mode": "HTML", "disable_web_page_preview": False,
            "disable_notification": silent,
        }, timeout=15)
        if response.ok: return True, "Telegram message sent."
        return False, f"HTTP {response.status_code}: {response.text[:500]}"
    except Exception as exc:
        return False, str(exc)

def build_dashboard_rows():
    rows, diagnostics = [], []
    crypto, diag = get_crypto()
    diagnostics.append(("CoinGecko", diag))
    for coin_id, ticker in CRYPTO.items():
        item = crypto.get(coin_id, {})
        price, change = item.get("usd"), item.get("usd_24h_change")
        signal, confidence = signal_from_change(change)
        rows.append({"asset": ticker, "name": ticker, "source": "CoinGecko",
                     "price": price, "change_pct": change, "signal": signal,
                     "confidence": confidence, "currency": "$",
                     "status": "OK" if price is not None else "NO DATA"})
    for symbol, name in US_ASSETS.items():
        data, diag = get_yahoo(symbol)
        diagnostics.append((f"Yahoo:{symbol}", diag))
        price, change = (data["price"], data["change"]) if data else (None, None)
        signal, confidence = signal_from_change(change)
        rows.append({"asset": symbol, "name": name, "source": "Yahoo Finance",
                     "price": price, "change_pct": change, "signal": signal,
                     "confidence": confidence, "currency": "$",
                     "status": "OK" if price is not None else "NO DATA"})
    for symbol, name in NGX_ASSETS.items():
        data, diag = get_ngx(symbol)
        diagnostics.append((f"NGX:{symbol}", diag))
        price, change = (data["price"], data["change"]) if data else (None, None)
        signal, confidence = signal_from_change(change)
        rows.append({"asset": symbol, "name": name, "source": "NGX Pulse",
                     "price": price, "change_pct": change, "signal": signal,
                     "confidence": confidence, "currency": "₦",
                     "status": "OK" if price is not None else "NO DATA"})
    for symbol, name in SIX_ASSETS.items():
        data, diag = get_yahoo(symbol)
        diagnostics.append((f"Yahoo:{symbol}", diag))
        price, change = (data["price"], data["change"]) if data else (None, None)
        signal, confidence = signal_from_change(change)
        rows.append({"asset": symbol, "name": name, "source": "Yahoo Finance",
                     "price": price, "change_pct": change, "signal": signal,
                     "confidence": confidence, "currency": "$",
                     "status": "OK" if price is not None else "NO DATA"})
    return rows, diagnostics

def telegram_report(rows):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"<b>🤖 AI MARKET INTELLIGENCE {APP_VERSION}</b>", f"<i>{now}</i>", ""]
    groups = [
        ("₿ CRYPTO", [r for r in rows if r["source"] == "CoinGecko"]),
        ("🇺🇸 US / ETF", [r for r in rows if r["source"] == "Yahoo Finance" and r["asset"] in US_ASSETS]),
        ("🇳🇬 NGX", [r for r in rows if r["source"] == "NGX Pulse"]),
        ("🌏 SIX TRACKED ASSETS", [r for r in rows if r["asset"] in SIX_ASSETS]),
    ]
    for title, group in groups:
        lines.append(f"<b>{title}</b>")
        for r in group:
            if r["change_pct"] is None or pd.isna(r["change_pct"]):
                lines.append(f"⚪ <b>{html.escape(r['asset'])}</b> — no data")
            else:
                lines.append(
                    f"{movement_icon(r['change_pct'])} <b>{html.escape(r['asset'])}</b> "
                    f"{fmt_price(r['price'], r['currency'])} "
                    f"({r['change_pct']:+.2f}%) • {r['signal']} {r['confidence']}%"
                )
        lines.append("")
    lines += ["━━━━━━━━━━━━━━━━",
              "ℹ️ Hypothetical paper-analysis signals only. No trades are executed.",
              f'🌐 <a href="{DASHBOARD_URL}">Open dashboard</a>']
    return "
".join(lines)

st.title("📊 AI Market Intelligence")
st.caption(f"{APP_VERSION} • informational / paper-trading dashboard")

with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Refresh market data"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.subheader("📣 Telegram")
    st.success("Configured") if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID else st.warning("Not configured")
    if st.button("📨 Send Telegram test"):
        ok, result = send_telegram_message(
            f"<b>🤖 AI Market Intelligence</b>

Telegram connection test successful.
"
            f'<a href="{DASHBOARD_URL}">Open dashboard</a>'
        )
        (st.success if ok else st.error)(result)
    st.divider()
    st.subheader("💾 Paper history")
    st.caption(str(PAPER_FILE))
    st.write(f"Records: {len(load_paper_history())}")
    if st.button("🗑️ Clear local paper history"):
        if PAPER_FILE.exists(): PAPER_FILE.unlink()
        st.rerun()

rows, diagnostics = build_dashboard_rows()
timestamp = datetime.now(timezone.utc).isoformat()
record_snapshot([{
    "timestamp": timestamp, "asset": r["asset"], "source": r["source"],
    "price": r["price"], "change_pct": r["change_pct"], "signal": r["signal"],
    "confidence": r["confidence"], "status": r["status"],
} for r in rows])
df = pd.DataFrame(rows)

tabs = st.tabs(["📈 Market Signals", "₿ Crypto", "🇺🇸 US / ETFs", "🇳🇬 NGX",
                "🌏 Six Assets", "🧪 API Diagnostics", "📝 Paper History"])

with tabs[0]:
    st.info("Signals/confidence are hypothetical paper-analysis outputs. They do not execute trades or determine how much money to risk.")
    view = df.copy()
    view["price"] = view.apply(lambda r: fmt_price(r["price"], r["currency"]), axis=1)
    view["change_pct"] = view["change_pct"].map(lambda x: "N/A" if pd.isna(x) else f"{x:+.2f}%")
    view["confidence"] = view["confidence"].map(lambda x: f"{x}%")
    st.dataframe(view[["asset","name","source","price","change_pct","signal","confidence","status"]],
                 use_container_width=True, hide_index=True)

with tabs[1]:
    st.dataframe(df[df.source == "CoinGecko"][["asset","price","change_pct","signal","confidence","status"]],
                 use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(df[(df.source == "Yahoo Finance") & (df.asset.isin(US_ASSETS))][
        ["asset","name","price","change_pct","signal","confidence","status"]],
        use_container_width=True, hide_index=True)
with tabs[3]:
    if not NGXPULSE_API_KEY: st.warning("Add NGXPULSE_API_KEY to Streamlit Secrets to enable NGX data.")
    st.dataframe(df[df.source == "NGX Pulse"][["asset","name","price","change_pct","signal","confidence","status"]],
                 use_container_width=True, hide_index=True)
with tabs[4]:
    st.dataframe(df[df.asset.isin(SIX_ASSETS)][["asset","name","price","change_pct","signal","confidence","status"]],
                 use_container_width=True, hide_index=True)
with tabs[5]:
    diag_rows = [{"source": s, "HTTP status": d.get("status"), "request time (s)": d.get("elapsed"),
                  "status": "OK" if not d.get("error") else "FAILED",
                  "reason": d.get("error") or "Request successful"} for s, d in diagnostics]
    st.dataframe(pd.DataFrame(diag_rows), use_container_width=True, hide_index=True)
with tabs[6]:
    history = load_paper_history()
    if history.empty: st.info("No paper-trade snapshots recorded yet.")
    else:
        st.dataframe(history.tail(500), use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download paper history CSV", history.to_csv(index=False),
                           file_name="paper_trade_history.csv", mime="text/csv")
