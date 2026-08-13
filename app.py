import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone

st.set_page_config(
    page_title="AI Market Intelligence",
    page_icon="🤖",
    layout="wide"
)

# ============================================================
# ASSET UNIVERSE
# ============================================================

TRADFI = {
    "ZHONGJIUSDT": {
        "name": "ZhongJi InnoLight",
        "ref": "HKEX 3308",
        "theme": "AI optical infrastructure",
        "underlying": "3308.HK"
    },
    "HANMIUSDT": {
        "name": "Hanmi Semiconductor",
        "ref": "KRX 042700",
        "theme": "HBM / semiconductor equipment",
        "underlying": "042700.KS"
    },
    "SAMSUNGEMUSDT": {
        "name": "Samsung Electro-Mechanics",
        "ref": "KRX 009150",
        "theme": "AI components / MLCC",
        "underlying": "009150.KS"
    },
    "LGELECTRONICSUSDT": {
        "name": "LG Electronics",
        "ref": "KRX 066570",
        "theme": "Electronics / data-center cooling",
        "underlying": "066570.KS"
    },
    "NAVERUSDT": {
        "name": "NAVER",
        "ref": "KRX 035420",
        "theme": "AI / cloud / internet",
        "underlying": "035420.KS"
    },
    "KODEX200USDT": {
        "name": "Samsung KODEX 200 ETF",
        "ref": "KRX 069500",
        "theme": "Korean large-cap index",
        "underlying": "069500.KS"
    }
}

CRYPTO = {
    "BTCUSDT": (
        "Bitcoin",
        "Binance",
        "Crypto / store of value"
    ),
    "ETHUSDT": (
        "Ethereum",
        "Binance",
        "Smart-contract platform"
    ),
    "SOLUSDT": (
        "Solana",
        "Binance",
        "Layer-1 blockchain"
    ),
    "BNBUSDT": (
        "BNB",
        "Binance",
        "Exchange ecosystem"
    ),
    "XRPUSDT": (
        "XRP",
        "Binance",
        "Payments / settlement"
    ),
    "DOGEUSDT": (
        "Dogecoin",
        "Binance",
        "Meme / payments"
    ),
    "LINKUSDT": (
        "Chainlink",
        "Binance",
        "Oracle infrastructure"
    ),
    "AVAXUSDT": (
        "Avalanche",
        "Binance",
        "Layer-1 blockchain"
    )
}

US_STOCKS = {
    "NVDA": (
        "NVIDIA",
        "NASDAQ",
        "AI accelerators / data centers"
    ),
    "AMD": (
        "AMD",
        "NASDAQ",
        "AI accelerators / CPUs"
    ),
    "AVGO": (
        "Broadcom",
        "NASDAQ",
        "AI networking / semiconductors"
    ),
    "MSFT": (
        "Microsoft",
        "NASDAQ",
        "Cloud / AI"
    ),
    "GOOGL": (
        "Alphabet",
        "NASDAQ",
        "AI / cloud / search"
    ),
    "AMZN": (
        "Amazon",
        "NASDAQ",
        "Cloud / AI / commerce"
    ),
    "META": (
        "Meta",
        "NASDAQ",
        "AI / advertising"
    ),
    "TSLA": (
        "Tesla",
        "NASDAQ",
        "EV / autonomy / AI"
    ),
    "AAPL": (
        "Apple",
        "NASDAQ",
        "Consumer tech / AI"
    )
}

ETFS = {
    "QQQ": (
        "Invesco QQQ",
        "NASDAQ",
        "Nasdaq-100"
    ),
    "SPY": (
        "SPDR S&P 500 ETF",
        "NYSE Arca",
        "S&P 500"
    )
}


# ============================================================
# BASE SCORES
# ============================================================

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
    "SPY": 57
}


# ============================================================
# SESSION STATE
# ============================================================

if "custom_assets" not in st.session_state:
    st.session_state.custom_assets = []

if "paper" not in st.session_state:
    st.session_state.paper = []


# ============================================================
# BINANCE DATA
# ============================================================

@st.cache_data(ttl=30)
def binance_klines(symbol, interval="5m", limit=200):

    response = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit
        },
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError("Binance returned no candle data")

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
            "ignore"
        ]
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df["time"] = pd.to_datetime(
        df["open_time"],
        unit="ms",
        utc=True
    )

    return df


# ============================================================
# YAHOO FINANCE DATA
# ============================================================

