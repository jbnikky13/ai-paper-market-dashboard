import html
import json
import os
from pathlib import Path

from financials import get_quarterly_financials, fmt_money, short_text

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
STATE = Path("financial_seen.json")

TRACKED = {
    "NVDA":"NVIDIA", "AMD":"AMD", "AVGO":"Broadcom", "MSFT":"Microsoft", "GOOGL":"Alphabet",
    "AMZN":"Amazon", "META":"Meta", "TSLA":"Tesla", "AAPL":"Apple",
    "3308.HK":"ZhongJi InnoLight", "042700.KS":"Hanmi Semiconductor", "009150.KS":"Samsung Electro-Mechanics",
    "066570.KS":"LG Electronics", "035420.KS":"NAVER",
}


def load_state():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(data):
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def send(text):
    if not TOKEN or not CHANNEL:
        raise SystemExit("TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID is missing")
    import requests
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=25,
    )
    if not r.ok:
        raise SystemExit(f"Telegram HTTP {r.status_code}: {r.text[:500]}")


def line(label, value):
    return f"<b>{html.escape(label)}:</b> {html.escape(str(value or 'N/A'))}"


def render(row):
    q = row.get("quarter_end", "N/A")
    return "\n".join([
        f"<b>📑 {html.escape(row.get('company',''))} ({html.escape(row.get('symbol',''))})</b>",
        f"<i>Quarter ended {html.escape(q)}</i>",
        line("Reported profit", fmt_money(row.get("profit"))),
        line("Operating cash flow", fmt_money(row.get("operating_cash_flow"))),
        line("Debt", fmt_money(row.get("debt"))),
        line("Revenue", fmt_money(row.get("revenue"))),
        line("Expansion costs / capex", fmt_money(row.get("expansion_costs"))),
        line("Profit / audit status", row.get("profit_status")),
        line("Refining margins", short_text(row.get("refining_margins"), 500)),
        line("Crude-supply terms", short_text(row.get("crude_supply_terms"), 500)),
        line("Use of money raised", short_text(row.get("money_raised_use"), 650)),
        line("Source", row.get("narrative_source") or row.get("source_url") or row.get("data_source")),
    ])


def main():
    state = load_state()
    changed = []
    for symbol, name in TRACKED.items():
        try:
            row = get_quarterly_financials(symbol, name, limit=1)[0]
        except Exception as exc:
            print(f"{symbol}: financial lookup failed: {exc}")
            continue
        if row.get("quarter_end") in (None, "N/A"):
            continue
        key = f"{row.get('quarter_end')}|{row.get('narrative_source') or row.get('source_url')}"
        if state.get(symbol) != key:
            changed.append(row)
            state[symbol] = key
    save_state(state)

    if not changed:
        print("No new quarterly financial filing detected.")
        return

    header = "<b>📊 AI MARKET INTELLIGENCE — NEW QUARTERLY FINANCIALS</b>\n"
    header += "<i>Figures are reported values; quarterly filings are normally unaudited.</i>\n\n"
    # Telegram messages are kept comfortably below the platform limit.
    batch = header
    for row in changed:
        block = render(row) + "\n\n"
        if len(batch) + len(block) > 3800:
            send(batch.rstrip())
            batch = ""
        batch += block
    if batch.strip():
        send(batch.rstrip())
    print(f"Sent {len(changed)} new quarterly financial update(s).")


if __name__ == "__main__":
    main()
