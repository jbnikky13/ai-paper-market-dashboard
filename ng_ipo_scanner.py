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
    pending = set()
    for page in SOURCE_PAGES:
        for item in discover_links(page):
            key = f"{item.get('url','')}|{item.get('title','')}"
            if state.get(key) or key in pending:
                continue
            intelligence = analyze(item["url"])
            # Failed downloads are not marked seen; they can be retried.
            if not intelligence:
                continue
            item["checked_at"] = datetime.now(timezone.utc).isoformat()
            item.update(intelligence)
            pending.add(key)
            fresh.append(item)
    return fresh


def commit_delivered(items):
    state = load_state()
    for item in items:
        key = f"{item.get('url','')}|{item.get('title','')}"
        state[key] = item.get("checked_at") or datetime.now(timezone.utc).isoformat()
    save_state(state)


def telegram_text(x):
    fields = ("audited_profit", "operating_cash_flow", "debt", "refining_margins",
              "crude_supply_terms", "expansion_costs", "use_of_proceeds")
    lines = [
        "<b>🚨 🇳🇬 IPO / PUBLIC-OFFER ALERT</b>",
        f"<b>{html.escape(x.get('title','Capital-market document'))}</b>",
        f"Stage: <b>{html.escape(str(x.get('stage','OFFICIAL-SOURCE SIGNAL')))}</b>",
        "Status: <b>OFFICIAL-SOURCE DOCUMENT — VERIFY APPROVAL</b>",
        "<b>Financial figures:</b> Automated number extraction is not verified and is intentionally withheld. Check the original audited statements and offer document.",
    ]
    for key in fields:
        label = key.replace("_", " ").title()
        lines.append(f"<b>{label}:</b> {html.escape(str(x.get(key) or 'N/A'))}")
    lines += [
        f"<b>Verification:</b> {html.escape(str(x.get('verification','N/A')))}",
        f"<b>Source:</b> {html.escape(x.get('source_url',x.get('url','')))}",
    ]
    return '\\n'.join(lines)