@st.cache_data(ttl=120)
def yahoo_klines(symbol, interval="15m"):

    if interval in ["1m", "5m", "15m"]:
        yahoo_interval = "15m"
    else:
        yahoo_interval = "1h"

    response = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={
            "range": "5d",
            "interval": yahoo_interval,
            "events": "history"
        },
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=10
    )

    response.raise_for_status()

    result = response.json()["chart"]["result"][0]

    quote = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "time": pd.to_datetime(
            result["timestamp"],
            unit="s",
            utc=True
        ),
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"],
        "volume": quote.get(
            "volume",
            [np.nan] * len(result["timestamp"])
        )
    })

    return df.dropna(
        subset=["close"]
    ).reset_index(drop=True)


# ============================================================
# TECHNICAL FEATURES
# ============================================================

def features(df):

    close = df["close"].astype(float)

    returns = close.pct_change()

    fast_ema = close.ewm(
        span=12,
        adjust=False
    ).mean()

    slow_ema = close.ewm(
        span=26,
        adjust=False
    ).mean()

    # RSI
    delta = close.diff()

    gain = delta.clip(
        lower=0
    ).rolling(14).mean()

    loss = (
        -delta.clip(upper=0)
    ).rolling(14).mean()

    rs = gain / loss.replace(
        0,
        np.nan
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    # Volume ratio
    average_volume = (
        df["volume"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    if (
        np.isfinite(average_volume)
        and average_volume != 0
    ):
        volume_ratio = float(
            df["volume"].iloc[-1]
            / average_volume
        )
    else:
        volume_ratio = np.nan

    # Momentum
    if len(close) >= 21:

        momentum = float(
            (
                close.iloc[-1]
                / close.iloc[-21]
                - 1
            ) * 100
        )

    else:
        momentum = 0

    # EMA trend
    trend = float(
        (
            fast_ema.iloc[-1]
            / slow_ema.iloc[-1]
            - 1
        ) * 100
    )

    # Volatility
    volatility = float(
        returns
        .rolling(20)
        .std()
        .iloc[-1] * 100
    )

    return (
        float(rsi.iloc[-1]),
        volume_ratio,
        momentum,
        trend,
        volatility
    )


# ============================================================
# SIGNAL ENGINE
# ============================================================

def make_signal(features_data, base):

    (
        rsi,
        volume_ratio,
        momentum,
        trend,
        volatility
    ) = features_data

    score = float(base)

    # Momentum
    score += np.clip(
        momentum * 2.0,
        -10,
        10
    )

    # EMA trend
    score += np.clip(
        trend * 80,
        -8,
        8
    )

    # RSI
    if 50 <= rsi <= 70:

        score += 4

    elif rsi > 75:

        score -= 5

    elif rsi < 30:

        score += 3

    # Volume confirmation
    if (
        np.isfinite(volume_ratio)
        and volume_ratio > 1.5
        and momentum > 0
    ):

        score += 4

    # High volatility penalty
    if (
        np.isfinite(volatility)
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

    return signal, score


# ============================================================
# BASE SCORE FOR CUSTOM ASSETS
# ============================================================

def base_for(symbol):

    if symbol in BASE:

        return BASE[symbol]

    # Unknown assets begin neutral.
    return 55


# ============================================================
# PAPER TRADE RESULT
# ============================================================

def direction_correct(
    observation,
    current_price,
    recorded_price
):

    if (
        not np.isfinite(current_price)
        or not np.isfinite(recorded_price)
    ):

        return None

    change = (
        current_price
        / recorded_price
        - 1
    ) * 100

    if observation == "Bullish":

        return change > 0

    if observation == "Bearish":

        return change < 0

    # Neutral = movement less than 0.5%
    return abs(change) < 0.50


# ============================================================
# PAGE TITLE
# ============================================================

st.title(
    "🤖 AI Market Intelligence — Paper Trading"
)

st.caption(
    "Read-only market data • "
    "Hypothetical signals • "
    "No real orders • "
    "Confidence is a model score, not a probability of profit."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Controls")

    category = st.selectbox(
        "Asset category",
        [
            "TradFi / New Binance Perps",
            "Crypto",
            "US Stocks",
            "Indexes / ETFs",
            "Custom Watchlist"
        ]
    )

    interval = st.selectbox(
        "Binance candle interval",
        [
            "1m",
            "5m",
            "15m",
            "1h"
        ],
        index=1
    )

    st.divider()

    st.subheader(
        "🔎 Custom Asset Scanner"
    )

    custom_type = st.selectbox(
        "Market",
        [
            "Binance crypto",
            "US/HK/KR stock or ETF"
        ]
    )

    custom_symbol = st.text_input(
        "Symbol",
        placeholder="e.g. SUIUSDT or AAPL"
    ).strip().upper()

    custom_name = st.text_input(
        "Display name (optional)"
    ).strip()

    if st.button(
        "Add to watchlist"
    ):

        if custom_symbol:

            item = {
                "symbol": custom_symbol,
                "name": (
                    custom_name
                    or custom_symbol
                ),
                "market": (
                    "binance"
                    if custom_type
                    == "Binance crypto"
                    else "yahoo"
                )
            }

            if (
                item
                not in st.session_state.custom_assets
            ):

                st.session_state.custom_assets.append(
                    item
                )

                st.success(
                    f"Added {custom_symbol}"
                )

            else:

                st.info(
                    "Already in custom watchlist."
                )

        else:

            st.warning(
                "Enter a symbol first."
            )

    if st.session_state.custom_assets:

        st.caption(
            "Custom watchlist"
        )

        for item in st.session_state.custom_assets:

            st.write(
                f"• {item['symbol']}"
            )

        if st.button(
            "Clear custom watchlist"
        ):

            st.session_state.custom_assets = []

            st.rerun()

    st.divider()

    if st.button(
        "Clear paper history"
    ):

        st.session_state.paper = []

        st.rerun()


# ============================================================
# BUILD WATCHLIST
# ============================================================

if category == "TradFi / New Binance Perps":

    watch = {
        symbol: {
            "name": data["name"],
            "ref": data["ref"],
            "theme": data["theme"],
            "underlying": data["underlying"]
        }

        for symbol, data
        in TRADFI.items()
    }

elif category == "Crypto":

    watch = {
        symbol: {
            "name": data[0],
            "ref": data[1],
            "theme": data[2]
        }

        for symbol, data
        in CRYPTO.items()
    }

elif category == "US Stocks":

    watch = {
        symbol: {
            "name": data[0],
            "ref": data[1],
            "theme": data[2]
        }

        for symbol, data
        in US_STOCKS.items()
    }

elif category == "Indexes / ETFs":

    watch = {
        symbol: {
            "name": data[0],
            "ref": data[1],
            "theme": data[2]
        }

        for symbol, data
        in ETFS.items()
    }

else:

    watch = {
        item["symbol"]: {
            "name": item["name"],
            "ref": item["market"],
            "theme": "Custom watchlist",
            "market": item["market"]
        }

        for item
        in st.session_state.custom_assets
    }


# ============================================================
# LOAD DATA
# ============================================================

rows = []

raw = {}

source_map = {}


for symbol, meta in watch.items():

    try:

        # ----------------------------------------------------
        # NEW TRADFI BINANCE PERPETUALS
        # ----------------------------------------------------

        if category == "TradFi / New Binance Perps":

            try:

                # First try Binance contract.
                df = binance_klines(
                    symbol,
                    interval
                )

                source = "Binance contract"

            except Exception:

                # If contract doesn't exist yet,
                # use the underlying HKEX/KRX asset.
                df = yahoo_klines(
                    meta["underlying"],
                    interval
                )

                source = (
                    f"Underlying {meta['ref']}"
                )

        # ----------------------------------------------------
        # CRYPTO / CUSTOM
        # ----------------------------------------------------

        elif category in [
            "Crypto",
            "Custom Watchlist"
        ]:

            if (
                category == "Crypto"
                or meta.get("market")
                == "binance"
            ):

                df = binance_klines(
                    symbol,
                    interval
                )

                source = "Binance"

            else:

                df = yahoo_klines(
                    symbol,
                    interval
                )

                source = "Yahoo Finance"

        # ----------------------------------------------------
        # STOCKS / ETFs
        # ----------------------------------------------------

        else:

            df = yahoo_klines(
                symbol,
                interval
            )

            source = "Yahoo Finance"


        # Save data
        raw[symbol] = df

        source_map[symbol] = source

        # Technical indicators
        f = features(df)

        # AI signal
        signal, confidence = make_signal(
            f,
            base_for(symbol)
        )

        rows.append(
            [
                symbol,
                meta["name"],
                meta["ref"],
                float(
                    df["close"].iloc[-1]
                ),
                signal,
                confidence,
                f[0],
                f[2],
                f[3],
                f[1],
                f[4],
                source
            ]
        )


    except Exception:

        rows.append(
            [
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
                "Unavailable"
            ]
        )


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
        "Data source"
    ]
)


st.subheader(
    f"{category} Signal Board"
)


st.dataframe(
    board.style.format(
        {
            "Price": "{:.6f}",
            "Confidence": "{:.0f}%",
            "RSI": "{:.1f}",
            "Momentum %": "{:.2f}",
            "Trend %": "{:.2f}",
            "Volume ratio": "{:.2f}",
            "Volatility %": "{:.2f}"
        }
    ),
    use_container_width=True,
    hide_index=True
)


# ============================================================
# PRE-LAUNCH NOTICE
# ============================================================

if category == "TradFi / New Binance Perps":

    st.info(
        "Pre-launch mode: if a Binance perpetual is "
        "unavailable, the dashboard analyzes its listed "
        "HKEX/KRX underlying instead. After launch, it "
        "automatically switches to Binance contract data."
    )


# ============================================================
# ASSET INSPECTION
# ============================================================

available = list(raw)


if available:

    selected = st.selectbox(
        "Inspect asset",
        available
    )

    df = raw[selected]

    meta = watch[selected]

    f = features(df)

    signal, confidence = make_signal(
        f,
        base_for(selected)
    )


    # Metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Signal",
        signal
    )

    col2.metric(
        "Confidence",
        f"{confidence}%"
    )

    col3.metric(
        "RSI",
        f"{f[0]:.1f}"
    )

    col4.metric(
        "Momentum",
        f"{f[2]:.2f}%"
    )

    col5.metric(
        "Volatility",
        f"{f[4]:.2f}%"
    )


    # Price chart
    st.line_chart(
        df.set_index("time")["close"],
        height=320
    )


    st.caption(
        f"{meta['name']} • "
        f"{meta['ref']} • "
        f"{meta['theme']} • "
        f"Source: {source_map[selected]}"
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
            "Bearish"
        ],
        horizontal=True
    )

    note = st.text_input(
        "Reason / note",
        placeholder=(
            "e.g. positive momentum + "
            "volume confirmation"
        )
    )


    if st.button(
        "Record paper observation"
    ):

        st.session_state.paper.append(
            {
                "Time":
                    datetime.now(
                        timezone.utc
                    ).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    ),

                "Category":
                    category,

                "Symbol":
                    selected,

                "Price":
                    float(
                        df["close"].iloc[-1]
                    ),

                "Signal":
                    signal,

                "Confidence":
                    confidence,

                "Observation":
                    direction,

                "Note":
                    note
            }
        )

        st.success(
            "Paper observation recorded."
        )


