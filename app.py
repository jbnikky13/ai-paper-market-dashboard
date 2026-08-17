import os, html, time
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="AI Market Intelligence v4.5", page_icon="📊", layout="wide")
VERSION="v4.5"; DASHBOARD_URL="https://ai-paper-market-dashboard.streamlit.app/"
DATA_DIR=Path(os.getenv("MARKET_DATA_DIR",".market_data")); DATA_DIR.mkdir(exist_ok=True)
PAPER_FILE=DATA_DIR/"paper_trades.csv"; NEWS_FILE=DATA_DIR/"news_seen.csv"
CG="https://api.coingecko.com/api/v3"; YAHOO="https://query1.finance.yahoo.com/v8/finance/chart"; NGX="https://www.ngxpulse.ng"
GNEWS="https://gnews.io/api/v4"

CRYPTO={"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB","ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US_ASSETS={"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS={"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank","ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo","MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods","BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings","PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}
SIX_ASSETS={"3308.HK":"ZhongJi InnoLight","042700.KS":"Hanmi Semiconductor","009150.KS":"Samsung Electro-Mechanics","066570.KS":"LG Electronics","035420.KS":"NAVER","069500.KS":"KODEX 200 ETF"}

def secret(n):
    try:
        v=st.secrets.get(n)
        if v is not None:return str(v)
    except Exception:pass
    return os.getenv(n,"")

TELEGRAM_BOT_TOKEN=secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID=secret("TELEGRAM_CHANNEL_ID")
NGXPULSE_API_KEY=secret("NGXPULSE_API_KEY")
COINGECKO_DEMO_API_KEY=secret("COINGECKO_DEMO_API_KEY")
GNEWS_API_KEY=secret("GNEWS_API_KEY")

def get(url,params=None,headers=None,timeout=20):
    t=time.time()
    try:
        r=requests.get(url,params=params,headers=headers or {"User-Agent":"AI-Market-Intelligence-v4.5"},timeout=timeout)
        return r,round(time.time()-t,2),None
    except Exception as e:return None,round(time.time()-t,2),str(e)

@st.cache_data(ttl=300,show_spinner=False)
def crypto():
    h={"User-Agent":"AI-Market-Intelligence-v4.5"}
    if COINGECKO_DEMO_API_KEY:h["x-cg-demo-api-key"]=COINGECKO_DEMO_API_KEY
    u=f"{CG}/simple/price"; r,e,err=get(u,{"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"},h)
    d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"error":err}
    if not r:return {},d
    if not r.ok:d["error"]=r.text[:500];return {},d
    try:return r.json(),d
    except Exception as x:d["error"]=str(x);return {},d

@st.cache_data(ttl=120,show_spinner=False)
def yahoo(symbol):
    u=f"{YAHOO}/{symbol}"; r,e,err=get(u,{"range":"5d","interval":"1d"},{"User-Agent":"Mozilla/5.0"})
    d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"error":err}
    if not r or not r.ok:
        if r:d["error"]=r.text[:500]
        return None,d
    try:
        res=r.json()["chart"]["result"][0]; meta=res.get("meta",{}); p=meta.get("regularMarketPrice"); prev=meta.get("previousClose")
        closes=[x for x in res.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
        if p is None and closes:p=closes[-1]
        if prev is None and len(closes)>1:prev=closes[-2]
        if p is None or prev in (None,0):d["error"]="Price/previous close unavailable.";return None,d
        return {"price":float(p),"change":(float(p)/float(prev)-1)*100},d
    except Exception as x:d["error"]=str(x);return None,d

@st.cache_data(ttl=300,show_spinner=False)
def ngx_all():
    u=f"{NGX}/api/ngxdata/stocks"
    if not NGXPULSE_API_KEY:return {},{"endpoint":u,"status":None,"elapsed":0,"count":0,"error":"NGXPULSE_API_KEY is not configured in Streamlit Secrets."}
    r,e,err=get(u,headers={"X-API-Key":NGXPULSE_API_KEY,"Content-Type":"application/json","User-Agent":"AI-Market-Intelligence-v4.5"})
    d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"count":0,"error":err}
    if not r:return {},d
    if not r.ok:
        try:b=r.json();d["error"]=b.get("message") or b.get("error") or r.text[:500]
        except Exception:d["error"]=r.text[:500]
        return {},d
    try:
        p=r.json(); rows=p if isinstance(p,list) else (p.get("data") or p.get("stocks") or []);out={}
        for x in rows:
            if not isinstance(x,dict):continue
            s=str(x.get("symbol") or "").upper().strip()
            if not s:continue
            try:p=float(x["current_price"]) if x.get("current_price") is not None else None
            except:p=None
            try:c=float(x["change_percent"]) if x.get("change_percent") is not None else None
            except:c=None
            out[s]={"name":x.get("name") or s,"price":p,"change":c}
        d["count"]=len(out)
        if not out:d["error"]="HTTP request succeeded, but no recognised stock records were returned."
        return out,d
    except Exception as x:d["error"]=f"Could not parse NGX response: {x}";return {},d

