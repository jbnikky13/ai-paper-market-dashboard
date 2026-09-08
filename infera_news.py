import os
import requests

INFERA_DEFAULT_URL = "https://infera-ten.vercel.app"
UA = {"User-Agent": "AI-Market-Intelligence/5.0"}


def _number(value, default=0):
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return default


def _story(item):
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or item.get("externalUrl") or item.get("external_url") or "").strip()
    if not title or not url or not (url.startswith("http://") or url.startswith("https://")):
        return None

    source = item.get("source")
    if isinstance(source, dict):
        source = source.get("name") or source.get("title")
    source = str(source or "Infera")
    relevance = item.get("marketRelevanceScore")
    if relevance is None:
        relevance = item.get("market_relevance_score")
    if relevance is None:
        relevance = item.get("marketRelevance")
    if relevance is None:
        relevance = item.get("market_relevance")
    if relevance is None:
        relevance = item.get("importanceScore") or item.get("importance_score") or item.get("trendScore") or item.get("trend_score")

    return {
        "title": title,
        "url": url,
        "source": source,
        "publishedAt": item.get("publishedAt") or item.get("published_at") or "",
        "summary": item.get("summary") or item.get("description") or "",
        "region": item.get("region") or "Global",
        "relevance": _number(relevance),
        "momentum": _number(item.get("momentumScore") if item.get("momentumScore") is not None else item.get("momentum_score")),
        "importance": _number(item.get("importanceScore") if item.get("importanceScore") is not None else item.get("importance_score")),
    }


def fetch_infera_news(limit=15, base_url=None):
    """Fetch live intelligence from Infera. Never raises; returns items + diagnostics."""
    base = (base_url or os.getenv("INFERA_URL") or INFERA_DEFAULT_URL).strip().rstrip("/")
    endpoint = f"{base}/api/news"
    try:
        response = requests.get(endpoint, headers=UA, timeout=30)
        if not response.ok:
            return [], {"provider": "Infera", "status": response.status_code, "error": f"HTTP {response.status_code}", "fallback": True}
        body = response.json()
        raw = body.get("stories") if isinstance(body, dict) else body
        if not isinstance(raw, list):
            return [], {"provider": "Infera", "status": response.status_code, "error": "Invalid response shape", "fallback": True}
        items = [_story(x) for x in raw]
        items = [x for x in items if x]
        items.sort(key=lambda x: (x["relevance"], x["momentum"], x["importance"]), reverse=True)
        if not items:
            return [], {"provider": "Infera", "status": 200, "error": "No usable stories", "fallback": True}
        return items[:limit], {"provider": "Infera", "status": 200, "error": None, "fallback": False, "count": len(items), "generatedAt": body.get("generatedAt") if isinstance(body, dict) else None}
    except requests.RequestException as exc:
        return [], {"provider": "Infera", "status": None, "error": str(exc), "fallback": True}
    except (ValueError, TypeError) as exc:
        return [], {"provider": "Infera", "status": 200, "error": f"Invalid JSON: {exc}", "fallback": True}
    except Exception as exc:
        return [], {"provider": "Infera", "status": None, "error": str(exc), "fallback": True}
