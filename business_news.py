import html
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote
import requests
import xml.etree.ElementTree as ET

GNEWS = "https://gnews.io/api/v4"
UA = {"User-Agent": "AI-Market-Intelligence/5.0"}

AFRICA_QUERIES = [
    'Nigeria business economy companies markets investment',
    'Nigeria oil gas energy business NNPC Dangote',
    'Nigeria banking fintech telecom business',
    'Africa business economy investment markets',
]

# Topics that are useful to investors/operators; these are used to suppress generic noise.
POSITIVE_TERMS = {
    "earnings": 4, "profit": 4, "revenue": 3, "cash flow": 4, "results": 3,
    "acquisition": 4, "merger": 4, "investment": 3, "funding": 3, "ipo": 5,
    "listing": 5, "shares": 3, "stock": 3, "dividend": 4, "debt": 3,
    "bond": 3, "interest rate": 3, "inflation": 3, "naira": 3, "exchange rate": 3,
    "oil": 3, "gas": 3, "crude": 3, "refinery": 4, "lng": 4, "power": 3,
    "electricity": 3, "telecom": 3, "bank": 2, "fintech": 3, "manufacturing": 3,
    "trade": 2, "exports": 3, "imports": 2, "regulation": 3, "policy": 2,
    "startup": 2, "technology": 2, "expansion": 3, "contract": 3,
}
NOISE_TERMS = {
    "football": -6, "soccer": -6, "celebrity": -6, "movie": -6, "music": -6,
    "actor": -6, "actress": -6, "reality show": -6, "gaming": -5, "videogame": -5,
    "crime drama": -5, "weather": -4, "survival": -5, "sports": -5,
}


def _score(title, description=""):
    text = f"{title} {description}".lower()
    score = 0
    for term, weight in POSITIVE_TERMS.items():
        if term in text:
            score += weight
    for term, weight in NOISE_TERMS.items():
        if term in text:
            score += weight
    if any(x in text for x in ("nigeria", "nigerian", "ngx", "lagos", "abuja")):
        score += 6
    elif any(x in text for x in ("africa", "african", "ghana", "kenya", "south africa", "egypt")):
        score += 3
    return score


def _region(title, description=""):
    text = f"{title} {description}".lower()
    if any(x in text for x in ("nigeria", "nigerian", "ngx", "lagos", "abuja", "naira")):
        return "Nigeria"
    if "africa" in text or "african" in text:
        return "Africa"
    return "Global"


def _clean(items):
    out, seen = [], set()
    for a in items:
        title = (a.get("title") or "").strip()
        url = (a.get("url") or "").strip()
        if not title:
            continue
        key = re.sub(r"\W+", " ", title.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        score = _score(title, a.get("description", ""))
        if score < 3:
            continue
        a["relevance"] = min(100, max(0, 50 + score * 5))
        a["region"] = _region(title, a.get("description", ""))
        out.append(a)
    return sorted(out, key=lambda x: (x["relevance"], x.get("publishedAt", "")), reverse=True)


def fetch_gnews(api_key, max_per_query=8):
    if not api_key:
        return [], "GNews API key not configured"
    items = []
    for q in AFRICA_QUERIES:
        try:
            r = requests.get(
                f"{GNEWS}/search",
                params={"q": q, "lang": "en", "max": max_per_query, "sortby": "publishedAt", "apikey": api_key},
                headers=UA, timeout=15,
            )
            if not r.ok:
                continue
            for a in r.json().get("articles", []):
                items.append({
                    "title": a.get("title", ""), "description": a.get("description", ""),
                    "url": a.get("url", ""), "source": (a.get("source") or {}).get("name", "Unknown"),
                    "publishedAt": a.get("publishedAt", ""), "provider": "GNews",
                })
        except Exception:
            continue
        time.sleep(0.15)
    return _clean(items), "GNews"


def fetch_google_news_rss():
    items = []
    for q in AFRICA_QUERIES:
        try:
            url = f"https://news.google.com/rss/search?q={quote(q)}&hl=en-NG&gl=NG&ceid=NG:en"
            r = requests.get(url, headers=UA, timeout=15)
            if not r.ok:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall("./channel/item"):
                title = item.findtext("title") or ""
                link = item.findtext("link") or ""
                pub = item.findtext("pubDate") or ""
                source = item.findtext("source") or "Google News"
                items.append({"title": title, "description": "", "url": link, "source": source, "publishedAt": pub, "provider": "Google News RSS"})
        except Exception:
            continue
    return _clean(items), "Google News RSS"


def fetch_africa_business_news(api_key="", limit=12):
    items, provider = fetch_gnews(api_key)
    if not items:
        items, provider = fetch_google_news_rss()
    return items[:limit], provider


def render_telegram(items, limit=8):
    lines = [f"🌍 <b>AFRICA BUSINESS & MARKET NEWS ({min(limit, len(items))})</b>"]
    for a in items[:limit]:
        title = html.escape(a["title"])
        source = html.escape(a.get("source", "Unknown"))
        region = html.escape(a.get("region", "Africa"))
        url = html.escape(a.get("url", ""), quote=True)
        lines.append(f'• <a href="{url}">{title}</a>\n  <i>{region} • {source} • relevance {a.get("relevance", 0)}%</i>')
    return "\n".join(lines) if len(lines) > 1 else "🌍 <b>AFRICA BUSINESS & MARKET NEWS</b>\nℹ️ No relevant business stories found."
