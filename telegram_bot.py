import os, html, time
from datetime import datetime, timezone
import requests
from business_news import fetch_africa_business_news, fetch_market_news, render_telegram, render_global_telegram

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
CHANNEL=os.getenv("TELEGRAM_CHANNEL_ID","").strip()
INVESTO_KEY=os.getenv("INVESTO_API_KEY","").strip()
NGX_KEY=os.getenv("NGXPULSE_API_KEY","").strip()
CG_KEY=os.getenv("COINGECKO_DEMO_API_KEY","").strip()
GNEWS_KEY=os.getenv("GNEWS_API_KEY","").strip()
VERSION="v6.0.0"
CG="https://api.coingecko.com/api/v3"; YAHOO="https://query1.finance.yahoo.com/v8/finance/chart"; INVESTO="https://investo.ng/api/v1"
CRYPTO={"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB","ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US={"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS={"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank","ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo","MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods","BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings","PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}

def req(url,params=None,headers=None,timeout=15):
    last=None
    for i in range(2):
        try:
            r=requests.get(url,params=params,headers=headers or {"User-Agent":f"AI-Market-Intelligence/{VERSION}"},timeout=timeout)
            if r.ok:return r,None
            last=f"HTTP {r.status_code}: {(r.text or '')[:250]}"
            if r.status_code not in (408,425,429,500,502,503,504):break
        except Exception as e:last=f"Network error: {e}"
        time.sleep(1+i)
    return None,last

def crypto():
    h={"User-Agent":f"AI-Market-Intelligence/{VERSION}"}
    if CG_KEY:h["x-cg-demo-api-key"]=CG_KEY
    r,e=req(f"{CG}/simple/price",{"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"},h)
    try:return (r.json() if r else {}),e
    except Exception as x:return {},str(x)

def yahoo(symbol):
    r,e=req(f"{YAHOO}/{symbol}",{"range":"1mo","interval":"1d","includePrePost":"false"},{"User-Agent":"Mozilla/5.0"})
    if not r:return None,e
    try:
        z=r.json()["chart"]["result"][0];m=z.get("meta",{});q=z.get("indicators",{}).get("quote",[{}])[0];closes=[float(x) for x in q.get("close",[]) if x is not None]
        price=m.get("regularMarketPrice") or (closes[-1] if closes else None);prev=m.get("previousClose") or (closes[-2] if len(closes)>1 else None)
        if price is None:return None,"Yahoo returned no price"
        return {"price":float(price),"change":((float(price)/float(prev))-1)*100 if prev else None,"currency":m.get("currency") or "USD","name":m.get("longName") or m.get("shortName") or symbol,"source":"Yahoo Finance"},None
    except Exception as e:return None,str(e)

def investo():
    if not INVESTO_KEY:return {},"NO_KEY"
    r,e=req(f"{INVESTO}/stocks",headers={"Authorization":f"Bearer {INVESTO_KEY}","User-Agent":f"AI-Market-Intelligence/{VERSION}"},timeout=20)
    if not r:return {},"ERROR"
    try:
        rows=r.json().get("data",[]);out={}
        for x in rows:
            s=str(x.get("symbol") or "").upper().strip()
            if s in NGX_ASSETS and x.get("price") is not None:out[s]={"price":float(x["price"]),"change":float(x["change_percent"]) if x.get("change_percent") is not None else None,"currency":"NGN","name":x.get("name") or NGX_ASSETS[s],"source":"Investo"}
        return out,"LIVE" if out else "EMPTY"
    except Exception:return {},"ERROR"

def ngx():
    out,mode=investo()
    if out:return out,"LIVE","Investo"
    fallback={}
    if NGX_KEY:
        r,_=req("https://www.ngxpulse.ng/api/ngxdata/stocks",headers={"X-API-Key":NGX_KEY,"User-Agent":f"AI-Market-Intelligence/{VERSION}"})
        if r:
            try:
                body=r.json();rows=body if isinstance(body,list) else (body.get("data") or body.get("stocks") or [])
                for x in rows:
                    s=str(x.get("symbol") or x.get("ticker") or "").upper().strip()
                    if s in NGX_ASSETS and x.get("current_price") is not None:fallback[s]={"price":float(x["current_price"]),"change":float(x["change_percent"]) if x.get("change_percent") is not None else None,"currency":"NGN","name":NGX_ASSETS[s],"source":"Kobo/NGX Pulse"}
            except Exception:pass
    if fallback:return fallback,"FALLBACK","Kobo/NGX Pulse"
    yf={}
    for s,n in NGX_ASSETS.items():
        x,_=yahoo(f"{s}.LG")
        if x and x.get("price") is not None:x["name"]=n;x["currency"]="NGN";x["source"]="Yahoo Finance fallback";yf[s]=x
    return yf,"YAHOO_FALLBACK" if yf else "UNAVAILABLE","Yahoo Finance" if yf else "None"

def money(price,currency):return f"{{'USD':'$','NGN':'₦'}.get(currency,currency+' ')}{price:,.2f}"

def market_lines():
    cr=[];stocks=[];c,_=crypto()
    for cid,s in CRYPTO.items():
        x=c.get(cid,{})
        if x.get("usd") is not None:cr.append((s,x["usd"],x.get("usd_24h_change"),"USD","CoinGecko"))
    for s,n in US.items():
        x,_=yahoo(s)
        if x:stocks.append((s,n,x["price"],x.get("change"),x.get("currency","USD"),"Yahoo Finance","US / ETFs"))
    ngxdata,mode,source=ngx()
    for s,n in NGX_ASSETS.items():
        x=ngxdata.get(s)
        if x:stocks.append((s,n,x["price"],x.get("change"),"NGN",x.get("source",source),"NGX"))
    lines=[f"<b>🤖 AI MARKET INTELLIGENCE {VERSION}</b>",f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>","","<b>₿ CRYPTOCURRENCY PRICES</b>"]
    for s,p,ch,cur,src in cr:
        chs="N/A" if ch is None else f"{ch:+.2f}%";icon="🟢" if (ch or 0)>0 else ("🔴" if (ch or 0)<0 else "🟡");lines.append(f"{icon} <b>{s}</b> — {money(p,cur)} ({chs}) • {src}")
    lines += ["","<b>📈 STOCK & ETF PRICES</b>"]
    for s,n,p,ch,cur,src,mkt in stocks:
        chs="N/A" if ch is None else f"{ch:+.2f}%";icon="🟢" if (ch or 0)>0 else ("🔴" if (ch or 0)<0 else "🟡");lines.append(f"{icon} <b>{html.escape(n)}</b> ({s}) — {money(p,cur)} ({chs}) • {mkt} • {src}")
    lines += ["",f"🇳🇬 <b>NGX DATA: {mode}</b>","<i>Primary: Investo API • fallback: Kobo/NGX Pulse → Yahoo Finance</i>"]
    if mode=="UNAVAILABLE":lines.append("<i>NGX data unavailable; no prices are fabricated.</i>")
    return lines

def split_html(text,limit=3500):
    if len(text)<=limit:return [text]
    parts=[];cur=""
    for line in text.split("\n"):
        nxt=line if not cur else cur+"\n"+line
        if len(nxt)>limit and cur:parts.append(cur);cur=line
        else:cur=nxt
    if cur:parts.append(cur)
    return parts

def send(messages):
    if not TOKEN:return False,"TELEGRAM_BOT_TOKEN is missing."
    if not CHANNEL:return False,"TELEGRAM_CHANNEL_ID is missing."
    for i,msg in enumerate(messages,1):
        try:
            r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",json={"chat_id":CHANNEL,"text":msg,"parse_mode":"HTML","disable_web_page_preview":False},timeout=20)
            if not r.ok:return False,f"Message {i}/{len(messages)} failed: HTTP {r.status_code}: {r.text[:500]}"
        except Exception as e:return False,f"Message {i}/{len(messages)} failed: {e}"
    return True,f"Telegram sent successfully in {len(messages)} message(s)."

if __name__=="__main__":
    market=market_lines();global_news,_=fetch_market_news(GNEWS_KEY,4);africa_news,_=fetch_africa_business_news(GNEWS_KEY,4);messages=[]
    for section in ["\n".join(market),render_global_telegram(global_news,4),render_telegram(africa_news,4)]:messages.extend(split_html(section))
    ok,result=send(messages);print(result)
    if not ok:raise SystemExit(1)
