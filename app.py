import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="AI Daily Scanner",
    layout="wide"
)

st.title("🚀 AI Daily Crypto Scanner")

# ====================================
# GET TOP 100 COINS
# ====================================
url = "https://api.coingecko.com/api/v3/coins/markets"

params = {
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 100,
    "page": 1,
    "sparkline": False,
    "price_change_percentage": "24h"
}

response = requests.get(
    url,
    params=params,
    timeout=20
)

coins = response.json()

results = []

# ====================================
# SIMPLE AI SCORE
# ====================================
for coin in coins:

    try:

        score = 0

        change = coin.get(
            "price_change_percentage_24h",
            0
        )

        marketcap = coin.get(
            "market_cap_rank",
            999
        )

        volume = coin.get(
            "total_volume",
            0
        )

        if change > 3:
            score += 30

        if change > 7:
            score += 20

        if marketcap <= 50:
            score += 25

        if volume > 100000000:
            score += 25

        if score >= 80:
            signal = "🔥 STRONG BUY"

        elif score >= 60:
            signal = "🟢 BUY"

        elif score >= 40:
            signal = "🟡 WAIT"

        else:
            signal = "🔴 AVOID"

        results.append({

            "Coin": coin["name"],
            "Symbol": coin["symbol"].upper(),
            "Price": coin["current_price"],
            "24H %": round(change,2),
            "Rank": marketcap,
            "Score": score,
            "Signal": signal

        })

    except:
        pass

df = pd.DataFrame(results)

df = df.sort_values(
    "Score",
    ascending=False
)

# ====================================
# TOP SIGNAL
# ====================================
st.subheader("🔥 Top Opportunity Today")

st.dataframe(
    df.head(10),
    use_container_width=True
)

# ====================================
# FULL SCANNER
# ====================================
st.subheader("📊 Top 100 Scanner")

st.dataframe(
    df,
    use_container_width=True,
    height=700
)
