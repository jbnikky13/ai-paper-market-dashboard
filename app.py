import os, html, time
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="AI Market Intelligence v4.5.1", page_icon="📊", layout="wide")
VERSION="v4.5.1"
DASHBOARD_URL="https://ai-paper-market-dashboard.streamlit.app/"
DATA_DIR=Path(os.getenv("MARKET_DATA_DIR",".market_data")); DATA_DIR.mkdir(exist_ok=True)
PAPER_FILE=DATA_DIR/"paper_trades.csv"
NEWS_FILE=DATA_DIR/"news_seen.csv"

CG="https://api.coingecko.com/api/v3"
YAHOO="https://query1.finance.yahoo.com/v8/finance/chart"
NGX="https://www.ngxpulse.ng"
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
        r=requests.get(url,params=params,headers=headers or {"User-Agent":"AI-Market-Intelligence-v4.5.1"},timeout=timeout)
        return r,round(time.time()-t,2),None
    except Exception as e:return None,round(time.time()-t,2),str(e)

def parse_gnews_error(r):
    if not r:return "No HTTP response received."
    try:
        body=r.json()
        errors=body.get("errors")
        if isinstance(errors,list): return "; ".join(str(x) for x in errors)
        if isinstance(errors,dict): return "; ".join(f"{k}: {v}" for k,v in errors.items())
        return str(body.get("message") or body.get("error") or body)[:700]
    except Exception:
        return (r.text or "Empty error response")[:700]

def gnews_status(status,error):
    if status==200:return "OK"
    if status==400:return f"Bad request — {error}"
    if status==401:return f"Unauthorized — API key missing, invalid, or expired. {error}"
    if status==403:return f"Forbidden — daily quota/subscription restriction. {error}"
    if status==429:return f"Rate limited — too many requests. {error}"
    if status in (500,503):return f"GNews server unavailable ({status}). {error}"
    return f"HTTP {status} — {error}"

@st.cache_data(ttl=300,show_spinner=False)
def crypto():
    h={"User-Agent":"AI-Market-Intelligence-v4.5.1"}
    if COINGECKO_DEMO_API_KEY:h["x-cg-demo-api-key"]=COINGECKO_DEMO_API_KEY
    u=f"{CG}/simple/price"; r,e,err=get(u,{"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"},h)
    d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"error":err}
    if not r:return {},d
    if not r.ok:d["error"]=r.text[:500];return {},d
    try:return r.json(),d
    except Exception as x:d["error"]=str(x);return {},d

@st.cache_data(ttl=120,show_spinner=False)
def yahoo(symbol):
    u=f"{YAHOO}/{symbol}";r,e,err=get(u,{"range":"5d","interval":"1d"},{"User-Agent":"Mozilla/5.0"})
    d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"error":err}
    if not r or not r.ok:
        if r:d["error"]=r.text[:500]
        return None,d
    try:
        z=r.json()["chart"]["result"][0];m=z.get("meta",{});p=m.get("regularMarketPrice");pr=m.get("previousClose")
        cl=[x for x in z.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
        if p is None and cl:p=cl[-1]
        if pr is None and len(cl)>1:pr=cl[-2]
        if p is None or pr in (None,0):d["error"]="Price/previous close unavailable.";return None,d
        return {"price":float(p),"change":(float(p)/float(pr)-1)*100},d
    except Exception as x:d["error"]=str(x);return None,d

@st.cache_data(ttl=300,show_spinner=False)
def ngx_all():
    u=f"{NGX}/api/ngxdata/stocks"
    if not NGXPULSE_API_KEY:return {},{"endpoint":u,"status":None,"elapsed":0,"count":0,"error":"NGXPULSE_API_KEY is not configured."}
    r,e,err=get(u,headers={"X-API-Key":NGXPULSE_API_KEY,"Content-Type":"application/json","User-Agent":"AI-Market-Intelligence-v4.5.1"})
    d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"count":0,"error":err}
    if not r:return {},d
    if not r.ok:
        d["error"]=parse_gnews_error(r);return {},d
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
            out[s]={"name":x.get("name") or s,"price":pp,"change":ch}
        d["count"]=len(out)
        if not out:d["error"]="Request succeeded but no recognised stock records were returned."
        return out,d
    except Exception as x:d["error"]=f"Could not parse NGX response: {x}";return {},d

