import html, hashlib, json, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
import requests

INFERA_DEFAULT_URL = "https://infera-ten.vercel.app"
INFERA_BUSINESS_TOPIC = f"{INFERA_DEFAULT_URL}/topic/business"
INFERA_BUSINESS_API = f"{INFERA_DEFAULT_URL}/api/topic/business"
UA = {"User-Agent": "AI-Market-Intelligence/6.2"}
STATE_FILE = Path("news_seen.json")
SEEN_HOURS = 48

POSITIVE_TERMS = {"earnings":4,"profit":4,"revenue":3,"results":3,"acquisition":4,"merger":4,"investment":3,"funding":3,"listing":5,"shares":3,"stock":3,"dividend":4,"debt":3,"bond":3,"interest rate":3,"inflation":3,"oil":3,"gas":3,"crude":3,"refinery":4,"lng":4,"power":3,"electricity":3,"telecom":3,"bank":2,"fintech":3,"manufacturing":3,"trade":2,"exports":3,"imports":3,"regulation":3,"policy":2,"startup":2,"technology":2,"expansion":3,"contract":3,"tariff":3,"central bank":4,"fed":4,"ecb":4,"boe":3}
NOISE_TERMS = {"football":-7,"soccer":-7,"celebrity":-7,"movie":-7,"music":-7,"actor":-7,"actress":-7,"reality show":-7,"gaming":-6,"videogame":-6,"crime drama":-6,"weather":-5,"sports":-6}

def _normal_title(value):
    value=re.sub(r"\s+"," ",str(value or "").lower()).strip()
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9\s]"," ",value)).strip()

def story_fingerprint(item):
    url=str(item.get("url") or "").strip().lower().split("#")[0]
    base=url or _normal_title(item.get("title"))
    return hashlib.sha256(base.encode()).hexdigest()[:20]

def _similar(a,b):
    aa={w for w in _normal_title(a.get("title")).split() if len(w)>3};bb={w for w in _normal_title(b.get("title")).split() if len(w)>3}
    return bool(aa and bb) and len(aa&bb)/max(1,min(len(aa),len(bb)))>=0.72

def load_seen():
    try:
        data=json.loads(STATE_FILE.read_text());cutoff=datetime.now(timezone.utc)-timedelta(hours=SEEN_HOURS)
        return {k:v for k,v in data.items() if datetime.fromisoformat(v.replace("Z","+00:00"))>=cutoff}
    except Exception:return {}

def save_seen(items):
    seen=load_seen();now=datetime.now(timezone.utc).isoformat()
    for item in items:seen[story_fingerprint(item)]=now
    try:STATE_FILE.write_text(json.dumps(seen,indent=2))
    except Exception:pass

def dedupe_items(items,limit=None):
    seen=load_seen();out=[]
    for item in items:
        if story_fingerprint(item) in seen or any(_similar(item,x) for x in out):continue
        out.append(item)
        if limit and len(out)>=limit:break
    if out:save_seen(out)
    return out

def _score(title,description=""):
    text=f"{title} {description}".lower()
    return sum(w for t,w in POSITIVE_TERMS.items() if t in text)+sum(w for t,w in NOISE_TERMS.items() if t in text)

def _region(title,description=""):
    text=f"{title} {description}".lower()
    if any(x in text for x in ("nigeria","nigerian","ngx","lagos","abuja","naira")):return "Nigeria"
    if any(x in text for x in ("africa","african","ghana","kenya","south africa","egypt","morocco")):return "Africa"
    return "Global"

