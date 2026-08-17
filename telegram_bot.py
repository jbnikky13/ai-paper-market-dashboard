import os,html,time
from datetime import datetime,timezone
import requests

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN",""); CHANNEL=os.getenv("TELEGRAM_CHANNEL_ID",""); NGX_KEY=os.getenv("NGXPULSE_API_KEY",""); CG_KEY=os.getenv("COINGECKO_DEMO_API_KEY","")
DASH="https://ai-paper-market-dashboard.streamlit.app/"; VERSION="v4.4.1"
CG="https://api.coingecko.com/api/v3"; YAHOO="https://query1.finance.yahoo.com/v8/finance/chart"; NGX="https://www.ngxpulse.ng"
CRYPTO={"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB","ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US={"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS={"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank","ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo","MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods","BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings","PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}
SIX={"3308.HK":"ZhongJi InnoLight","042700.KS":"Hanmi Semiconductor","009150.KS":"Samsung Electro-Mechanics","066570.KS":"LG Electronics","035420.KS":"NAVER","069500.KS":"KODEX 200 ETF"}

def req(url,params=None,headers=None):
    last=None
    for i in range(3):
        try:
            r=requests.get(url,params=params,headers=headers or {"User-Agent":"AI-Market-Intelligence-v4.4.1"},timeout=20)
            if r.ok:return r, None
            try:b=r.json();msg=b.get("message") or b.get("error") or r.text[:500]
            except:msg=r.text[:500]
            last=f"HTTP {r.status_code}: {msg}"
            if r.status_code not in (408,425,429,500,502,503,504):break
        except Exception as e:last=str(e)
        time.sleep(2**i)
    return None,last

def sig(c):
    if c is None:return "NO DATA",0
    c=float(c)
    if c>=2:return "BULLISH",min(95,round(55+abs(c)*5))
    if c<=-2:return "BEARISH",min(95,round(55+abs(c)*5))
    return "NEUTRAL",max(50,min(75,round(60+abs(c)*2)))

def price(p,c="$"):
    if p is None:return "N/A"
    if c=="₦":return f"₦{p:,.2f}"
    return f"${p:.6f}" if p<1 else f"${p:,.2f}"

def crypto():
    h={"User-Agent":"AI-Market-Intelligence-v4.4.1"}
    if CG_KEY:h["x-cg-demo-api-key"]=CG_KEY
    r,e=req(f"{CG}/simple/price",{"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"},h)
    return (r.json() if r else {}),e

def yahoo(s):
    u=f"{YAHOO}/{s}";r,e=req(u,{"range":"5d","interval":"1d"},{"User-Agent":"Mozilla/5.0"})
    if not r:return None,e
    try:
        z=r.json()["chart"]["result"][0];m=z.get("meta",{});p=m.get("regularMarketPrice");pr=m.get("previousClose");cl=[x for x in z.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
        if p is None and cl:p=cl[-1]
        if pr is None and len(cl)>1:pr=cl[-2]
        if p is None or pr in (None,0):return None,"Price unavailable."
        return {"price":float(p),"change":(float(p)/float(pr)-1)*100},None
    except Exception as x:return None,str(x)

def ngx_all():
    u=f"{NGX}/api/ngxdata/stocks"
    if not NGX_KEY:return {}, "NGXPULSE_API_KEY is not configured."
    r,e=req(u,headers={"X-API-Key":NGX_KEY,"Content-Type":"application/json","User-Agent":"AI-Market-Intelligence-v4.4.1"})
    if not r:return {},e
    try:
        p=r.json();rows=p if isinstance(p,list) else (p.get("data") or p.get("stocks") or []);out={}
        for x in rows:
            if not isinstance(x,dict):continue
            s=str(x.get("symbol") or "").upper().strip()
            if not s:continue
            try:pp=float(x["current_price"]) if x.get("current_price") is not None else None
            except:pp=None
            try:ch=float(x["change_percent"]) if x.get("change_percent") is not None else None
            except:ch=None
            out[s]={"price":pp,"change":ch}
        return out,None if out else "No recognised stock records returned."
    except Exception as x:return {},f"Could not parse NGX response: {x}"

def add(lines,s,x,c="$"):
    if not x or x.get("price") is None:lines.append(f"⚪ <b>{html.escape(s)}</b> — unavailable");return
    ch=x.get("change");sg,cf=sig(ch);ico="🟢" if ch is not None and ch>1 else ("🔴" if ch is not None and ch<-1 else "🟡")
    lines.append(f"{ico} <b>{html.escape(s)}</b> {price(x['price'],c)} ({ch:+.2f}%) • {sg} {cf}%" if ch is not None else f"⚪ <b>{html.escape(s)}</b> {price(x['price'],c)} — no change data")

def build():
    lines=[f"<b>🤖 AI MARKET INTELLIGENCE {VERSION}</b>",f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>",""]
    lines.append("<b>₿ CRYPTO</b>");c,e=crypto()
    if c:
        for cid,s in CRYPTO.items():
            q=c.get(cid,{});add(lines,s,{"price":q.get("usd"),"change":q.get("usd_24h_change")} if q.get("usd") is not None else None)
    else:lines.append(f"⚠️ CoinGecko unavailable: {html.escape(str(e))}")
    lines+=["","<b>🇺🇸 US / ETFs</b>"]
    for s in US:add(lines,s,yahoo(s)[0])
    lines+=["","<b>🇳🇬 NGX</b>"];n,e=ngx_all()
    if n:
        for s in NGX_ASSETS:add(lines,s,n.get(s),"₦")
    else:lines.append(f"⚠️ NGX unavailable — {html.escape(str(e or 'Unknown error'))}")
    lines+=["","<b>🌏 SIX TRACKED ASSETS</b>"]
    for s,name in SIX.items():add(lines,name,yahoo(s)[0])
    lines+=["","━━━━━━━━━━━━━━━━","ℹ️ Hypothetical paper-analysis signals only. No trades are executed.",f'🌐 <a href="{DASH}">Open dashboard</a>']
    return "\n".join(lines)

def send(msg):
    if not TOKEN:return False,"TELEGRAM_BOT_TOKEN is missing."
    if not CHANNEL:return False,"TELEGRAM_CHANNEL_ID is missing."
    try:
        r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",json={"chat_id":CHANNEL,"text":msg,"parse_mode":"HTML"},timeout=20)
        return (True,"Telegram message sent.") if r.ok else (False,f"HTTP {r.status_code}: {r.text[:500]}")
    except Exception as e:return False,str(e)

if __name__=="__main__":
    msg=build();print(msg);ok,result=send(msg);print(result)
    if not ok:raise SystemExit(1)
