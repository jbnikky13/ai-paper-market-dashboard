"""Daily downside-risk briefing for the user's focused stock watchlist.

This is a once-daily, research-only warning report, not continuous surveillance
or a price-prediction engine. Missing/stale data is shown explicitly.
"""
import html
import os
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from business_news import fetch_infera_business_topic
from telegram_bot import send, split_html, kobo_ngx

UA = {"User-Agent": "AI-Market-Intelligence-Risk-Monitor/1.0"}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
WATCHLIST = [
    {"symbol": "NVDA", "name": "NVIDIA", "market": "US", "yahoo": "NVDA"},
    {"symbol": "MTNN", "name": "MTN Nigeria", "market": "NGX", "yahoo": "MTNN.LG"},
    {"symbol": "TIP", "name": "The Initiates Plc", "market": "NGX", "yahoo": "TIP.LG"},
    {"symbol": "GTCO", "name": "GTCO", "market": "NGX", "yahoo": "GTCO.LG"},
    {"symbol": "DANGCEM", "name": "Dangote Cement", "market": "NGX", "yahoo": "DANGCEM.LG"},
]
ALIASES = {
    "NVDA": ("nvidia", "nvda", "jensen huang", "ai chip"),
    "MTNN": ("mtn nigeria", "mtn group", "mt n nigeria", "mt n"),
    "TIP": ("the initiates", "tip plc", "initiates plc"),
    "GTCO": ("gtco", "guaranty trust", "gtbank", "guaranty trust holding"),
    "DANGCEM": ("dangote cement", "dangote group", "dangote"),
}
MACRO_TERMS = (
    "central bank", "cbn", "interest rate", "inflation", "naira", "foreign exchange",
    "fx market", "exchange rate", "tariff", "export restriction", "fed decision",
    "federal reserve", "oil price", "crude oil", "energy cost", "regulatory",
    "regulation", "tax policy", "capital requirement", "telecom regulation",
)
HIGH_IMPACT_TERMS = (
    "profit warning", "guidance cut", "dividend cut", "dividend suspended",
    "regulatory sanction", "investigation", "fraud", "default", "downgrade",
    "recall", "lawsuit", "license suspended", "capital shortfall",
)


def _get_history(symbol):
    """Return completed daily bars and source timestamp; no synthetic values."""
    try:
        response = requests.get(
            f"{YAHOO_CHART}/{quote(symbol, safe='')}",
            params={"range": "1mo", "interval": "1d", "includePrePost": "false"},
            headers=UA,
            timeout=20,
        )
        response.raise_for_status()
        result = response.json().get("chart", {}).get("result") or []
        if not result:
            return None, "No chart result"
        item = result[0]
        quote_data = item.get("indicators", {}).get("quote", [{}])[0]
        timestamps = item.get("timestamp") or []
        closes_raw = quote_data.get("close") or []
        bars = [(int(ts), float(close)) for ts, close in zip(timestamps, closes_raw) if ts and close is not None]
        if not bars:
            return None, "No completed daily closes"
        meta = item.get("meta", {})
        closes = [bar[1] for bar in bars]
        latest = meta.get("regularMarketPrice")
        # Use the latest daily close for a stable close-to-close comparison.
        latest = float(latest) if latest is not None else closes[-1]
        previous = closes[-2] if len(closes) >= 2 else None
        daily = ((closes[-1] / previous) - 1) * 100 if previous else None
        weekly = ((closes[-1] / closes[-6]) - 1) * 100 if len(closes) >= 6 else None
        stamp = int(meta.get("regularMarketTime") or bars[-1][0])
        currency = str(meta.get("currency") or ("NGN" if symbol.endswith(".LG") else "USD"))
        name = str(meta.get("longName") or meta.get("shortName") or symbol)
        return {
            "price": latest,
            "currency": currency,
            "daily": daily,
            "weekly": weekly,
            "timestamp": datetime.fromtimestamp(stamp, timezone.utc),
            "source": "Yahoo Finance daily chart",
            "name": name,
        }, None
    except Exception as exc:
        return None, str(exc)


def _news_for_watchlist(limit=60):
    stories, meta = fetch_infera_business_topic(limit=limit)
    return stories, meta


def _matches_news(story, item):
    text = f"{story.get('title', '')} {story.get('description', '')}".lower()
    aliases = ALIASES[item["symbol"]]
    company_match = any(alias in text for alias in aliases)
    macro_match = any(term in text for term in MACRO_TERMS)
    # Global macro stories are relevant to all holdings, but remain labelled broad-market context.
    return company_match or macro_match


def _money(value, currency):
    symbol = "$" if currency == "USD" else "₦" if currency == "NGN" else f"{currency} "
    return f"{symbol}{value:,.2f}"


def _risk(item, stories):
    daily = item.get("daily")
    weekly = item.get("weekly")
    related = item.get("news", [])
    high_news = any(
        any(term in f"{x.get('title', '')} {x.get('description', '')}".lower() for term in HIGH_IMPACT_TERMS)
        for x in related
    )
    if high_news or (daily is not None and daily <= -5) or (weekly is not None and weekly <= -10):
        return "HIGH"
    if (daily is not None and daily <= -3) or (weekly is not None and weekly <= -5) or related:
        return "MODERATE"
    return "LOW"