@st.cache_data(ttl=300,show_spinner=False)
def news_search():
    if not GNEWS_API_KEY:
        return [],{"endpoint":f"{GNEWS}/search","status":None,"error":"GNEWS_API_KEY is not configured."}
    queries=[
        "cryptocurrency bitcoin ethereum crypto market",
        "US stocks shares technology market NVIDIA Tesla Microsoft",
        "Nigeria NGX stocks shares Nigerian Exchange",
    ]
    articles=[]; diags=[]
    for q in queries:
        u=f"{GNEWS}/search";r,e,err=get(u,{"q":q,"lang":"en","max":10,"sortby":"publishedAt","apikey":GNEWS_API_KEY},{"User-Agent":"AI-Market-Intelligence-v4.5"})
        d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"error":err,"query":q}
        if not r:diags.append(d);continue
        if not r.ok:d["error"]=r.text[:500];diags.append(d);continue
        try:
            data=r.json()
            for a in data.get("articles",[]):
                articles.append({
                    "title":a.get("title","").strip(),
                    "description":a.get("description") or "",
                    "url":a.get("url") or "",
                    "source":(a.get("source") or {}).get("name","Unknown"),
                    "publishedAt":a.get("publishedAt",""),
                    "query":q
                })
            diags.append(d)
        except Exception as x:d["error"]=str(x);diags.append(d)
    seen=set();out=[]
    for a in sorted(articles,key=lambda x:x["publishedAt"],reverse=True):
        key=a["url"] or a["title"].lower()
        if key and key not in seen:seen.add(key);out.append(a)
    return out,diags

def signal(c):
    if c is None or pd.isna(c):return "NO DATA",0
    c=float(c)
    if c>=2:return "BULLISH",min(95,round(55+abs(c)*5))
    if c<=-2:return "BEARISH",min(95,round(55+abs(c)*5))
    return "NEUTRAL",max(50,min(75,round(60+abs(c)*2)))

def fmt(p,c="$"):
    if p is None or pd.isna(p):return "N/A"
    if c=="₦":return f"₦{p:,.2f}"
    return f"${p:.6f}" if p<1 else f"${p:,.2f}"

def history():
    cols=["timestamp","asset","source","price","change_pct","signal","confidence","status"]
    if not PAPER_FILE.exists():return pd.DataFrame(columns=cols)
    try:
        d=pd.read_csv(PAPER_FILE)
        for c in cols:
            if c not in d:d[c]=""
        return d[cols]
    except:return pd.DataFrame(columns=cols)

def news_seen():
    if not NEWS_FILE.exists():return set()
    try:return set(pd.read_csv(NEWS_FILE)["key"].astype(str))
    except:return set()

def save_news_seen(keys):
    pd.DataFrame({"key":list(keys)[-1000:]}).to_csv(NEWS_FILE,index=False)

def snapshot(rows):
    pd.concat([history(),pd.DataFrame(rows)],ignore_index=True).tail(5000).to_csv(PAPER_FILE,index=False)

def telegram(msg):
    if not TELEGRAM_BOT_TOKEN:return False,"TELEGRAM_BOT_TOKEN is not configured."
    if not TELEGRAM_CHANNEL_ID:return False,"TELEGRAM_CHANNEL_ID is not configured."
    try:
        r=requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",json={"chat_id":TELEGRAM_CHANNEL_ID,"text":msg,"parse_mode":"HTML","disable_web_page_preview":False},timeout=15)
        return (True,"Telegram message sent.") if r.ok else (False,f"HTTP {r.status_code}: {r.text[:500]}")
    except Exception as x:return False,str(x)

def market_rows():
    rows=[];diags=[]
    c,dc=crypto();diags.append(("CoinGecko",dc))
    for cid,s in CRYPTO.items():
        x=c.get(cid,{});p=x.get("usd");ch=x.get("usd_24h_change");sg,cf=signal(ch)
        rows.append({"asset":s,"name":s,"source":"CoinGecko","price":p,"change_pct":ch,"signal":sg,"confidence":cf,"currency":"$","status":"OK" if p is not None else "NO DATA"})
    for s,n in US_ASSETS.items():
        x,dx=yahoo(s);diags.append((f"Yahoo:{s}",dx));p,ch=(x["price"],x["change"]) if x else (None,None);sg,cf=signal(ch)
        rows.append({"asset":s,"name":n,"source":"Yahoo Finance","price":p,"change_pct":ch,"signal":sg,"confidence":cf,"currency":"$","status":"OK" if p is not None else "NO DATA"})
    n,dn=ngx_all();diags.append(("NGX Pulse /stocks",dn))
    for s,nm in NGX_ASSETS.items():
        x=n.get(s);p,ch=((x["price"],x["change"]) if x else (None,None));sg,cf=signal(ch)
        rows.append({"asset":s,"name":x.get("name",nm) if x else nm,"source":"NGX Pulse","price":p,"change_pct":ch,"signal":sg,"confidence":cf,"currency":"₦","status":"OK" if p is not None else "NO DATA"})
    for s,nm in SIX_ASSETS.items():
        x,dx=yahoo(s);diags.append((f"Yahoo:{s}",dx));p,ch=(x["price"],x["change"]) if x else (None,None);sg,cf=signal(ch)
        rows.append({"asset":s,"name":nm,"source":"Yahoo Finance","price":p,"change_pct":ch,"signal":sg,"confidence":cf,"currency":"$","status":"OK" if p is not None else "NO DATA"})
    return rows,diags

