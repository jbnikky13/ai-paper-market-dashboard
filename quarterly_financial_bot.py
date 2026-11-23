import html
import json
import os
import time
from pathlib import Path

import requests
from financials import get_quarterly_financials, fmt_money, short_text

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
STATE = Path("financial_seen.json")

TRACKED = {
    "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "MSFT": "Microsoft",
    "GOOGL": "Alphabet", "AMZN": "Amazon", "META": "Meta", "TSLA": "Tesla",
    "AAPL": "Apple", "3308.HK": "ZhongJi InnoLight",
    "042700.KS": "Hanmi Semiconductor", "009150.KS": "Samsung Electro-Mechanics",
    "066570.KS": "LG Electronics", "035420.KS": "NAVER",
}


def load_state():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def send(text, attempts=4):
    if not TOKEN or not CHANNEL:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID is missing")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for attempt in range(attempts):
        try:
            response = requests.post(
                url,
                json={"chat_id": CHANNEL, "text": text, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=30,
            )
            payload = response.json() if response.content else {}
            if response.ok and payload.get("ok") is True:
                return
            if response.status_code == 429:
                delay = payload.get("parameters", {}).get("retry_after", 10)
                time.sleep(max(1, int(delay)) + 1)
                continue
            if response.status_code >= 500 and attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 15))
                continue
            raise RuntimeError(
                f"Telegram rejected message: HTTP {response.status_code}: "
                f"{str(payload)[:400]}"
            )
        except (requests.RequestException, ValueError) as exc:
            if attempt + 1 >= attempts:
                raise RuntimeError(f"Telegram delivery failed: {exc}") from exc
            time.sleep(min(2 ** attempt, 15))
    raise RuntimeError("Telegram delivery failed after retries")


def line(label, value):
    return f"<b>{html.escape(label)}:</b> {html.escape(str(value or 'N/A'))}"


def render(row):
    q = row.get("quarter_end", "N/A")
    return "\n".join([
        f"<b>📑 {html.escape(row.get('company', ''))} ({html.escape(row.get('symbol', ''))})</b>",
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
    if not TOKEN or not CHANNEL:
        raise SystemExit("TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID is missing")

    state = load_state()
    pending_state = dict(state)
    changed = []
    for symbol, name in TRACKED.items():
        try:
            rows = get_quarterly_financials(symbol, name, limit=1)
            row = rows[0] if rows else None
        except Exception as exc:
            print(f"{symbol}: financial lookup failed: {exc}")
            continue
        if not row or row.get("quarter_end") in (None, "N/A"):
            continue
        # Include the filing URL and period so a new filing for an existing
        # quarter is not silently treated as already delivered.
        key = f"{row.get('quarter_end')}|{row.get('narrative_source') or row.get('source_url')}"
        if state.get(symbol) != key:
            changed.append(row)
            pending_state[symbol] = key

    if not changed:
        print("No new quarterly financial filing detected.")
        return

    header = (
        "<b>📊 AI MARKET INTELLIGENCE — NEW QUARTERLY FINANCIALS</b>\n"
        "<i>Figures are reported values; quarterly filings are normally unaudited.</i>\n\n"
    )
    batch = header
    messages = []
    for row in changed:
        block = render(row) + "\n\n"
        if len(batch) + len(block) > 3600 and batch.strip():
            messages.append(batch.rstrip())
            batch = ""
        batch += block
    if batch.strip():
        messages.append(batch.rstrip())

    # Do not advance the state until every Telegram message is acknowledged.
    for message in messages:
        send(message)
    STATE.write_text(json.dumps(pending_state, indent=2), encoding="utf-8")
    print(f"Sent {len(changed)} new quarterly financial update(s) in {len(messages)} message(s).")


if __name__ == "__main__":
    main()
