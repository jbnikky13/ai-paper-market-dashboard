"""Fetch live stock-news feeds and print a Telegram-safe report preview.

This script never calls telegram_bot.send and requires no Telegram credentials.
"""
from datetime import datetime, timezone
from pathlib import Path
import sys

# When executed as `python scripts/preview_stock_risk_report.py`, Python puts
# scripts/ (not the repository root) on sys.path. Add the root so the project
# modules can be imported consistently in CI and local runs.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import stock_risk_monitor
from stock_news_sources import fetch_market_news
from telegram_bot import KOBO_KEY, kobo_ngx


def main():
    now = datetime.now(timezone.utc)
    stories, meta = fetch_market_news(now=now, limit=250)
    ngx_rows, ngx_status, ngx_source = kobo_ngx()
    print("=== LIVE NGX QUOTE PROVIDER RESULTS ===")
    print(f"Provider: {ngx_source} | status: {ngx_status} | API key configured: {bool(KOBO_KEY)}")
    for symbol in ("MTNN", "TIP", "GTCO", "DANGCEM"):
        row = ngx_rows.get(symbol)
        if row:
            print(f"{symbol}: price={row['price']} NGN | daily={row.get('change')}% | 7-day={row.get('weekly')}% | stale={row.get('stale')} | {row.get('timestamp_label')}")
        else:
            print(f"{symbol}: unavailable from NGX provider")
    print("=== LIVE NEWS PROVIDER RESULTS ===")
    print(f"Overall: {meta.get('status')} | stories: {meta.get('count')} | retrieved: {meta.get('retrieved_at')}")
    for provider in meta.get("providers", []):
        print(f"{provider.get('provider')} [{provider.get('category')}]: {provider.get('status')} ({provider.get('count', 0)} stories)")
        if provider.get("error"):
            print(f"  error: {provider['error']}")
    # Show provider-specific samples so high-priority categories cannot hide
    # Reuters or Infera evidence in the preview.
    for category in ("publisher", "independent", "official", "infera"):
        provider_stories = [story for story in stories if story.get("category") == category]
        print(f"\n--- {category.upper()} SAMPLE ({len(provider_stories)} returned) ---")
        for story in provider_stories[:5]:
            print(
                f"  - [{story.get('source')} | domain={story.get('publisher_domain', 'unknown')} "
                f"| verified={story.get('source_verified', False)}] "
                f"{story.get('title')} | {story.get('publishedAt') or 'timestamp unavailable'}"
            )

    # Reuse the just-fetched stories; build_report formats but does not send.
    stock_risk_monitor._news_for_watchlist = lambda limit=250: (stories[:limit], meta)
    lines, results = stock_risk_monitor.build_report(now=now)
    print("\n=== TELEGRAM REPORT PREVIEW (NOT SENT) ===")
    print("\n".join(lines))
    print("\n=== PRICE/RISK SUMMARY ===")
    for item, data in results:
        print(f"{item['symbol']}: risk={data.get('risk')} confidence={data.get('data_confidence')} price={data.get('price', 'N/A')}")


if __name__ == "__main__":
    main()