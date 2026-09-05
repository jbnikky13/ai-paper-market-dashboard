import pandas as pd
import streamlit as st

from financials import get_quarterly_financials, fmt_money, short_text

st.set_page_config(page_title="Quarterly Financial Intelligence", page_icon="📑", layout="wide")

US = {
    "NVDA":"NVIDIA", "AMD":"AMD", "AVGO":"Broadcom", "MSFT":"Microsoft", "GOOGL":"Alphabet",
    "AMZN":"Amazon", "META":"Meta", "TSLA":"Tesla", "AAPL":"Apple",
}
NGX = {
    "DANGCEM":"Dangote Cement", "GTCO":"GTCO", "ZENITHBANK":"Zenith Bank", "ACCESSCORP":"Access Holdings",
    "UBA":"UBA", "FIRSTHOLDCO":"First HoldCo", "MTNN":"MTN Nigeria", "AIRTELAFRI":"Airtel Africa",
    "BUAFOODS":"BUA Foods", "BUACEMENT":"BUA Cement", "SEPLAT":"Seplat Energy", "ARADEL":"Aradel Holdings",
    "PRESCO":"Presco", "NB":"Nigerian Breweries", "FLOURMILL":"Flour Mills",
}
SIX = {
    "3308.HK":"ZhongJi InnoLight", "042700.KS":"Hanmi Semiconductor", "009150.KS":"Samsung Electro-Mechanics",
    "066570.KS":"LG Electronics", "035420.KS":"NAVER", "069500.KS":"KODEX 200 ETF",
}

st.title("📑 Quarterly Financial Intelligence")
st.caption("Reported quarterly fundamentals + filing-derived narrative. Missing data is shown as N/A; the system never invents figures.")

universe = {**US, **NGX, **SIX}
symbol = st.selectbox("Company / asset", list(universe.keys()), format_func=lambda x: f"{universe[x]} ({x})")
limit = st.slider("Quarters to display", 1, 8, 4)

if st.button("🔄 Refresh quarterly data"):
    st.cache_data.clear()
    st.rerun()

with st.spinner("Loading quarterly financials and latest filing..."):
    rows = get_quarterly_financials(symbol, universe[symbol], limit=limit)

df = pd.DataFrame(rows)

if df.empty:
    st.warning("No quarterly data was returned by the configured public sources.")
    st.stop()

latest = df.iloc[0]
cols = st.columns(4)
cols[0].metric("Latest quarter", latest.get("quarter_end", "N/A"))
cols[1].metric("Reported profit", fmt_money(latest.get("profit")))
cols[2].metric("Operating cash flow", fmt_money(latest.get("operating_cash_flow")))
cols[3].metric("Debt", fmt_money(latest.get("debt")))

st.info(f"Profit status: {latest.get('profit_status','N/A')} • Source: {latest.get('data_source','N/A')}")

st.subheader("Quarter-by-quarter financials")
view = df[["quarter_end","revenue","profit","operating_cash_flow","debt","expansion_costs","profit_status","data_source"]].copy()
view.columns = ["Quarter end","Revenue","Profit","Operating cash flow","Debt","Expansion / capex","Profit status","Source"]
for c in ["Revenue","Profit","Operating cash flow","Debt","Expansion / capex"]:
    view[c] = view[c].map(fmt_money)
st.dataframe(view, use_container_width=True, hide_index=True)

st.subheader("Management / filing intelligence")
fields = [
    ("Refining margins", "refining_margins"),
    ("Crude-supply terms", "crude_supply_terms"),
    ("Expansion costs", "expansion_costs"),
    ("Exactly how money raised will be used", "money_raised_use"),
]
for label, key in fields:
    value = latest.get(key)
    st.markdown(f"**{label}**")
    if key == "expansion_costs":
        st.write(fmt_money(value))
    else:
        st.write(short_text(value, 1000))

if latest.get("narrative_source"):
    st.caption(f"Narrative source: {latest['narrative_source']}")

st.subheader("Important interpretation")
st.warning("A quarterly 10-Q is normally unaudited. The dashboard therefore labels quarterly profit as reported rather than falsely calling it audited. Audited figures are identified when they come from an annual 10-K. Narrative fields are only shown when a filing contains relevant language; otherwise they remain N/A.")