else:

    st.warning(
        "No market data is currently "
        "available for this watchlist."
    )


# ============================================================
# PAPER-PREDICTION ACCURACY
# ============================================================

st.subheader(
    "📈 Paper-Prediction Accuracy"
)


if st.session_state.paper:

    history = pd.DataFrame(
        st.session_state.paper
    )

    results = []


    for _, row in history.iterrows():

        try:

            symbol = row["Symbol"]


            if symbol in raw:

                current_price = float(
                    raw[symbol]["close"].iloc[-1]
                )

                recorded_price = float(
                    row["Price"]
                )

                correct = direction_correct(
                    row["Observation"],
                    current_price,
                    recorded_price
                )

                price_change = (
                    current_price
                    / recorded_price
                    - 1
                ) * 100


                results.append(
                    {
                        **row.to_dict(),

                        "Current price":
                            current_price,

                        "Move since observation %":
                            price_change,

                        "Result":
                            (
                                "Correct"
                                if correct
                                else "Incorrect"
                            )
                    }
                )


            else:

                results.append(
                    {
                        **row.to_dict(),

                        "Current price":
                            np.nan,

                        "Move since observation %":
                            np.nan,

                        "Result":
                            "Pending"
                    }
                )


        except Exception:

            results.append(
                {
                    **row.to_dict(),

                    "Current price":
                        np.nan,

                    "Move since observation %":
                        np.nan,

                    "Result":
                        "Pending"
                }
            )


    result_df = pd.DataFrame(
        results
    )


    scored = result_df[
        result_df["Result"].isin(
            [
                "Correct",
                "Incorrect"
            ]
        )
    ]


    if len(scored):

        accuracy = (
            scored["Result"]
            == "Correct"
        ).mean() * 100


        col1, col2, col3 = st.columns(3)


        col1.metric(
            "Scored observations",
            len(scored)
        )


        col2.metric(
            "Model hit rate",
            f"{accuracy:.1f}%"
        )


        col3.metric(
            "Pending",
            int(
                (
                    result_df["Result"]
                    == "Pending"
                ).sum()
            )
        )


    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )


    # CSV export
    st.download_button(
        "⬇️ Download Paper History CSV",
        result_df.to_csv(
            index=False
        ),
        "paper_prediction_history.csv",
        "text/csv"
    )


else:

    st.info(
        "Record paper observations to start "
        "measuring model accuracy."
    )


# ============================================================
# LAST REFRESH
# ============================================================

st.caption(
    "Last refresh: "
    + datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
)
