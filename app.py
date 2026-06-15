import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# =====================================
# CONFIG
# =====================================
st.set_page_config(page_title="AI Daily Crypto Scanner", layout="wide")

# Auto-refresh setiap 10 menit (600 detik) - lebih stabil
st_autorefresh(interval=600000, key="refresh")

st.title("🚀 AI Daily Crypto Scanner")
st.caption("Powered by CoinGecko + Enhanced AI Scoring")

# =====================================
# SESSION STATE untuk menyimpan pilihan user
# =====================================
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "BTC"

# =====================================
# SIDEBAR
# =====================================
currency = st.sidebar.selectbox("Currency", ["USD", "IDR"])

# =====================================
# AMBIL KURS IDR REAL-TIME (cache 1 jam)
# =====================================
@st.cache_data(ttl=3600)
def get_usd_to_idr():
    try:
        # Menggunakan API gratis dari exchangerate-api.com
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data["rates"]["IDR"]
        else:
            return 15500  # fallback value
    except:
        return 15500  # fallback

usd_to_idr = get_usd_to_idr()
if currency == "IDR":
    st.sidebar.info(f"💱 Kurs: 1 USD = {usd_to_idr:,.0f} IDR")

# =====================================
# LOAD DATA DARI COINGECKO (dengan cache & error handling)
# =====================================
@st.cache_data(ttl=300)  # cache 5 menit
def load_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h,7d"  # tambahkan data 7 hari
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code != 200:
            st.error(f"API Error: {response.status_code}")
            return None
        
        coins = response.json()
        return coins
    except Exception as e:
        st.error(f"Gagal mengambil data: {e}")
        return None

coins = load_coins()

if coins is None:
    st.stop()  # Hentikan eksekusi jika data gagal load

# =====================================
# HITUNG AI SCORE (VERSI LEBIH CERDAS)
# =====================================
results = []

for coin in coins:
    try:
        score = 0
        
        # Data dasar
        change_24h = coin.get("price_change_percentage_24h", 0) or 0
        change_7d = coin.get("price_change_percentage_7d_in_currency", 0) or 0
        marketcap_rank = coin.get("market_cap_rank", 999) or 999
        volume = coin.get("total_volume", 0) or 0
        market_cap = coin.get("market_cap", 0) or 0
        ath = coin.get("ath", 1) or 1
        current_price = coin.get("current_price", 0) or 0
        
        # --- KRITERIA SKOR ---
        
        # 1. Momentum 24h (max 50 poin)
        if change_24h > 10:
            score += 50
        elif change_24h > 5:
            score += 35
        elif change_24h > 2:
            score += 20
        elif change_24h > 0:
            score += 10
        
        # 2. Momentum 7 hari (akselerasi) - tambahan 20 poin
        if change_7d > 20:
            score += 20
        elif change_7d > 10 and change_24h > change_7d * 0.3:
            # Naik dalam 24 jam lebih cepat dari rata-rata 7 hari
            score += 15
        
        # 3. Rank market cap (max 25 poin)
        if marketcap_rank <= 20:
            score += 25
        elif marketcap_rank <= 50:
            score += 20
        elif marketcap_rank <= 100:
            score += 10
        
        # 4. Likuiditas (volume vs market cap) - max 20 poin
        if market_cap > 0:
            volume_ratio = volume / market_cap
            if volume_ratio > 0.1:  # volume > 10% market cap
                score += 20
            elif volume_ratio > 0.05:
                score += 10
        
        # 5. Distance to ATH (max 15 poin)
        if current_price > 0 and ath > 0:
            pct_to_ath = (current_price / ath) * 100
            if pct_to_ath > 90:  # dalam 10% dari ATH
                score += 15
            elif pct_to_ath > 75:
                score += 8
        
        # --- DETERMINE SIGNAL ---
        if score >= 80:
            signal = "🔥 STRONG BUY"
        elif score >= 65:
            signal = "🟢 BUY"
        elif score >= 45:
            signal = "🟡 WAIT"
        else:
            signal = "🔴 AVOID"
        
        # Konversi harga berdasarkan mata uang
        price = current_price
        if currency == "IDR":
            price *= usd_to_idr
        
        results.append({
            "Coin": coin["name"],
            "Symbol": coin["symbol"].upper(),
            "Price": round(price, 4),
            "24H %": round(change_24h, 2),
            "7D %": round(change_7d, 2),
            "Rank": marketcap_rank,
            "Volume (M)": round(volume / 1_000_000, 1),
            "Score": score,
            "Signal": signal
        })
        
    except Exception as e:
        # Skip coin yang bermasalah
        continue

