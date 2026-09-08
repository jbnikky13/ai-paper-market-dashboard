import html, hashlib, json, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

GNEWS="https://gnews.io/api/v4"
INFERA_DEFAULT_URL="https://infera-ten.vercel.app"
INFERA_BUSINESS_TOPIC=f"{INFERA_DEFAULT_URL}/topic/business"
UA={"User-Agent":"AI-Market-Intelligence/6.0"}
STATE_FILE=Path("news_seen.json")
SEEN_HOURS=48
GLOBAL_QUERIES=["global markets stocks economy business investment","US markets stocks earnings Federal Reserve economy","Europe markets business economy companies","Asia markets stocks semiconductor business economy","oil gas commodities markets business"]
AFRICA_QUERIES=["Nigeria business economy companies markets investment","Nigeria oil gas energy business NNPC Dangote refinery","Nigeria banking fintech telecom business","Nigeria NGX stocks companies earnings","Africa business economy investment markets","South Africa Kenya Egypt Ghana business markets investment"]
POSITIVE_TERMS={"earnings":4,"profit":4,"revenue":3,"cash flow":4,"results":3,"acquisition":4,"merger":4,"investment":3,"funding":3,"listing":5,"shares":3,"stock":3,"dividend":4,"debt":3,"bond":3,"interest rate":3,"inflation":3,"naira":3,"exchange rate":3,"oil":3,"gas":3,"crude":3,"refinery":4,"lng":4,"power":3,"electricity":3,"telecom":3,"bank":2,"fintech":3,"manufacturing":3,"trade":2,"exports":3,"imports":2,"regulation":3,"policy":2,"startup":2,"technology":2,"expansion":3,"contract":3,"tariff":3,"central bank":4,"fed":4,"ecb":4,"boe":3}
NOISE_TERMS={"football":-7,"soccer":-7,"celebrity":-7,"movie":-7,"music":-7,"actor":-7,"actress":-7,"reality show":-7,"gaming":-6,"videogame":-6,"crime drama":-6,"weather":-5,"survival":-6,"sports":-6}

def _normal_title(v):
    v=re.sub(r"\s+"," ",str(v or "").lower()).strip()
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9\s]"," ",v)).strip()

def story_fingerprint(item):
    url=str(item.get("url") or "").strip().lower().split("#")[0]
    base=url or _normal_title(item.get("title"))
    return hashlib.sha256(base.encode()).hexdigest()[:20]

def _similar(a,b):
    ta={w for w in _normal_title(a.get("title")).split() if len(w)>3};tb={w for w in _normal_title(b.get("title")).split() if len(w)>3}
    return bool(ta and tb) and len(ta&tb)/max(1,min(len(ta),len(tb)))>=0.72

def load_seen():
    try:
        data=json.loads(STATE_FILE.read_text())
        cutoff=datetime.now(timezone.utc)-timedelta(hours=SEEN_HOURS)
        return {k:v for k,v in data.items() if datetime.fromisoformat(v.replace("Z","+00:00"))>=cutoff}
    except Exception:return {}

def save_seen(items):
    seen=load_seen();now=datetime.now(timezone.utc).isoformat()
    for item in items:seen[story_fingerprint(item)]=now
    STATE_FILE.write_text(json.dumps(seen,indent=2))

def dedupe_items(items,limit=None):
    seen=load_seen();out=[]
    for item in items:
        if story_fingerprint(item) in seen or any(_similar(item,x) for x in out):continue
        out.append(item)
        if limit and len(out)>=limit:break
    if out:save_seen(out)
    return out

def _score(title,description="",region="Global"):
    text=f"{title} {description}".lower();score=sum(w for t,w in POSITIVE_TERMS.items() if t in text)+sum(w for t,w in NOISE_TERMS.items() if t in text)
    if any(x in text for x in ("nigeria","nigerian","ngx","lagos","abuja","naira")):score+=8
    elif region=="Africa" and any(x in text for x in ("africa","african","ghana","kenya","south africa","egypt","morocco")):score+=5
    return score

def _region(title,description="",forced=None):
    if forced:return forced
    text=f"{title} {description}".lower()
    if any(x in text for x in ("nigeria","nigerian","ngx","lagos","abuja","naira")):return "Nigeria"
    if any(x in text for x in ("africa","african","ghana","kenya","south africa","egypt","morocco")):return "Africa"
    return "Global"

def _parse_published(value):
    if not value:return None
    raw=str(value).strip();candidates=[raw]
    if raw.endswith("Z"):candidates.append(raw[:-1]+"+00:00")
    for candidate in candidates:
        try:
            dt=datetime.fromisoformat(candidate)
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:pass
    try:
        from email.utils import parsedate_to_datetime
        dt=parsedate_to_datetime(raw)
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError,ValueError):return None

