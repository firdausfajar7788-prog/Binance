import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import time

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="AI Daily Crypto Scanner PRO",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# CUSTOM CSS
# =========================================================
st.markdown("""
<style>
    .stApp {
        background: #0a0a1a;
    }
    
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #111827, #0b1220);
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 4px 20px rgba(0,255,255,0.05);
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8;
        font-size: 13px;
    }
    [data-testid="stMetricValue"] {
        color: #f1f5f9;
        font-size: 24px;
        font-weight: 700;
    }
    
    .signal-strong-buy {
        background: linear-gradient(135deg, rgba(0,255,136,0.2), rgba(0,255,136,0.05));
        border: 1px solid #00ff88;
        border-radius: 8px;
        padding: 4px 12px;
        color: #00ff88;
        font-weight: 600;
    }
    .signal-buy {
        background: linear-gradient(135deg, rgba(0,200,255,0.2), rgba(0,200,255,0.05));
        border: 1px solid #00c8ff;
        border-radius: 8px;
        padding: 4px 12px;
        color: #00c8ff;
        font-weight: 600;
    }
    .signal-wait {
        background: linear-gradient(135deg, rgba(255,170,0,0.2), rgba(255,170,0,0.05));
        border: 1px solid #ffaa00;
        border-radius: 8px;
        padding: 4px 12px;
        color: #ffaa00;
        font-weight: 600;
    }
    .signal-avoid {
        background: linear-gradient(135deg, rgba(255,59,92,0.2), rgba(255,59,92,0.05));
        border: 1px solid #ff3b5c;
        border-radius: 8px;
        padding: 4px 12px;
        color: #ff3b5c;
        font-weight: 600;
    }
    
    .stButton > button {
        background: linear-gradient(145deg, #00ff88, #00cc66);
        color: #000;
        font-weight: 700;
        border: none;
        border-radius: 10px;
        padding: 10px 24px;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: scale(1.03);
        box-shadow: 0 0 30px rgba(0,255,136,0.3);
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# SESSION STATE INIT
# =========================================================
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "BTC"

if "last_notified" not in st.session_state:
    st.session_state.last_notified = {}

if "last_update_time" not in st.session_state:
    st.session_state.last_update_time = datetime.now()

# =========================================================
# HEADER
# =========================================================
st.title("🚀 AI Daily Crypto Scanner PRO")
st.caption("Powered by CoinGecko + Enhanced AI Scoring + Telegram Alerts")

# Tampilkan waktu update terakhir
col_time, _ = st.columns([2, 3])
with col_time:
    st.caption(f"🕐 Last updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}")

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    # --- Currency ---
    currency = st.selectbox("💱 Currency", ["USD", "IDR"])
    
    st.divider()
    
    # --- Telegram Settings ---
    st.subheader("📱 Telegram Alert")
    
    # Ambil dari secrets jika ada, fallback ke input kosong
    default_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    default_chat = st.secrets.get("TELEGRAM_CHAT_ID", "")
    
    BOT_TOKEN = st.text_input(
        "Bot Token",
        type="password",
        value=default_token,
        help="Dapatkan dari @BotFather"
    )
    
    CHAT_ID = st.text_input(
        "Chat ID",
        value=default_chat,
        help="Dapatkan dari @userinfobot"
    )
    
    send_notifications = st.checkbox("🔔 Kirim Notifikasi", value=True)
    
    notify_min_score = st.slider(
        "Min Score untuk Notifikasi",
        50, 100, 65
    )
    
    col_test1, col_test2 = st.columns(2)
    with col_test1:
        if st.button("🚀 Test Telegram", use_container_width=True):
            if BOT_TOKEN and CHAT_ID:
                try:
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    response = requests.post(
                        url,
                        json={
                            "chat_id": CHAT_ID,
                            "text": "🚀 Scanner PRO aktif! Notifikasi akan dikirim otomatis."
                        },
                        timeout=10
                    )
                    if response.status_code == 200:
                        st.success("✅ Pesan test terkirim!")
                    else:
                        st.error(f"❌ Error: {response.status_code}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
            else:
                st.warning("⚠️ Isi Bot Token dan Chat ID")
    
    with col_test2:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    st.divider()
    
    # --- Info ---
    st.subheader("📊 Status")
    st.metric("Coins Scanned", "100")
    st.metric("Auto Refresh", "10 menit")

# =========================================================
# GET USD TO IDR
# =========================================================
@st.cache_data(ttl=3600)
def get_usd_to_idr():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data["rates"]["IDR"]
        else:
            return 15500
    except:
        return 15500

usd_to_idr = get_usd_to_idr()
if currency == "IDR":
    st.sidebar.info(f"💱 1 USD = {usd_to_idr:,.0f} IDR")

# =========================================================
# TELEGRAM FUNCTIONS
# =========================================================
def send_telegram(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        return False, "Bot token atau Chat ID kosong"
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
        if response.status_code == 200:
            return True, "Berhasil"
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def format_telegram_message(row):
    emoji = "🚀" if "STRONG" in row["Signal"] else "📈"
    return f"""
{emoji} <b>SIGNAL DETECTED!</b>

<b>Coin:</b> {row['Coin']} ({row['Symbol']})
<b>Signal:</b> {row['Signal']}
<b>Score:</b> {row['Score']}/100
<b>Price:</b> ${row['Price']:.4f}
<b>24H:</b> {row['24H %']}%
<b>7D:</b> {row['7D %']}%
<b>Rank:</b> #{row['Rank']}
<b>Volume:</b> {row['Volume (M)']}M

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

# =========================================================
# LOAD DATA FROM COINGECKO
# =========================================================
@st.cache_data(ttl=300)
def load_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h,7d"
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code != 200:
            st.error(f"⚠️ API Error: {response.status_code} - Gunakan data cache jika tersedia")
            return None
        coins = response.json()
        return coins
    except Exception as e:
        st.error(f"⚠️ Gagal mengambil data: {e}")
        return None

# =========================================================
# CALCULATE AI SCORE
# =========================================================
def calculate_scores(coins, currency, usd_to_idr):
    results = []
    
    for coin in coins:
        try:
            score = 0
            
            change_24h = coin.get("price_change_percentage_24h", 0) or 0
            change_7d = coin.get("price_change_percentage_7d_in_currency", 0) or 0
            marketcap_rank = coin.get("market_cap_rank", 999) or 999
            volume = coin.get("total_volume", 0) or 0
            market_cap = coin.get("market_cap", 0) or 0
            ath = coin.get("ath", 1) or 1
            current_price = coin.get("current_price", 0) or 0
            
            # --- 1. Momentum 24h ---
            if change_24h > 10:
                score += 50
            elif change_24h > 5:
                score += 35
            elif change_24h > 2:
                score += 20
            elif change_24h > 0:
                score += 10
            
            # --- 2. Momentum 7 hari ---
            if change_7d > 20:
                score += 20
            elif change_7d > 10 and change_24h > change_7d * 0.3:
                score += 15
            
            # --- 3. Market cap rank ---
            if marketcap_rank <= 20:
                score += 25
            elif marketcap_rank <= 50:
                score += 20
            elif marketcap_rank <= 100:
                score += 10
            
            # --- 4. Likuiditas (Volume/Market Cap) ---
            if market_cap > 0:
                volume_ratio = volume / market_cap
                if volume_ratio > 0.1:
                    score += 20
                elif volume_ratio > 0.05:
                    score += 10
                # Bonus: volume spike
                if volume_ratio > 0.15:
                    score += 5
            
            # --- 5. Distance to ATH ---
            if current_price > 0 and ath > 0:
                pct_to_ath = (current_price / ath) * 100
                if pct_to_ath > 90:
                    score += 15
                elif pct_to_ath > 75:
                    score += 8
            
            # --- 6. Volume spike (tambahan) ---
            # Cek apakah volume > 2x volume rata-rata (estimasi)
            # Tidak ada data volume 7d dari endpoint ini, skip
            
            # --- Signal ---
            if score >= 80:
                signal = "🔥 STRONG BUY"
            elif score >= 65:
                signal = "🟢 BUY"
            elif score >= 45:
                signal = "🟡 WAIT"
            else:
                signal = "🔴 AVOID"
            
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
            continue
    
    return results

# =========================================================
# MAIN EXECUTION
# =========================================================
coins = load_coins()

if coins is None:
    st.warning("⚠️ Data tidak tersedia. Coba refresh halaman atau periksa koneksi internet.")
    st.stop()

# Proses data
results = calculate_scores(coins, currency, usd_to_idr)

if not results:
    st.error("Tidak ada data yang bisa diproses")
    st.stop()

df = pd.DataFrame(results)
df = df.sort_values("Score", ascending=False)

# Update waktu
st.session_state.last_update_time = datetime.now()

# =========================================================
# TELEGRAM NOTIFICATION
# =========================================================
if BOT_TOKEN and CHAT_ID and send_notifications:
    new_signals = df[
        (df["Signal"].isin(["🟢 BUY", "🔥 STRONG BUY"])) &
        (df["Score"] >= notify_min_score)
    ]
    
    notified_count = 0
    failed_count = 0
    
    for _, row in new_signals.iterrows():
        symbol = row["Symbol"]
        signal = row["Signal"]
        last_signal = st.session_state.last_notified.get(symbol)
        
        if last_signal != signal:
            message = format_telegram_message(row)
            success, msg = send_telegram(BOT_TOKEN, CHAT_ID, message)
            if success:
                st.session_state.last_notified[symbol] = signal
                notified_count += 1
            else:
                failed_count += 1
            time.sleep(0.3)  # Rate limit protection
    
    if notified_count > 0:
        st.sidebar.success(f"✅ {notified_count} notifikasi terkirim!")
    if failed_count > 0:
        st.sidebar.error(f"❌ {failed_count} notifikasi gagal!")

# =========================================================
# MARKET MOOD
# =========================================================
avg_score = df["Score"].mean()
if avg_score >= 65:
    mood = "🟢 BULLISH"
elif avg_score >= 45:
    mood = "🟡 NEUTRAL"
else:
    mood = "🔴 BEARISH"

# =========================================================
# METRICS
# =========================================================
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric("📊 Market Mood", mood)
with c2:
    st.metric("🪙 Coins Scanned", len(df))
with c3:
    st.metric("📈 Average Score", round(avg_score, 1))
with c4:
    strong_count = len(df[df["Signal"] == "🔥 STRONG BUY"])
    st.metric("🔥 Strong Buy", strong_count)
with c5:
    buy_count = len(df[df["Signal"] == "🟢 BUY"])
    st.metric("🟢 Buy", buy_count)

# =========================================================
# TOP 3 OPPORTUNITIES
# =========================================================
st.subheader("🔥 Top 3 Opportunities")
top3 = df.head(3)

cols_top = st.columns(3)
for idx, (_, row) in enumerate(top3.iterrows()):
    with cols_top[idx]:
        signal_class = "signal-strong-buy" if "STRONG" in row["Signal"] else "signal-buy"
        st.markdown(f"""
        <div style="background: linear-gradient(145deg, #111827, #0b1220); 
                    border: 1px solid #1e293b; 
                    border-radius: 16px; 
                    padding: 20px; 
                    margin: 5px;">
            <h3 style="color: #f1f5f9; margin: 0;">{row['Coin']} <span style="font-size: 14px; color: #94a3b8;">{row['Symbol']}</span></h3>
            <div style="margin: 10px 0;">
                <span class="{signal_class}">{row['Signal']}</span>
                <span style="float: right; color: #f1f5f9; font-size: 20px; font-weight: 700;">{row['Score']}</span>
            </div>
            <div style="display: flex; gap: 20px; color: #94a3b8; font-size: 14px;">
                <span>24h: <span style="color: {'#00ff88' if row['24H %'] > 0 else '#ff3b5c'}">{row['24H %']}%</span></span>
                <span>7d: <span style="color: {'#00ff88' if row['7D %'] > 0 else '#ff3b5c'}">{row['7D %']}%</span></span>
                <span>Rank: #{row['Rank']}</span>
            </div>
            <div style="color: #94a3b8; font-size: 14px; margin-top: 8px;">
                Price: ${row['Price']:,.4f}
            </div>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# TABBED VIEW
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 Breakout Watchlist",
    "💎 Strong Buy",
    "🟢 Buy",
    "📊 Full Scanner"
])

with tab1:
    breakout = df[(df["24H %"] > 5) & (df["Score"] > 40)]
    if not breakout.empty:
        st.dataframe(
            breakout.head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.4f"),
                "24H %": st.column_config.NumberColumn(format="%.2f%%"),
                "7D %": st.column_config.NumberColumn(format="%.2f%%"),
                "Score": st.column_config.NumberColumn(format="%.0f"),
            }
        )
    else:
        st.info("ℹ️ Tidak ada coin yang memenuhi kriteria breakout saat ini")

with tab2:
    strong = df[df["Signal"] == "🔥 STRONG BUY"]
    if not strong.empty:
        st.dataframe(
            strong,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.4f"),
                "24H %": st.column_config.NumberColumn(format="%.2f%%"),
                "7D %": st.column_config.NumberColumn(format="%.2f%%"),
                "Score": st.column_config.NumberColumn(format="%.0f"),
            }
        )
    else:
        st.info("ℹ️ Tidak ada rekomendasi Strong Buy saat ini")

with tab3:
    buy = df[df["Signal"] == "🟢 BUY"]
    if not buy.empty:
        st.dataframe(
            buy,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.4f"),
                "24H %": st.column_config.NumberColumn(format="%.2f%%"),
                "7D %": st.column_config.NumberColumn(format="%.2f%%"),
                "Score": st.column_config.NumberColumn(format="%.0f"),
            }
        )
    else:
        st.info("ℹ️ Tidak ada rekomendasi Buy saat ini")

with tab4:
    st.dataframe(
        df,
        use_container_width=True,
        height=500,
        hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.4f"),
            "24H %": st.column_config.NumberColumn(format="%.2f%%"),
            "7D %": st.column_config.NumberColumn(format="%.2f%%"),
            "Score": st.column_config.NumberColumn(format="%.0f"),
        }
    )
    
    # Download CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download CSV",
        csv,
        f"crypto_scanner_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        "text/csv",
        use_container_width=True
    )

# =========================================================
# AVOID (di bawah tabs)
# =========================================================
with st.expander("⚠️ Avoid List (Click to expand)"):
    avoid = df[df["Signal"] == "🔴 AVOID"]
    if not avoid.empty:
        st.dataframe(
            avoid.head(30),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("ℹ️ Tidak ada coin yang perlu dihindari")

# =========================================================
# COIN DETAIL
# =========================================================
st.divider()
st.subheader("📈 Coin Detail")

selected = st.selectbox(
    "Select Coin",
    df["Symbol"].tolist(),
    index=df["Symbol"].tolist().index(st.session_state.selected_symbol)
    if st.session_state.selected_symbol in df["Symbol"].values else 0,
    key="coin_selector"
)

st.session_state.selected_symbol = selected
selected_row = df[df["Symbol"] == selected].iloc[0]

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("🪙 Coin", selected_row["Coin"])
    st.metric("💰 Price", f"{selected_row['Price']:,.4f} {currency}")
    
with col2:
    st.metric("📈 24H Change", f"{selected_row['24H %']}%",
              delta=f"{selected_row['24H %']}%",
              delta_color="normal")
    st.metric("📈 7D Change", f"{selected_row['7D %']}%",
              delta=f"{selected_row['7D %']}%",
              delta_color="normal")
    
with col3:
    st.metric("🏆 Market Cap Rank", f"#{selected_row['Rank']}")
    st.metric("🧠 AI Score", f"{selected_row['Score']}/100")
    st.metric("📡 Signal", selected_row["Signal"])

# =========================================================
# AUTO REFRESH
# =========================================================
st_autorefresh(interval=600000, key="refresh")  # 10 menit

# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption(
    f"🔄 Last updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')} | "
    f"Total Coins: {len(df)} | "
    f"Telegram: {'✅ Aktif' if BOT_TOKEN and CHAT_ID else '❌ Tidak aktif'} | "
    f"Currency: {currency}"
)
