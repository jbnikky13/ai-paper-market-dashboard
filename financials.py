import html
import re
import time
from datetime import datetime, timezone

import requests

SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
YAHOO_TS = "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}"

# CIKs for the U.S. equities already tracked by the dashboard.
SEC_CIK = {
    "NVDA": "0001045810", "AMD": "0000002488", "AVGO": "0001730168",
    "MSFT": "0000789019", "GOOGL": "0001652044", "AMZN": "0001018724",
    "META": "0001326801", "TSLA": "0001318605", "AAPL": "0000320193",
}

HEADERS = {"User-Agent": "AI-Market-Intelligence/5.0 (github.com/jbnikky13/ai-paper-market-dashboard)"}


def _get(url, params=None, timeout=25):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        if r.ok:
            return r, None
        return None, f"HTTP {r.status_code}: {(r.text or '')[:300]}"
    except Exception as exc:
        return None, str(exc)


def _yahoo_series(symbol, types):
    params = {
        "symbol": symbol,
        "period1": "946684800",
        "period2": str(int(time.time())),
        "type": ",".join(types),
        "merge": "false",
        "padTimeSeries": "true",
    }
    r, err = _get(YAHOO_TS.format(symbol=symbol), params)
    if not r:
        return {}, err
    try:
        data = r.json().get("timeseries", {}).get("result", [])
        out = {}
        for item in data:
            for key, value in item.items():
                if key.startswith("quarterly") and isinstance(value, list):
                    for row in value:
                        period = row.get("asOfDate")
                        raw = row.get("reportedValue")
                        if period and isinstance(raw, dict) and raw.get("raw") is not None:
                            out.setdefault(period, {})[key] = raw["raw"]
        return out, None
    except Exception as exc:
        return {}, f"Could not parse Yahoo fundamentals: {exc}"


def _latest_periods(series, limit=8):
    return sorted(series.keys(), reverse=True)[:limit]


def _sec_facts(symbol):
    cik = SEC_CIK.get(symbol)
    if not cik:
        return {}, "SEC CIK not configured for this symbol."
    r, err = _get(SEC_COMPANYFACTS.format(cik=cik))
    if not r:
        return {}, err
    try:
        return r.json(), None
    except Exception as exc:
        return {}, f"Could not parse SEC company facts: {exc}"


def _fact_values(facts, names):
    usgaap = facts.get("facts", {}).get("us-gaap", {})
    for name in names:
        node = usgaap.get(name)
        if not node:
            continue
        units = node.get("units", {})
        unit = units.get("USD") or next(iter(units.values()), [])
        rows = []
        for row in unit:
            end = row.get("end")
            if not end:
                continue
            form = row.get("form")
            if form not in ("10-Q", "10-K"):
                continue
            rows.append(row)
        if rows:
            return rows
    return []


