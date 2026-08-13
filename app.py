import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timezone

# ============================================================
# AI MARKET INTELLIGENCE v4.2
# CoinGecko crypto data + Yahoo Finance + Binance fallback
# Read-only / paper-analysis dashboard
# ============================================================

st.set_page_config(
    page_title="AI Market Intelligence v4.2",
    page_icon="🤖",
    layout="wide",
)

# ============================================================
# CONFIG
# ============================================================

COINGECKO_PUBLIC_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_DEMO_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_PRO_BASE = "https://pro-api.coingecko.com/api/v3"

YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
BINANCE_BASE = "https://api.binance.com/api/v3"

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

ETFS = {
    "QQQ": ("Invesco QQQ", "NASDAQ", "Nasdaq-100"),
    "SPY": ("SPDR S&P 500 ETF", "NYSE Arca", "S&P 500"),
}

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
# SECRETS
# ============================================================

def get_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)


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

# ============================================================
# SESSION STATE
# ============================================================

if "api_diagnostics" not in st.session_state:
    st.session_state.api_diagnostics = []

if "custom_assets" not in st.session_state:
    st.session_state.custom_assets = []

# ============================================================
# API DIAGNOSTICS
# ============================================================

def reset_api_diagnostics():
    st.session_state.api_diagnostics = []


