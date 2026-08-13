import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timezone

# ============================================================
# AI MARKET INTELLIGENCE v4.3
# ============================================================
# DATA SOURCES
# 1. CoinGecko       -> Crypto
# 2. Yahoo Finance   -> US stocks / ETFs
# 3. Binance         -> Existing six contracts
# 4. NGX Pulse       -> Nigerian Exchange stocks
#
# READ-ONLY / PAPER ANALYSIS
# NO REAL ORDERS ARE EXECUTED
# ============================================================

st.set_page_config(
    page_title="AI Market Intelligence v4.3",
    page_icon="🤖",
    layout="wide",
)

# ============================================================
# API BASE URLS
# ============================================================

COINGECKO_PUBLIC_BASE = (
    "https://api.coingecko.com/api/v3"
)

COINGECKO_DEMO_BASE = (
    "https://api.coingecko.com/api/v3"
)

COINGECKO_PRO_BASE = (
    "https://pro-api.coingecko.com/api/v3"
)

YAHOO_BASE = (
    "https://query1.finance.yahoo.com/v8/finance/chart"
)

BINANCE_BASE = (
    "https://api.binance.com/api/v3"
)

NGXPULSE_BASE = (
    "https://www.ngxpulse.ng"
)

# ============================================================
# EXISTING SIX ASSETS
# ============================================================

TRADFI = {
    "ZHONGJIUSDT": {
        "name": "ZhongJi InnoLight",
        "ref": "HKEX 3308",
        "theme": "AI optical infrastructure",
        "underlying": "3308.HK",
    },

    "HANMIUSDT": {
        "name": "Hanmi Semiconductor",
        "ref": "KRX 042700",
        "theme": "HBM / semiconductor equipment",
        "underlying": "042700.KS",
    },

    "SAMSUNGEMUSDT": {
        "name": "Samsung Electro-Mechanics",
        "ref": "KRX 009150",
        "theme": "AI components / MLCC",
        "underlying": "009150.KS",
    },

    "LGELECTRONICSUSDT": {
        "name": "LG Electronics",
        "ref": "KRX 066570",
        "theme": "Electronics / data-center cooling",
        "underlying": "066570.KS",
    },

    "NAVERUSDT": {
        "name": "NAVER",
        "ref": "KRX 035420",
        "theme": "AI / cloud / internet",
        "underlying": "035420.KS",
    },

    "KODEX200USDT": {
        "name": "Samsung KODEX 200 ETF",
        "ref": "KRX 069500",
        "theme": "Korean large-cap index",
        "underlying": "069500.KS",
    },
}

# ============================================================
# CRYPTO
# ============================================================

CRYPTO = {
    "BTCUSDT": ("Bitcoin", "bitcoin"),
    "ETHUSDT": ("Ethereum", "ethereum"),
    "SOLUSDT": ("Solana", "solana"),
    "BNBUSDT": ("BNB", "binancecoin"),
    "XRPUSDT": ("XRP", "ripple"),
    "DOGEUSDT": ("Dogecoin", "dogecoin"),
    "LINKUSDT": ("Chainlink", "chainlink"),
    "AVAXUSDT": ("Avalanche", "avalanche"),
}

# ============================================================
# US STOCKS
# ============================================================

US_STOCKS = {
    "NVDA": ("NVIDIA", "NASDAQ", "AI accelerators / data centers"),
    "AMD": ("AMD", "NASDAQ", "AI accelerators / CPUs"),
    "AVGO": ("Broadcom", "NASDAQ", "AI networking / semiconductors"),
    "MSFT": ("Microsoft", "NASDAQ", "Cloud / AI"),
    "GOOGL": ("Alphabet", "NASDAQ", "AI / cloud / search"),
    "AMZN": ("Amazon", "NASDAQ", "Cloud / AI / commerce"),
    "META": ("Meta", "NASDAQ", "AI / advertising"),
    "TSLA": ("Tesla", "NASDAQ", "EV / autonomy / AI"),
    "AAPL": ("Apple", "NASDAQ", "Consumer tech / AI"),
}

# ============================================================
# ETFs
# ============================================================

ETFS = {
    "QQQ": ("Invesco QQQ", "NASDAQ", "Nasdaq-100"),
    "SPY": ("SPDR S&P 500 ETF", "NYSE Arca", "S&P 500"),
}

# ============================================================
# DEFAULT AI SCORES
# ============================================================

BASE_SCORE = {
    "ZHONGJIUSDT": 68,
    "HANMIUSDT": 74,
    "SAMSUNGEMUSDT": 72,
    "LGELECTRONICSUSDT": 63,
    "NAVERUSDT": 58,
    "KODEX200USDT": 55,

    "BTCUSDT": 60,
    "ETHUSDT": 60,
    "SOLUSDT": 57,
    "BNBUSDT": 58,
    "XRPUSDT": 55,
    "DOGEUSDT": 50,
    "LINKUSDT": 57,
    "AVAXUSDT": 54,

    "NVDA": 67,
    "AMD": 61,
    "AVGO": 65,
    "MSFT": 62,
    "GOOGL": 60,
    "AMZN": 60,
    "META": 61,
    "TSLA": 52,
    "AAPL": 59,

    "QQQ": 58,
    "SPY": 57,
}

# ============================================================
# NGX WATCHLIST
# ============================================================