def _quarterly_sec_metrics(facts):
    # SEC facts are the preferred source for U.S. reported figures. We keep
    # only facts with a fiscal quarter marker where available.
    metrics = {}
    mapping = {
        "net_profit": ["NetIncomeLoss", "ProfitLoss"],
        "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "total_debt": ["LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtCurrent", "LongTermDebtNoncurrent", "LongTermDebt"],
        "cash": ["CashAndCashEquivalentsAtCarryingValue"],
        "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    }
    for label, names in mapping.items():
        rows = _fact_values(facts, names)
        for row in rows:
            end = row.get("end")
            if not end:
                continue
            fp = row.get("fp") or ""
            # Prefer explicit quarterly facts; annual facts are retained only
            # when the period is FY so the UI can show the audit status.
            if fp in ("Q1", "Q2", "Q3", "FY"):
                metrics.setdefault(end, {})[label] = row.get("val")
                metrics[end]["form"] = row.get("form")
                metrics[end]["fp"] = fp
    return metrics


def _sec_filings(symbol, limit=12):
    cik = SEC_CIK.get(symbol)
    if not cik:
        return [], "SEC CIK not configured for this symbol."
    r, err = _get(SEC_SUBMISSIONS.format(cik=cik))
    if not r:
        return [], err
    try:
        recent = r.json().get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession = recent.get("accessionNumber", [])
        primary = recent.get("primaryDocument", [])
        filing_dates = recent.get("filingDate", [])
        periods = recent.get("reportDate", [])
        out = []
        for i, form in enumerate(forms):
            if form not in ("10-Q", "10-K", "20-F", "6-K", "8-K"):
                continue
            acc = accession[i].replace("-", "")
            doc = primary[i]
            out.append({
                "form": form,
                "filing_date": filing_dates[i],
                "report_date": periods[i],
                "accession": accession[i],
                "url": f"{SEC_ARCHIVES}/{int(cik)}/{acc}/{doc}",
            })
            if len(out) >= limit:
                break
        return out, None
    except Exception as exc:
        return [], f"Could not parse SEC submissions: {exc}"


def _strip_html(text):
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _snippet(text, patterns, window=420):
    lower = text.lower()
    for pattern in patterns:
        m = re.search(pattern, lower, flags=re.I)
        if m:
            start = max(0, m.start() - 120)
            end = min(len(text), m.end() + window)
            snippet = text[start:end].strip()
            return snippet[:900]
    return None


def _filing_narrative(filing):
    r, err = _get(filing["url"])
    if not r:
        return {"error": err}
    text = _strip_html(r.text)
    return {
        "refining_margins": _snippet(text, [r"refining margin", r"refining margins", r"crack spread", r"refinery margin"]),
        "crude_supply_terms": _snippet(text, [r"crude supply", r"crude oil supply", r"supply agreement", r"crude purchase agreement"]),
        "expansion_costs": _snippet(text, [r"expansion costs?", r"expansion project", r"growth capital", r"capital expenditures?"]),
        "money_raised_use": _snippet(text, [r"use of proceeds", r"proceeds from the offering", r"net proceeds", r"how we intend to use" ]),
        "source_url": filing["url"],
        "filing_form": filing["form"],
        "filing_date": filing["filing_date"],
        "report_date": filing["report_date"],
    }


def _energy_flags(name, symbol):
    text = f"{name} {symbol}".lower()
    return any(k in text for k in ("oil", "energy", "refin", "petroleum", "seplat", "aradel"))


def get_quarterly_financials(symbol, name, limit=8):
    """Return structured quarterly financial intelligence without inventing missing data.

    Numerical figures use Yahoo's public fundamentals endpoint where available,
    while SEC Company Facts is preferred for U.S. issuers. Narrative fields are
    extracted only from the latest relevant SEC filing and otherwise remain N/A.
    Quarterly SEC filings are normally unaudited; annual 10-K figures are audited.
    """
    types = [
        "quarterlyTotalRevenue", "quarterlyNetIncome", "quarterlyOperatingCashFlow",
        "quarterlyTotalDebt", "quarterlyLongTermDebt", "quarterlyCapitalExpenditure",
        "quarterlyOperatingIncome", "quarterlyGrossProfit",
    ]
    yahoo, yahoo_err = _yahoo_series(symbol, types)
    facts, sec_err = _sec_facts(symbol)
    sec_metrics = _quarterly_sec_metrics(facts) if facts else {}
    periods = sorted(set(yahoo) | set(sec_metrics), reverse=True)[:limit]
    filings, filings_err = _sec_filings(symbol)

    rows = []
    for period in periods:
        y = yahoo.get(period, {})
        s = sec_metrics.get(period, {})
        row = {
            "symbol": symbol,
            "company": name,
            "quarter_end": period,
            "revenue": s.get("revenue", y.get("quarterlyTotalRevenue")),
            "profit": s.get("net_profit", y.get("quarterlyNetIncome")),
            "operating_cash_flow": s.get("operating_cash_flow", y.get("quarterlyOperatingCashFlow")),
            "debt": s.get("total_debt", y.get("quarterlyTotalDebt", y.get("quarterlyLongTermDebt"))),
            "expansion_costs": abs(y.get("quarterlyCapitalExpenditure")) if y.get("quarterlyCapitalExpenditure") is not None else None,
            "operating_income": s.get("operating_income", y.get("quarterlyOperatingIncome")),
            "gross_profit": s.get("gross_profit", y.get("quarterlyGrossProfit")),
            "profit_status": "reported; quarterly filing normally unaudited",
            "data_source": "SEC Company Facts + Yahoo fundamentals" if symbol in SEC_CIK else "Yahoo fundamentals",
            "source_url": f"https://www.sec.gov/edgar/browse/?CIK={SEC_CIK[symbol]}" if symbol in SEC_CIK else "",
        }
        if row["profit"] is not None and s.get("form") == "10-K":
            row["profit_status"] = "audited annual filing (10-K)"
        rows.append(row)

    # Attach the most recent filing narrative to the latest quarter only.
    narrative = {}
    if filings:
        relevant = next((f for f in filings if f["form"] in ("10-Q", "10-K", "20-F", "6-K")), filings[0])
        narrative = _filing_narrative(relevant)
    else:
        narrative = {"error": filings_err or sec_err or yahoo_err or "No filing source available."}

    for row in rows:
        row.update({
            "refining_margins": narrative.get("refining_margins") if _energy_flags(name, symbol) else None,
            "crude_supply_terms": narrative.get("crude_supply_terms") if _energy_flags(name, symbol) else None,
            "money_raised_use": narrative.get("money_raised_use"),
            "narrative_source": narrative.get("source_url", ""),
        })
    if not rows:
        # Still return a transparent status row so the dashboard can explain why.
        return [{
            "symbol": symbol, "company": name, "quarter_end": "N/A", "revenue": None,
            "profit": None, "operating_cash_flow": None, "debt": None, "expansion_costs": None,
            "operating_income": None, "gross_profit": None,
            "profit_status": "NO QUARTERLY DATA", "data_source": "No machine-readable quarterly source returned",
            "source_url": narrative.get("source_url", ""), "refining_margins": None,
            "crude_supply_terms": None, "money_raised_use": None, "narrative_source": narrative.get("source_url", ""),
        }]
    return rows


def latest_quarter(symbol, name):
    rows = get_quarterly_financials(symbol, name, limit=1)
    return rows[0] if rows else None


def fmt_money(value, currency="$", decimals=0):
    if value is None:
        return "N/A"
    try:
        return f"{currency}{float(value):,.{decimals}f}"
    except Exception:
        return "N/A"


def short_text(value, max_len=360):
    if not value:
        return "N/A"
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value if len(value) <= max_len else value[:max_len - 1].rstrip() + "…"