def _is_today(value):
    dt=_parse_published(value)
    return dt is not None and dt.date()==datetime.now(timezone.utc).date()

def _clean(items,forced=None,allow_missing_date=False):
    out=[];keys=set();today=datetime.now(timezone.utc).date()
    for a in items:
        title=str(a.get("title") or "").strip();url=str(a.get("url") or "").strip();published=str(a.get("publishedAt") or "").strip()
        if not title or not url or not url.startswith(("http://","https://")):continue
        dt=_parse_published(published)
        if dt is None:
            if not allow_missing_date:continue
            dt=datetime.now(timezone.utc);a["publishedAt"]=dt.isoformat()
        elif dt.date()!=today:continue
        key=_normal_title(title)
        if key in keys:continue
        keys.add(key);region=_region(title,a.get("description",""),forced);score=_score(title,a.get("description",""),region)
        if score<3:continue
        if not a.get("relevance"):a["relevance"]=min(100,max(0,50+score*5))
        a["region"]=region;out.append(a)
    return sorted(out,key=lambda x:_parse_published(x.get("publishedAt")) or datetime.now(timezone.utc),reverse=True)

def _gnews(api_key,queries,forced=None,max_per=8):
    if not api_key:return []
    items=[]
    for q in queries:
        try:
            r=requests.get(f"{GNEWS}/search",params={"q":q,"lang":"en","max":max_per,"sortby":"publishedAt","apikey":api_key},headers=UA,timeout=15)
            if r.ok:
                for a in r.json().get("articles",[]):items.append({"title":a.get("title",""),"description":a.get("description",""),"url":a.get("url",""),"source":(a.get("source") or {}).get("name","Unknown"),"publishedAt":a.get("publishedAt",""),"provider":"GNews"})
        except Exception:pass
    return _clean(items,forced)

def _rss(queries,forced=None):
    items=[]
    for q in queries:
        try:
            r=requests.get(f"https://news.google.com/rss/search?q={quote(q)}&hl=en-NG&gl=NG&ceid=NG:en",headers=UA,timeout=15)
            if not r.ok:continue
            root=ET.fromstring(r.content)
            for x in root.findall("./channel/item"):items.append({"title":x.findtext("title") or "","description":"","url":x.findtext("link") or "","source":x.findtext("source") or "Google News","publishedAt":x.findtext("pubDate") or "","provider":"Google News RSS"})
        except Exception:pass
    return _clean(items,forced)

def _date_from_node(node):
    if not node:return None
    for attr in ("datetime","dateTime","content"):
        v=node.get(attr)
        if v and _parse_published(v):return v
    text=node.get_text(" ",strip=True)
    return text if _parse_published(text) else None

def _extract_jsonld(soup):
    found=[]
    for tag in soup.find_all("script",type="application/ld+json"):
        try:
            data=json.loads(tag.string or tag.get_text())
        except Exception:continue
        stack=data if isinstance(data,list) else [data]
        while stack:
            x=stack.pop()
            if isinstance(x,list):stack.extend(x);continue
            if not isinstance(x,dict):continue
            if "@graph" in x and isinstance(x["@graph"],list):stack.extend(x["@graph"])
            if x.get("headline") and (x.get("url") or x.get("mainEntityOfPage")):
                u=x.get("url") or x.get("mainEntityOfPage")
                if isinstance(u,dict):u=u.get("@id") or u.get("url")
                found.append({"title":str(x.get("headline")),"url":str(u or ""),"description":str(x.get("description") or ""),"publishedAt":str(x.get("datePublished") or x.get("dateModified") or ""),"source":str((x.get("publisher") or {}).get("name") if isinstance(x.get("publisher"),dict) else x.get("publisher") or "Infera"),"provider":"Infera Business Topic"})
    return found

def fetch_infera_business_topic(limit=20):
    """Primary Infera source. Reads the live /topic/business page and only accepts articles whose exposed publication date is today."""
    try:
        r=requests.get(INFERA_BUSINESS_TOPIC,headers=UA,timeout=30)
        if not r.ok:return [],{"provider":"Infera Business Topic","status":r.status_code,"error":f"HTTP {r.status_code}"}
        soup=BeautifulSoup(r.text,"html.parser");items=_extract_jsonld(soup)
        # Also inspect visible article cards. This covers Next.js-rendered topic pages that don't expose useful JSON-LD.
        for link in soup.find_all("a",href=True):
            href=urljoin(INFERA_BUSINESS_TOPIC,link.get("href"));title=link.get_text(" ",strip=True)
            if not title or len(title)<18 or href.rstrip("/")==INFERA_BUSINESS_TOPIC.rstrip("/"):continue
            if "/topic/" in href and "/topic/business" not in href:continue
            container=link
            for _ in range(4):
                container=container.parent if container and container.parent else container
                if not container:break
                txt=container.get_text(" ",strip=True)
                if len(txt)>len(title)+10:break
            pub=None;source="Infera"
            if container:
                t=container.find("time")
                pub=_date_from_node(t)
                if not pub:
                    for m in container.find_all("meta"):
                        pub=pub or _date_from_node(m)
                src=container.find(attrs={"data-source":True})
                if src:source=str(src.get("data-source") or source)
            items.append({"title":title,"description":"","url":href,"source":source,"publishedAt":pub or "","provider":"Infera Business Topic"})
        # De-duplicate raw page extraction before applying the strict date filter.
        unique=[];seen_urls=set()
        for x in items:
            u=x.get("url","").split("#")[0]
            if u and u not in seen_urls:seen_urls.add(u);unique.append(x)
        clean=_clean(unique,allow_missing_date=False)
        return clean[:limit],{"provider":"Infera Business Topic","status":200,"count":len(clean),"error":None}
    except Exception as e:return [],{"provider":"Infera Business Topic","status":None,"error":str(e)}

