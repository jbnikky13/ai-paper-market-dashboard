import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timezone, timedelta

st.set_page_config(
    page_title="AI Market Intelligence v4",
    page_icon="🤖",
    layout="wide",
)

# ============================================================
# CONFIG
# ============================================================

COINCAP_BASE = "https://api.coincap.io/v2"
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

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
    "BNBUSDT": ("BNB", "binance-coin"),
    "XRPUSDT": ("XRP", "xrp"),
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

BASE = {
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

COINCAP_TOKEN = get_secret(
    "COINCAP_TOKEN"
)


def supabase_ready():
    return bool(
        SUPABASE_URL
        and SUPABASE_KEY
    )


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ============================================================
# PERSISTENT PAPER HISTORY — SUPABASE
# ============================================================

@st.cache_data(ttl=15)
def load_history():

    if not supabase_ready():
        return []

    try:

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/paper_observations",
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
            f"{SUPABASE_URL}/rest/v1/paper_observations",
            headers=supabase_headers(),
            json=row,
            timeout=10,
        )

        r.raise_for_status()

        load_history.clear()

        return (
            True,
            "Saved."
        )

    except Exception as e:

        return (
            False,
            str(e)
        )


def delete_history():

    if not supabase_ready():

        return (
            False,
            "Supabase is not configured."
        )

    try:

        r = requests.delete(
            f"{SUPABASE_URL}/rest/v1/paper_observations",
            headers=supabase_headers(),
            params={
                "id": "not.is.null"
            },
            timeout=10,
        )

        r.raise_for_status()

        load_history.clear()

        return (
            True,
            "History deleted."
        )

    except Exception as e:

        return (
            False,
            str(e)
        )


# ============================================================
# COINCAP — CRYPTO DATA SOURCE
# ============================================================

def coincap_headers():

    headers = {
        "Accept": "application/json",
        "User-Agent":
            "AI-Market-Intelligence/4.0",
    }

    if COINCAP_TOKEN:

        headers[
            "Authorization"
        ] = f"Bearer {COINCAP_TOKEN}"

    return headers


@st.cache_data(ttl=30)
def coincap_asset_search(query):

    r = requests.get(
        f"{COINCAP_BASE}/assets",
        headers=coincap_headers(),
        params={
            "search": query,
            "limit": 10,
        },
        timeout=15,
    )

    r.raise_for_status()

    return r.json().get(
        "data",
        []
    )


@st.cache_data(ttl=30)
def coincap_history(
    asset_id,
    interval="m15",
    hours=72
):

    end = datetime.now(
        timezone.utc
    )

    start = (
        end
        - timedelta(hours=hours)
    )

    params = {
        "interval": interval,
        "start": int(
            start.timestamp() * 1000
        ),
        "end": int(
            end.timestamp() * 1000
        ),
    }

    r = requests.get(
        f"{COINCAP_BASE}/assets/"
        f"{asset_id}/history",
        headers=coincap_headers(),
        params=params,
        timeout=15,
    )

    r.raise_for_status()

    data = r.json().get(
        "data",
        []
    )

    if not data:

        raise ValueError(
            "CoinCap returned no historical data."
        )

    df = pd.DataFrame(
        data
    )

    df["time"] = pd.to_datetime(
        df["time"],
        unit="ms",
        utc=True,
    )

    df["close"] = pd.to_numeric(
        df["priceUsd"],
        errors="coerce",
    )

    # CoinCap history provides price history.
    # Historical candle volume isn't supplied here.
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

    return df.dropna(
        subset=["close"]
    ).reset_index(
        drop=True
    )


# ============================================================
# YAHOO FINANCE
# ============================================================

