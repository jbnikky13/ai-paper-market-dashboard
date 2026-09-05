import html
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "AI-Market-Intelligence/5.6 (github.com/jbnikky13/ai-paper-market-dashboard)"}
PATTERNS = {
    "audited_profit": [r"audited.{0,140}(?:profit|net income|profit after tax)", r"profit after tax", r"net profit", r"net income"],
    "operating_cash_flow": [r"net cash (?:provided by|generated from) operating activities", r"cash flows from operating activities", r"operating cash flow"],
    "debt": [r"total debt", r"total borrowings", r"total indebtedness", r"indebtedness", r"long[- ]term debt"],
    "refining_margins": [r"refining margins?", r"refinery margins?", r"crack spread"],
    "crude_supply_terms": [r"crude (?:oil )?supply", r"crude purchase agreement", r"crude supply agreement", r"supply agreement"],
    "expansion_costs": [r"expansion costs?", r"expansion project", r"capital expenditure", r"growth capital", r"capex"],
    "use_of_proceeds": [r"use of proceeds", r"proceeds of the offer", r"purpose of the offer", r"application of proceeds", r"use of the net proceeds"],
}
MONEY_RE = re.compile(r"(?:(?:US|U\.S\.)\s*\$|\$|NGN\s*|N\s*|₦)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*(thousand|million|billion|trillion|bn|b|m|k)?", re.I)


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=40)
        return (r.content, r.headers.get("content-type", "")) if r.ok else (b"", "")
    except requests.RequestException:
        return b"", ""


def clean(raw):
    s = BeautifulSoup(raw, "html.parser")
    for x in s(["script", "style", "noscript"]):
        x.decompose()
    return re.sub(r"\s+", " ", html.unescape(s.get_text(" ", strip=True))).strip()


def extract_pdf(content):
    try:
        from io import BytesIO
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        text = re.sub(r"\s+", " ", " ".join(pages)).strip()
        if len(text) >= 500:
            return text, "text"
    except Exception:
        pass
    return extract_pdf_ocr(content), "ocr"


def extract_pdf_ocr(content):
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(content, dpi=180, first_page=1, last_page=80, fmt="jpeg", thread_count=1)
        chunks = []
        for image in images:
            try:
                chunks.append(pytesseract.image_to_string(image, config="--psm 6"))
            finally:
                image.close()
        return re.sub(r"\s+", " ", " ".join(chunks)).strip()
    except Exception:
        return ""


def extract(text, patterns, window=1100):
    low = text.lower()
    for p in patterns:
        m = re.search(p, low, re.I)
        if m:
            return text[max(0, m.start()-220):min(len(text), m.end()+window)].strip()
    return None


def normalize_number(raw, scale=None):
    try:
        n = Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    factor = {"thousand":10**3,"million":10**6,"billion":10**9,"trillion":10**12,"bn":10**9,"b":10**9,"m":10**6,"k":10**3}.get((scale or "").lower(), 1)
    return float(n * factor)


def extract_money_values(text, patterns):
    candidates = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            context = text[max(0, match.start()-260):min(len(text), match.end()+520)]
            for nm in MONEY_RE.finditer(context):
                base = float(nm.group(1).replace(",", ""))
                if 1900 <= base <= 2100 or base < 1000:
                    continue
                value = normalize_number(nm.group(1), nm.group(2))
                if value is not None:
                    candidates.append({"value": value, "raw": nm.group(0).strip(), "context": context[:900]})
    seen, out = set(), []
    for item in candidates:
        key = (item["value"], item["context"][:150])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:30]


def best(candidates):
    return candidates[0] if candidates else None


def score(profile):
    total = 0
    for key in ("audited_profit", "operating_cash_flow", "debt", "use_of_proceeds"):
        if profile.get(key):
            total += 10
    p, c = profile.get("audited_profit_value"), profile.get("operating_cash_flow_value")
    if p is not None and c is not None and p > 0:
        ratio = c / p
        profile["cash_conversion"] = ratio
        total += 20 if ratio >= .8 else 15 if ratio >= .5 else 8 if ratio >= 0 else 2
    d = profile.get("debt_value")
    if d is not None and p is not None and p > 0:
        leverage = d / p
        profile["debt_to_profit"] = leverage
        total += 20 if leverage <= 1 else 15 if leverage <= 2 else 8 if leverage <= 4 else 3
    if profile.get("refining_margins") or profile.get("crude_supply_terms"):
        total += 10
    if profile.get("expansion_costs"):
        total += 5
    if profile.get("use_of_proceeds"):
        total += 5
    return min(100, int(total))


def analyze(url):
    content, content_type = fetch(url)
    if not content:
        return None
    if "pdf" in content_type.lower() or url.lower().split("?")[0].endswith(".pdf"):
        text, method = extract_pdf(content)
        document_type = "PDF"
    else:
        text, method = clean(content), "html"
        document_type = "HTML"
    if not text:
        return {"source_url": url, "verification": "Document downloaded but no text could be extracted", "ipo_quality_score": 0, "extraction_method": method}
    out = {"source_url": url, "document_type": document_type, "extraction_method": method}
    for key, patterns in PATTERNS.items():
        out[key] = extract(text, patterns)
    out["audited_profit_candidate"] = best(extract_money_values(text, [r"net income", r"net profit", r"profit after tax"]))
    out["operating_cash_flow_candidate"] = best(extract_money_values(text, [r"net cash (?:provided by|generated from) operating activities", r"cash flows from operating activities"]))
    out["debt_candidate"] = best(extract_money_values(text, [r"total debt", r"total borrowings", r"total indebtedness", r"long[- ]term debt"]))
    out["ipo_proceeds_candidate"] = best(extract_money_values(text, [r"gross proceeds", r"net proceeds", r"proceeds of the offer", r"proceeds of the offering"]))
    for source, target in [("audited_profit_candidate", "audited_profit_value"), ("operating_cash_flow_candidate", "operating_cash_flow_value"), ("debt_candidate", "debt_value"), ("ipo_proceeds_candidate", "ipo_proceeds_value")]:
        candidate = out.get(source)
        out[target] = candidate["value"] if candidate else None
    out["disclosure_coverage"] = round(sum(bool(out.get(k)) for k in PATTERNS) / len(PATTERNS) * 100)
    out["ipo_quality_score"] = score(out)
    out["verification"] = "Official document content detected; numeric values are extraction candidates and must be verified against the original financial tables."
    return out


def discover_links(page_url):
    content, _ = fetch(page_url)
    if not content:
        return []
    soup = BeautifulSoup(content, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        href = urljoin(page_url, a["href"])
        hay = (title + " " + href).lower()
        if any(k in hay for k in ("prospectus", "public offer", "ipo", "offer for subscription", "offer for sale", "listing")):
            out.append({"title": title or "Capital-market document", "url": href})
    return out