if not results:
    st.error("Tidak ada data yang bisa diproses")
    st.stop()

df = pd.DataFrame(results)
df = df.sort_values("Score", ascending=False)

# =====================================
# MARKET MOOD
# =====================================
avg_score = df["Score"].mean()
if avg_score >= 65:
    mood = "🟢 BULLISH"
elif avg_score >= 45:
    mood = "🟡 NEUTRAL"
else:
    mood = "🔴 BEARISH"

# =====================================
# METRICS
# =====================================
c1, c2, c3 = st.columns(3)
c1.metric("Market Mood", mood)
c2.metric("Coins Scanned", len(df))
c3.metric("Average Score", round(avg_score, 1))

# =====================================
# TOP 3 OPPORTUNITIES
# =====================================
st.subheader("🔥 Top 3 Opportunities")
top3 = df.head(3)
for idx, row in top3.iterrows():
    st.success(
        f"""**{row['Coin']}** ({row['Symbol']})  
        Signal: {row['Signal']} | Score: {row['Score']}  
        24h: {row['24H %']}% | 7d: {row['7D %']}% | Rank: #{row['Rank']}"""
    )

# =====================================
# BREAKOUT WATCHLIST (24h > 5% DAN Score > 40)
# =====================================
st.subheader("🚀 Breakout Watchlist")
breakout = df[(df["24H %"] > 5) & (df["Score"] > 40)]
if not breakout.empty:
    st.dataframe(breakout.head(10), use_container_width=True)
else:
    st.info("Tidak ada coin yang memenuhi kriteria breakout saat ini")

# =====================================
# STRONG BUY
# =====================================
st.subheader("💎 Strong Buy")
strong = df[df["Signal"] == "🔥 STRONG BUY"]
if not strong.empty:
    st.dataframe(strong, use_container_width=True)
else:
    st.info("Tidak ada rekomendasi Strong Buy saat ini")

# =====================================
# AVOID
# =====================================
st.subheader("⚠️ Avoid")
avoid = df[df["Signal"] == "🔴 AVOID"]
st.dataframe(avoid.head(20), use_container_width=True)

# =====================================
# FULL SCANNER
# =====================================
st.subheader("📊 Top 100 Scanner")
st.dataframe(df, use_container_width=True, height=500)

# =====================================
# CHART (menggunakan session state)
# =====================================
st.subheader("📈 Coin Detail")

selected = st.selectbox(
    "Select Coin",
    df["Symbol"],
    index=list(df["Symbol"]).index(st.session_state.selected_symbol) 
    if st.session_state.selected_symbol in df["Symbol"].values else 0,
    key="coin_selector"
)

# Simpan ke session state
st.session_state.selected_symbol = selected

selected_row = df[df["Symbol"] == selected].iloc[0]

# Tampilkan detail lebih rapi
col1, col2 = st.columns(2)
with col1:
    st.metric("Coin", selected_row["Coin"])
    st.metric("Price", f"{selected_row['Price']:,.4f} {currency}")
    st.metric("24H Change", f"{selected_row['24H %']}%")
with col2:
    st.metric("Market Cap Rank", f"#{selected_row['Rank']}")
    st.metric("AI Score", f"{selected_row['Score']}/100")
    st.metric("Signal", selected_row["Signal"])
