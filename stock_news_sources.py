"""Independent news collection for the daily stock-risk monitor.

Nairametrics is consumed from its publisher RSS feed. Reuters headlines are
discovered through Google News RSS restricted to reuters.com because Reuters
does not maintain a working public RSS feed. Official-source discovery is
restricted to known issuer/exchange/regulator domains; Google News is only the
discovery transport, never the publisher attribution.
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
import xml.etree.ElementTree as ET
import re

import requests

UA = {"User-Agent": "AI-Market-Intelligence-Risk-Monitor/2.0"}
TIMEOUT = 20
MAX_AGE_DAYS = 7
WATCH_TERMS = (
    "NVIDIA OR NVDA",
    '"MTN Nigeria" OR MTNN',
    '"The Initiates Plc" OR TIP Nigeria',
    'GTCO OR "Guaranty Trust"',
    '"Dangote Cement" OR DANGCEM',
)
MACRO_TERMS = (
    'Nigeria CBN inflation naira interest rates',
    'Federal Reserve US technology semiconductor export controls',
)

# Only these domains qualify as official issuer, exchange or regulator evidence.
OFFICIAL_DOMAINS = {
    "ngxgroup.com", "doclib.ngxgroup.com", "sec.gov.ng",
    "investor.nvidia.com", "nvidianews.nvidia.com",
    "mtn.com", "mtn.ng", "gtco-plc.com", "gtbank.com",
    "dangotecement.com", "dangote.com",
}
GOOGLE_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


def _google_feed(query):
    return GOOGLE_RSS.format(query=quote(query, safe=""))


def _parse_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _normalise_story_timestamp(story):
    """Normalize publisher RSS and Infera API timestamps to aware UTC datetimes."""
    value = story.get("published_at")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    value = story.get("publishedAt") or story.get("published_at")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return _parse_date(value)


def _host(url):
    from urllib.parse import urlparse
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _is_official(url):
    host = _host(url)
    return any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_DOMAINS)


def _valid_headline(title):
    """Reject empty or generic search-index placeholders, not real headlines."""
    cleaned = " ".join(str(title or "").split())
    lowered = cleaned.lower()
    if len(cleaned) < 8 or lowered.startswith(("untitled", "- ", "newsroom")):
        return False
    if re.fullmatch(r"[\W_]+", cleaned):
        return False
    return True


def _items_from_feed(xml_text, provider, category, now):
    root = ET.fromstring(xml_text)
    items = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        description = (node.findtext("description") or "").strip()
        published = _parse_date(node.findtext("pubDate"))
        source_node = node.find("source")
        source_name = (source_node.text or "").strip() if source_node is not None else ""
        source_url = source_node.attrib.get("url", "") if source_node is not None else ""
        if not _valid_headline(title) or not link:
            continue
        if published and (published > now + timedelta(hours=2) or published < now - timedelta(days=MAX_AGE_DAYS)):
            continue
        # Google News links carry the publisher in the title; preserve that
        # attribution and the Google News URL if no canonical URL is exposed.
        publisher = source_name or provider
        if category == "official":
            if not source_url or not _is_official(source_url):
                continue
            publisher = _host(source_url)
        elif category == "independent":
            if not source_url or "reuters.com" not in _host(source_url):
                continue
            publisher = "Reuters"
        items.append({
            "title": title,
            "url": link,
            "description": description,
            "publishedAt": published.isoformat() if published else "",
            "published_at": published,
            "source": publisher,
            "publisher_domain": _host(source_url) if source_url else _host(link),
            "provider": provider,
            "category": category,
            "source_verified": category == "official",
        })
    return items


def _fetch_feed(url, provider, category, now, timeout=TIMEOUT):
    response = requests.get(url, headers=UA, timeout=timeout)
    response.raise_for_status()
    return _items_from_feed(response.text, provider, category, now)


def fetch_market_news(now=None, limit=250):
    """Return deduplicated, recent stories and per-provider health metadata."""
    now = now or datetime.now(timezone.utc)
    providers = [
        ("Nairametrics", "publisher", "https://nairametrics.com/feed"),
    ]
    for term in WATCH_TERMS + MACRO_TERMS:
        providers.append(("Reuters via Google News", "independent", _google_feed(f"site:reuters.com {term} when:7d")))
    official_queries = (
        'site:ngxgroup.com OR site:doclib.ngxgroup.com "company announcement" Nigeria',
        'site:sec.gov.ng Nigeria issuer filing company announcement',
        'site:investor.nvidia.com OR site:nvidianews.nvidia.com NVIDIA',
        'site:mtn.com OR site:mtn.ng investor results MTN Nigeria',
        'site:gtco-plc.com OR site:gtbank.com investor results GTCO',
        'site:dangotecement.com OR site:dangote.com investor results cement',
    )
    for query in official_queries:
        providers.append(("Official issuer/exchange discovery", "official", _google_feed(query + " when:7d")))

    all_items = []
    statuses = []
    # Keep the existing Infera feed as a supplemental source rather than a
    # single point of failure for the daily risk monitor.
    try:
        from business_news import fetch_infera_business_topic
        infera_items, infera_meta = fetch_infera_business_topic(limit=limit)
        for item in infera_items:
            item = dict(item)
            item["category"] = "infera"
            item["provider"] = "Infera Business Topic"
            item["source_verified"] = False
            item["published_at"] = _normalise_story_timestamp(item)
            all_items.append(item)
        statuses.append({
            "provider": "Infera Business Topic",
            "category": "infera",
            "status": "ok" if infera_items else "empty",
            "count": len(infera_items),
            "error": infera_meta.get("error"),
        })
    except Exception as exc:
        statuses.append({
            "provider": "Infera Business Topic",
            "category": "infera",
            "status": "error",
            "count": 0,
            "error": str(exc)[:180],
        })
    for provider, category, url in providers:
        try:
            items = _fetch_feed(url, provider, category, now)
            statuses.append({
                "provider": provider,
                "category": category,
                "status": "ok" if items else "empty",
                "count": len(items),
                "error": None,
            })
            all_items.extend(items)
        except Exception as exc:
            statuses.append({
                "provider": provider,
                "category": category,
                "status": "error",
                "count": 0,
                "error": str(exc)[:180],
            })

    # Prefer direct publisher / official items over discovery duplicates.
    priority = {"official": 0, "publisher": 1, "independent": 2, "infera": 3}
    all_items.sort(key=lambda x: (priority.get(x["category"], 9), -(_normalise_story_timestamp(x).timestamp() if _normalise_story_timestamp(x) else 0)))
    seen = set()
    unique = []
    for item in all_items:
        key = item["url"].split("?")[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:limit], {
        "provider": "Nairametrics + Reuters + official issuer/exchange discovery",
        "status": "ok" if any(x["count"] for x in statuses) else "degraded",
        "count": len(unique),
        "providers": statuses,
        "retrieved_at": now.isoformat(),
    }


def story_text(story):
    return f"{story.get('title', '')} {story.get('description', '')}".lower()