NGX_WATCHLIST = {
    "DANGCEM": (
        "Dangote Cement Plc",
        "Industrial Goods",
        "Cement / Infrastructure",
    ),

    "GTCO": (
        "Guaranty Trust Holding Company",
        "Financial Services",
        "Banking",
    ),

    "ZENITHBANK": (
        "Zenith Bank Plc",
        "Financial Services",
        "Banking",
    ),

    "ACCESSCORP": (
        "Access Holdings Plc",
        "Financial Services",
        "Banking",
    ),

    "UBA": (
        "United Bank for Africa Plc",
        "Financial Services",
        "Banking",
    ),

    "FIRSTHOLDCO": (
        "First HoldCo Plc",
        "Financial Services",
        "Banking",
    ),

    "MTNN": (
        "MTN Nigeria Communications Plc",
        "ICT",
        "Telecommunications",
    ),

    "AIRTELAFRI": (
        "Airtel Africa Plc",
        "ICT",
        "Telecommunications",
    ),

    "BUAFOODS": (
        "BUA Foods Plc",
        "Consumer Goods",
        "Food / Consumer",
    ),

    "BUACEMENT": (
        "BUA Cement Plc",
        "Industrial Goods",
        "Cement",
    ),

    "SEPLAT": (
        "Seplat Energy Plc",
        "Oil & Gas",
        "Energy",
    ),

    "ARADEL": (
        "Aradel Holdings Plc",
        "Oil & Gas",
        "Energy",
    ),

    "PRESCO": (
        "Presco Plc",
        "Agriculture",
        "Agro-industrial",
    ),

    "NB": (
        "Nigerian Breweries Plc",
        "Consumer Goods",
        "Brewing",
    ),

    "FLOURMILL": (
        "Flour Mills of Nigeria Plc",
        "Consumer Goods",
        "Food",
    ),
}

# ============================================================
# SECRETS
# ============================================================

def get_secret(name, default=""):
    try:
        return st.secrets.get(
            name,
            default,
        )
    except Exception:
        return os.getenv(
            name,
            default,
        )


SUPABASE_URL = get_secret(
    "SUPABASE_URL"
).rstrip("/")

SUPABASE_KEY = get_secret(
    "SUPABASE_KEY"
)

COINGECKO_DEMO_API_KEY = get_secret(
    "COINGECKO_DEMO_API_KEY"
)

COINGECKO_PRO_API_KEY = get_secret(
    "COINGECKO_PRO_API_KEY"
)

NGXPULSE_API_KEY = get_secret(
    "NGXPULSE_API_KEY"
)

# ============================================================
# SESSION STATE
# ============================================================

if "api_diagnostics" not in st.session_state:
    st.session_state.api_diagnostics = []

if "custom_assets" not in st.session_state:
    st.session_state.custom_assets = []

# ============================================================
# DIAGNOSTICS
# ============================================================

def record_api_diagnostic(
    service,
    endpoint,
    status_code=None,
    ok=False,
    message="",
    response="",
):
    st.session_state.api_diagnostics.append({
        "time_utc":
            datetime.now(
                timezone.utc
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "service":
            service,

        "http_status":
            status_code,

        "status":
            "OK" if ok else "ERROR",

        "endpoint":
            endpoint,

        "message":
            message,

        "response":
            str(response)[:500],
    })


# ============================================================
# SUPABASE
# ============================================================

def supabase_ready():
    return bool(
        SUPABASE_URL
        and SUPABASE_KEY
    )


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,

        "Authorization":
            f"Bearer {SUPABASE_KEY}",

        "Content-Type":
            "application/json",

        "Prefer":
            "return=representation",
    }


@st.cache_data(ttl=15)
def load_history():

    if not supabase_ready():
        return []

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/"
            "paper_observations",

            headers=supabase_headers(),

            params={
                "select": "*",
                "order":
                    "created_at.desc",
            },

            timeout=10,
        )

        r.raise_for_status()

        return r.json()

    except Exception:
        return []


def save_history(row):

    if not supabase_ready():
        return (
            False,
            "Supabase is not configured.",
        )

    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/"
            "paper_observations",

            headers=supabase_headers(),

            json=row,

            timeout=10,
        )

        r.raise_for_status()

        load_history.clear()

        return True, "Saved."

    except Exception as e:

        return False, str(e)


def delete_history():

    if not supabase_ready():
        return (
            False,
            "Supabase is not configured.",
        )

    try:
        r = requests.delete(
            f"{SUPABASE_URL}/rest/v1/"
            "paper_observations",

            headers=supabase_headers(),

            params={
                "id": "not.is.null",
            },

            timeout=10,
        )

        r.raise_for_status()

        load_history.clear()

        return True, "History deleted."

    except Exception as e:

        return False, str(e)


# ============================================================
# COINGECKO
# ============================================================

def coingecko_config():

    if COINGECKO_PRO_API_KEY:

        return (
            COINGECKO_PRO_BASE,

            {
                "x-cg-pro-api-key":
                    COINGECKO_PRO_API_KEY
            },

            "CoinGecko Pro",
        )

    if COINGECKO_DEMO_API_KEY:

        return (
            COINGECKO_DEMO_BASE,

            {
                "x-cg-demo-api-key":
                    COINGECKO_DEMO_API_KEY
            },

            "CoinGecko Demo",
        )

    return (
        COINGECKO_PUBLIC_BASE,
        {},
        "CoinGecko Public",
    )


