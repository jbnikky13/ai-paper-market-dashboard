import os, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
import streamlit as st
from business_news import fetch_africa_business_news

st.set_page_config(page_title="AI Market Intelligence v5.0", page_icon="📊", layout="wide")
VERSION = "v5.0"
DASHBOARD_URL = "https://ai-paper-market-dashboard.streamlit.app/"
DATA_DIR = Path(os.getenv("MARKET_DATA_DIR", ".market_data")); DATA_DIR.mkdir(exist_ok=True)
PAPER_FILE = DATA_DIR / "market_history.csv"
CG = "https://api.coingecko.com/api/v3"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
NGX = "https://www.ngxpulse.ng"

CRYPTO = {"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB","ripple":"XRP","dogecoin":"DOGE","chainlink":"LINK","avalanche-2":"AVAX"}
US_ASSETS = {"NVDA":"NVIDIA","AMD":"AMD","AVGO":"Broadcom","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AAPL":"Apple","QQQ":"Nasdaq-100 ETF","SPY":"S&P 500 ETF"}
NGX_ASSETS = {"DANGCEM":"Dangote Cement","GTCO":"GTCO","ZENITHBANK":"Zenith Bank","ACCESSCORP":"Access Holdings","UBA":"UBA","FIRSTHOLDCO":"First HoldCo","MTNN":"MTN Nigeria","AIRTELAFRI":"Airtel Africa","BUAFOODS":"BUA Foods","BUACEMENT":"BUA Cement","SEPLAT":"Seplat Energy","ARADEL":"Aradel Holdings","PRESCO":"Presco","NB":"Nigerian Breweries","FLOURMILL":"Flour Mills"}
# Yahoo's NGX suffix is .LG for many Nigerian listings and is used only as a fallback.
NGX_YAHOO = {s: f"{s}.LG" for s in NGX_ASSETS}
SIX_ASSETS = {"3308.HK":"ZhongJi InnoLight","042700.KS":"Hanmi Semiconductor","009150.KS":"Samsung Electro-Mechanics","066570.KS":"LG Electronics","035420.KS":"NAVER","069500.KS":"KODEX 200 ETF"}

def secret(name):
    try:
        v = st.secrets.get(name)
        if v is not None: return str(v)
    except Exception: pass
    return os.getenv(name, "")

NGX_KEY = secret("NGXPULSE_API_KEY")
CG_KEY = secret("COINGECKO_DEMO_API_KEY")
GNEWS_KEY = secret("GNEWS_API_KEY")

def get(url, params=None, headers=None, timeout=15):
    try:
        r = requests.get(url, params=params, headers=headers or {"User-Agent":"AI-Market-Intelligence/5.0"}, timeout=timeout)
        return r, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=300, show_spinner=False)
def crypto_data():
    headers = {"User-Agent":"AI-Market-Intelligence/5.0"}
    if CG_KEY: headers["x-cg-demo-api-key"] = CG_KEY
    r, err = get(f"{CG}/simple/price", {"ids":",".join(CRYPTO),"vs_currencies":"usd","include_24hr_change":"true"}, headers)
    if not r or not r.ok: return {}, err or (r.text[:300] if r else "No response")
    try: return r.json(), None
    except Exception as e: return {}, str(e)

