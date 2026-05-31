import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# =====================================
# CONFIG
# =====================================
st.set_page_config(
    page_title="AI Daily Crypto Scanner",
    layout="wide"
)

st_autorefresh(
    interval=300000,
    key="refresh"
)

st.title("🚀 AI Daily Crypto Scanner")
st.caption("Powered by CoinGecko")

# =====================================
# SIDEBAR
# =====================================
currency = st.sidebar.selectbox(
    "Currency",
    ["USD", "IDR"]
)

# =====================================
# KURS
# =====================================
usd_to_idr = 16500

# =====================================
# LOAD DATA
# =====================================
url = "https://api.coingecko.com/api/v3/coins/markets"

params = {
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 100,
    "page": 1,
    "sparkline": False,
    "price_change_percentage": "24h"
}

coins = requests.get(
    url,
    params=params,
    timeout=20
).json()

results = []

# =====================================
# AI SCORE
# =====================================
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

        price = coin["current_price"]

        if currency == "IDR":
            price *= usd_to_idr

        results.append({

            "Coin": coin["name"],
            "Symbol": coin["symbol"].upper(),
            "Price": round(price, 4),
            "24H %": round(change, 2),
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

# =====================================
# MARKET MOOD
# =====================================
avg_score = df["Score"].mean()

if avg_score >= 70:
    mood = "🟢 BULLISH"

elif avg_score >= 50:
    mood = "🟡 NEUTRAL"

else:
    mood = "🔴 BEARISH"

# =====================================
# METRICS
# =====================================
c1,c2,c3 = st.columns(3)

c1.metric(
    "Market Mood",
    mood
)

c2.metric(
    "Coins Scanned",
    len(df)
)

c3.metric(
    "Average Score",
    round(avg_score,1)
)

# =====================================
# TOP OPPORTUNITY
# =====================================
top = df.iloc[0]

st.success(
f"""
🔥 TOP OPPORTUNITY

Coin : {top['Coin']}
Signal : {top['Signal']}
Score : {top['Score']}
"""
)

# =====================================
# BREAKOUT WATCHLIST
# =====================================
st.subheader("🚀 Breakout Watchlist")

breakout = df[
    df["24H %"] > 5
]

st.dataframe(
    breakout.head(10),
    use_container_width=True
)

# =====================================
# STRONG BUY
# =====================================
st.subheader("💎 Strong Buy")

strong = df[
    df["Signal"] == "🔥 STRONG BUY"
]

st.dataframe(
    strong,
    use_container_width=True
)

# =====================================
# AVOID
# =====================================
st.subheader("⚠️ Avoid")

avoid = df[
    df["Signal"] == "🔴 AVOID"
]

st.dataframe(
    avoid.head(20),
    use_container_width=True
)

# =====================================
# FULL SCANNER
# =====================================
st.subheader("📊 Top 100 Scanner")

st.dataframe(
    df,
    use_container_width=True,
    height=700
)

# =====================================
# CHART
# =====================================
st.subheader("📈 Coin Detail")

selected = st.selectbox(
    "Select Coin",
    df["Symbol"]
)

selected_row = df[
    df["Symbol"] == selected
].iloc[0]

st.write(selected_row)