def coingecko_request(
    path,
    params=None,
):

    base, headers, plan = (
        coingecko_config()
    )

    endpoint = (
        f"{base}{path}"
    )

    try:

        r = requests.get(
            endpoint,
            headers=headers,
            params=params or {},
            timeout=15,
        )

        preview = r.text[:500]

        if r.ok:

            data = r.json()

            record_api_diagnostic(
                plan,
                r.url,
                r.status_code,
                True,
                "Request succeeded.",
                preview,
            )

            return data, ""

        if r.status_code == 401:
            message = (
                "401: CoinGecko API key "
                "missing or invalid."
            )

        elif r.status_code == 403:
            message = (
                "403: CoinGecko access denied."
            )

        elif r.status_code == 404:
            message = (
                "404: CoinGecko asset/endpoint "
                "not found."
            )

        elif r.status_code == 429:
            message = (
                "429: CoinGecko rate limit reached."
            )

        else:
            message = (
                f"CoinGecko HTTP "
                f"{r.status_code}."
            )

        record_api_diagnostic(
            plan,
            r.url,
            r.status_code,
            False,
            message,
            preview,
        )

        return None, message

    except Exception as e:

        record_api_diagnostic(
            plan,
            endpoint,
            None,
            False,
            str(e),
        )

        return None, str(e)