@st.cache_data(ttl=300,show_spinner=False)
def news_search():
    u=f"{GNEWS}/search"
    if not GNEWS_API_KEY:
        return [],{"endpoint":u,"status":None,"elapsed":0,"count":0,"error":"GNEWS_API_KEY is not configured in Streamlit Secrets."}
    # One broad query per refresh avoids unnecessary quota consumption.
    q='(bitcoin OR ethereum OR cryptocurrency OR crypto OR stocks OR shares OR "Nigerian Exchange" OR NGX OR NVIDIA OR AMD OR Tesla OR Microsoft)'
    r,e,err=get(u,{"q":q,"lang":"en","max":10,"sortby":"publishedAt","apikey":GNEWS_API_KEY},{"User-Agent":"AI-Market-Intelligence-v4.5.1"})
    d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"count":0,"error":err,"query":q}
    if not r:return [],d
    if not r.ok:d["error"]=parse_gnews_error(r);return [],d
    try:
        data=r.json();out=[]
        for a in data.get("articles",[]):
            out.append({"title":a.get("title","").strip(),"description":a.get("description") or "","url":a.get("url") or "","source":(a.get("source") or {}).get("name","Unknown"),"publishedAt":a.get("publishedAt","")})
        d["count"]=len(out)
        return out,d
    except Exception as x:d["error"]=f"Could not parse GNews JSON: {x}";return [],d

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

st.title("📊 AI Market Intelligence")
st.caption(f"{VERSION} • market signals + news diagnostics")
if st.button("🔄 Refresh market data & news"):st.cache_data.clear();st.rerun()

rows,diags=market_rows();articles,news_diag=news_search()
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
    if news_diag.get("status")==200 and not news_diag.get("error"):
        st.success(f"GNews connected — {news_diag.get('count',0)} articles received.")
        for a in articles:
            st.markdown(f"**[{a['title']}]({a['url']})** — {a['source']}")
            if a["description"]:st.caption(a["description"])
    else:
        st.error(f"News unavailable — {gnews_status(news_diag.get('status'),news_diag.get('error') or 'No response')}")
        st.write("Endpoint:",news_diag.get("endpoint"))
        st.write("HTTP status:",news_diag.get("status","N/A"))
        st.write("Exact API reason:",news_diag.get("error") or "No response")
        st.info("Add or replace GNEWS_API_KEY in Streamlit Secrets, then refresh.")
with tabs[6]:
    ds=[{"source":n,"HTTP status":d.get("status"),"request time (s)":d.get("elapsed"),"records":d.get("count",""),"status":"OK" if not d.get("error") else "FAILED","endpoint":d.get("endpoint",""),"exact reason":d.get("error") or "Request successful"} for n,d in diags]
    ds.append({"source":"GNews","HTTP status":news_diag.get("status"),"request time (s)":news_diag.get("elapsed"),"records":news_diag.get("count",""),"status":"OK" if not news_diag.get("error") else "FAILED","endpoint":news_diag.get("endpoint",""),"exact reason":news_diag.get("error") or "Request successful"})
    st.dataframe(pd.DataFrame(ds),use_container_width=True,hide_index=True)
with tabs[7]:
    h=history()
    if h.empty:st.info("No paper snapshots recorded yet.")
    else:
        st.dataframe(h.tail(500),use_container_width=True,hide_index=True)
        st.download_button("⬇️ Download history",h.to_csv(index=False),file_name="paper_trade_history.csv",mime="text/csv")
