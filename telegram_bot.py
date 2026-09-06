import os, html, time
from datetime import datetime, timezone
import requests
from business_news import fetch_africa_business_news, fetch_market_news, render_telegram, render_global_telegram

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
CHANNEL=os.getenv("TELEGRAM_CHANNEL_ID","").strip()
NGX_KEY=os.getenv("NGXPULSE_API_KEY","").strip()
CG_KEY=os.getenv("COINGECKO_DEMO_API_KEY","").strip()
GNEWS_KEY=os.getenv("GNEWS_API_KEY","").strip()
VERSION="v5.5"
CG="https://api.coingecko.com/api/v3"; YAHOO="https://query1.finance.yahoo.com/v8/finance/chart"; NGX="https://www.ngxpulse.ng"
CRYPTO={"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB","ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US={"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS={"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank","ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo","MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods","BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings","PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}

def req(url,params=None,headers=None):
    last=None
    for i in range(2):
        try:
            r=requests.get(url,params=params,headers=headers or {"User-Agent":"AI-Market-Intelligence/5.5"},timeout=15)
            if r.ok:return r,None
            last=f"HTTP {r.status_code}: {(r.text or '')[:250]}"
            if r.status_code not in (408,425,429,500,502,503,504):break
        except Exception as e:last=f"Network error: {e}"
        time.sleep(1+i)
    return None,last

def crypto():
    h={"User-Agent":"AI-Market-Intelligence/5.5"}
    if CG_KEY:h["x-cg-demo-api-key"]=CG_KEY
    r,e=req(f"{CG}/simple/price",{"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"},h)
    return (r.json() if r else {}),e

def yahoo(symbol):
    r,e=req(f"{YAHOO}/{symbol}",{"range":"1mo","interval":"1d","includePrePost":"false"},{"User-Agent":"Mozilla/5.0"})
    if not r:return None,e
    try:
        z=r.json()["chart"]["result"][0]; m=z.get("meta",{}); q=z.get("indicators",{}).get("quote",[{}])[0]
        cl=[float(x) for x in q.get("close",[]) if x is not None]
        p=m.get("regularMarketPrice") or (cl[-1] if cl else None)
        prev=m.get("previousClose") or (cl[-2] if len(cl)>1 else None)
        if p is None:return None,"Yahoo returned no price"
        return {"price":float(p),"change":((float(p)/float(prev))-1)*100 if prev else None,"currency":m.get("currency") or "USD","name":m.get("longName") or m.get("shortName") or symbol,"source":"Yahoo Finance"},None
    except Exception as x:return None,str(x)

def ngx():
    primary={}
    if NGX_KEY:
        r,e=req(f"{NGX}/api/ngxdata/stocks",headers={"X-API-Key":NGX_KEY,"Content-Type":"application/json","User-Agent":"AI-Market-Intelligence/5.5"})
        if r:
            try:
                body=r.json(); rows=body if isinstance(body,list) else (body.get("data") or body.get("stocks") or [])
                for x in rows:
                    s=str(x.get("symbol") or x.get("ticker") or "").upper().strip()
                    if not s:continue
                    try:p=float(x.get("current_price")) if x.get("current_price") is not None else None
                    except:p=None
                    try:ch=float(x.get("change_percent")) if x.get("change_percent") is not None else None
                    except:ch=None
                    if p is not None:primary[s]={"price":p,"change":ch,"currency":"NGN","name":NGX_ASSETS.get(s,s),"source":"NGX Pulse","status":"LIVE"}
            except Exception:pass
    if primary:return primary,"LIVE"
    fallback={}
    for s,name in NGX_ASSETS.items():
        x,_=yahoo(f"{s}.LG")
        if x and x.get("price") is not None:
            x["name"]=name;x["currency"]=x.get("currency") or "NGN";x["status"]="FALLBACK";fallback[s]=x
    return fallback,"FALLBACK" if fallback else "UNAVAILABLE"

def money(price,currency):
    symbols={"USD":"$","NGN":"₦"}
    return f"{symbols.get(currency,currency+' ')}{price:,.2f}"

def market_lines():
    crypto_rows=[]; stock_rows=[]
    c,_=crypto()
    for cid,s in CRYPTO.items():
        x=c.get(cid,{})
        if x.get("usd") is not None:crypto_rows.append({"symbol":s,"name":s,"price":x.get("usd"),"change":x.get("usd_24h_change"),"currency":"USD","source":"CoinGecko"})
    for s,n in US.items():
        x,_=yahoo(s)
        if x:stock_rows.append({"symbol":s,"name":n or x.get("name",s),"price":x["price"],"change":x.get("change"),"currency":x.get("currency","USD"),"source":x.get("source","Yahoo Finance"),"market":"US / ETFs"})
    n,mode=ngx()
    for s,name in NGX_ASSETS.items():
        x=n.get(s)
        if x:stock_rows.append({"symbol":s,"name":name,"price":x["price"],"change":x.get("change"),"currency":x.get("currency","NGN"),"source":x.get("source",mode),"market":"NGX"})
    lines=[f"<b>🤖 AI MARKET INTELLIGENCE {VERSION}</b>",f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>","","<b>₿ CRYPTOCURRENCY PRICES</b>","<i>Latest available prices at the time of this bot update.</i>"]
    for x in crypto_rows:
        change="N/A" if x.get("change") is None else f"{x['change']:+.2f}%"; icon="🟢" if (x.get("change") or 0)>0 else ("🔴" if (x.get("change") or 0)<0 else "🟡")
        lines.append(f"{icon} <b>{html.escape(x['name'])}</b> ({x['symbol']}) — {money(x['price'],x['currency'])} ({change}) • {x['currency']} • {x['source']}")
    lines += ["","<b>📈 STOCK & ETF PRICES</b>","<i>Latest available prices across US/ETFs and NGX.</i>"]
    for x in stock_rows:
        change="N/A" if x.get("change") is None else f"{x['change']:+.2f}%"; icon="🟢" if (x.get("change") or 0)>0 else ("🔴" if (x.get("change") or 0)<0 else "🟡")
        lines.append(f"{icon} <b>{html.escape(x['name'])}</b> ({html.escape(x['symbol'])}) — {money(x['price'],x['currency'])} ({change}) • {x['market']} • {x['currency']} • {x['source']}")
    lines += ["",f"🇳🇬 <b>NGX DATA: {mode}</b>"]
    if mode=="LIVE":lines.append("<i>Source: NGX Pulse</i>")
    elif mode=="FALLBACK":lines.append("<i>NGX Pulse failed; validated Yahoo Finance quotes are being used as the fallback.</i>")
    else:lines.append("<i>NGX Pulse and Yahoo Finance fallback both failed; no NGX prices are fabricated.</i>")
    return lines

def build_sections():
    global_news,global_provider=fetch_market_news(GNEWS_KEY,limit=8)
    africa_news,africa_provider=fetch_africa_business_news(GNEWS_KEY,limit=8)
    return market_lines(),render_global_telegram(global_news,limit=8),render_telegram(africa_news,limit=8),global_provider,africa_provider

def split_html(text,limit=3500):
    if len(text)<=limit:return [text]
    parts=[]; cur=""
    for line in text.split("\n"):
        candidate=line if not cur else cur+"\n"+line
        if len(candidate)>limit and cur:
            parts.append(cur);cur=line
        else:cur=candidate
    if cur:parts.append(cur)
    return parts

def send(messages):
    if not TOKEN:return False,"TELEGRAM_BOT_TOKEN is missing."
    if not CHANNEL:return False,"TELEGRAM_CHANNEL_ID is missing."
    if isinstance(messages,str):messages=split_html(messages)
    for i,msg in enumerate(messages,1):
        try:
            r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",json={"chat_id":CHANNEL,"text":msg,"parse_mode":"HTML","disable_web_page_preview":False},timeout=20)
            if not r.ok:return False,f"Message {i}/{len(messages)} failed: HTTP {r.status_code}: {r.text[:500]}"
        except Exception as e:return False,f"Message {i}/{len(messages)} failed: {e}"
    return True,f"Telegram sent successfully in {len(messages)} message(s)."

if __name__=="__main__":
    market,global_html,africa_html,gp,ap=build_sections()
    header="\n".join(market)
    footer=f"<i>Global news provider: {html.escape(gp)} | Africa news provider: {html.escape(ap)}</i>\n\nℹ️ Hypothetical paper-analysis only. No trades are executed."
    sections=[header,global_html,africa_html,footer]
    messages=[]
    for section in sections:messages.extend(split_html(section,limit=3500))
    ok,result=send(messages);print(result)
    if not ok:raise SystemExit(1)
