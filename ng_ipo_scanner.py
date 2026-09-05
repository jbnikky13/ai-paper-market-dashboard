import html
import json
from datetime import datetime, timezone
from pathlib import Path
from ng_prospectus_intelligence import discover_links, analyze

STATE = Path("ng_ipo_seen.json")
SOURCE_PAGES = [
    "https://www.sec.gov.ng/for-investors/keep-track-of-circulars/",
    "https://www.sec.gov.ng/get-listed/",
    "https://ngxgroup.com/exchange/raise-capital/notices-to-issuers/",
    "https://ngxgroup.com/exchange/raise-capital/listing-your-company/",
    "https://www.invest.ngxgroup.com/",
]


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def save_state(x):
    STATE.write_text(json.dumps(x, indent=2))


def scan():
    state = load_state()
    fresh = []
    for page in SOURCE_PAGES:
        for item in discover_links(page):
            key = f"{item.get('url','')}|{item.get('title','')}"
            if state.get(key):
                continue
            intelligence = analyze(item["url"])
            item["checked_at"] = datetime.now(timezone.utc).isoformat()
            if intelligence:
                item.update(intelligence)
            state[key] = item["checked_at"]
            fresh.append(item)
    save_state(state)
    return fresh


def telegram_text(x):
    fields = ("audited_profit", "operating_cash_flow", "debt", "refining_margins", "crude_supply_terms", "expansion_costs", "use_of_proceeds")
    lines = [
        "<b>🚨 🇳🇬 IPO / PUBLIC-OFFER ALERT</b>",
        f"<b>{html.escape(x.get('title','Capital-market document'))}</b>",
        f"Stage: <b>{html.escape(str(x.get('stage','OFFICIAL-SOURCE SIGNAL')))}</b>",
        "Status: <b>OFFICIAL-SOURCE DOCUMENT — VERIFY APPROVAL</b>",
    ]
    for k in fields:
        label = k.replace('_', ' ').title()
        lines.append(f"<b>{label}:</b> {html.escape(str(x.get(k) or 'N/A'))}")
    for label, key in (("Audited profit", "audited_profit_value"), ("Operating cash flow", "operating_cash_flow_value"), ("Debt", "debt_value"), ("IPO proceeds", "ipo_proceeds_value"), ("Offer price", "offer_price_value"), ("Implied offer value", "implied_offer_value")):
        if x.get(key) is not None:
            lines.append(f"<b>{label}:</b> {x[key]:,.2f}")
    if x.get('cash_conversion') is not None:
        lines.append(f"<b>Cash conversion:</b> {x['cash_conversion']:.2f}x")
    if x.get('debt_to_profit') is not None:
        lines.append(f"<b>Debt / profit:</b> {x['debt_to_profit']:.2f}x")
    if x.get('pe') is not None:
        lines.append(f"<b>P/E:</b> {x['pe']:.2f}x")
    lines += [
        f"<b>IPO Quality Score:</b> {x.get('ipo_quality_score','N/A')}/100",
        f"<b>Disclosure coverage:</b> {x.get('disclosure_coverage','N/A')}%",
        f"<b>Verification:</b> {html.escape(str(x.get('verification','N/A')))}",
        f"<b>Source:</b> {html.escape(x.get('source_url',x.get('url','')))}",
    ]
    return '\n'.join(lines)
