import html, hashlib, json, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

INFERA_DEFAULT_URL = "https://infera-ten.vercel.app"
INFERA_BUSINESS_TOPIC = f"{INFERA_DEFAULT_URL}/topic/business"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AI-Market-Intelligence/6.2)"}
STATE_FILE = Path("news_seen.json")
SEEN_HOURS = 48

POSITIVE_TERMS = {"earnings":4,"profit":4,"revenue":3,"results":3,"acquisition":4,"merger":4,"investment":3,"funding":3,"listing":5,"shares":3,"stock":3,"dividend":4,"debt":3,"bond":3,"interest rate":3,"inflation":3,"oil":3,"gas":3,"crude":3,"refinery":4,"lng":4,"power":3,"electricity":3,"telecom":3,"bank":2,"fintech":3,"manufacturing":3,"trade":2,"exports":3,"imports":2,"regulation":3,"policy":2,"startup":2,"technology":2,"expansion":3,"contract":3,"tariff":3,"central bank":4,"fed":4,"ecb":4,"boe":3}
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

def _jsonld_articles(soup):
    found=[]
    for tag in soup.find_all("script",type="application/ld+json"):
        try:data=json.loads(tag.string or tag.get_text())
        except Exception:continue
        stack=list(data) if isinstance(data,list) else [data]
        while stack:
            obj=stack.pop()
            if isinstance(obj,list):stack.extend(obj);continue
            if not isinstance(obj,dict):continue
            if isinstance(obj.get("@graph"),list):stack.extend(obj["@graph"])
            title=obj.get("headline") or obj.get("name");url=obj.get("url") or obj.get("mainEntityOfPage")
            if isinstance(url,dict):url=url.get("@id") or url.get("url")
            if title and isinstance(url,str):
                found.append({"title":str(title).strip(),"url":urljoin(INFERA_BUSINESS_TOPIC,url),"description":str(obj.get("description") or "").strip(),"publishedAt":str(obj.get("datePublished") or obj.get("dateModified") or ""),"source":"Infera"})
    return found

def _next_data_articles(soup):
    found=[];tag=soup.find("script",id="__NEXT_DATA__")
    if not tag:return found
    try:data=json.loads(tag.string or tag.get_text())
    except Exception:return found
    def walk(obj):
        if isinstance(obj,dict):
            title=obj.get("title") or obj.get("headline");url=obj.get("url") or obj.get("href") or obj.get("link") or obj.get("externalUrl")
            if isinstance(title,str) and isinstance(url,str) and len(title.strip())>=18 and (url.startswith("/") or url.startswith("http")):
                found.append({"title":title.strip(),"url":urljoin(INFERA_BUSINESS_TOPIC,url),"description":str(obj.get("description") or obj.get("summary") or "").strip(),"publishedAt":str(obj.get("publishedAt") or obj.get("published_at") or obj.get("datePublished") or obj.get("date") or ""),"source":str(obj.get("source") or "Infera")})
            for value in obj.values():walk(value)
        elif isinstance(obj,list):
            for value in obj:walk(value)
    walk(data);return found

def _visible_link_articles(soup):
    found=[]
    for link in soup.find_all("a",href=True):
        href=urljoin(INFERA_BUSINESS_TOPIC,link.get("href"));title=re.sub(r"\s+"," ",link.get_text(" ",strip=True))
        if len(title)<18 or not href.startswith(("http://","https://")) or "/topic/business" in href.rstrip("/"):continue
        container=link
        for _ in range(5):
            if not getattr(container,"parent",None):break
            container=container.parent
            if len(container.get_text(" ",strip=True))>len(title)+10:break
        published="";description=""
        if container:
            time_tag=container.find("time")
            if time_tag:published=time_tag.get("datetime") or time_tag.get_text(" ",strip=True)
            meta=container.find("meta",attrs={"property":re.compile("published|modified",re.I)})
            if meta:published=published or meta.get("content","")
            description=container.get_text(" ",strip=True)[:500]
        found.append({"title":title,"url":href,"description":description,"publishedAt":published,"source":"Infera"})
    return found

def fetch_infera_business_topic(limit=20):
    """Single source of truth for bot business news: Infera /topic/business. No date gate."""
    try:
        r=requests.get(INFERA_BUSINESS_TOPIC,headers=UA,timeout=30)
        if not r.ok:return [],{"provider":"Infera Business Topic","status":r.status_code,"error":f"HTTP {r.status_code}"}
        soup=BeautifulSoup(r.text,"html.parser")
        raw=_jsonld_articles(soup)+_next_data_articles(soup)+_visible_link_articles(soup)
        unique=[];seen=set()
        for item in raw:
            url=str(item.get("url") or "").split("#")[0];title=str(item.get("title") or "").strip()
            if not title or not url or url in seen:continue
            seen.add(url)
            score=_score(title,item.get("description",""))
            item["region"]=_region(title,item.get("description",""));item["relevance"]=min(100,max(0,50+score*5));unique.append(item)
        return unique[:limit],{"provider":"Infera Business Topic","status":200,"count":len(unique),"error":None}
    except Exception as e:return [],{"provider":"Infera Business Topic","status":None,"count":0,"error":str(e)}

def fetch_market_news(api_key="",limit=4):
    """Global bot news comes exclusively from Infera's Business topic page."""
    items,_=fetch_infera_business_topic(max(limit,12))
    return dedupe_items(items,limit),"Infera Business Topic"

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