def _normalise_topic_story(story):
    if not isinstance(story,dict):return None
    title=str(story.get("title") or "").strip()
    if not title:return None
    # Infera's topic page links to /story/{id}; use the canonical story URL when an id exists.
    sid=story.get("id")
    url=str(story.get("url") or "").strip()
    if sid is not None and str(sid).strip():
        url=f"{INFERA_DEFAULT_URL}/story/{quote(str(sid),safe='')}"
    elif url and not url.startswith(("http://","https://")):
        url=f"{INFERA_DEFAULT_URL}/{url.lstrip('/')}"
    if not url:return None
    description=str(story.get("description") or story.get("summary") or "").strip()
    relevance=story.get("marketRelevance",story.get("market_relevance_score",story.get("marketRelevanceScore",0)))
    try:relevance=max(0,min(100,round(float(relevance))))
    except (TypeError,ValueError):relevance=0
    if not relevance:
        relevance=min(100,max(0,50+_score(title,description)*5))
    return {
        "title":title,
        "url":url,
        "description":description,
        "publishedAt":str(story.get("publishedAt") or story.get("published_at") or ""),
        "source":str(story.get("sourceName") or story.get("source") or "Infera"),
        "region":_region(title,description),
        "relevance":relevance,
        "momentum":story.get("momentumScore",story.get("momentum_score",0)),
        "importance":story.get("importanceScore",story.get("importance_score",0)),
    }

def fetch_infera_business_topic(limit=20):
    """Single source of truth: the same /api/topic/business data rendered by Infera /topic/business."""
    try:
        # The public topic page is client-rendered and fetches its stories from this route.
        # Scraping the HTML would only retrieve the loading shell, which caused the empty feed.
        r=requests.get(INFERA_BUSINESS_API,headers={**UA,"Accept":"application/json"},timeout=30)
        if not r.ok:
            return [],{"provider":"Infera Business Topic","status":r.status_code,"error":f"HTTP {r.status_code}","endpoint":INFERA_BUSINESS_API}
        body=r.json()
        topic=body.get("topic") if isinstance(body,dict) else None
        raw=topic.get("stories") if isinstance(topic,dict) else []
        if not isinstance(raw,list):raw=[]
        items=[];seen=set()
        for story in raw:
            item=_normalise_topic_story(story)
            if not item:continue
            fp=story_fingerprint(item)
            if fp in seen:continue
            seen.add(fp);items.append(item)
        # Preserve Infera's ordering from the topic page: it is already ordered by published_at desc.
        return items[:limit],{"provider":"Infera Business Topic","status":200,"count":len(items),"error":None,"endpoint":INFERA_BUSINESS_API}
    except ValueError as e:
        return [],{"provider":"Infera Business Topic","status":200,"count":0,"error":f"Invalid JSON: {e}","endpoint":INFERA_BUSINESS_API}
    except Exception as e:
        return [],{"provider":"Infera Business Topic","status":None,"count":0,"error":str(e),"endpoint":INFERA_BUSINESS_API}

def fetch_market_news(api_key="",limit=4):
    """Global bot news comes exclusively from Infera's Business topic data."""
    items,meta=fetch_infera_business_topic(max(limit,12))
    return dedupe_items(items,limit),"Infera Business Topic" if not meta.get("error") else "Infera Business Topic (error)"

def fetch_africa_business_news(api_key="",limit=4):
    return [],"Disabled"

def _render(title,items,limit):
    lines=[title]
    for item in items[:limit]:
        headline=html.escape(item.get("title",""));source=html.escape(item.get("source","Infera"));region=html.escape(item.get("region","Global"));url=html.escape(item.get("url",""),quote=True)
        rel=int(item.get("relevance",0) or 0);level="High relevance" if rel>=80 else ("Medium relevance" if rel>=60 else "Relevant")
        lines.append(f'• <a href="{url}">{headline}</a>\n  <i>{region} • {source} • {level}</i>')
    if len(lines)==1:lines.append("ℹ️ No business intelligence available from Infera Business topic.")
    return "\n".join(lines)

def render_telegram(items,limit=4):return _render("🇳🇬 <b>AFRICA / NIGERIA BUSINESS NEWS</b>",items,limit)
def render_global_telegram(items,limit=4):return _render("🌐 <b>GLOBAL MARKET & BUSINESS INTELLIGENCE</b>",items,limit)
