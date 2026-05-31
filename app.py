import streamlit as st
import pandas as pd
import requests

st.set_page_config(
    page_title="AI Daily Signal Scanner",
    layout="wide"
)

st.title("🚀 AI Daily Signal Scanner")

# =====================================================
# LOAD COINGECKO
# =====================================================

url = "https://api.coingecko.com/api/v3/coins/markets"

params = {
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 100,
    "page": 1,
    "sparkline": False,
    "price_change_percentage": "24h,7d"
}

response = requests.get(
    url,
    params=params,
    timeout=30
)

data = response.json()

df = pd.DataFrame(data)

# =====================================================
# SCORE
# =====================================================

def calculate_score(row):

    score = 0

    change24 = row.get(
        "price_change_percentage_24h",
        0
    )

    change7d = row.get(
        "price_change_percentage_7d_in_currency",
        0
    )

    volume = row.get(
        "total_volume",
        0
    )

    rank = row.get(
        "market_cap_rank",
        999
    )

    # 24H momentum
    if change24 > 10:
        score += 25
    elif change24 > 5:
        score += 20
    elif change24 > 2:
        score += 10

    # 7D trend
    if change7d > 15:
        score += 25
    elif change7d > 5:
        score += 15
    elif change7d > 0:
        score += 10

    # market cap
    if rank <= 20:
        score += 20
    elif rank <= 50:
        score += 15
    elif rank <= 100:
        score += 10

    # volume
    if volume > 1_000_000_000:
        score += 20
    elif volume > 100_000_000:
        score += 10

    return score

df["score"] = df.apply(
    calculate_score,
    axis=1
)

# =====================================================
# SIGNAL
# =====================================================

def signal(score):

    if score >= 75:
        return "🔥 STRONG BUY"

    elif score >= 55:
        return "🟢 BUY"

    elif score >= 35:
        return "🟡 WATCH"

    else:
        return "🔴 AVOID"

df["signal"] = df["score"].apply(
    signal
)

# =====================================================
# MARKET MOOD
# =====================================================

avg_score = df["score"].mean()

if avg_score > 60:

    mood = "🟢 BULLISH"

elif avg_score > 40:

    mood = "🟡 SIDEWAYS"

else:

    mood = "🔴 BEARISH"

col1,col2,col3 = st.columns(3)

col1.metric(
    "Market Mood",
    mood
)

col2.metric(
    "Coins Scanned",
    len(df)
)

col3.metric(
    "Average Score",
    round(avg_score,1)
)

# =====================================================
# TOP SIGNAL
# =====================================================

st.subheader("🔥 Strong Buy Today")

strong = df[
    df["signal"] == "🔥 STRONG BUY"
].sort_values(
    "score",
    ascending=False
)

st.dataframe(
    strong[
        [
            "symbol",
            "name",
            "current_price",
            "price_change_percentage_24h",
            "score",
            "signal"
        ]
    ],
    use_container_width=True
)

# =====================================================
# BUY ZONE
# =====================================================

st.subheader("🟢 Buy Zone")

buy = df[
    df["signal"] == "🟢 BUY"
].sort_values(
    "score",
    ascending=False
)

st.dataframe(
    buy[
        [
            "symbol",
            "name",
            "current_price",
            "price_change_percentage_24h",
            "score",
            "signal"
        ]
    ],
    use_container_width=True
)

# =====================================================
# FULL SCANNER
# =====================================================

st.subheader("📊 Full Scanner")

scanner = df[
    [
        "market_cap_rank",
        "symbol",
        "name",
        "current_price",
        "price_change_percentage_24h",
        "price_change_percentage_7d_in_currency",
        "total_volume",
        "score",
        "signal"
    ]
].sort_values(
    "score",
    ascending=False
)

st.dataframe(
    scanner,
    use_container_width=True,
    height=700
)
