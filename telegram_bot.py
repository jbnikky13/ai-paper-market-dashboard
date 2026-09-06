import os, html, time
from datetime import datetime, timezone
import requests
from business_news import fetch_africa_business_news, render_telegram

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
CHANNEL=os.getenv("TELEGRAM_CHANNEL_ID","").strip()
NGX_KEY=os.getenv("NGXPULSE_API_KEY","").strip()
CG_KEY=os.getenv("COINGECKO_DEMO_API_KEY","").strip()
GNEWS_KEY=os.getenv("GNEWS_API_KEY","").strip()
VERSION="v5.0"
CG="https://api.coingecko.com/api/v3"; YAHOO="https://query1.finance.yahoo.com/v8/finance/chart"; NGX="https://www.ngxpulse.ng"
CRYPTO={"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB","ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US={"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS={"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank","ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo","MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods","BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings","PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}
SIX={"3308.HK":"ZhongJi InnoLight","042700.KS":"Hanmi Semiconductor","009150.KS":"Samsung Electro-Mechanics","066570.KS":"LG Electronics","035420.KS":"NAVER","069500.KS":"KODEX 200 ETF"}


def req(url,params=None,headers=None):
    last=None
    for i in range(2):
        try:
            r=requests.get(url,params=params,headers=headers or {"User-Agent":"AI-Market-Intelligence/5.0"},timeout=15)
            if r.ok:return r,None
            last=f"HTTP {r.status_code}: {(r.text or '')[:250]}"
            if r.status_code not in (408,425,429,500,502,503,504):break
        except Exception as e:last=f"Network error: {e}"
        time.sleep(1+i)
    return None,last


def outlook(change):
    if change is None:return "NO DATA",0
    c=float(change)
    if c>=2:return "BULLISH",min(95,round(55+abs(c)*5))
    if c<=-2:return "BEARISH",min(95,round(55+abs(c)*5))
    return "NEUTRAL",max(50,min(75,round(60+abs(c)*2)))


def crypto():
    h={"User-Agent":"AI-Market-Intelligence/5.0"}
    if CG_KEY:h["x-cg-demo-api-key"]=CG_KEY
    r,e=req(f"{CG}/simple/price",{"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"},h)
    return (r.json() if r else {}),e


def yahoo(symbol):
    r,e=req(f"{YAHOO}/{symbol}",{"range":"1mo","interval":"1d"},{"User-Agent":"Mozilla/5.0"})
    if not r:return None,e
    try:
        z=r.json()["chart"]["result"][0];m=z.get("meta",{});cl=[float(x) for x in z.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
        p=m.get("regularMarketPrice") or (cl[-1] if cl else None); prev=m.get("previousClose") or (cl[-2] if len(cl)>1 else None)
        return ({"price":float(p),"change":((float(p)/float(prev))-1)*100 if prev else None} if p is not None else None),None
    except Exception as x:return None,str(x)


def ngx():
    primary={}
    if NGX_KEY:
        r,e=req(f"{NGX}/api/ngxdata/stocks",headers={"X-API-Key":NGX_KEY,"Content-Type":"application/json","User-Agent":"AI-Market-Intelligence/5.0"})
        if r:
            try:
                body=r.json();rows=body if isinstance(body,list) else (body.get("data") or body.get("stocks") or [])
                for x in rows:
                    s=str(x.get("symbol") or "").upper().strip()
                    if s:
                        try:p=float(x.get("current_price")) if x.get("current_price") is not None else None
                        except:p=None
                        try:ch=float(x.get("change_percent")) if x.get("change_percent") is not None else None
                        except:ch=None
                        primary[s]={"price":p,"change":ch,"status":"LIVE"}
            except Exception:pass
    if primary:return primary,"LIVE"
    fallback={}
    for s in NGX_ASSETS:
        x,_=yahoo(f"{s}.LG")
        if x:fallback[s]={**x,"status":"FALLBACK"}
    return fallback,"FALLBACK" if fallback else "UNAVAILABLE"


def market_message():
    rows=[]
    c,_=crypto()
    for cid,s in CRYPTO.items():
        x=c.get(cid,{})
        if x.get("usd") is not None:
            label,conf=outlook(x.get("usd_24h_change"));rows.append((s,"Crypto",x.get("usd"),x.get("usd_24h_change"),label,conf))
    for s,n in US.items():
        x,_=yahoo(s)
        if x:
            label,conf=outlook(x.get("change"));rows.append((s,"US / ETFs",x["price"],x.get("change"),label,conf))
    n,mode=ngx()
    for s,name in NGX_ASSETS.items():
        x=n.get(s)
        if x:
            label,conf=outlook(x.get("change"));rows.append((s,"NGX",x["price"],x.get("change"),label,conf))
    for s,name in SIX.items():
        x,_=yahoo(s)
        if x:
            label,conf=outlook(x.get("change"));rows.append((s,"Asia / Six",x["price"],x.get("change"),label,conf))
    rows.sort(key=lambda x:(x[5],abs(x[3] or 0)),reverse=True)
    lines=[f"<b>🤖 AI MARKET INTELLIGENCE {VERSION}</b>",f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>","","<b>🏆 TOP MARKET OPPORTUNITIES</b>","<i>Research ranking only — no trade setups or execution.</i>"]
    for i,(s,m,p,ch,label,conf) in enumerate(rows[:8],1):
        icon="🟢" if label=="BULLISH" else ("🔴" if label=="BEARISH" else "🟡")
        change="N/A" if ch is None else f"{ch:+.2f}%"
        cur="₦" if m=="NGX" else "$"
        lines.append(f"{i}. {icon} <b>{html.escape(s)}</b> — {cur}{p:,.2f} ({change}) • {label} {conf}% • {m}")
    lines += ["",f"🇳🇬 <b>NGX DATA: {mode}</b>","<i>NGX Pulse is primary; Yahoo Finance is used only as a fallback when required.</i>"]
    return "\n".join(lines)


def send(msg):
    if not TOKEN:return False,"TELEGRAM_BOT_TOKEN is missing."
    if not CHANNEL:return False,"TELEGRAM_CHANNEL_ID is missing."
    try:
        r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",json={"chat_id":CHANNEL,"text":msg,"parse_mode":"HTML","disable_web_page_preview":False},timeout=20)
        return (True,"Telegram message sent.") if r.ok else (False,f"HTTP {r.status_code}: {r.text[:500]}")
    except Exception as e:return False,str(e)


if __name__=="__main__":
    news,provider=fetch_africa_business_news(GNEWS_KEY,limit=12)
    msg=market_message()+"\n\n"+render_telegram(news,limit=8)+f"\n\n<i>News provider: {html.escape(provider)}</i>\n\nℹ️ Hypothetical paper-analysis only. No trades are executed."
    ok,result=send(msg);print(result)
    if not ok:raise SystemExit(1)
