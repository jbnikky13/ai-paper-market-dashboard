import html
import re
import time
from urllib.parse import quote, urlparse
import requests
import xml.etree.ElementTree as ET

GNEWS = "https://gnews.io/api/v4"
UA = {"User-Agent": "AI-Market-Intelligence/5.8"}

BLOCKED_NEWS_DOMAINS = {
    "theafricareport.com", "ft.com", "wsj.com", "bloomberg.com", "economist.com",
    "barrons.com", "businessinsider.com", "nytimes.com", "washingtonpost.com",
    "forbes.com", "seekingalpha.com", "morningstar.com"
}
BLOCKED_SOURCE_NAMES = {
    "the africa report", "financial times", "wall street journal", "bloomberg",
    "the economist", "barron's", "business insider", "new york times",
    "washington post", "forbes", "seeking alpha", "morningstar"
}

GLOBAL_QUERIES = [
    "global markets stocks economy business investment",
    "US markets stocks earnings Federal Reserve economy",
    "Europe markets business economy companies",
    "Asia markets stocks semiconductor business economy",
    "oil gas commodities markets business",
]
AFRICA_QUERIES = [
    "Nigeria business economy companies markets investment",
    "Nigeria oil gas energy business NNPC Dangote refinery",
    "Nigeria banking fintech telecom business",
    "Nigeria NGX stocks companies earnings",
    "Africa business economy investment markets",
    "South Africa Kenya Egypt Ghana business markets investment",
]
POSITIVE_TERMS = {"earnings":4,"profit":4,"revenue":3,"cash flow":4,"results":3,"acquisition":4,"merger":4,"investment":3,"funding":3,"listing":5,"shares":3,"stock":3,"dividend":4,"debt":3,"bond":3,"interest rate":3,"inflation":3,"naira":3,"exchange rate":3,"oil":3,"gas":3,"crude":3,"refinery":4,"lng":4,"power":3,"electricity":3,"telecom":3,"bank":2,"fintech":3,"manufacturing":3,"trade":2,"exports":3,"imports":2,"regulation":3,"policy":2,"startup":2,"technology":2,"expansion":3,"contract":3,"tariff":3,"central bank":4,"fed":4,"ecb":4,"boe":3}
NOISE_TERMS = {"football":-7,"soccer":-7,"celebrity":-7,"movie":-7,"music":-7,"actor":-7,"actress":-7,"reality show":-7,"gaming":-6,"videogame":-6,"crime drama":-6,"weather":-5,"survival":-6,"sports":-6}


def _domain(url):
    try:
        host=urlparse(url).netloc.lower().split(":")[0]
        return host[4:] if host.startswith("www.") else host
    except Exception:return ""


def _blocked_url(url):
    host=_domain(url)
    return any(host==d or host.endswith("."+d) for d in BLOCKED_NEWS_DOMAINS)


def _blocked_article(a):
    source=(a.get("source") or "").strip().lower()
    title=(a.get("title") or "").lower()
    if _blocked_url(a.get("url") or ""):return True
    if source in BLOCKED_SOURCE_NAMES or any(x in source for x in BLOCKED_SOURCE_NAMES):return True
    wall_terms=("sign up to read","subscribe to read","subscription required","subscribers only","members only","login to read","log in to read")
    return any(t in title for t in wall_terms)


def _score(title, description="", region="Global"):
    text=f"{title} {description}".lower();score=0
    for term,weight in POSITIVE_TERMS.items():
        if term in text:score+=weight
    for term,weight in NOISE_TERMS.items():
        if term in text:score+=weight
    if any(x in text for x in ("nigeria","nigerian","ngx","lagos","abuja","naira")):score+=8
    elif region=="Africa" and any(x in text for x in ("africa","african","ghana","kenya","south africa","egypt","morocco")):score+=5
    return score


