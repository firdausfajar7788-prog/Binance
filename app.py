import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Crypto Scanner Test",
    layout="wide"
)

st.title("🚀 CoinGecko Test")

try:

    url = "https://api.coingecko.com/api/v3/coins/markets"

    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 20,
        "page": 1,
        "sparkline": False
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    data = response.json()

    st.success("Berhasil ambil data CoinGecko")

    df = pd.DataFrame(data)

    st.dataframe(
        df[[
            "name",
            "symbol",
            "current_price",
            "market_cap_rank",
            "price_change_percentage_24h"
        ]]
    )

except Exception as e:

    st.error(f"Error: {e}")
