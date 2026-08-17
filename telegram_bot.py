import os,html,time,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import requests

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
CHANNEL=os.getenv("TELEGRAM_CHANNEL_ID","").strip()
NGX_KEY=os.getenv("NGXPULSE_API_KEY","").strip()
CG_KEY=os.getenv("COINGECKO_DEMO_API_KEY","").strip()
GNEWS_KEY=os.getenv("GNEWS_API_KEY","").strip()
DASH="https://ai-paper-market-dashboard.streamlit.app/"
VERSION="v4.5.1"
CG="https://api.coingecko.com/api/v3";YAHOO="https://query1.finance.yahoo.com/v8/finance/chart";NGX="https://www.ngxpulse.ng";GNEWS="https://gnews.io/api/v4"
STATE=Path("news_seen.json")
CRYPTO={"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB","ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US={"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS={"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank","ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo","MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods","BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings","PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}
SIX={"3308.HK":"ZhongJi InnoLight","042700.KS":"Hanmi Semiconductor","009150.KS":"Samsung Electro-Mechanics","066570.KS":"LG Electronics","035420.KS":"NAVER","069500.KS":"KODEX 200 ETF"}

def req(url,params=None,headers=None):
    last=None
    for i in range(3):
        try:
            r=requests.get(url,params=params,headers=headers or {"User-Agent":"AI-Market-Intelligence-v4.5.1"},timeout=20)
            if r.ok:return r,None
            try:
                b=r.json()
                errors=b.get("errors")
                if isinstance(errors,list):msg="; ".join(str(x) for x in errors)
                elif isinstance(errors,dict):msg="; ".join(f"{k}: {v}" for k,v in errors.items())
                else:msg=str(b.get("message") or b.get("error") or b)[:700]
            except:msg=(r.text or "Empty error response")[:700]
            last=f"HTTP {r.status_code}: {msg}"
            if r.status_code not in (408,425,429,500,502,503,504):break
        except Exception as e:last=f"Network error: {e}"
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
    h={"User-Agent":"AI-Market-Intelligence-v4.5.1"}
    if CG_KEY:h["x-cg-demo-api-key"]=CG_KEY
    r,e=req(f"{CG}/simple/price",{"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"},h)
    return (r.json() if r else {}),e

def yahoo(s):
    r,e=req(f"{YAHOO}/{s}",{"range":"5d","interval":"1d"},{"User-Agent":"Mozilla/5.0"})
    if not r:return None,e
    try:
        z=r.json()["chart"]["result"][0];m=z.get("meta",{});p=m.get("regularMarketPrice");pr=m.get("previousClose")
        cl=[x for x in z.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
        if p is None and cl:p=cl[-1]
        if pr is None and len(cl)>1:pr=cl[-2]
        if p is None or pr in (None,0):return None,"Price unavailable."
        return {"price":float(p),"change":(float(p)/float(pr)-1)*100},None
    except Exception as x:return None,str(x)

def ngx_all():
    u=f"{NGX}/api/ngxdata/stocks"
    if not NGX_KEY:return {}, "NGXPULSE_API_KEY is not configured."
    r,e=req(u,headers={"X-API-Key":NGX_KEY,"Content-Type":"application/json","User-Agent":"AI-Market-Intelligence-v4.5.1"})
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

def news():
    u=f"{GNEWS}/search"
    if not GNEWS_KEY:return [],{"status":None,"error":"GNEWS_API_KEY is missing or empty.","endpoint":u}
    q='(bitcoin OR ethereum OR cryptocurrency OR crypto OR stocks OR shares OR "Nigerian Exchange" OR NGX OR NVIDIA OR AMD OR Tesla OR Microsoft)'
    r,e=req(u,{"q":q,"lang":"en","max":10,"sortby":"publishedAt","apikey":GNEWS_KEY},{"User-Agent":"AI-Market-Intelligence-v4.5.1"})
    if not r:return [],{"status":None,"error":e or "No HTTP response received.","endpoint":u,"query":q}
    if not r.ok:
        try:
            b=r.json();errs=b.get("errors")
            if isinstance(errs,list):reason="; ".join(str(x) for x in errs)
            elif isinstance(errs,dict):reason="; ".join(f"{k}: {v}" for k,v in errs.items())
            else:reason=str(b.get("message") or b.get("error") or b)[:700]
        except:reason=(r.text or "Empty response")[:700]
        return [],{"status":r.status_code,"error":reason,"endpoint":u,"query":q}
    try:
        data=r.json();arts=[]
        for a in data.get("articles",[]):
            arts.append({"title":a.get("title","").strip(),"url":a.get("url") or "","source":(a.get("source") or {}).get("name","Unknown"),"publishedAt":a.get("publishedAt","")})
        return arts,{"status":200,"error":None,"endpoint":u,"count":len(arts),"query":q}
    except Exception as x:return [],{"status":200,"error":f"Could not parse GNews JSON: {x}","endpoint":u}

def news_reason(d):
    s=d.get("status")
    e=d.get("error") or "Unknown error"
    if s==401:return f"HTTP 401 Unauthorized — your GNEWS_API_KEY is missing, invalid, or expired. {e}"
    if s==403:return f"HTTP 403 Forbidden — your GNews daily quota/subscription restriction was reached. {e}"
    if s==429:return f"HTTP 429 Rate Limited — too many requests. {e}"
    if s==400:return f"HTTP 400 Bad Request — query/parameters rejected. {e}"
    if s in (500,503):return f"HTTP {s} GNews server issue. {e}"
    if s:return f"HTTP {s} — {e}"
    return e

def load_seen():
    try:
        x=json.loads(STATE.read_text(encoding="utf8"))
        return set(x if isinstance(x,list) else [])
    except:return set()

def save_seen(keys):
    STATE.write_text(json.dumps(list(keys)[-1000:]),encoding="utf8")

def add(lines,s,x,c="$"):
    if not x or x.get("price") is None:lines.append(f"⚪ <b>{html.escape(s)}</b> — unavailable");return
    ch=x.get("change");sg,cf=sig(ch);ico="🟢" if ch is not None and ch>1 else ("🔴" if ch is not None and ch<-1 else "🟡")
    lines.append(f"{ico} <b>{html.escape(s)}</b> {price(x['price'],c)} ({ch:+.2f}%) • {sg} {cf}%" if ch is not None else f"⚪ <b>{html.escape(s)}</b> {price(x['price'],c)} — no change data")

def market():
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
    else:lines.append(f"⚠️ NGX unavailable: {html.escape(str(e or 'Unknown error'))}")
    lines+=["","<b>🌏 SIX TRACKED ASSETS</b>"]
    for s,name in SIX.items():add(lines,name,yahoo(s)[0])
    return "\n".join(lines)

def news_message():
    arts,d=news()
    if d.get("status")!=200:
        return f"📰 <b>MARKET NEWS</b>\n⚠️ <b>News unavailable</b>\n{html.escape(news_reason(d))}\n🔎 Endpoint: <code>{html.escape(d.get('endpoint',''))}</code>"
    old=load_seen();new=[];keys=set(old)
    for a in arts:
        k=a["url"] or hashlib.sha256(a["title"].encode()).hexdigest()
        if k not in old:new.append(a);keys.add(k)
    save_seen(keys)
    if not new:
        return "📰 <b>MARKET NEWS</b>\nℹ️ GNews connection OK, but there are no new articles since the previous update."
    lines=[f"📰 <b>NEW MARKET NEWS ({len(new[:8])})</b>"]
    for a in new[:8]:
        u=html.escape(a["url"],quote=True);title=html.escape(a["title"]);src=html.escape(a["source"])
        lines.append(f"• <a href=\"{u}\">{title}</a>\n  <i>{src}</i>")
    return "\n".join(lines)

def send(msg):
    if not TOKEN:return False,"TELEGRAM_BOT_TOKEN is missing."
    if not CHANNEL:return False,"TELEGRAM_CHANNEL_ID is missing."
    try:
        r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",json={"chat_id":CHANNEL,"text":msg,"parse_mode":"HTML","disable_web_page_preview":False},timeout=20)
        return (True,"Telegram message sent.") if r.ok else (False,f"HTTP {r.status_code}: {r.text[:500]}")
    except Exception as e:return False,str(e)

if __name__=="__main__":
    msg=market()+"\n\n"+news_message()+"\n\nℹ️ Hypothetical paper-analysis only. No trades are executed."
    ok,result=send(msg);print(result)
    if not ok:raise SystemExit(1)
