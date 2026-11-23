"""Daily downside-risk briefing for the user's focused stock watchlist.

This is a once-daily, research-only warning report, not continuous surveillance
or a price-prediction engine. Missing/stale data is shown explicitly.
"""
import html
import os
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from stock_news_sources import fetch_market_news
from telegram_bot import send, split_html, kobo_ngx

UA = {"User-Agent": "AI-Market-Intelligence-Risk-Monitor/1.0"}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
WATCHLIST = [
    {"symbol": "NVDA", "name": "NVIDIA", "market": "US", "yahoo": "NVDA"},
    {"symbol": "MTNN", "name": "MTN Nigeria", "market": "NGX", "yahoo": None},
    {"symbol": "TIP", "name": "The Initiates Plc", "market": "NGX", "yahoo": None},
    {"symbol": "GTCO", "name": "GTCO", "market": "NGX", "yahoo": None},
    {"symbol": "DANGCEM", "name": "Dangote Cement", "market": "NGX", "yahoo": None},
]
ALIASES = {
    "NVDA": ("nvidia", "nvda", "jensen huang"),
    "MTNN": ("mtn nigeria", "mtn nigeria plc", "mtnn"),
    "TIP": ("the initiates plc", "the initiates", "initiates plc"),
    "GTCO": ("gtco", "guaranty trust holding company", "guaranty trust", "gtbank"),
    "DANGCEM": ("dangote cement", "dangote cement plc", "dangcem"),
}
MARKET_CONTEXT_TERMS = (
    "ngx sell-off", "ngx selloff", "stock market", "equity market", "equities",
    "shares", "share price", "capital market", "market sell-off", "market selloff",
    "market rally", "market retreat", "market capitalization", "market capitalisation",
    "investor sentiment", "foreign portfolio", "bond yield", "treasury bills",
    "monetary policy", "interest rate", "inflation", "naira", "exchange rate",
    "foreign exchange", "fx market", "crude oil", "oil price", "federal reserve",
    "central bank", "cbn",
)
MARKET_GEO_TERMS = ("nigeria", "nigerian", "ngx", "naira", "cbn", "us market", "wall street", "federal reserve", "global markets")
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


def _news_for_watchlist(limit=250):
    return fetch_market_news(limit=limit)


def _matches_news(story, item):
    """Match issuer-specific evidence only; broad macro news is reported separately."""
    # Use the headline, not the full article description: publisher boilerplate
    # can mention Nigeria/markets even when the story itself is unrelated.
    text = " ".join(str(story.get("title", "")).lower().split())
    for alias in ALIASES[item["symbol"]]:
        # Phrase aliases use literal matching; ticker-like aliases require token
        # boundaries so short symbols such as TIP do not match ordinary words.
        if len(alias) <= 5:
            import re
            if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text):
                return True
        elif alias in text:
            return True
    return False


def _is_market_context(story):
    """Keep only broad-market headlines, never individual issuer filings."""
    if story.get("category") == "official":
        return False
    # Use headline text only; article descriptions and publisher suffixes can
    # make an issuer filing look like broad market coverage.
    text = " ".join(str(story.get("title", "")).lower().split())
    has_market_signal = any(term in text for term in MARKET_CONTEXT_TERMS)
    has_market_geography = any(term in text for term in MARKET_GEO_TERMS)
    return has_market_signal and has_market_geography


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
    if (daily is not None and daily <= -3) or (weekly is not None and weekly <= -5):
        return "MODERATE"
    if daily is None and weekly is None:
        return "UNKNOWN"
    return "LOW"


def _data_confidence(item, news_meta):
    price_coverage = "available" if item.get("price") is not None else "missing"
    history_coverage = "complete" if item.get("daily") is not None and item.get("weekly") is not None else "partial"
    providers = news_meta.get("providers", [])
    successful = sum(1 for p in providers if p.get("status") == "ok")
    if price_coverage == "missing" or successful == 0:
        return "LOW", price_coverage, history_coverage
    if history_coverage == "partial" or successful < len(providers):
        return "MEDIUM", price_coverage, history_coverage
    return "HIGH", price_coverage, history_coverage


