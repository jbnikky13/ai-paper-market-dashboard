import os, html, time
from datetime import datetime, timezone
import requests
from business_news import fetch_africa_business_news, fetch_market_news, render_telegram, render_global_telegram

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
NGX_KEY = os.getenv("NGXPULSE_API_KEY", "").strip()
CG_KEY = os.getenv("COINGECKO_DEMO_API_KEY", "").strip()
GNEWS_KEY = os.getenv("GNEWS_API_KEY", "").strip()
VERSION = "v5.7.2"
CG = "https://api.coingecko.com/api/v3"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
NGX = "https://www.ngxpulse.ng"
CRYPTO = {"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB","ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US = {"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS = {"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank","ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo","MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods","BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings","PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}

def req(url, params=None, headers=None):
    last = None
    for i in range(2):
        try:
            r = requests.get(url, params=params, headers=headers or {"User-Agent": f"AI-Market-Intelligence/{VERSION}"}, timeout=15)
            if r.ok:
                return r, None
            last = f"HTTP {r.status_code}: {(r.text or '')[:250]}"
            if r.status_code not in (408,425,429,500,502,503,504):
                break
        except Exception as e:
            last = f"Network error: {e}"
        time.sleep(1 + i)
    return None, last

def crypto():
    headers = {"User-Agent": f"AI-Market-Intelligence/{VERSION}"}
    if CG_KEY:
        headers["x-cg-demo-api-key"] = CG_KEY
    r, e = req(f"{CG}/simple/price", {"ids": ",".join(CRYPTO), "vs_currencies": "usd", "include_24hr_change": "true"}, headers)
    return (r.json() if r else {}), e

def yahoo(symbol):
    r, e = req(f"{YAHOO}/{symbol}", {"range":"1mo", "interval":"1d", "includePrePost":"false"}, {"User-Agent":"Mozilla/5.0"})
    if not r:
        return None, e
    try:
        z = r.json()["chart"]["result"][0]
        m = z.get("meta", {})
        q = z.get("indicators", {}).get("quote", [{}])[0]
        closes = [float(x) for x in q.get("close", []) if x is not None]
        price = m.get("regularMarketPrice") or (closes[-1] if closes else None)
        prev = m.get("previousClose") or (closes[-2] if len(closes) > 1 else None)
        if price is None:
            return None, "Yahoo returned no price"
        return {"price":float(price), "change":((float(price)/float(prev))-1)*100 if prev else None, "currency":m.get("currency") or "USD", "name":m.get("longName") or m.get("shortName") or symbol, "source":"Yahoo Finance"}, None
    except Exception as e:
        return None, str(e)

def ngx():
    primary = {}
    if NGX_KEY:
        r, _ = req(f"{NGX}/api/ngxdata/stocks", headers={"X-API-Key":NGX_KEY,"Content-Type":"application/json","User-Agent":f"AI-Market-Intelligence/{VERSION}"})
        if r:
            try:
                body = r.json()
                rows = body if isinstance(body, list) else (body.get("data") or body.get("stocks") or [])
                for x in rows:
                    symbol = str(x.get("symbol") or x.get("ticker") or "").upper().strip()
                    if not symbol:
                        continue
                    try: price = float(x.get("current_price")) if x.get("current_price") is not None else None
                    except: price = None
                    try: change = float(x.get("change_percent")) if x.get("change_percent") is not None else None
                    except: change = None
                    if price is not None:
                        primary[symbol] = {"price":price,"change":change,"currency":"NGN","name":NGX_ASSETS.get(symbol,symbol),"source":"NGX Pulse"}
            except Exception:
                pass
    if primary:
        return primary, "LIVE"
    fallback = {}
    for symbol, name in NGX_ASSETS.items():
        x, _ = yahoo(f"{symbol}.LG")
        if x and x.get("price") is not None:
            x["name"] = name
            x["currency"] = x.get("currency") or "NGN"
            fallback[symbol] = x
    return fallback, "FALLBACK" if fallback else "UNAVAILABLE"

def money(price, currency):
    symbols = {"USD":"$", "NGN":"₦"}
    return f"{symbols.get(currency, currency + ' ')}{price:,.2f}"

def market_lines():
    crypto_rows, stock_rows = [], []
    c, _ = crypto()
    for cid, symbol in CRYPTO.items():
        x = c.get(cid, {})
        if x.get("usd") is not None:
            crypto_rows.append({"symbol":symbol,"name":symbol,"price":x.get("usd"),"change":x.get("usd_24h_change"),"currency":"USD","source":"CoinGecko"})
    for symbol, name in US.items():
        x, _ = yahoo(symbol)
        if x:
            stock_rows.append({"symbol":symbol,"name":name,"price":x["price"],"change":x.get("change"),"currency":x.get("currency","USD"),"source":"Yahoo Finance","market":"US / ETFs"})
    n, mode = ngx()
    for symbol, name in NGX_ASSETS.items():
        x = n.get(symbol)
        if x:
            stock_rows.append({"symbol":symbol,"name":name,"price":x["price"],"change":x.get("change"),"currency":x.get("currency","NGN"),"source":x.get("source",mode),"market":"NGX"})
    lines = [f"<b>🤖 AI MARKET INTELLIGENCE {VERSION}</b>", f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>", "", "<b>₿ CRYPTOCURRENCY PRICES</b>", "<i>Latest available prices at the time of this bot update.</i>"]
    for x in crypto_rows:
        change = "N/A" if x.get("change") is None else f"{x['change']:+.2f}%"
        icon = "🟢" if (x.get("change") or 0) > 0 else ("🔴" if (x.get("change") or 0) < 0 else "🟡")
        lines.append(f"{icon} <b>{html.escape(x['name'])}</b> ({x['symbol']}) — {money(x['price'],x['currency'])} ({change}) • {x['currency']} • {x['source']}")
    lines += ["", "<b>📈 STOCK & ETF PRICES</b>", "<i>Latest available prices across US/ETFs and NGX.</i>"]
    for x in stock_rows:
        change = "N/A" if x.get("change") is None else f"{x['change']:+.2f}%"
        icon = "🟢" if (x.get("change") or 0) > 0 else ("🔴" if (x.get("change") or 0) < 0 else "🟡")
        lines.append(f"{icon} <b>{html.escape(x['name'])}</b> ({html.escape(x['symbol'])}) — {money(x['price'],x['currency'])} ({change}) • {x['market']} • {x['currency']} • {x['source']}")
    lines += ["", f"🇳🇬 <b>NGX DATA: {mode}</b>"]
    if mode == "LIVE":
        lines.append("<i>Source: NGX Pulse</i>")
    elif mode == "FALLBACK":
        lines.append("<i>NGX Pulse failed; validated Yahoo Finance quotes are being used as the fallback.</i>")
    else:
        lines.append("<i>NGX Pulse and Yahoo Finance fallback both failed; no NGX prices are fabricated.</i>")
    return lines

def build_sections():
    global_news, _ = fetch_market_news(GNEWS_KEY, limit=4)
    africa_news, _ = fetch_africa_business_news(GNEWS_KEY, limit=4)
    return market_lines(), render_global_telegram(global_news, limit=4), render_telegram(africa_news, limit=4)

def split_html(text, limit=3500):
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for line in text.split("\n"):
        candidate = line if not current else current + "\n" + line
        if len(candidate) > limit and current:
            parts.append(current)
            current = line
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts

def send(messages):
    if not TOKEN:
        return False, "TELEGRAM_BOT_TOKEN is missing."
    if not CHANNEL:
        return False, "TELEGRAM_CHANNEL_ID is missing."
    if isinstance(messages, str):
        messages = split_html(messages)
    for i, msg in enumerate(messages, 1):
        try:
            r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id":CHANNEL,"text":msg,"parse_mode":"HTML","disable_web_page_preview":False}, timeout=20)
            if not r.ok:
                return False, f"Message {i}/{len(messages)} failed: HTTP {r.status_code}: {r.text[:500]}"
        except Exception as e:
            return False, f"Message {i}/{len(messages)} failed: {e}"
    return True, f"Telegram sent successfully in {len(messages)} message(s)."

if __name__ == "__main__":
    market, global_html, africa_html = build_sections()
    sections = ["\n".join(market), global_html, africa_html]
    messages = []
    for section in sections:
        messages.extend(split_html(section, limit=3500))
    ok, result = send(messages)
    print(result)
    if not ok:
        raise SystemExit(1)