def _infera_story(a):
    if not isinstance(a,dict):return None
    title=str(a.get("title") or "").strip();url=str(a.get("url") or a.get("externalUrl") or a.get("external_url") or "").strip()
    if not title or not url:return None
    src=a.get("source");src=src.get("name") if isinstance(src,dict) else src
    rel=0
    for key in ("marketRelevanceScore","market_relevance_score","marketRelevance","market_relevance","importanceScore","importance_score","trendScore","trend_score"):
        if a.get(key) is not None:rel=a.get(key);break
    try:rel=max(0,min(100,round(float(rel))))
    except Exception:rel=0
    return {"title":title,"description":str(a.get("summary") or a.get("description") or ""),"url":url,"source":str(src or "Infera"),"publishedAt":str(a.get("publishedAt") or a.get("published_at") or ""),"provider":"Infera","relevance":rel,"region":a.get("region") or "Global"}

def fetch_infera_global_news(limit=20):
    # Retained as a secondary Infera compatibility path. The bot's primary path is /topic/business.
    base=(os.getenv("INFERA_URL") or INFERA_DEFAULT_URL).strip().rstrip("/")
    try:
        r=requests.get(f"{base}/api/news",headers=UA,timeout=30)
        if not r.ok:return [],{"provider":"Infera","status":r.status_code,"error":f"HTTP {r.status_code}"}
        body=r.json();raw=body.get("stories") if isinstance(body,dict) else body
        if not isinstance(raw,list):return [],{"provider":"Infera","status":200,"error":"Invalid response"}
        items=_clean([x for x in (_infera_story(s) for s in raw) if x],allow_missing_date=False)
        return items[:limit],{"provider":"Infera","status":200,"count":len(items),"error":None}
    except Exception as e:return [],{"provider":"Infera","status":None,"error":str(e)}

def fetch_market_news(api_key="",limit=4):
    # Primary source: Infera's own Business topic. Only stories with an explicit date of today pass.
    items,_=fetch_infera_business_topic(max(limit,12))
    if items:return dedupe_items(items,limit),"Infera Business Topic"
    # Secondary source: Infera API, still strict on publication date.
    items,_=fetch_infera_global_news(max(limit,12))
    if items:return dedupe_items(items,limit),"Infera"
    # Last-resort external feeds, also today-only.
    items=_gnews(api_key,GLOBAL_QUERIES) or _rss(GLOBAL_QUERIES)
    return dedupe_items(items,limit),"GNews/RSS"

def fetch_africa_business_news(api_key="",limit=4):
    items=_gnews(api_key,AFRICA_QUERIES,"Africa") or _rss(AFRICA_QUERIES,"Africa")
    items.sort(key=lambda x:(1 if x.get("region")=="Nigeria" else 0,x.get("relevance",0),x.get("publishedAt","")),reverse=True)
    return dedupe_items(items,limit),"GNews/RSS"

def _render(title,items,limit):
    lines=[title]
    for a in items[:limit]:
        h=html.escape(a.get("title",""));src=html.escape(a.get("source","Unknown"));region=html.escape(a.get("region","Global"));url=html.escape(a.get("url",""),quote=True)
        rel=int(a.get("relevance",0) or 0);level="High relevance" if rel>=80 else ("Medium relevance" if rel>=60 else "Relevant")
        lines.append(f'• <a href="{url}">{h}</a>\n  <i>{region} • {src} • {level}</i>')
    if len(lines)==1:lines.append("ℹ️ No new relevant business stories found.")
    return "\n".join(lines)

def render_telegram(items,limit=4):return _render("🇳🇬 <b>AFRICA / NIGERIA BUSINESS NEWS</b>",items,limit)
def render_global_telegram(items,limit=4):return _render("🌐 <b>GLOBAL MARKET & BUSINESS INTELLIGENCE</b>",items,limit)