def build_report(now=None):
    now = now or datetime.now(timezone.utc)
    stories, news_meta = _news_for_watchlist()
    # Kobo Terminal is the primary NGX source. Yahoo .LG symbols are not
    # canonical NGX tickers and are intentionally not queried.
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
        if item["market"] == "NGX":
            fallback = kobo_data.get(item["symbol"])
            if fallback and fallback.get("price") is not None and not fallback.get("stale"):
                quote_data, error = {
                    "price": float(fallback["price"]),
                    "currency": "NGN",
                    "daily": fallback.get("change"),
                    "weekly": fallback.get("weekly"),
                    "weekly_label": "7-day",
                    "timestamp": fallback.get("timestamp") or now,
                    "timestamp_label": fallback.get("timestamp_label") or "provider timestamp unavailable",
                    "source": fallback.get("source", kobo_source),
                }, None
            else:
                quote_data, error = None, (
                    "Kobo Terminal API key is not configured" if kobo_status == "NO_KEY"
                    else "Kobo Terminal returned no matching quote"
                    if kobo_status == "EMPTY"
                    else "Kobo Terminal quote snapshot is stale"
                    if kobo_status == "STALE"
                    else kobo_status if str(kobo_status).startswith("ERROR")
                    else "Kobo Terminal request failed"
                )
        else:
            quote_data, error = _get_history(item["yahoo"])
        if quote_data:
            quote_data["news"] = [s for s in stories if _matches_news(s, item)][:4]
            quote_data["risk"] = _risk(quote_data, stories)
        else:
            quote_data = {"news": [s for s in stories if _matches_news(s, item)][:4], "risk": "UNKNOWN", "error": error}
        confidence, price_coverage, history_coverage = _data_confidence(quote_data, news_meta)
        quote_data["data_confidence"] = confidence
        quote_data["price_coverage"] = price_coverage
        quote_data["history_coverage"] = history_coverage
        quote_data["unusual_move"] = bool(quote_data.get("daily") is not None and abs(quote_data["daily"]) >= 10)
        results.append((item, quote_data))
        if quote_data.get("price") is None:
            lines.append(f"⚪ <b>{html.escape(item['name'])} ({item['symbol']})</b> — price unavailable")
            lines.append(f"  <i>Reason: {html.escape(str(quote_data.get('error', 'No verified quote'))[:180])}</i>")
        else:
            daily = quote_data.get("daily")
            weekly = quote_data.get("weekly")
            daily_text = "N/A" if daily is None else f"{daily:+.2f}%"
            weekly_text = "N/A" if weekly is None else f"{weekly:+.2f}%"
            weekly_label = quote_data.get("weekly_label", "5-session")
            icon = "🔴" if quote_data["risk"] == "HIGH" else "🟠" if quote_data["risk"] == "MODERATE" else "🟢"
            stamp = quote_data.get("timestamp_label") or quote_data["timestamp"].strftime("%Y-%m-%d %H:%M UTC")
            lines.append(
                f"{icon} <b>{html.escape(item['name'])} ({item['symbol']})</b> — "
                f"{_money(quote_data['price'], quote_data['currency'])}"
            )
            unusual = " • ⚡ UNUSUAL MOVE" if quote_data.get("unusual_move") else ""
            lines.append(f"  Daily: {daily_text} • {weekly_label}: {weekly_text} • Downside risk: <b>{quote_data['risk']}</b>{unusual}")
            lines.append(f"  Data confidence: <b>{confidence}</b> • Price: {price_coverage} • History: {history_coverage}")
            lines.append(f"  <i>Quote timestamp: {stamp} • {html.escape(quote_data['source'])}</i>")
        if quote_data.get("news"):
            for story in quote_data["news"][:2]:
                title = html.escape(str(story.get("title", "Untitled"))[:220])
                url = html.escape(str(story.get("url", "")), quote=True)
                source = html.escape(str(story.get("source", story.get("provider", "Unknown"))))
                category = html.escape(str(story.get("category", "news")).upper())
                lines.append(f'  • <a href="{url}">{title}</a> <i>({source} • {category})</i>')
        elif quote_data.get("price") is not None:
            lines.append("  <i>No matching recent headline found in configured feeds; this is not proof that no risk exists.</i>")
        lines.append("")
    context_stories = [s for s in stories if _is_market_context(s)][:3]
    if context_stories:
        lines += ["<b>MARKET CONTEXT — NOT COMPANY-SPECIFIC</b>"]
        for story in context_stories:
            title = html.escape(str(story.get("title", "Untitled"))[:220])
            url = html.escape(str(story.get("url", "")), quote=True)
            source = html.escape(str(story.get("source", story.get("provider", "Unknown"))))
            lines.append(f'  • <a href="{url}">{title}</a> <i>({source} • broad context)</i>')
        lines.append("")

    lines += [
        "<b>ALERT RULES</b>",
        "• Daily decline ≥3%: price-weakness flag.",
        "• 5-session (US) / 7-day (NGX) decline ≥5%: weekly weakness flag.",
        "• High-impact company headline: elevated review flag.",
        "• Unusual moves of either direction receive a separate event-review flag.",
        "• Thresholds trigger review, not an automatic sell signal.",
        "• An unusual upward move is not, by itself, a downside-risk signal.",
        "",
        "<b>DATA LIMITATIONS</b>",
        "• NGX quotes use Kobo Terminal daily market snapshots; US quotes use Yahoo Finance daily bars. Each source timestamp is shown separately.",
        "• News: Nairametrics publisher RSS; Reuters headlines via Google News RSS; official issuer, NGX and SEC Nigeria domain-filtered discovery; Infera retained as a supplemental feed.",
        "• Reuters has no working public RSS feed; Google News is the discovery transport, not the publisher.",
        "• Official discovery depends on indexing and is not a complete filing feed.",
        "• No matching headline does not prove no risk; provider errors and empty feeds are shown below.",
        "• Valuation is not scored until a consistent, timestamped valuation feed is configured.",
        f"<i>News: {html.escape(str(news_meta.get('provider', 'Unknown')))} • status: {html.escape(str(news_meta.get('status', 'unknown')))} • usable stories: {news_meta.get('count', 0)}</i>",
        *[f"  • {html.escape(p.get('provider', 'provider'))}: {html.escape(p.get('status', 'unknown'))} ({p.get('count', 0)} stories)" for p in news_meta.get('providers', [])],
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
