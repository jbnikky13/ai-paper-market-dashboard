import os, html, time
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="AI Market Intelligence v4.4.1", page_icon="📊", layout="wide")
VERSION="v4.4.1"; DASHBOARD_URL="https://ai-paper-market-dashboard.streamlit.app/"
DATA_DIR=Path(os.getenv("MARKET_DATA_DIR",".market_data")); DATA_DIR.mkdir(exist_ok=True)
PAPER_FILE=DATA_DIR/"paper_trades.csv"
CG="https://api.coingecko.com/api/v3"; YAHOO="https://query1.finance.yahoo.com/v8/finance/chart"; NGX="https://www.ngxpulse.ng"

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
TELEGRAM_BOT_TOKEN=secret("TELEGRAM_BOT_TOKEN"); TELEGRAM_CHANNEL_ID=secret("TELEGRAM_CHANNEL_ID")
NGXPULSE_API_KEY=secret("NGXPULSE_API_KEY"); COINGECKO_DEMO_API_KEY=secret("COINGECKO_DEMO_API_KEY")

def get(url,params=None,headers=None,timeout=20):
    t=time.time()
    try:
        r=requests.get(url,params=params,headers=headers or {"User-Agent":"AI-Market-Intelligence-v4.4.1"},timeout=timeout)
        return r,round(time.time()-t,2),None
    except Exception as e:return None,round(time.time()-t,2),str(e)

@st.cache_data(ttl=300,show_spinner=False)
def crypto():
    h={"User-Agent":"AI-Market-Intelligence-v4.4.1"}
    if COINGECKO_DEMO_API_KEY:h["x-cg-demo-api-key"]=COINGECKO_DEMO_API_KEY
    u=f"{CG}/simple/price"; r,e,err=get(u,{"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true","include_24hr_vol":"true"},h)
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
    r,e,err=get(u,headers={"X-API-Key":NGXPULSE_API_KEY,"Content-Type":"application/json","User-Agent":"AI-Market-Intelligence-v4.4.1"})
    d={"endpoint":u,"status":r.status_code if r else None,"elapsed":e,"count":0,"error":err}
    if not r:return {},d
    if not r.ok:
        try:b=r.json();d["error"]=b.get("message") or b.get("error") or r.text[:500]
        except Exception:d["error"]=r.text[:500]
        return {},d
    try:
        p=r.json(); rows=p if isinstance(p,list) else (p.get("data") or p.get("stocks") or [])
        out={}
        for x in rows:
            if not isinstance(x,dict):continue
            s=str(x.get("symbol") or "").upper().strip()
            if not s:continue
            try:price=float(x["current_price"]) if x.get("current_price") is not None else None
            except:price=None
            try:change=float(x["change_percent"]) if x.get("change_percent") is not None else None
            except:change=None
            out[s]={"name":x.get("name") or s,"price":price,"change":change}
        d["count"]=len(out)
        if not out:d["error"]="HTTP request succeeded, but no recognised stock records were returned."
        return out,d
    except Exception as x:d["error"]=f"Could not parse NGX response: {x}";return {},d

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

def snapshot(rows):
    d=pd.concat([history(),pd.DataFrame(rows)],ignore_index=True).tail(5000)
    DATA_DIR.mkdir(exist_ok=True);d.to_csv(PAPER_FILE,index=False)

def telegram(msg):
    if not TELEGRAM_BOT_TOKEN:return False,"TELEGRAM_BOT_TOKEN is not configured."
    if not TELEGRAM_CHANNEL_ID:return False,"TELEGRAM_CHANNEL_ID is not configured."
    try:
        r=requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",json={"chat_id":TELEGRAM_CHANNEL_ID,"text":msg,"parse_mode":"HTML"},timeout=15)
        return (True,"Telegram message sent.") if r.ok else (False,f"HTTP {r.status_code}: {r.text[:500]}")
    except Exception as x:return False,str(x)

def rows_and_diag():
    rows=[];diags=[]
    c,dc=crypto();diags.append(("CoinGecko",dc))
    for cid,s in CRYPTO.items():
        x=c.get(cid,{});p=x.get("usd");ch=x.get("usd_24h_change");sg,cf=signal(ch)
        rows.append({"asset":s,"name":s,"source":"CoinGecko","price":p,"change_pct":ch,"signal":sg,"confidence":cf,"currency":"$","status":"OK" if p is not None else "NO DATA"})
    for s,n in US_ASSETS.items():
        x,dx=yahoo(s);diags.append((f"Yahoo:{s}",dx));p,ch=(x["price"],x["change"]) if x else (None,None);sg,cf=signal(ch)
        rows.append({"asset":s,"name":n,"source":"Yahoo Finance","price":p,"change_pct":ch,"signal":sg,"confidence":cf,"currency":"$","status":"OK" if p is not None else "NO DATA"})
    nd,dn=ngx_all();diags.append(("NGX Pulse /stocks",dn))
    for s,n in NGX_ASSETS.items():
        x=nd.get(s);p,ch=((x["price"],x["change"]) if x else (None,None));sg,cf=signal(ch)
        rows.append({"asset":s,"name":x.get("name",n) if x else n,"source":"NGX Pulse","price":p,"change_pct":ch,"signal":sg,"confidence":cf,"currency":"₦","status":"OK" if p is not None else "NO DATA"})
    for s,n in SIX_ASSETS.items():
        x,dx=yahoo(s);diags.append((f"Yahoo:{s}",dx));p,ch=(x["price"],x["change"]) if x else (None,None);sg,cf=signal(ch)
        rows.append({"asset":s,"name":n,"source":"Yahoo Finance","price":p,"change_pct":ch,"signal":sg,"confidence":cf,"currency":"$","status":"OK" if p is not None else "NO DATA"})
    return rows,diags