def record_api_diagnostic(
    service,
    endpoint,
    status_code=None,
    ok=False,
    message="",
    response="",
):
    st.session_state.api_diagnostics.append({
        "time_utc": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S"),

        "service": service,

        "http_status": status_code,

        "status": (
            "OK"
            if ok
            else "ERROR"
        ),

        "endpoint": endpoint,

        "message": message,

        "response": str(response)[:500],
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
        "Authorization": (
            f"Bearer {SUPABASE_KEY}"
        ),
        "Content-Type": "application/json",
        "Prefer": "return=representation",
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
                "order": "created_at.desc",
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
            "Supabase is not configured."
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
            "Supabase is not configured."
        )

    try:

        r = requests.delete(
            f"{SUPABASE_URL}/rest/v1/"
            "paper_observations",

            headers=supabase_headers(),

            params={
                "id": "not.is.null"
            },

            timeout=10,
        )

        r.raise_for_status()

        load_history.clear()

        return True, "History deleted."

    except Exception as e:

        return False, str(e)

# ============================================================
# COINGECKO CONFIGURATION
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


# ============================================================
# COINGECKO REQUEST
# ============================================================

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

        response = requests.get(
            endpoint,
            headers=headers,
            params=params or {},
            timeout=15,
        )

        preview = response.text[:500]

        if response.ok:

            try:

                payload = response.json()

            except ValueError:

                message = (
                    "CoinGecko returned HTTP "
                    "success but the response "
                    "was not valid JSON."
                )

                record_api_diagnostic(
                    plan,
                    response.url,
                    response.status_code,
                    False,
                    message,
                    preview,
                )

                return None, message

            record_api_diagnostic(
                plan,
                response.url,
                response.status_code,
                True,
                "Request succeeded.",
                preview,
            )

            return payload, ""

        if response.status_code == 401:

            message = (
                "401 Unauthorized: the "
                "CoinGecko API key is "
                "missing or invalid."
            )

        elif response.status_code == 403:

            message = (
                "403 Forbidden: the selected "
                "CoinGecko endpoint or API "
                "key is not permitted."
            )

        elif response.status_code == 404:

            message = (
                "404 Not Found: check the "
                "CoinGecko coin ID or endpoint."
            )

        elif response.status_code == 429:

            message = (
                "429 Too Many Requests: "
                "CoinGecko rate limit reached. "
                "Wait and retry."
            )

        elif response.status_code >= 500:

            message = (
                f"{response.status_code}: "
                "CoinGecko server error."
            )

        else:

            message = (
                f"CoinGecko returned HTTP "
                f"{response.status_code}."
            )

        record_api_diagnostic(
            plan,
            response.url,
            response.status_code,
            False,
            message,
            preview,
        )

        return None, message

    except requests.exceptions.Timeout:

        message = (
            "Connection timed out after "
            "15 seconds."
        )

        record_api_diagnostic(
            plan,
            endpoint,
            None,
            False,
            message,
        )

        return None, message

    except requests.exceptions.ConnectionError as e:

        message = (
            "Connection error while contacting "
            f"CoinGecko: {e}"
        )

        record_api_diagnostic(
            plan,
            endpoint,
            None,
            False,
            message,
        )

        return None, message

    except Exception as e:

        message = (
            f"Unexpected CoinGecko error: {e}"
        )

        record_api_diagnostic(
            plan,
            endpoint,
            None,
            False,
            message,
        )

        return None, message


# ============================================================
# COINGECKO COIN LIST
# ============================================================

@st.cache_data(ttl=300)
def coingecko_coin_list():

    payload, error = (
        coingecko_request(
            "/coins/list",
            {
                "include_platform":
                    "false"
            },
        )
    )

    if not payload:

        raise RuntimeError(
            error
            or
            "CoinGecko returned no coin list."
        )

    return payload


# ============================================================
# FIND COINGECKO ASSET
# ============================================================

@st.cache_data(ttl=120)
def coingecko_find_asset(query):

    query = query.strip().lower()

    payload, error = (
        coingecko_request(
            f"/coins/{query}",

            {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
            },
        )
    )

    if payload and payload.get("id"):

        return payload, ""

    try:

        assets = (
            coingecko_coin_list()
        )

    except Exception as e:

        return None, str(e)

    exact = []

    for asset in assets:

        asset_id = str(
            asset.get("id", "")
        ).lower()

        symbol = str(
            asset.get("symbol", "")
        ).lower()

        name = str(
            asset.get("name", "")
        ).lower()

        if query in {
            asset_id,
            symbol,
            name,
        }:

            exact.append(asset)

    if exact:

        return exact[0], ""

    partial = []

    for asset in assets:

        asset_id = str(
            asset.get("id", "")
        ).lower()

        symbol = str(
            asset.get("symbol", "")
        ).lower()

        name = str(
            asset.get("name", "")
        ).lower()

        if (
            query in asset_id
            or query in symbol
            or query in name
        ):

            partial.append(asset)

    if partial:

        return partial[0], ""

    return None, (
        f"No CoinGecko coin matched "
        f"'{query}'."
    )


# ============================================================
# COINGECKO HISTORICAL DATA
# ============================================================

@st.cache_data(ttl=60)
def coingecko_history(
    asset_id,
    interval="15m",
):

    if interval in [
        "5m",
        "15m",
    ]:

        days = 1

    else:

        days = 7

    payload, error = (
        coingecko_request(
            f"/coins/{asset_id}/"
            "market_chart",

            {
                "vs_currency": "usd",
                "days": days,
            },
        )
    )

    if not payload:

        raise RuntimeError(
            error
            or
            "CoinGecko returned no "
            "historical data."
        )

    prices = payload.get(
        "prices",
        []
    )

    volumes = payload.get(
        "total_volumes",
        []
    )

    if not prices:

        raise RuntimeError(
            f"No price history returned "
            f"for '{asset_id}'."
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

    df["close"] = pd.to_numeric(
        df["close"],
        errors="coerce",
    )

    if volumes:

        volume_df = pd.DataFrame(
            volumes,
            columns=[
                "volume_time_ms",
                "volume",
            ],
        )

        volume_df["time"] = pd.to_datetime(
            volume_df[
                "volume_time_ms"
            ],
            unit="ms",
            utc=True,
        )

        volume_df["volume"] = pd.to_numeric(
            volume_df["volume"],
            errors="coerce",
        )

        volume_df = volume_df[
            [
                "time",
                "volume",
            ]
        ]

        df = pd.merge_asof(
            df.sort_values("time"),
            volume_df.sort_values("time"),
            on="time",
            direction="nearest",
        )

    else:

        df["volume"] = np.nan

    # Build simple OHLC from price points.
    df["open"] = (
        df["close"].shift(1)
    )

    df["high"] = df[
        [
            "open",
            "close",
        ]
    ].max(axis=1)

    df["low"] = df[
        [
            "open",
            "close",
        ]
    ].min(axis=1)

    df = (
        df[
            [
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ]
        .dropna(
            subset=["close"]
        )
        .set_index("time")
    )

    if interval == "15m":

        df = df.resample(
            "15min"
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        })

    elif interval == "1h":

        df = df.resample(
            "1h"
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        })

    df = (
        df
        .dropna(
            subset=["close"]
        )
        .reset_index()
    )

    if len(df) < 10:

        raise RuntimeError(
            "CoinGecko returned too few "
            "data points for the signal model."
        )

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
        if interval in [
            "5m",
            "15m",
        ]
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
            "interval": yahoo_interval,
            "events": "history",
        },

        timeout=15,
    )

    r.raise_for_status()

    payload = r.json()

    result = (
        payload
        .get("chart", {})
        .get("result")
    )

    if not result:

        error = (
            payload
            .get("chart", {})
            .get("error")
        )

        raise RuntimeError(
            str(error)
            if error
            else
            "Yahoo returned no data."
        )

    result = result[0]

    quote = (
        result
        .get("indicators", {})
        .get("quote", [{}])[0]
    )

    timestamps = result.get(
        "timestamp",
        []
    )

    df = pd.DataFrame({
        "time": pd.to_datetime(
            timestamps,
            unit="s",
            utc=True,
        ),

        "open": quote.get("open"),

        "high": quote.get("high"),

        "low": quote.get("low"),

        "close": quote.get("close"),

        "volume": quote.get("volume"),
    })

    return (
        df
        .dropna(
            subset=["close"]
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# BINANCE
# ============================================================

@st.cache_data(ttl=30)
def binance_klines(
    symbol,
    interval="5m",
    limit=200,
):

    r = requests.get(
        f"{BINANCE_BASE}/klines",

        params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
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
            "Binance returned no "
            "candle data."
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
# TECHNICAL FEATURES
# ============================================================

def get_features(df):

    close = (
        df["close"]
        .astype(float)
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
        / loss.replace(
            0,
            np.nan,
        )
    )

    rsi = (
        100
        - 100 / (1 + rs)
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
            / volume_mean
        )

    else:

        volume_ratio = np.nan

    if len(close) >= 21:

        momentum = float(
            (
                close.iloc[-1]
                / close.iloc[-21]
                - 1
            )
            * 100
        )

    else:

        momentum = 0.0

    trend = float(
        (
            fast_ema.iloc[-1]
            / slow_ema.iloc[-1]
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

    return (
        float(rsi.iloc[-1]),
        volume_ratio,
        momentum,
        trend,
        volatility,
    )


# ============================================================
# HYPOTHETICAL SIGNAL MODEL
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
        and volume_ratio > 1.5
        and momentum > 0
    ):

        score += 4

    if (
        np.isfinite(
            volatility
        )
        and volatility > 3
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
    "🤖 AI Market Intelligence v4.2"
)

st.caption(
    "Read-only market data • "
    "hypothetical signals • "
    "persistent paper observations • "
    "no real orders"
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

    st.subheader(
        "🔎 Custom Asset Scanner"
    )

    custom_type = st.selectbox(
        "Market",

        [
            "Crypto via CoinGecko",
            "US/HK/KR stock or ETF",
        ],
    )

    custom_symbol = st.text_input(
        "Symbol or crypto ID",

        placeholder=(
            "e.g. SUI, pepe, AAPL"
        ),
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

        elif (
            custom_type
            == "Crypto via CoinGecko"
        ):

            asset, error = (
                coingecko_find_asset(
                    custom_symbol
                )
            )

            if not asset:

                st.error(
                    "CoinGecko lookup failed: "
                    f"{error}"
                )

            else:

                item = {

                    "symbol": str(
                        asset.get(
                            "symbol",
                            custom_symbol,
                        )
                    ).upper(),

                    "name": (
                        custom_name
                        or asset.get(
                            "name",
                            custom_symbol,
                        )
                    ),

                    "market":
                        "coingecko",

                    "asset_id":
                        asset["id"],
                }

                if item not in (
                    st.session_state
                    .custom_assets
                ):

                    st.session_state\
                        .custom_assets\
                        .append(item)

                st.success(
                    f"Added {item['name']}"
                )

        else:

            item = {

                "symbol":
                    custom_symbol.upper(),

                "name": (
                    custom_name
                    or custom_symbol.upper()
                ),

                "market":
                    "yahoo",
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
                f"• {item['name']} "
                f"({item['symbol']})"
            )

        if st.button(
            "Clear custom watchlist"
        ):

            st.session_state.custom_assets = []

            st.rerun()

    st.divider()

    _, _, cg_plan = (
        coingecko_config()
    )

    st.info(
        f"Crypto source: {cg_plan}"
    )

    if cg_plan == (
        "CoinGecko Public"
    ):

        st.caption(
            "No API key configured. "
            "Using CoinGecko public API."
        )

    elif cg_plan == (
        "CoinGecko Demo"
    ):

        st.success(
            "CoinGecko Demo API key detected."
        )

    else:

        st.success(
            "CoinGecko Pro API key detected."
        )

    if supabase_ready():

        st.success(
            "🟢 Persistent history connected"
        )

    else:

        st.warning(
            "🟡 Persistent history needs Supabase"
        )


# ============================================================
# BUILD WATCHLIST
# ============================================================

if category == (
    "TradFi / New Binance Perps"
):

    watch = {
        symbol: {
            **data
        }

        for symbol, data
        in TRADFI.items()
    }

elif category == "Crypto":

    watch = {}

    for symbol, data in CRYPTO.items():

        watch[symbol] = {

            "name": data[0],

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

            "name": data[0],

            "ref": data[1],

            "theme": data[2],
        }

elif category == (
    "Indexes / ETFs"
):

    watch = {}

    for symbol, data in (
        ETFS.items()
    ):

        watch[symbol] = {

            "name": data[0],

            "ref": data[1],

            "theme": data[2],
        }

else:

    watch = {}

    for item in (
        st.session_state
        .custom_assets
    ):

        watch[item["symbol"]] = {

            "name":
                item["name"],

            "ref": (
                "CoinGecko"
                if item["market"]
                == "coingecko"
                else
                "Yahoo Finance"
            ),

            "theme":
                "Custom watchlist",

            "market":
                item["market"],

            "asset_id":
                item.get(
                    "asset_id"
                ),
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
        # TRADFI
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
                    f"Underlying "
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

        elif (
            category == "Crypto"

            or (

                category
                == "Custom Watchlist"

                and
                meta.get("market")
                == "coingecko"
            )
        ):

            df = coingecko_history(
                meta["asset_id"],
                interval,
            )

            _, _, cg_plan = (
                coingecko_config()
            )

            source = cg_plan

            status = (
                f"🟢 {cg_plan}"
            )

        # ----------------------------------------------------
        # STOCKS / ETFs
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

        source_map[symbol] = source

        features = get_features(
            df
        )

        signal, confidence = (
            make_signal(
                features,
                base_for(symbol),
            )
        )

        rows.append([

            symbol,

            meta["name"],

            meta["ref"],

            float(
                df["close"].iloc[-1]
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
                "{:.6f}",

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
# API DIAGNOSTICS
# ============================================================

with st.expander(
    "🔧 API Diagnostics",
    expanded=bool(

        st.session_state
        .api_diagnostics

        and any(

            x["status"]
            == "ERROR"

            for x in (
                st.session_state
                .api_diagnostics
            )
        )
    ),
):

    base, _, cg_plan = (
        coingecko_config()
    )

    st.write(
        "**CoinGecko mode:**",
        cg_plan,
    )

    st.code(
        base
    )

    if cg_plan == (
        "CoinGecko Public"
    ):

        st.info(
            "No CoinGecko key is configured. "
            "Using the public API."
        )

    elif cg_plan == (
        "CoinGecko Demo"
    ):

        st.success(
            "CoinGecko Demo key detected."
        )

    else:

        st.success(
            "CoinGecko Pro key detected."
        )

    if (
        st.session_state
        .api_diagnostics
    ):

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

                for item in reversed(
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
                + latest_error[
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
            "No API requests have "
            "been recorded yet."
        )

    if st.button(
        "Clear API diagnostics"
    ):

        reset_api_diagnostics()

        st.rerun()


# ============================================================
# DATA SOURCE ERRORS
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


if category == "Crypto":

    st.info(
        "Crypto data is supplied by "
        "CoinGecko. This dashboard is "
        "read-only and does not send "
        "cryptocurrency orders."
    )


if category == (
    "TradFi / New Binance Perps"
):

    st.info(
        "If a contract is unavailable, "
        "the dashboard falls back to "
        "its configured HKEX/KRX underlying."
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

    meta = watch[selected]

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
        "Confidence score",
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

    # ========================================================
    # PAPER OBSERVATION
    # ========================================================

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
                "Observation was not saved "
                "permanently: "
                + message
            )

else:

    st.warning(
        "No market data is currently available."
    )


# ============================================================
# PAPER HISTORY
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
                raw[symbol][
                    "close"
                ].iloc[-1]
            )

            recorded_price = float(
                row["price"]
            )

            move = (
                current_price
                / recorded_price
                - 1
            ) * 100

            observation = row[
                "observation"
            ]

            if observation == (
                "Bullish"
            ):

                correct = move > 0

            elif observation == (
                "Bearish"
            ):

                correct = move < 0

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
        result_df[
            "result"
        ].isin([
            "Correct",
            "Incorrect",
        ])
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
                scored[
                    "result"
                ]
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
                result_df[
                    "result"
                ]
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
            "Persistent history is not configured. "
            "Add Supabase credentials to enable it."
        )


# ============================================================
# FOOTER
# ============================================================

st.caption(

    "AI Market Intelligence v4.2 • "
    "CoinGecko crypto data • "
    "Yahoo Finance • "
    "Binance fallback • "
    "Persistent paper history • "
    "Read-only analysis • "
    "Last refresh: "

    + datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
)
