# ============================================================
# COINCAP — CRYPTO DATA SOURCE
# ============================================================

COINCAP_BASE = "https://rest.coincap.io/v3"

if "api_diagnostics" not in st.session_state:
    st.session_state.api_diagnostics = []


def reset_api_diagnostics():
    st.session_state.api_diagnostics = []


def record_api_diagnostic(
    service,
    endpoint,
    method,
    http_status=None,
    ok=False,
    message="",
    response_preview="",
):
    st.session_state.api_diagnostics.append({
        "time_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        ),
        "service": service,
        "method": method,
        "http_status": http_status,
        "status": "OK" if ok else "ERROR",
        "endpoint": endpoint,
        "message": message,
        "response": response_preview[:500],
    })


def coincap_headers():
    headers = {
        "Accept": "application/json",
        "User-Agent": "AI-Market-Intelligence/4.1",
    }

    if COINCAP_TOKEN:
        headers["Authorization"] = f"Bearer {COINCAP_TOKEN}"

    return headers


def coincap_request(path, params=None):

    endpoint = f"{COINCAP_BASE}{path}"

    try:

        response = requests.get(
            endpoint,
            headers=coincap_headers(),
            params=params or {},
            timeout=15,
        )

        preview = response.text[:500]

        if response.ok:

            try:
                payload = response.json()

            except ValueError:

                error = (
                    "HTTP succeeded, but CoinCap returned "
                    "invalid JSON."
                )

                record_api_diagnostic(
                    "CoinCap",
                    response.url,
                    "GET",
                    response.status_code,
                    False,
                    error,
                    preview,
                )

                return None, response, error

            record_api_diagnostic(
                "CoinCap",
                response.url,
                "GET",
                response.status_code,
                True,
                "Request succeeded.",
                preview,
            )

            return payload, response, ""

        if response.status_code == 401:

            explanation = (
                "401 Unauthorized — the CoinCap API key "
                "is missing or invalid. Check COINCAP_TOKEN "
                "in Streamlit Secrets."
            )

        elif response.status_code == 403:

            explanation = (
                "403 Forbidden — the API key may be invalid, "
                "expired, or the endpoint may not be available "
                "on the current CoinCap plan."
            )

        elif response.status_code == 404:

            explanation = (
                "404 Not Found — check the CoinCap v3 endpoint "
                "or asset ID."
            )

        elif response.status_code == 429:

            explanation = (
                "429 Too Many Requests — CoinCap rate limit "
                "reached. Wait and retry."
            )

        elif response.status_code >= 500:

            explanation = (
                f"{response.status_code} server error "
                "returned by CoinCap."
            )

        else:

            explanation = (
                f"CoinCap returned HTTP "
                f"{response.status_code}."
            )

        record_api_diagnostic(
            "CoinCap",
            response.url,
            "GET",
            response.status_code,
            False,
            explanation,
            preview,
        )

        return None, response, explanation

    except requests.exceptions.Timeout:

        error = (
            "Request timed out after 15 seconds. "
            "The deployed app could not reach CoinCap."
        )

        record_api_diagnostic(
            "CoinCap",
            endpoint,
            "GET",
            None,
            False,
            error,
            "",
        )

        return None, None, error

    except requests.exceptions.ConnectionError as e:

        error = (
            "Connection error — the deployed app could "
            f"not connect to CoinCap. Details: {e}"
        )

        record_api_diagnostic(
            "CoinCap",
            endpoint,
            "GET",
            None,
            False,
            error,
            "",
        )

        return None, None, error

    except Exception as e:

        error = (
            f"Unexpected CoinCap request error: {e}"
        )

        record_api_diagnostic(
            "CoinCap",
            endpoint,
            "GET",
            None,
            False,
            error,
            "",
        )

        return None, None, error


@st.cache_data(ttl=60)
def coincap_find_asset(query):

    query_clean = query.strip().lower()

    payload, response, error = coincap_request(
        f"/assets/{query_clean}"
    )

    if payload and isinstance(payload, dict):

        data = payload.get("data")

        if isinstance(data, dict) and data.get("id"):
            return data, ""

    payload, response, collection_error = coincap_request(
        "/assets",
        params={"limit": 2000},
    )

    if payload and isinstance(payload, dict):

        assets = payload.get("data", [])

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

            if query_clean in {
                asset_id,
                symbol,
                name,
            }:

                return asset, ""

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
                query_clean in asset_id
                or query_clean in symbol
                or query_clean in name
            ):

                return asset, ""

    return None, (
        collection_error
        or error
        or f"No CoinCap asset matched '{query}'."
    )


@st.cache_data(ttl=60)
def coincap_history(
    asset_id,
    interval="m15",
    hours=72,
):

    end = datetime.now(timezone.utc)

    start = end - timedelta(
        hours=hours
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

    payload, response, error = coincap_request(
        f"/assets/{asset_id}/history",
        params=params,
    )

    if not payload:

        raise RuntimeError(
            error or
            "CoinCap returned no response."
        )

    data = payload.get(
        "data",
        []
    )

    if not data:

        raise RuntimeError(
            "CoinCap returned HTTP success "
            "but no historical data for "
            f"'{asset_id}'."
        )

    df = pd.DataFrame(data)

    if (
        "time" not in df.columns
        or "priceUsd" not in df.columns
    ):

        raise RuntimeError(
            "CoinCap response is missing "
            "'time' or 'priceUsd'."
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

    df["open"] = df["close"].shift(1)

    df["high"] = df[
        ["open", "close"]
    ].max(axis=1)

    df["low"] = df[
        ["open", "close"]
    ].min(axis=1)

    df["volume"] = np.nan

    return (
        df
        .dropna(subset=["close"])
        .reset_index(drop=True)
    )