def news_block(articles,limit=10):
    if not articles:return "📰 <b>MARKET NEWS</b>\nNo news available."
    lines=["📰 <b>MARKET NEWS</b>"]
    for a in articles[:limit]:
        title=html.escape(a["title"]);source=html.escape(a["source"])
        url=html.escape(a["url"],quote=True)
        lines.append(f"• <a href=\"{url}\">{title}</a>\n  <i>{source}</i>")
    return "\n".join(lines)

st.title("📊 AI Market Intelligence")
st.caption(f"{VERSION} • paper-analysis dashboard + market news")
if st.button("🔄 Refresh market data & news"):st.cache_data.clear();st.rerun()
rows,diags=market_rows(); articles,news_diags=news_search()
snapshot([{"timestamp":datetime.now(timezone.utc).isoformat(),"asset":x["asset"],"source":x["source"],"price":x["price"],"change_pct":x["change_pct"],"signal":x["signal"],"confidence":x["confidence"],"status":x["status"]} for x in rows])
df=pd.DataFrame(rows)
tabs=st.tabs(["📈 Signals","₿ Crypto","🇺🇸 US / ETFs","🇳🇬 NGX","🌏 Six Assets","📰 News","🧪 Diagnostics","📝 History"])
with tabs[0]:
    st.info("Signals/confidence are hypothetical paper-analysis outputs. No trades are executed.")
    v=df.copy();v["price"]=v.apply(lambda r:fmt(r.price,r.currency),axis=1);v["change_pct"]=v.change_pct.map(lambda x:"N/A" if pd.isna(x) else f"{x:+.2f}%")
    st.dataframe(v[["asset","name","source","price","change_pct","signal","confidence","status"]],use_container_width=True,hide_index=True)
with tabs[1]:st.dataframe(df[df.source=="CoinGecko"],use_container_width=True,hide_index=True)
with tabs[2]:st.dataframe(df[(df.source=="Yahoo Finance")&df.asset.isin(US_ASSETS)],use_container_width=True,hide_index=True)
with tabs[3]:
    d=next((x for n,x in diags if n=="NGX Pulse /stocks"),{})
    if d.get("status")==200 and not d.get("error"):st.success(f"NGX Pulse connected — {d.get('count',0)} records.")
    else:st.error(f"NGX unavailable. HTTP {d.get('status','N/A')} | {d.get('error','Unknown error')}")
    st.caption(d.get("endpoint",f"{NGX}/api/ngxdata/stocks"));st.dataframe(df[df.source=="NGX Pulse"],use_container_width=True,hide_index=True)
with tabs[4]:st.dataframe(df[df.asset.isin(SIX_ASSETS)],use_container_width=True,hide_index=True)
with tabs[5]:
    st.write(news_block(articles,20))
    if not GNEWS_API_KEY:st.warning("Add GNEWS_API_KEY to enable the news feed.")
with tabs[6]:
    all_diag=[{"source":n,"HTTP status":d.get("status"),"request time (s)":d.get("elapsed"),"records":d.get("count",""),"status":"OK" if not d.get("error") else "FAILED","endpoint":d.get("endpoint",""),"exact reason":d.get("error") or "Request successful"} for n,d in diags]
    for d in news_diags:all_diag.append({"source":"GNews","HTTP status":d.get("status"),"request time (s)":d.get("elapsed"),"records":"","status":"OK" if not d.get("error") else "FAILED","endpoint":d.get("endpoint",""),"exact reason":d.get("error") or "Request successful"})
    st.dataframe(pd.DataFrame(all_diag),use_container_width=True,hide_index=True)
with tabs[7]:
    h=history()
    if h.empty:st.info("No paper snapshots recorded yet.")
    else:
        st.dataframe(h.tail(500),use_container_width=True,hide_index=True)
        st.download_button("⬇️ Download history",h.to_csv(index=False),file_name="paper_trade_history.csv",mime="text/csv")