@st.cache_data(ttl=180, show_spinner=False)
def yahoo(symbol):
    r, err = get(f"{YAHOO}/{symbol}", {"range":"1mo","interval":"1d","includePrePost":"false"}, {"User-Agent":"Mozilla/5.0"})
    if not r or not r.ok: return None, err or (r.text[:300] if r else "No response")
    try:
        z = r.json()["chart"]["result"][0]; meta = z.get("meta", {})
        closes = [float(x) for x in z.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
        p = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
        prev = meta.get("previousClose") or (closes[-2] if len(closes)>1 else None)
        if p is None: return None, "Price unavailable"
        change = ((float(p)/float(prev))-1)*100 if prev else None
        return {"price":float(p),"change":change,"closes":closes}, None
    except Exception as e: return None, str(e)

@st.cache_data(ttl=300, show_spinner=False)
def ngx_primary():
    endpoint = f"{NGX}/api/ngxdata/stocks"
    if not NGX_KEY: return {}, {"status":None,"source":"NGX Pulse","error":"NGXPULSE_API_KEY is not configured."}
    r, err = get(endpoint, headers={"X-API-Key":NGX_KEY,"Content-Type":"application/json","User-Agent":"AI-Market-Intelligence/5.0"})
    if not r or not r.ok: return {}, {"status":r.status_code if r else None,"source":"NGX Pulse","error":err or (r.text[:400] if r else "No response")}
    try:
        body = r.json(); rows = body if isinstance(body,list) else (body.get("data") or body.get("stocks") or []); out={}
        for x in rows:
            if not isinstance(x,dict): continue
            s=str(x.get("symbol") or "").upper().strip()
            if not s: continue
            try: p=float(x.get("current_price")) if x.get("current_price") is not None else None
            except Exception: p=None
            try: ch=float(x.get("change_percent")) if x.get("change_percent") is not None else None
            except Exception: ch=None
            out[s]={"name":x.get("name") or s,"price":p,"change":ch,"status":"LIVE"}
        return out, {"status":200,"source":"NGX Pulse","error":None,"count":len(out)}
    except Exception as e: return {}, {"status":200,"source":"NGX Pulse","error":str(e)}

def build_ngx():
    primary, diag = ngx_primary()
    if primary:
        return primary, {**diag,"mode":"LIVE"}
    out={}; fallback_ok=0
    for symbol, yahoo_symbol in NGX_YAHOO.items():
        x, _ = yahoo(yahoo_symbol)
        if x and x.get("price") is not None:
            out[symbol]={"name":NGX_ASSETS[symbol],"price":x["price"],"change":x.get("change"),"status":"FALLBACK"}
            fallback_ok += 1
    if out:
        return out, {**diag,"mode":"FALLBACK","fallback_count":fallback_ok,"fallback_note":"NGX Pulse unavailable; Yahoo Finance fallback used."}
    return {}, {**diag,"mode":"UNAVAILABLE","fallback_count":0}

def outlook(change, closes=None):
    if change is None: return "NO DATA", 0, "Insufficient price data"
    c=float(change); score=50
    if c > 0: score += min(20, c*4)
    else: score += max(-20, c*4)
    reasons=[]
    if c >= 2: label="BULLISH"; reasons.append("positive daily momentum")
    elif c <= -2: label="BEARISH"; reasons.append("negative daily momentum")
    else: label="NEUTRAL"; reasons.append("limited daily directional move")
    if closes and len(closes)>=10:
        sma5=sum(closes[-5:])/5; sma10=sum(closes[-10:])/10
        if closes[-1] > sma5 > sma10:
            score += 12; reasons.append("price above rising short-term averages")
        elif closes[-1] < sma5 < sma10:
            score -= 12; reasons.append("price below falling short-term averages")
        elif closes[-1] > sma10: score += 4; reasons.append("price above 10-day average")
    return label, max(50,min(95,round(score))), "; ".join(reasons)

def fmt(p, currency="$"):
    if p is None or pd.isna(p): return "N/A"
    return f"₦{p:,.2f}" if currency=="₦" else (f"${p:.6f}" if p < 1 else f"${p:,.2f}")

def collect():
    rows=[]; diagnostics=[]
    c, err=crypto_data(); diagnostics.append(("CoinGecko", {"status":200 if c else None,"error":err}))
    for cid,symbol in CRYPTO.items():
        x=c.get(cid,{})
        label,conf,reason=outlook(x.get("usd_24h_change"))
        rows.append({"asset":symbol,"name":symbol,"market":"Crypto","source":"CoinGecko","price":x.get("usd"),"change_pct":x.get("usd_24h_change"),"outlook":label,"confidence":conf,"reason":reason,"currency":"$","status":"LIVE" if x.get("usd") is not None else "NO DATA"})
    for symbol,name in US_ASSETS.items():
        x,err=yahoo(symbol); diagnostics.append((f"Yahoo:{symbol}",{"status":200 if x else None,"error":err}))
        label,conf,reason=outlook(x.get("change") if x else None,x.get("closes") if x else None)
        rows.append({"asset":symbol,"name":name,"market":"US / ETFs","source":"Yahoo Finance","price":x.get("price") if x else None,"change_pct":x.get("change") if x else None,"outlook":label,"confidence":conf,"reason":reason,"currency":"$","status":"LIVE" if x else "NO DATA"})
    ngx,diag=build_ngx(); diagnostics.append(("NGX",diag))
    for symbol,name in NGX_ASSETS.items():
        x=ngx.get(symbol); label,conf,reason=outlook(x.get("change") if x else None)
        rows.append({"asset":symbol,"name":x.get("name",name) if x else name,"market":"NGX","source":x.get("status","NO DATA") if x else diag.get("mode","UNAVAILABLE"),"price":x.get("price") if x else None,"change_pct":x.get("change") if x else None,"outlook":label,"confidence":conf,"reason":reason,"currency":"₦","status":x.get("status","NO DATA") if x else "NO DATA"})
    for symbol,name in SIX_ASSETS.items():
        x,err=yahoo(symbol); diagnostics.append((f"Yahoo:{symbol}",{"status":200 if x else None,"error":err}))
        label,conf,reason=outlook(x.get("change") if x else None,x.get("closes") if x else None)
        rows.append({"asset":symbol,"name":name,"market":"Asia / Six","source":"Yahoo Finance","price":x.get("price") if x else None,"change_pct":x.get("change") if x else None,"outlook":label,"confidence":conf,"reason":reason,"currency":"$","status":"LIVE" if x else "NO DATA"})
    return pd.DataFrame(rows), diagnostics

def save_history(df):
    if df.empty: return
    x=df[["asset","market","source","price","change_pct","outlook","confidence","status"]].copy(); x.insert(0,"timestamp",datetime.now(timezone.utc).isoformat())
    try:
        old=pd.read_csv(PAPER_FILE) if PAPER_FILE.exists() else pd.DataFrame()
        pd.concat([old,x],ignore_index=True).tail(10000).to_csv(PAPER_FILE,index=False)
    except Exception: pass

st.title("📊 AI Market Intelligence")
st.caption(f"{VERSION} • market outlook, ranked opportunities, Africa business intelligence • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
if st.button("🔄 Refresh market data & news"):
    st.cache_data.clear(); st.rerun()

df, diagnostics=collect(); save_history(df)
news, news_provider = fetch_africa_business_news(GNEWS_KEY, limit=15)

# This is a research-ranking layer, NOT a trade/setup engine.
st.subheader("🏆 Ranked Market Opportunities")
st.caption("Ranking is for research attention only. It does not provide entries, stop-losses, take-profits, or trade instructions.")
rank=df[df.status.isin(["LIVE","FALLBACK"])].copy()
rank["attention"]=(rank["confidence"] + rank["change_pct"].fillna(0).abs().clip(upper=8)*2).round(0)
rank=rank.sort_values(["attention","confidence"],ascending=False).head(10)
for i,(_,r) in enumerate(rank.iterrows(),1):
    icon="🟢" if r.outlook=="BULLISH" else ("🔴" if r.outlook=="BEARISH" else "🟡")
    ch="N/A" if pd.isna(r.change_pct) else f"{r.change_pct:+.2f}%"
    st.markdown(f"**#{i} {icon} {r.asset} — {r.name}** · {r.market} · {r.outlook} · confidence {int(r.confidence)}% · {ch}")
    st.caption(r.reason)

st.divider()
tabs=st.tabs(["📈 All Markets","₿ Crypto","🇺🇸 US / ETFs","🇳🇬 NGX","🌏 Asia / Six","🌍 Africa Business News","🧪 Diagnostics","📝 History"])
with tabs[0]:
    v=df.copy(); v["price"]=v.apply(lambda r:fmt(r.price,r.currency),axis=1); v["change_pct"]=v.change_pct.map(lambda x:"N/A" if pd.isna(x) else f"{x:+.2f}%")
    st.dataframe(v[["asset","name","market","source","price","change_pct","outlook","confidence","status"]],use_container_width=True,hide_index=True)
with tabs[1]: st.dataframe(df[df.market=="Crypto"],use_container_width=True,hide_index=True)
with tabs[2]: st.dataframe(df[df.market=="US / ETFs"],use_container_width=True,hide_index=True)
with tabs[3]:
    diag=next((d for n,d in diagnostics if n=="NGX"),{})
    mode=diag.get("mode")
    if mode=="LIVE": st.success(f"NGX LIVE — {diag.get('count',0)} records from NGX Pulse.")
    elif mode=="FALLBACK": st.warning(f"NGX FALLBACK — NGX Pulse unavailable; {diag.get('fallback_count',0)} symbols loaded from Yahoo Finance.")
    else: st.error(f"NGX UNAVAILABLE — {diag.get('error','Unknown error')}")
    st.dataframe(df[df.market=="NGX"],use_container_width=True,hide_index=True)
with tabs[4]: st.dataframe(df[df.market=="Asia / Six"],use_container_width=True,hide_index=True)
with tabs[5]:
    st.success(f"News provider: {news_provider} • Nigeria/Africa business focus • irrelevant general-interest stories filtered")
    if not news: st.info("No relevant Africa business stories were returned.")
    for a in news:
        title=a.get("title",""); url=a.get("url",""); src=a.get("source","Unknown"); rel=a.get("relevance",0); region=a.get("region","Africa")
        if url: st.markdown(f"**[{title}]({url})**")
        else: st.markdown(f"**{title}**")
        st.caption(f"{region} • {src} • relevance {rel}%")
with tabs[6]:
    for name,d in diagnostics:
        st.write(f"**{name}** — HTTP {d.get('status','N/A')} • {d.get('error') or 'OK'}")
with tabs[7]:
    if PAPER_FILE.exists():
        try: st.dataframe(pd.read_csv(PAPER_FILE).tail(500),use_container_width=True,hide_index=True)
        except Exception as e: st.error(str(e))
    else: st.info("No market history saved yet.")

st.info("ℹ️ Hypothetical paper-analysis only. This dashboard provides market intelligence and research rankings, not trade setups or execution.")