def _region(title,description="",forced=None):
    if forced:return forced
    text=f"{title} {description}".lower()
    if any(x in text for x in ("nigeria","nigerian","ngx","lagos","abuja","naira")):return "Nigeria"
    if any(x in text for x in ("africa","african","ghana","kenya","south africa","egypt","morocco")):return "Africa"
    return "Global"


def _clean(items,forced_region=None):
    out,seen=[],set()
    for a in items:
        title=(a.get("title") or "").strip();url=(a.get("url") or "").strip()
        if not title or not url or _blocked_article(a):continue
        key=re.sub(r"\W+"," ",title.lower()).strip()
        if key in seen:continue
        seen.add(key);region=_region(title,a.get("description", ""),forced_region);score=_score(title,a.get("description", ""),region)
        if score<3:continue
        a["relevance"]=min(100,max(0,50+score*5));a["region"]=region;out.append(a)
    return sorted(out,key=lambda x:(x["relevance"],x.get("publishedAt", "")),reverse=True)


def _gnews_queries(api_key,queries,forced_region=None,max_per_query=8):
    if not api_key:return []
    items=[]
    for q in queries:
        try:
            r=requests.get(f"{GNEWS}/search",params={"q":q,"lang":"en","max":max_per_query,"sortby":"publishedAt","apikey":api_key},headers=UA,timeout=15)
            if not r.ok:continue
            for a in r.json().get("articles",[]):items.append({"title":a.get("title", ""),"description":a.get("description", ""),"url":a.get("url", ""),"source":(a.get("source") or {}).get("name","Unknown"),"publishedAt":a.get("publishedAt", ""),"provider":"GNews"})
        except Exception:continue
        time.sleep(.15)
    return _clean(items,forced_region)


def _rss_queries(queries,forced_region=None):
    items=[]
    for q in queries:
        try:
            url=f"https://news.google.com/rss/search?q={quote(q)}&hl=en-NG&gl=NG&ceid=NG:en";r=requests.get(url,headers=UA,timeout=15)
            if not r.ok:continue
            root=ET.fromstring(r.content)
            for item in root.findall("./channel/item"):
                items.append({"title":item.findtext("title") or "","description":"","url":item.findtext("link") or "","source":item.findtext("source") or "Google News","publishedAt":item.findtext("pubDate") or "","provider":"Google News RSS"})
        except Exception:continue
    return _clean(items,forced_region)


def fetch_market_news(api_key="",limit=4):
    items=_gnews_queries(api_key,GLOBAL_QUERIES);provider="GNews" if items else "Google News RSS"
    if not items:items=_rss_queries(GLOBAL_QUERIES)
    return items[:limit],provider


def fetch_africa_business_news(api_key="",limit=4):
    items=_gnews_queries(api_key,AFRICA_QUERIES,"Africa");provider="GNews" if items else "Google News RSS"
    if not items:items=_rss_queries(AFRICA_QUERIES,"Africa")
    items.sort(key=lambda x:(1 if x.get("region")=="Nigeria" else 0,x.get("relevance",0)),reverse=True)
    return items[:limit],provider


def _render_section(title,items,limit):
    lines=[f"{title} ({min(limit,len(items))})"]
    for a in items[:limit]:
        headline=html.escape(a["title"]);source=html.escape(a.get("source","Unknown"));region=html.escape(a.get("region","Global"));url=html.escape(a.get("url",""),quote=True)
        if url:lines.append(f'• <a href="{url}">{headline}</a>\n  <i>{region} • {source} • relevance {a.get("relevance",0)}%</i>')
        else:lines.append(f"• <b>{headline}</b>\n  <i>{region} • {source} • relevance {a.get('relevance',0)}%</i>")
    if len(lines)==1:lines.append("ℹ️ No relevant business stories found.")
    return "\n".join(lines)


def render_telegram(items,limit=4):return _render_section("🌍 <b>AFRICA BUSINESS & MARKET NEWS</b>",items,limit)
def render_global_telegram(items,limit=4):return _render_section("🌐 <b>GLOBAL MARKET & BUSINESS NEWS</b>",items,limit)
