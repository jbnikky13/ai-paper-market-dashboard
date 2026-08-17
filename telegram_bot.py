"""
AI Market Intelligence v4.4 - Independent Telegram Worker

This file intentionally does NOT import app.py.
It can run when the Streamlit dashboard is offline.
It fetches its own market data and posts informational updates.
It does not execute trades.
"""

import os
import html
import time
from datetime import datetime, timezone
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
NGXPULSE_API_KEY = os.getenv("NGXPULSE_API_KEY", "")
COINGECKO_DEMO_API_KEY = os.getenv("COINGECKO_DEMO_API_KEY", "")
DASHBOARD_URL = "https://ai-paper-market-dashboard.streamlit.app/"

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
NGXPULSE_BASE = "https://www.ngxpulse.ng"

CRYPTO = {"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB",
          "ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US_ASSETS = {"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft",
             "GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla",
             "AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS = {"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank",
              "ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo",
              "MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods",
              "BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings",
              "PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}
SIX_ASSETS = {"3308.HK":"ZhongJi InnoLight","042700.KS":"Hanmi Semiconductor",
              "009150.KS":"Samsung Electro-Mechanics","066570.KS":"LG Electronics",
              "035420.KS":"NAVER","069500.KS":"KODEX 200 ETF"}

def request_json(url, *, params=None, headers=None, retries=3):
    last_error = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers or {"User-Agent":"AI-Market-Intelligence-v4.4"}, timeout=20)
            if r.ok: return r.json(), {"status":r.status_code,"error":None}
            last_error = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code not in (408,425,429,500,502,503,504): break
        except Exception as exc: last_error = str(exc)
        time.sleep(2 ** attempt)
    return None, {"status":None,"error":last_error}

def signal_from_change(change):
    if change is None: return "NO DATA", 0
    change = float(change)
    if change >= 2: return "BULLISH", min(95, round(55 + abs(change)*5))
    if change <= -2: return "BEARISH", min(95, round(55 + abs(change)*5))
    return "NEUTRAL", max(50, min(75, round(60 + abs(change)*2)))

def icon(change):
    if change is None: return "⚪"
    if change > 1: return "🟢"
    if change < -1: return "🔴"
    return "🟡"

def price_text(price, currency="$"):
    if price is None: return "N/A"
    if currency == "₦": return f"₦{price:,.2f}"
    if price < 1: return f"${price:.6f}"
    return f"${price:,.2f}"

def get_crypto():
    headers = {"x-cg-demo-api-key":COINGECKO_DEMO_API_KEY} if COINGECKO_DEMO_API_KEY else {}
    return request_json(f"{COINGECKO_BASE}/simple/price",
        params={"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"},
        headers=headers)

def get_yahoo(symbol):
    data, diag = request_json(f"{YAHOO_BASE}/{symbol}",
        params={"range":"5d","interval":"1d"}, headers={"User-Agent":"Mozilla/5.0"})
    if not data: return None, diag
    try:
        result = data["chart"]["result"]
        meta = result[0].get("meta", {})
        price, previous = meta.get("regularMarketPrice"), meta.get("previousClose")
        closes = [x for x in result[0].get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
        if price is None and closes: price = closes[-1]
        if previous is None and len(closes)>1: previous = closes[-2]
        if price is None or previous in (None,0): return None, {"status":diag["status"],"error":"Price unavailable."}
        return {"price":float(price),"change":((float(price)/float(previous))-1)*100}, diag
    except Exception as exc:
        return None, {"status":diag["status"],"error":str(exc)}

def get_ngx(symbol):
    if not NGXPULSE_API_KEY: return None, {"status":None,"error":"NGXPULSE_API_KEY is not configured."}
    data, diag = request_json(f"{NGXPULSE_BASE}/api/ngxdata/prices/{symbol}",
        params={"days":5}, headers={"X-API-Key":NGXPULSE_API_KEY,"User-Agent":"AI-Market-Intelligence-v4.4"})
    if not data: return None, diag
    try:
        history = (data.get("history") or data.get("data") or []) if isinstance(data,dict) else data
        prices = []
        for row in history:
            if not isinstance(row,dict): continue
            for key in ("close","current_price","price","close_price"):
                if row.get(key) is not None:
                    try: prices.append(float(row[key]))
                    except (TypeError,ValueError): pass
                    break
        if not prices: return None, {"status":diag["status"],"error":"No numeric NGX prices."}
        current, previous = prices[-1], prices[-2] if len(prices)>1 else prices[-1]
        return {"price":current,"change":((current/previous)-1)*100 if previous else 0}, diag
    except Exception as exc:
        return None, {"status":diag["status"],"error":str(exc)}

def telegram_send(message):
    if not TELEGRAM_BOT_TOKEN: return False, "TELEGRAM_BOT_TOKEN is missing."
    if not TELEGRAM_CHANNEL_ID: return False, "TELEGRAM_CHANNEL_ID is missing."
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHANNEL_ID,"text":message,"parse_mode":"HTML",
                  "disable_web_page_preview":False}, timeout=20)
        if r.ok: return True, "Telegram message sent."
        return False, f"HTTP {r.status_code}: {r.text[:500]}"
    except Exception as exc: return False, str(exc)

def add_line(lines, symbol, data, currency="$"):
    if not data:
        lines.append(f"⚪ <b>{html.escape(symbol)}</b> — unavailable")
        return
    change = data["change"]
    signal, confidence = signal_from_change(change)
    lines.append(f"{icon(change)} <b>{html.escape(symbol)}</b> {price_text(data['price'],currency)} "
                 f"({change:+.2f}%) • {signal} {confidence}%")

def build_report():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"<b>🤖 AI MARKET INTELLIGENCE v4.4</b>",f"<i>{now}</i>",""]

    lines.append("<b>₿ CRYPTO</b>")
    crypto, diag = get_crypto()
    if crypto:
        for coin_id,ticker in CRYPTO.items():
            item=crypto.get(coin_id,{})
            add_line(lines,ticker,{"price":item.get("usd"),"change":item.get("usd_24h_change")} if item.get("usd") is not None else None)
    else:
        lines.append(f"⚠️ CoinGecko unavailable: {html.escape(str(diag.get('error')))}")

    lines.append(""); lines.append("<b>🇺🇸 US / ETFs</b>")
    for symbol in US_ASSETS:
        data,_=get_yahoo(symbol); add_line(lines,symbol,data)

    lines.append(""); lines.append("<b>🇳🇬 NGX</b>")
    if not NGXPULSE_API_KEY: lines.append("⚠️ NGX Pulse API key not configured.")
    else:
        for symbol in NGX_ASSETS:
            data,_=get_ngx(symbol); add_line(lines,symbol,data,"₦")

    lines.append(""); lines.append("<b>🌏 SIX TRACKED ASSETS</b>")
    for symbol,name in SIX_ASSETS.items():
        data,_=get_yahoo(symbol); add_line(lines,name,data)

    lines += ["","━━━━━━━━━━━━━━━━","ℹ️ Hypothetical paper-analysis signals only. No trades are executed.",
              f'🌐 <a href="{DASHBOARD_URL}">Open dashboard</a>']
    return "\n".join(lines)

def main():
    report=build_report()
    print(report)
    ok,result=telegram_send(report)
    print(result)
    if not ok: raise SystemExit(1)

if __name__=="__main__":
    main()