def report(rows):
    lines=[f"<b>🤖 AI MARKET INTELLIGENCE {VERSION}</b>",f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>",""]
    groups=[("₿ CRYPTO",[x for x in rows if x["source"]=="CoinGecko"]),("🇺🇸 US / ETFs",[x for x in rows if x["source"]=="Yahoo Finance" and x["asset"] in US_ASSETS]),("🇳🇬 NGX",[x for x in rows if x["source"]=="NGX Pulse"]),("🌏 SIX TRACKED ASSETS",[x for x in rows if x["asset"] in SIX_ASSETS])]
    for title,g in groups:
        lines.append(f"<b>{title}</b>")
        for x in g:
            ch=x["change_pct"]
            if ch is None:lines.append(f"⚪ <b>{html.escape(x['asset'])}</b> — no data")
            else:
                icon="🟢" if ch>1 else ("🔴" if ch<-1 else "🟡")
                lines.append(f"{icon} <b>{html.escape(x['asset'])}</b> {fmt(x['price'],x['currency'])} ({ch:+.2f}%) • {x['signal']} {x['confidence']}%")
        lines.append("")
    lines += ["━━━━━━━━━━━━━━━━","ℹ️ Hypothetical paper-analysis signals only. No trades are executed.",f'🌐 <a href="{DASHBOARD_URL}">Open dashboard</a>']
    return "\n".join(lines)

st.title("📊 AI Market Intelligence")
st.caption(f"{VERSION} • informational / paper-trading dashboard")
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Refresh market data"):st.cache_data.clear();st.rerun()
    st.divider();st.subheader("📣 Telegram")
    st.success("Configured") if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID else st.warning("Not configured")
    if st.button("📨 Send Telegram test"):
        ok,msg=telegram(f"<b>🤖 AI Market Intelligence {VERSION}</b>\n\nTelegram connection test successful.\n<a href='{DASHBOARD_URL}'>Open dashboard</a>")
        (st.success if ok else st.error)(msg)
    st.divider();st.subheader("💾 Paper history");st.caption(str(PAPER_FILE));st.write(f"Records: {len(history())}")
    if st.button("🗑️ Clear local paper history"):
        if PAPER_FILE.exists():PAPER_FILE.unlink()
        st.rerun()

rows,diags=rows_and_diag()
snapshot([{"timestamp":datetime.now(timezone.utc).isoformat(),"asset":x["asset"],"source":x["source"],"price":x["price"],"change_pct":x["change_pct"],"signal":x["signal"],"confidence":x["confidence"],"status":x["status"]} for x in rows])
df=pd.DataFrame(rows)
tabs=st.tabs(["📈 Market Signals","₿ Crypto","🇺🇸 US / ETFs","🇳🇬 NGX","🌏 Six Assets","🧪 API Diagnostics","📝 Paper History"])
with tabs[0]:
    st.info("Signals/confidence are hypothetical paper-analysis outputs. They do not execute trades or determine how much money to risk.")
    v=df.copy();v["price"]=v.apply(lambda r:fmt(r["price"],r["currency"]),axis=1);v["change_pct"]=v["change_pct"].map(lambda x:"N/A" if pd.isna(x) else f"{x:+.2f}%");v["confidence"]=v["confidence"].map(lambda x:f"{x}%")
    st.dataframe(v[["asset","name","source","price","change_pct","signal","confidence","status"]],use_container_width=True,hide_index=True)
with tabs[1]:st.dataframe(df[df.source=="CoinGecko"][["asset","price","change_pct","signal","confidence","status"]],use_container_width=True,hide_index=True)
with tabs[2]:st.dataframe(df[(df.source=="Yahoo Finance")&df.asset.isin(US_ASSETS)][["asset","name","price","change_pct","signal","confidence","status"]],use_container_width=True,hide_index=True)
with tabs[3]:
    d=next((x for n,x in diags if n=="NGX Pulse /stocks"),{})
    if d.get("status")==200 and not d.get("error"):st.success(f"NGX Pulse connected — received {d.get('count',0)} stock records.")
    else:st.error(f"NGX data unavailable. HTTP status: {d.get('status','N/A')} | Reason: {d.get('error','Unknown error')}")
    st.caption(f"Endpoint: {d.get('endpoint',NGX+'/api/ngxdata/stocks')}")
    st.dataframe(df[df.source=="NGX Pulse"][["asset","name","price","change_pct","signal","confidence","status"]],use_container_width=True,hide_index=True)
with tabs[4]:st.dataframe(df[df.asset.isin(SIX_ASSETS)][["asset","name","price","change_pct","signal","confidence","status"]],use_container_width=True,hide_index=True)
with tabs[5]:
    st.dataframe(pd.DataFrame([{"source":n,"HTTP status":d.get("status"),"request time (s)":d.get("elapsed"),"records":d.get("count",""),"status":"OK" if not d.get("error") else "FAILED","endpoint":d.get("endpoint",""),"exact reason":d.get("error") or "Request successful"} for n,d in diags]),use_container_width=True,hide_index=True)
with tabs[6]:
    h=history()
    if h.empty:st.info("No paper-trade snapshots recorded yet.")
    else:
        st.dataframe(h.tail(500),use_container_width=True,hide_index=True)
        st.download_button("⬇️ Download paper history CSV",h.to_csv(index=False),file_name="paper_trade_history.csv",mime="text/csv")