@st.cache_data(ttl=60)
def coingecko_history(
    asset_id,
    interval,
):

    days = (
        1
        if interval in ["5m", "15m"]
        else 7
    )

    data, error = coingecko_request(
        f"/coins/{asset_id}/market_chart",
        {
            "vs_currency": "usd",
            "days": days,
        },
    )

    if not data:
        raise RuntimeError(
            error
        )

    prices = data.get(
        "prices",
        [],
    )

    volumes = data.get(
        "total_volumes",
        [],
    )

    if not prices:
        raise RuntimeError(
            "CoinGecko returned no price data."
        )

    df = pd.DataFrame(
        prices,
        columns=[
            "time_ms",
            "close",
        ],
    )

    df["time"] = pd.to_datetime(
        df["time_ms"],
        unit="ms",
        utc=True,
    )

    if volumes:

        volume_df = pd.DataFrame(
            volumes,
            columns=[
                "time_ms",
                "volume",
            ],
        )

        volume_df["time"] = pd.to_datetime(
            volume_df["time_ms"],
            unit="ms",
            utc=True,
        )

        df = pd.merge_asof(
            df.sort_values("time"),
            volume_df[
                ["time", "volume"]
            ].sort_values("time"),
            on="time",
            direction="nearest",
        )

    else:

        df["volume"] = np.nan

    df["open"] = (
        df["close"].shift(1)
    )

    df["high"] = df[
        ["open", "close"]
    ].max(axis=1)

    df["low"] = df[
        ["open", "close"]
    ].min(axis=1)

    if interval == "15m":

        df = df.set_index(
            "time"
        ).resample(
            "15min"
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna(
            subset=["close"]
        ).reset_index()

    elif interval == "1h":

        df = df.set_index(
            "time"
        ).resample(
            "1h"
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna(
            subset=["close"]
        ).reset_index()

    return df


# ============================================================
# YAHOO FINANCE
# ============================================================

@st.cache_data(ttl=120)
def yahoo_history(
    symbol,
    interval="15m",
):

    yahoo_interval = (
        "15m"
        if interval in ["5m", "15m"]
        else "1h"
    )

    r = requests.get(
        f"{YAHOO_BASE}/{symbol}",

        headers={
            "User-Agent":
                "Mozilla/5.0"
        },

        params={
            "range": "5d",
            "interval":
                yahoo_interval,
            "events":
                "history",
        },

        timeout=15,
    )

    r.raise_for_status()

    result = (
        r.json()
        .get("chart", {})
        .get("result")
    )

    if not result:
        raise RuntimeError(
            "Yahoo Finance returned no data."
        )

    result = result[0]

    quote = (
        result
        .get("indicators", {})
        .get("quote", [{}])[0]
    )

    df = pd.DataFrame({
        "time":
            pd.to_datetime(
                result.get(
                    "timestamp",
                    [],
                ),
                unit="s",
                utc=True,
            ),

        "open":
            quote.get("open"),

        "high":
            quote.get("high"),

        "low":
            quote.get("low"),

        "close":
            quote.get("close"),

        "volume":
            quote.get("volume"),
    })

    return df.dropna(
        subset=["close"]
    )


# ============================================================
# BINANCE
# ============================================================

@st.cache_data(ttl=30)
def binance_klines(
    symbol,
    interval="15m",
    limit=200,
):

    r = requests.get(
        f"{BINANCE_BASE}/klines",

        params={
            "symbol":
                symbol,

            "interval":
                interval,

            "limit":
                limit,
        },

        timeout=10,
    )

    r.raise_for_status()

    data = r.json()

    if not isinstance(
        data,
        list,
    ):
        raise RuntimeError(
            "Binance returned no candle data."
        )

    df = pd.DataFrame(
        data,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qv",
            "trades",
            "tb",
            "tq",
            "ignore",
        ],
    )

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df["time"] = pd.to_datetime(
        df["open_time"],
        unit="ms",
        utc=True,
    )

    return df


# ============================================================
# NGX PULSE
# ============================================================

def ngx_headers():

    return {
        "X-API-Key":
            NGXPULSE_API_KEY,

        "Content-Type":
            "application/json",

        "User-Agent":
            "AI-Market-Intelligence-v4.3",
    }


def ngx_ready():
    return bool(
        NGXPULSE_API_KEY
    )


def ngx_request(
    path,
    params=None,
):

    endpoint = (
        f"{NGXPULSE_BASE}{path}"
    )

    if not ngx_ready():

        message = (
            "NGX Pulse API key is missing. "
            "Add NGXPULSE_API_KEY to "
            "Streamlit Secrets."
        )

        record_api_diagnostic(
            "NGX Pulse",
            endpoint,
            None,
            False,
            message,
        )

        return None, message

    try:

        r = requests.get(
            endpoint,
            headers=ngx_headers(),
            params=params or {},
            timeout=15,
        )

        preview = r.text[:500]

        if r.ok:

            try:
                data = r.json()

            except ValueError:

                message = (
                    "NGX Pulse returned HTTP "
                    "success but invalid JSON."
                )

                record_api_diagnostic(
                    "NGX Pulse",
                    r.url,
                    r.status_code,
                    False,
                    message,
                    preview,
                )

                return None, message

            record_api_diagnostic(
                "NGX Pulse",
                r.url,
                r.status_code,
                True,
                "NGX request succeeded.",
                preview,
            )

            return data, ""

        if r.status_code == 401:

            message = (
                "401 Unauthorized: NGXPULSE_API_KEY "
                "is missing or invalid."
            )

        elif r.status_code == 403:

            message = (
                "403 Forbidden: your NGX Pulse "
                "API tier does not permit this endpoint."
            )

        elif r.status_code == 404:

            message = (
                "404: NGX ticker or endpoint "
                "was not found."
            )

        elif r.status_code == 429:

            message = (
                "429: NGX Pulse rate limit reached."
            )

        elif r.status_code >= 500:

            message = (
                f"{r.status_code}: NGX Pulse "
                "server error."
            )

        else:

            message = (
                f"NGX Pulse returned HTTP "
                f"{r.status_code}."
            )

        record_api_diagnostic(
            "NGX Pulse",
            r.url,
            r.status_code,
            False,
            message,
            preview,
        )

        return None, message

    except requests.exceptions.Timeout:

        message = (
            "NGX Pulse request timed out."
        )

        record_api_diagnostic(
            "NGX Pulse",
            endpoint,
            None,
            False,
            message,
        )

        return None, message

    except requests.exceptions.ConnectionError:

        message = (
            "Could not connect to NGX Pulse."
        )

        record_api_diagnostic(
            "NGX Pulse",
            endpoint,
            None,
            False,
            message,
        )

        return None, message

    except Exception as e:

        record_api_diagnostic(
            "NGX Pulse",
            endpoint,
            None,
            False,
            str(e),
        )

        return None, str(e)


# ============================================================
# NGX ALL STOCKS
# ============================================================

@st.cache_data(ttl=300)
def ngx_all_stocks():

    data, error = ngx_request(
        "/api/ngxdata/stocks"
    )

    if not data:

        raise RuntimeError(
            error
        )

    if isinstance(
        data,
        dict,
    ):

        stocks = (
            data.get(
                "data"
            )
            or data.get(
                "stocks"
            )
            or []
        )

    else:

        stocks = data

    if not stocks:

        raise RuntimeError(
            "NGX Pulse returned an empty "
            "stock list."
        )

    return stocks


# ============================================================
# NGX HISTORICAL PRICES
# ============================================================

@st.cache_data(ttl=120)
def ngx_history(
    symbol,
    days=60,
):

    data, error = ngx_request(
        f"/api/ngxdata/prices/"
        f"{symbol}",
        {
            "days":
                days,
        },
    )

    if not data:

        raise RuntimeError(
            error
        )

    # API can return the history directly
    # or inside a data/history object.

    history = []

    if isinstance(
        data,
        dict,
    ):

        history = (
            data.get(
                "history"
            )
            or data.get(
                "data"
            )
            or []
        )

        # Handle a single snapshot.
        if (
            not history
            and
            data.get(
                "current_price"
            ) is not None
        ):

            history = [data]

    elif isinstance(
        data,
        list,
    ):

        history = data

    if not history:

        raise RuntimeError(
            "NGX Pulse returned no historical "
            f"data for {symbol}."
        )

    df = pd.DataFrame(
        history
    )

    # Normalize common NGX Pulse fields.

    date_col = None

    for candidate in [
        "date",
        "trade_date",
        "timestamp",
        "time",
    ]:

        if candidate in df.columns:

            date_col = candidate

            break

    if date_col is None:

        raise RuntimeError(
            "NGX historical response did not "
            "contain a date field."
        )

    price_col = None

    for candidate in [
        "close",
        "current_price",
        "price",
        "close_price",
    ]:

        if candidate in df.columns:

            price_col = candidate

            break

    if price_col is None:

        raise RuntimeError(
            "NGX historical response did not "
            "contain a price field."
        )

    df["time"] = pd.to_datetime(
        df[date_col],
        errors="coerce",
        utc=True,
    )

    df["close"] = pd.to_numeric(
        df[price_col],
        errors="coerce",
    )

    # NGX daily data does not necessarily
    # provide OHLCV in every response.
    # Construct compatible columns.

    for col in [
        "open",
        "high",
        "low",
        "volume",
    ]:

        if col not in df.columns:

            df[col] = np.nan

    df["open"] = pd.to_numeric(
        df["open"],
        errors="coerce",
    )

    df["high"] = pd.to_numeric(
        df["high"],
        errors="coerce",
    )

    df["low"] = pd.to_numeric(
        df["low"],
        errors="coerce",
    )

    df["volume"] = pd.to_numeric(
        df["volume"],
        errors="coerce",
    )

    df["open"] = (
        df["open"]
        .fillna(
            df["close"].shift(1)
        )
    )

    df["high"] = (
        df["high"]
        .fillna(
            df[
                ["open", "close"]
            ].max(axis=1)
        )
    )

    df["low"] = (
        df["low"]
        .fillna(
            df[
                ["open", "close"]
            ].min(axis=1)
        )
    )

    df = df[
        [
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]

    df = (
        df
        .dropna(
            subset=["time", "close"]
        )
        .sort_values("time")
        .drop_duplicates(
            subset=["time"]
        )
        .reset_index(
            drop=True
        )
    )

    if len(df) < 10:

        raise RuntimeError(
            f"Only {len(df)} NGX price points "
            "were returned; at least 10 are "
            "needed for the signal model."
        )

    return df


# ============================================================
# NGX MARKET OVERVIEW
# ============================================================

@st.cache_data(ttl=120)
def ngx_market_overview():

    data, error = ngx_request(
        "/api/ngxdata/market"
    )

    if not data:

        return None, error

    if isinstance(
        data,
        dict,
    ):

        return (
            data.get(
                "data",
                data,
            ),
            "",
        )

    return data, ""


# ============================================================
# TECHNICAL FEATURES
# ============================================================

def get_features(df):

    close = pd.to_numeric(
        df["close"],
        errors="coerce",
    )

    returns = (
        close.pct_change()
    )

    fast_ema = (
        close
        .ewm(
            span=12,
            adjust=False,
        )
        .mean()
    )

    slow_ema = (
        close
        .ewm(
            span=26,
            adjust=False,
        )
        .mean()
    )

    delta = close.diff()

    gain = (
        delta
        .clip(lower=0)
        .rolling(14)
        .mean()
    )

    loss = (
        -delta
        .clip(upper=0)
        .rolling(14)
        .mean()
    )

    rs = (
        gain
        /
        loss.replace(
            0,
            np.nan,
        )
    )

    rsi = (
        100
        -
        100 / (1 + rs)
    )

    volume_mean = (
        df["volume"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    if (
        np.isfinite(
            volume_mean
        )
        and volume_mean != 0
        and np.isfinite(
            df["volume"].iloc[-1]
        )
    ):

        volume_ratio = float(
            df["volume"].iloc[-1]
            /
            volume_mean
        )

    else:

        volume_ratio = np.nan

    if len(close) >= 21:

        momentum = float(
            (
                close.iloc[-1]
                /
                close.iloc[-21]
                - 1
            )
            * 100
        )

    else:

        momentum = 0.0

    trend = float(
        (
            fast_ema.iloc[-1]
            /
            slow_ema.iloc[-1]
            - 1
        )
        * 100
    )

    volatility = float(
        returns
        .rolling(20)
        .std()
        .iloc[-1]
        * 100
    )

    rsi_value = rsi.iloc[-1]

    if not np.isfinite(rsi_value):
        rsi_value = 50.0

    return (
        float(rsi_value),
        volume_ratio,
        momentum,
        trend,
        volatility,
    )


# ============================================================
# SIGNAL MODEL
# ============================================================

def make_signal(
    features,
    base,
):

    (
        rsi,
        volume_ratio,
        momentum,
        trend,
        volatility,
    ) = features

    score = float(base)

    score += np.clip(
        momentum * 2,
        -10,
        10,
    )

    score += np.clip(
        trend * 80,
        -8,
        8,
    )

    if 50 <= rsi <= 70:

        score += 4

    elif rsi > 75:

        score -= 5

    elif rsi < 30:

        score += 3

    if (
        np.isfinite(
            volume_ratio
        )
        and
        volume_ratio > 1.5
        and
        momentum > 0
    ):

        score += 4

    if (
        np.isfinite(
            volatility
        )
        and
        volatility > 3
    ):

        score -= 4

    score = int(
        np.clip(
            score,
            0,
            100,
        )
    )

    if score >= 68:

        signal = "Bullish"

    elif score <= 42:

        signal = "Bearish"

    else:

        signal = "Neutral"

    return signal, score


def base_for(symbol):

    return BASE_SCORE.get(
        symbol,
        55,
    )


# ============================================================
# HEADER
# ============================================================

st.title(
    "🤖 AI Market Intelligence v4.3"
)

st.caption(
    "Crypto • US Markets • Existing six assets "
    "• 🇳🇬 NGX • hypothetical signals "
    "• persistent paper observations "
    "• no real orders"
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Controls"
    )

    category = st.selectbox(
        "Asset category",

        [
            "TradFi / New Binance Perps",
            "Crypto",
            "US Stocks",
            "Indexes / ETFs",
            "🇳🇬 Nigerian Stocks (NGX)",
            "Custom Watchlist",
        ],
    )

    interval = st.selectbox(
        "Analysis interval",

        [
            "5m",
            "15m",
            "1h",
        ],

        index=1,
    )

    st.divider()

    # --------------------------------------------------------
    # API STATUS
    # --------------------------------------------------------

    st.subheader(
        "Data Sources"
    )

    if ngx_ready():

        st.success(
            "🟢 NGX Pulse connected"
        )

    else:

        st.warning(
            "🟡 NGX Pulse key missing"
        )

    _, _, cg_plan = (
        coingecko_config()
    )

    st.info(
        f"Crypto: {cg_plan}"
    )

    if supabase_ready():

        st.success(
            "🟢 Persistent history"
        )

    else:

        st.warning(
            "🟡 Supabase not configured"
        )

    st.divider()

    # --------------------------------------------------------
    # CUSTOM SCANNER
    # --------------------------------------------------------

    st.subheader(
        "🔎 Custom Asset Scanner"
    )

    custom_type = st.selectbox(
        "Market",

        [
            "Crypto via CoinGecko",
            "US/HK/KR stock or ETF",
            "NGX stock",
        ],
    )

    custom_symbol = st.text_input(
        "Symbol / CoinGecko ID"
    ).strip()

    custom_name = st.text_input(
        "Display name (optional)"
    ).strip()

    if st.button(
        "Add to watchlist"
    ):

        if not custom_symbol:

            st.warning(
                "Enter a symbol first."
            )

        else:

            item = {

                "symbol":
                    custom_symbol.upper(),

                "name":
                    custom_name
                    or custom_symbol.upper(),

                "market":
                    custom_type,
            }

            if item not in (
                st.session_state
                .custom_assets
            ):

                st.session_state\
                    .custom_assets\
                    .append(item)

            st.success(
                f"Added {item['symbol']}"
            )

    if st.session_state.custom_assets:

        st.caption(
            "Custom watchlist"
        )

        for item in (
            st.session_state
            .custom_assets
        ):

            st.write(
                f"• {item['name']}"
            )

        if st.button(
            "Clear custom watchlist"
        ):

            st.session_state.custom_assets = []

            st.rerun()


# ============================================================
# BUILD WATCHLIST
# ============================================================

if category == (
    "TradFi / New Binance Perps"
):

    watch = {
        k: dict(v)
        for k, v in TRADFI.items()
    }

elif category == "Crypto":

    watch = {}

    for symbol, data in (
        CRYPTO.items()
    ):

        watch[symbol] = {

            "name":
                data[0],

            "ref":
                "CoinGecko",

            "theme":
                "Crypto",

            "asset_id":
                data[1],
        }

elif category == "US Stocks":

    watch = {}

    for symbol, data in (
        US_STOCKS.items()
    ):

        watch[symbol] = {

            "name":
                data[0],

            "ref":
                data[1],

            "theme":
                data[2],
        }

elif category == (
    "Indexes / ETFs"
):

    watch = {}

    for symbol, data in (
        ETFS.items()
    ):

        watch[symbol] = {

            "name":
                data[0],

            "ref":
                data[1],

            "theme":
                data[2],
        }

elif category == (
    "🇳🇬 Nigerian Stocks (NGX)"
):

    watch = {}

    for symbol, data in (
        NGX_WATCHLIST.items()
    ):

        watch[symbol] = {

            "name":
                data[0],

            "ref":
                "NGX",

            "theme":
                data[2],

            "sector":
                data[1],

            "market":
                "ngx",
        }

else:

    watch = {}

    for item in (
        st.session_state
        .custom_assets
    ):

        market = item[
            "market"
        ]

        watch[
            item["symbol"]
        ] = {

            "name":
                item["name"],

            "ref":
                market,

            "theme":
                "Custom watchlist",

            "market":
                market,
        }


# ============================================================
# LOAD DATA
# ============================================================

rows = []

raw = {}

source_map = {}

errors = {}

for symbol, meta in (
    watch.items()
):

    try:

        # ----------------------------------------------------
        # EXISTING SIX
        # ----------------------------------------------------

        if category == (
            "TradFi / New Binance Perps"
        ):

            try:

                df = binance_klines(
                    symbol,
                    interval,
                )

                source = (
                    "Binance contract"
                )

                status = (
                    "🟢 Live Binance"
                )

            except Exception as e:

                df = yahoo_history(
                    meta["underlying"],
                    interval,
                )

                source = (
                    "Underlying "
                    f"{meta['ref']}"
                )

                status = (
                    "🟡 Underlying fallback"
                )

                errors[symbol] = (
                    "Binance unavailable: "
                    + str(e)
                )

        # ----------------------------------------------------
        # CRYPTO
        # ----------------------------------------------------

        elif category == "Crypto":

            df = coingecko_history(
                meta["asset_id"],
                interval,
            )

            source = cg_plan

            status = (
                f"🟢 {cg_plan}"
            )

        # ----------------------------------------------------
        # NGX
        # ----------------------------------------------------

        elif category == (
            "🇳🇬 Nigerian Stocks (NGX)"
        ):

            df = ngx_history(
                symbol,
                days=60,
            )

            source = (
                "NGX Pulse"
            )

            status = (
                "🟢 NGX Pulse"
            )

        # ----------------------------------------------------
        # CUSTOM
        # ----------------------------------------------------

        elif category == (
            "Custom Watchlist"
        ):

            if meta.get(
                "market"
            ) == "NGX stock":

                df = ngx_history(
                    symbol,
                    days=60,
                )

                source = (
                    "NGX Pulse"
                )

                status = (
                    "🟢 NGX Pulse"
                )

            elif meta.get(
                "market"
            ) == "Crypto via CoinGecko":

                # Treat the supplied symbol as
                # a CoinGecko ID.

                df = coingecko_history(
                    symbol.lower(),
                    interval,
                )

                source = cg_plan

                status = (
                    f"🟢 {cg_plan}"
                )

            else:

                df = yahoo_history(
                    symbol,
                    interval,
                )

                source = (
                    "Yahoo Finance"
                )

                status = (
                    "🟢 Yahoo Finance"
                )

        # ----------------------------------------------------
        # US / ETF
        # ----------------------------------------------------

        else:

            df = yahoo_history(
                symbol,
                interval,
            )

            source = (
                "Yahoo Finance"
            )

            status = (
                "🟢 Yahoo Finance"
            )

        raw[symbol] = df

        source_map[
            symbol
        ] = source

        features = get_features(
            df
        )

        signal, confidence = (
            make_signal(
                features,
                base_for(symbol),
            )
        )

        currency = (
            "₦"
            if category
            == "🇳🇬 Nigerian Stocks (NGX)"
            else "$"
        )

        rows.append([

            symbol,

            meta["name"],

            meta["ref"],

            currency,

            float(
                df[
                    "close"
                ].iloc[-1]
            ),

            signal,

            confidence,

            features[0],

            features[2],

            features[3],

            features[1],

            features[4],

            source,

            status,
        ])

    except Exception as e:

        errors[symbol] = str(e)

        rows.append([

            symbol,

            meta["name"],

            meta["ref"],

            (
                "₦"
                if category
                == "🇳🇬 Nigerian Stocks (NGX)"
                else "$"
            ),

            np.nan,

            "Unavailable",

            0,

            np.nan,

            np.nan,

            np.nan,

            np.nan,

            np.nan,

            "Unavailable",

            "🔴 Data unavailable",
        ])


# ============================================================
# SIGNAL BOARD
# ============================================================

board = pd.DataFrame(

    rows,

    columns=[

        "Symbol",
        "Asset",
        "Reference",
        "Currency",
        "Price",
        "Signal",
        "Confidence",
        "RSI",
        "Momentum %",
        "Trend %",
        "Volume ratio",
        "Volatility %",
        "Data source",
        "Status",
    ],
)

st.subheader(
    f"{category} Signal Board"
)

if not board.empty:

    st.dataframe(

        board.style.format({

            "Price":
                "{:.4f}",

            "Confidence":
                "{:.0f}%",

            "RSI":
                "{:.1f}",

            "Momentum %":
                "{:.2f}",

            "Trend %":
                "{:.2f}",

            "Volume ratio":
                "{:.2f}",

            "Volatility %":
                "{:.2f}",
        }),

        use_container_width=True,

        hide_index=True,
    )

else:

    st.info(
        "No assets are currently "
        "in this watchlist."
    )


# ============================================================
# NGX MARKET OVERVIEW
# ============================================================

if category == (
    "🇳🇬 Nigerian Stocks (NGX)"
):

    st.subheader(
        "🇳🇬 NGX Market Overview"
    )

    market_data, market_error = (
        ngx_market_overview()
    )

    if market_data:

        c1, c2, c3, c4, c5 = (
            st.columns(5)
        )

        asi = market_data.get(
            "asi"
        )

        pct = market_data.get(
            "pct_change"
        )

        market_cap = market_data.get(
            "market_cap"
        )

        volume = market_data.get(
            "volume"
        )

        advancers = market_data.get(
            "advancers"
        )

        decliners = market_data.get(
            "decliners"
        )

        c1.metric(
            "NGX ASI",
            (
                f"{asi:,.2f}"
                if isinstance(
                    asi,
                    (int, float),
                )
                else "N/A"
            ),
        )

        c2.metric(
            "Daily change",
            (
                f"{pct:.2f}%"
                if isinstance(
                    pct,
                    (int, float),
                )
                else "N/A"
            ),
        )

        c3.metric(
            "Market cap",
            (
                f"₦{market_cap:,.0f}"
                if isinstance(
                    market_cap,
                    (int, float),
                )
                else "N/A"
            ),
        )

        c4.metric(
            "Volume",
            (
                f"{volume:,.0f}"
                if isinstance(
                    volume,
                    (int, float),
                )
                else "N/A"
            ),
        )

        c5.metric(
            "Breadth",
            (
                f"{advancers} ↑ / "
                f"{decliners} ↓"
                if
                isinstance(
                    advancers,
                    (int, float),
                )
                and
                isinstance(
                    decliners,
                    (int, float),
                )
                else "N/A"
            ),
        )

    else:

        st.warning(
            "NGX market overview unavailable: "
            f"{market_error}"
        )


# ============================================================
# API DIAGNOSTICS
# ============================================================

with st.expander(
    "🔧 API Diagnostics",
    expanded=bool(
        st.session_state.api_diagnostics
        and any(
            x["status"] == "ERROR"
            for x in
            st.session_state
            .api_diagnostics
        )
    ),
):

    st.write(
        "**NGX Pulse:**",
        (
            "Configured"
            if ngx_ready()
            else
            "API key missing"
        ),
    )

    st.write(
        "**CoinGecko:**",
        cg_plan,
    )

    st.write(
        "**Supabase:**",
        (
            "Connected"
            if supabase_ready()
            else
            "Not configured"
        ),
    )

    if st.session_state.api_diagnostics:

        diagnostics = pd.DataFrame(
            st.session_state
            .api_diagnostics
        )

        st.dataframe(
            diagnostics,
            use_container_width=True,
            hide_index=True,
        )

        latest_error = next(
            (
                item
                for item
                in reversed(
                    st.session_state
                    .api_diagnostics
                )
                if item["status"]
                == "ERROR"
            ),
            None,
        )

        if latest_error:

            st.error(
                "Latest API failure: "
                +
                latest_error[
                    "message"
                ]
            )

            if latest_error[
                "response"
            ]:

                st.code(
                    latest_error[
                        "response"
                    ],
                    language="text",
                )

    else:

        st.info(
            "No API requests recorded yet."
        )

    if st.button(
        "Clear API diagnostics"
    ):

        st.session_state.api_diagnostics = []

        st.rerun()


# ============================================================
# DATA ERRORS
# ============================================================

if errors:

    with st.expander(
        "⚠️ Data-source errors"
    ):

        for symbol, error in (
            errors.items()
        ):

            st.write(
                f"**{symbol}:** {error}"
            )


# ============================================================
# ASSET INSPECTION
# ============================================================

if raw:

    selected = st.selectbox(
        "Inspect asset",
        list(raw.keys()),
    )

    df = raw[selected]

    meta = watch[
        selected
    ]

    features = get_features(
        df
    )

    signal, confidence = (
        make_signal(
            features,
            base_for(selected),
        )
    )

    c1, c2, c3, c4, c5 = (
        st.columns(5)
    )

    c1.metric(
        "Signal",
        signal,
    )

    c2.metric(
        "Confidence",
        f"{confidence}%",
    )

    c3.metric(
        "RSI",
        f"{features[0]:.1f}",
    )

    c4.metric(
        "Momentum",
        f"{features[2]:.2f}%",
    )

    c5.metric(
        "Volatility",
        f"{features[4]:.2f}%",
    )

    st.line_chart(
        df.set_index(
            "time"
        )["close"],
        height=320,
    )

    st.caption(
        f"{meta['name']} • "
        f"{meta['ref']} • "
        f"{meta['theme']} • "
        f"Source: "
        f"{source_map[selected]}"
    )

    # --------------------------------------------------------
    # PAPER OBSERVATION
    # --------------------------------------------------------

    st.subheader(
        "📝 Paper Observation"
    )

    direction = st.radio(
        "Hypothetical observation",

        [
            "Bullish",
            "Neutral",
            "Bearish",
        ],

        horizontal=True,
    )

    note = st.text_input(
        "Reason / note",
        placeholder=(
            "e.g. positive momentum + "
            "trend confirmation"
        ),
    )

    if st.button(
        "Record paper observation"
    ):

        observation = {

            "symbol":
                selected,

            "category":
                category,

            "price":
                float(
                    df[
                        "close"
                    ].iloc[-1]
                ),

            "signal":
                signal,

            "confidence":
                int(
                    confidence
                ),

            "observation":
                direction,

            "note":
                note,

            "created_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }

        ok, message = (
            save_history(
                observation
            )
        )

        if ok:

            st.success(
                "Paper observation saved."
            )

        else:

            st.warning(
                "Observation not permanently "
                "saved: "
                + message
            )

else:

    st.warning(
        "No market data available."
    )


# ============================================================
# PERSISTENT PAPER HISTORY
# ============================================================

st.subheader(
    "📈 Persistent Paper-Prediction History"
)

history = load_history()

if history:

    history_df = pd.DataFrame(
        history
    )

    results = []

    for _, row in (
        history_df.iterrows()
    ):

        current_price = np.nan

        move = np.nan

        result = "Pending"

        symbol = row.get(
            "symbol"
        )

        if symbol in raw:

            current_price = float(
                raw[
                    symbol
                ][
                    "close"
                ].iloc[-1]
            )

            recorded_price = float(
                row["price"]
            )

            move = (
                current_price
                /
                recorded_price
                - 1
            ) * 100

            observation = row[
                "observation"
            ]

            if observation == "Bullish":

                correct = (
                    move > 0
                )

            elif observation == "Bearish":

                correct = (
                    move < 0
                )

            else:

                correct = (
                    abs(move)
                    < 0.50
                )

            result = (
                "Correct"
                if correct
                else
                "Incorrect"
            )

        results.append({

            **row.to_dict(),

            "current_price":
                current_price,

            "move_since_observation_%":
                move,

            "result":
                result,
        })

    result_df = pd.DataFrame(
        results
    )

    scored = result_df[
        result_df["result"].isin(
            [
                "Correct",
                "Incorrect",
            ]
        )
    ]

    a, b, c = (
        st.columns(3)
    )

    a.metric(
        "Total observations",
        len(result_df),
    )

    if len(scored):

        accuracy = (
            (
                scored["result"]
                == "Correct"
            ).mean()
            * 100
        )

        b.metric(
            "Observed hit rate",
            f"{accuracy:.1f}%",
        )

    else:

        b.metric(
            "Observed hit rate",
            "Pending",
        )

    c.metric(
        "Pending",
        int(
            (
                result_df["result"]
                == "Pending"
            ).sum()
        ),
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "⬇️ Download paper history CSV",

        result_df.to_csv(
            index=False
        ),

        "paper_prediction_history.csv",

        "text/csv",
    )

    if st.button(
        "Delete all persistent paper history"
    ):

        ok, message = (
            delete_history()
        )

        if ok:

            st.success(
                message
            )

            st.rerun()

        else:

            st.error(
                message
            )

else:

    if supabase_ready():

        st.info(
            "No persistent paper observations "
            "recorded yet."
        )

    else:

        st.warning(
            "Persistent history requires "
            "Supabase credentials."
        )


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "AI Market Intelligence v4.3 • "
    "CoinGecko • Yahoo Finance • Binance • "
    "NGX Pulse • Persistent paper history • "
    "Read-only analysis • "
    "No real orders"
)