def build_report(now=None):
    now = now or datetime.now(timezone.utc)
    stories, news_meta = _news_for_watchlist()
    # Reuse the configured NGX provider if Yahoo has no usable .LG daily chart.
    # Kobo may not expose historical bars or an exchange timestamp; keep those N/A.
    kobo_data, kobo_status, kobo_source = kobo_ngx()
    lines = [
        "<b>🛡️ DAILY STOCK RISK WATCH</b>",
        f"<i>Generated {now.strftime('%Y-%m-%d %H:%M UTC')}</i>",
        "<i>Daily research snapshot only — not continuous real-time surveillance. It cannot guarantee advance notice of sudden market movements.</i>",
        "",
        "<b>WATCHLIST</b>",
    ]
    results = []
    for item in WATCHLIST:
        quote_data, error = _get_history(item["yahoo"])
        if not quote_data and item["market"] == "NGX":
            fallback = kobo_data.get(item["symbol"])
            if fallback and fallback.get("price") is not None:
                quote_data = {
                    "price": float(fallback["price"]),
                    "currency": "NGN",
                    "daily": fallback.get("change"),
                    "weekly": None,
                    "timestamp": now,
                    "timestamp_label": f"retrieved {now.strftime('%Y-%m-%d %H:%M UTC')}; provider quote timestamp unavailable",
                    "source": kobo_source,
                }
        if quote_data:
            quote_data["news"] = [s for s in stories if _matches_news(s, item)][:4]
            quote_data["risk"] = _risk(quote_data, stories)
        else:
            quote_data = {"news": [s for s in stories if _matches_news(s, item)][:4], "risk": "DATA UNAVAILABLE", "error": error}
        results.append((item, quote_data))
        if quote_data.get("price") is None:
            lines.append(f"⚪ <b>{html.escape(item['name'])} ({item['symbol']})</b> — price unavailable")
            lines.append(f"  <i>Reason: {html.escape(str(quote_data.get('error', 'No verified quote'))[:180])}</i>")
        else:
            daily = quote_data.get("daily")
            weekly = quote_data.get("weekly")
            daily_text = "N/A" if daily is None else f"{daily:+.2f}%"
            weekly_text = "N/A" if weekly is None else f"{weekly:+.2f}%"
            icon = "🔴" if quote_data["risk"] == "HIGH" else "🟠" if quote_data["risk"] == "MODERATE" else "🟢"
            stamp = quote_data.get("timestamp_label") or quote_data["timestamp"].strftime("%Y-%m-%d %H:%M UTC")
            lines.append(
                f"{icon} <b>{html.escape(item['name'])} ({item['symbol']})</b> — "
                f"{_money(quote_data['price'], quote_data['currency'])}"
            )
            lines.append(f"  Daily: {daily_text} • 5-session: {weekly_text} • Risk: <b>{quote_data['risk']}</b>")
            lines.append(f"  <i>Quote timestamp: {stamp} • {html.escape(quote_data['source'])}</i>")
        if quote_data.get("news"):
            for story in quote_data["news"][:2]:
                title = html.escape(str(story.get("title", "Untitled"))[:220])
                url = html.escape(str(story.get("url", "")), quote=True)
                source = html.escape(str(story.get("source", "Infera")))
                lines.append(f'  • <a href="{url}">{title}</a> <i>({source})</i>')
        elif quote_data.get("price") is not None:
            lines.append("  <i>No matching material headline found in the current Infera business feed.</i>")
        lines.append("")
    lines += [
        "<b>ALERT RULES</b>",
        "• Daily decline ≥3%: price-weakness flag.",
        "• Five-session decline ≥5%: weekly weakness flag.",
        "• High-impact company headline: elevated review flag.",
        "• Thresholds trigger review, not an automatic sell signal.",
        "",
        "<b>DATA LIMITATIONS</b>",
        "• Quotes are daily-bar data and may be delayed or stale; each timestamp is shown separately.",
        "• News is drawn from the Infera Business Topic feed; absence of a headline does not prove absence of risk.",
        "• Valuation is not scored in this first version because a consistent, timestamped valuation feed is not configured.",
        f"<i>News feed: {html.escape(str(news_meta.get('provider', 'Infera Business Topic')))} • status: {html.escape(str(news_meta.get('status', 'unknown')))}</i>",
        "",
        "<i>Research and monitoring only. Not investment advice or a prediction of exact price bottoms.</i>",
    ]
    return lines, results


def main():
    lines, results = build_report()
    messages = split_html("\n".join(lines), limit=3500)
    ok, result = send(messages)
    print(result)
    if not ok:
        raise SystemExit(1)
    for item, data in results:
        print(f"{item['symbol']}: {data.get('risk')} — {data.get('price', 'N/A')}")


if __name__ == "__main__":
    main()