@st.cache_data(ttl=120)
def yahoo_history(
    symbol,
    interval="15m"
):

    yahoo_interval = (
        "15m"
        if interval
        in ["1m", "5m", "15m"]
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

        raise ValueError(
            str(error)
            if error
            else
            "Yahoo returned no data."
        )

    result = result[0]

    quote = (
        result[
            "indicators"
        ]["quote"][0]
    )

    df = pd.DataFrame({

        "time":
            pd.to_datetime(
                result["timestamp"],
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
    ).reset_index(
        drop=True
    )


# ============================================================
# BINANCE
# ONLY USED FOR THE SIX TRADFI PERPETUALS
# ============================================================

@st.cache_data(ttl=30)
def binance_klines(
    symbol,
    interval="5m",
    limit=200
):

    r = requests.get(
        "https://api.binance.com/api/v3/klines",
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
        list
    ):

        raise ValueError(
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
            adjust=False
        )
        .mean()
    )

    slow_ema = (
        close
        .ewm(
            span=26,
            adjust=False
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
            np.nan
        )
    )

    rsi = (
        100
        - (
            100
            / (1 + rs)
        )
    )

    avg_volume = (
        df["volume"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    if (
        np.isfinite(avg_volume)
        and avg_volume != 0
    ):

        volume_ratio = float(
            df["volume"].iloc[-1]
            / avg_volume
        )

    else:

        volume_ratio = np.nan

    if len(close) >= 21:

        momentum = float(
            (
                close.iloc[-1]
                / close.iloc[-21]
                - 1
            ) * 100
        )

    else:

        momentum = 0.0

    trend = float(
        (
            fast_ema.iloc[-1]
            / slow_ema.iloc[-1]
            - 1
        ) * 100
    )

    volatility = float(
        returns
        .rolling(20)
        .std()
        .iloc[-1]
        * 100
    )

    return (
        float(
            rsi.iloc[-1]
        ),
        volume_ratio,
        momentum,
        trend,
        volatility,
    )


# ============================================================
# SIGNAL ENGINE
# ============================================================

def make_signal(
    f,
    base
):

    (
        rsi,
        volume_ratio,
        momentum,
        trend,
        volatility,
    ) = f

    score = float(
        base
    )

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
            100
        )
    )

    if score >= 68:

        signal = "Bullish"

    elif score <= 42:

        signal = "Bearish"

    else:

        signal = "Neutral"

    return (
        signal,
        score
    )


def base_for(symbol):

    return BASE.get(
        symbol,
        55
    )


# ============================================================
# SESSION STATE
# ============================================================

if (
    "custom_assets"
    not in st.session_state
):

    st.session_state.custom_assets = []


# ============================================================
# HEADER
# ============================================================

st.title(
    "🤖 AI Market Intelligence — v4"
)

st.caption(
    "Read-only market data • "
    "hypothetical signals • "
    "no real orders • "
    "confidence is a model score, "
    "not a probability of profit."
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
            "Crypto via CoinCap",
            "US/HK/KR stock or ETF",
        ],
    )

    custom_symbol = st.text_input(
        "Symbol or crypto ID",
        placeholder="e.g. SUI, pepe, AAPL",
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
            == "Crypto via CoinCap"
        ):

            try:

                matches = (
                    coincap_asset_search(
                        custom_symbol
                    )
                )

                if not matches:

                    st.error(
                        "No CoinCap asset found."
                    )

                else:

                    top = matches[0]

                    item = {
                        "symbol":
                            top.get(
                                "symbol",
                                "",
                            ).upper(),

                        "name":
                            (
                                custom_name
                                or top.get(
                                    "name",
                                    custom_symbol,
                                )
                            ),

                        "market":
                            "coincap",

                        "asset_id":
                            top["id"],
                    }

                    if (
                        item
                        not in
                        st.session_state
                        .custom_assets
                    ):

                        st.session_state\
                            .custom_assets\
                            .append(item)

                    st.success(
                        f"Added "
                        f"{item['name']} "
                        f"({item['asset_id']})"
                    )

            except Exception as e:

                st.error(
                    f"CoinCap search failed: {e}"
                )

        else:

            item = {
                "symbol":
                    custom_symbol.upper(),

                "name":
                    (
                        custom_name
                        or custom_symbol.upper()
                    ),

                "market":
                    "yahoo",
            }

            if (
                item
                not in
                st.session_state
                .custom_assets
            ):

                st.session_state\
                    .custom_assets\
                    .append(item)

            st.success(
                f"Added "
                f"{item['symbol']}"
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

            st.session_state\
                .custom_assets = []

            st.rerun()

    st.divider()

    if supabase_ready():

        st.success(
            "🟢 Persistent history connected"
        )

    else:

        st.warning(
            "🟡 Persistent history needs Supabase"
        )

    st.caption(
        "Crypto: CoinCap aggregated "
        "market data"
    )


# ============================================================
# WATCHLIST
# ============================================================

if (
    category
    == "TradFi / New Binance Perps"
):

    watch = {

        symbol: {

            "name":
                data["name"],

            "ref":
                data["ref"],

            "theme":
                data["theme"],

            "underlying":
                data["underlying"],

        }

        for symbol, data
        in TRADFI.items()
    }

elif category == "Crypto":

    watch = {

        symbol: {

            "name":
                data[0],

            "ref":
                "CoinCap",

            "theme":
                "Crypto",

            "asset_id":
                data[1],

        }

        for symbol, data
        in CRYPTO.items()
    }

elif category == "US Stocks":

    watch = {

        symbol: {

            "name":
                data[0],

            "ref":
                data[1],

            "theme":
                data[2],

        }

        for symbol, data
        in US_STOCKS.items()
    }

elif category == "Indexes / ETFs":

    watch = {

        symbol: {

            "name":
                data[0],

            "ref":
                data[1],

            "theme":
                data[2],

        }

        for symbol, data
        in ETFS.items()
    }

else:

    watch = {

        item["symbol"]: {

            "name":
                item["name"],

            "ref":
                (
                    "CoinCap"
                    if item["market"]
                    == "coincap"
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

        for item
        in st.session_state
        .custom_assets
    }


# ============================================================
# LOAD DATA
# ============================================================

rows = []
raw = {}
source_map = {}
errors = {}


for symbol, meta in watch.items():

    try:

        if (
            category
            == "TradFi / New Binance Perps"
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

            except Exception as binance_error:

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
                    + str(
                        binance_error
                    )
                )

        elif (
            category == "Crypto"
            or (
                category
                == "Custom Watchlist"
                and meta.get(
                    "market"
                )
                == "coincap"
            )
        ):

            # Crypto deliberately uses CoinCap,
            # not Binance.

            coincap_interval = {

                "5m":
                    "m5",

                "15m":
                    "m15",

                "1h":
                    "h1",

            }[interval]

            df = coincap_history(
                meta["asset_id"],
                coincap_interval,
                hours=72,
            )

            source = "CoinCap"

            status = (
                "🟢 CoinCap"
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

        raw[symbol] = df

        source_map[symbol] = source

        f = get_features(
            df
        )

        signal, confidence = (
            make_signal(
                f,
                base_for(symbol),
            )
        )

        rows.append([

            symbol,

            meta["name"],

            meta["ref"],

            float(
                df["close"]
                .iloc[-1]
            ),

            signal,

            confidence,

            f[0],

            f[2],

            f[3],

            f[1],

            f[4],

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


# ============================================================
# SIGNAL BOARD
# ============================================================

st.subheader(
    f"{category} Signal Board"
)

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


if errors:

    with st.expander(
        "🔧 Data-source diagnostics"
    ):

        for symbol, error in (
            errors.items()
        ):

            st.write(
                f"**{symbol}:** "
                f"{error}"
            )


if category == "Crypto":

    st.info(
        "Crypto data is intentionally "
        "sourced from CoinCap's aggregated "
        "market-data service, not Binance."
    )


if (
    category
    == "TradFi / New Binance Perps"
):

    st.info(
        "If a Binance perpetual is not "
        "live yet, the dashboard automatically "
        "analyzes the listed HKEX/KRX underlying. "
        "When the contract becomes available, "
        "it switches to Binance data."
    )


# ============================================================
# INSPECT ASSET
# ============================================================

available = list(
    raw.keys()
)


if available:

    selected = st.selectbox(
        "Inspect asset",
        available,
    )

    df = raw[selected]

    meta = watch[selected]

    f = get_features(
        df
    )

    signal, confidence = (
        make_signal(
            f,
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
        f"{f[0]:.1f}",
    )

    c4.metric(
        "Momentum",
        f"{f[2]:.2f}%",
    )

    c5.metric(
        "Volatility",
        f"{f[4]:.2f}%",
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
                    df["close"]
                    .iloc[-1]
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
                "Paper observation "
                "saved permanently."
            )

        else:

            st.warning(
                "It was not saved "
                "permanently. "
                + message
            )

else:

    st.warning(
        "No market data is "
        "currently available."
    )


# ============================================================
# PERSISTENT HISTORY
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
                raw[symbol]
                ["close"]
                .iloc[-1]
            )

            recorded_price = float(
                row["price"]
            )

            move = (
                current_price
                / recorded_price
                - 1
            ) * 100

            if (
                row["observation"]
                == "Bullish"
            ):

                correct = (
                    move > 0
                )

            elif (
                row["observation"]
                == "Bearish"
            ):

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
                else "Incorrect"
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
        ].isin(
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
            scored["result"]
            == "Correct"
        ).mean() * 100

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
            "No persistent paper "
            "observations recorded yet."
        )

    else:

        st.warning(
            "Persistent history is "
            "not configured yet."
        )


# ============================================================
# REFRESH TIME
# ============================================================

st.caption(
    "Last refresh: "
    + datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
)
