"""Fetch live stock-news feeds and print a Telegram-safe report preview.

This script never calls telegram_bot.send and requires no Telegram credentials.
"""
from datetime import datetime, timezone

import stock_risk_monitor
from stock_news_sources import fetch_market_news


def main():
    now = datetime.now(timezone.utc)
    stories, meta = fetch_market_news(now=now)
    print("=== LIVE NEWS PROVIDER RESULTS ===")
    print(f"Overall: {meta.get('status')} | stories: {meta.get('count')} | retrieved: {meta.get('retrieved_at')}")
    for provider in meta.get("providers", []):
        print(f"{provider.get('provider')} [{provider.get('category')}]: {provider.get('status')} ({provider.get('count', 0)} stories)")
        if provider.get("error"):
            print(f"  error: {provider['error']}")
    for story in stories[:25]:
        print(f"  - [{story.get('source')} / {story.get('category')}] {story.get('title')} | {story.get('publishedAt') or 'timestamp unavailable'}")

    # Reuse the just-fetched stories; build_report formats but does not send.
    stock_risk_monitor._news_for_watchlist = lambda limit=80: (stories[:limit], meta)
    lines, results = stock_risk_monitor.build_report(now=now)
    print("\n=== TELEGRAM REPORT PREVIEW (NOT SENT) ===")
    print("\n".join(lines))
    print("\n=== PRICE/RISK SUMMARY ===")
    for item, data in results:
        print(f"{item['symbol']}: risk={data.get('risk')} confidence={data.get('data_confidence')} price={data.get('price', 'N/A')}")


if __name__ == "__main__":
    main()