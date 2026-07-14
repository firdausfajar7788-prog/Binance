import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="AI Daily Crypto Scanner PRO (CoinCap)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# CUSTOM CSS
# =========================================================
st.markdown("""
<style>
    .stApp { background: #0a0a1a; }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #111827, #0b1220);
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 4px 20px rgba(0,255,255,0.05);
    }
    [data-testid="stMetricLabel"] { color: #94a3b8; font-size: 13px; }
    [data-testid="stMetricValue"] { color: #f1f5f9; font-size: 24px; font-weight: 700; }
    
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
    .volume-up { color: #00ff88; font-weight: 700; }
    .volume-down { color: #ff3b5c; font-weight: 700; }
    .volume-neutral { color: #ffaa00; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# SESSION STATE
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
st.title("🚀 AI Daily Crypto Scanner PRO (CoinCap)")
st.caption("Real-time data from CoinCap + Volume Trend 7-day comparison + Telegram Alerts")
col_time, _ = st.columns([2, 3])
with col_time:
    st.caption(f"🕐 Last updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}")

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("⚙️ Settings")
    currency = st.selectbox("💱 Currency", ["USD", "IDR"])
    st.divider()
    
    # Telegram
    st.subheader("📱 Telegram Alert")
    default_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    default_chat = st.secrets.get("TELEGRAM_CHAT_ID", "")
    BOT_TOKEN = st.text_input("Bot Token", type="password", value=default_token)
    CHAT_ID = st.text_input("Chat ID", value=default_chat)
    send_notifications = st.checkbox("🔔 Kirim Notifikasi", value=True)
    notify_min_score = st.slider("Min Score untuk Notifikasi", 50, 100, 65)
    
    col_test1, col_test2 = st.columns(2)
    with col_test1:
        if st.button("🚀 Test Telegram", use_container_width=True):
            if BOT_TOKEN and CHAT_ID:
                try:
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    r = requests.post(url, json={"chat_id": CHAT_ID, "text": "🚀 Scanner CoinCap aktif!"}, timeout=10)
                    st.success("✅ Pesan test terkirim!" if r.status_code == 200 else f"❌ Error {r.status_code}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
            else:
                st.warning("⚠️ Isi Bot Token dan Chat ID")
    with col_test2:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    st.divider()
    
    st.subheader("📊 Status")
    st.metric("Coins Scanned", "100")
    st.metric("Auto Refresh", "10 menit")
    st.divider()
    st.caption("📊 **Volume Trend Legend:**")
    st.caption("🔼 Volume > 130% rata-rata 7 hari (naik)")
    st.caption("🔽 Volume < 70% rata-rata 7 hari (turun)")
    st.caption("➡️ Volume stabil (70-130%)")

# =========================================================
# FUNGSI AMBIL KURS IDR
# =========================================================
@st.cache_data(ttl=3600)
def get_usd_to_idr():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()["rates"]["IDR"]
    except:
        pass
    return 15500

usd_to_idr = get_usd_to_idr()
if currency == "IDR":
    st.sidebar.info(f"💱 1 USD = {usd_to_idr:,.0f} IDR")

# =========================================================
# FUNGSI TELEGRAM
# =========================================================
def send_telegram(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        return False, "Kosong"
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        return r.status_code == 200, f"HTTP {r.status_code}"
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
<b>Volume:</b> {row['Volume (M)']}M {row.get('Volume Trend', '')}
<b>Rank:</b> #{row['Rank']}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

# =========================================================
# COINCAP API – AMBIL DATA ASET
# =========================================================
@st.cache_data(ttl=300)  # 5 menit
def load_coincap_assets(limit=200):
    """Ambil daftar aset dari CoinCap, diurutkan berdasarkan market cap (default)"""
    url = f"https://api.coincap.io/v2/assets?limit={limit}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()["data"]
            # Filter coin dengan price > 0 dan volume > 0
            coins = [c for c in data if float(c.get("priceUsd", 0)) > 0 and float(c.get("volumeUsd", 0)) > 0]
            return coins
        else:
            st.error(f"CoinCap API error: {resp.status_code}")
            return None
    except Exception as e:
        st.error(f"Gagal ambil data CoinCap: {e}")
        return None

# =========================================================
# COINCAP – AMBIL VOLUME HISTORIS 7 HARI
# =========================================================
@st.cache_data(ttl=3600)  # cache 1 jam
def get_coincap_volume_history(asset_id):
    """Ambil data volume harian 7 hari terakhir untuk satu asset"""
    url = f"https://api.coincap.io/v2/assets/{asset_id}/history?interval=d1"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()["data"]
            # Ambil 7 titik terakhir (hari)
            volumes = [float(d["volumeUsd"]) for d in data[-7:] if float(d["volumeUsd"]) > 0]
            if len(volumes) >= 3:
                return volumes
        return None
    except:
        return None

# =========================================================
# PROSES DATA COINCAP
# =========================================================
def process_coincap_data(assets, currency, usd_to_idr):
    results = []
    for asset in assets:
        try:
            symbol = asset["symbol"].upper()
            name = asset["name"]
            price_usd = float(asset["priceUsd"])
            volume_24h = float(asset["volumeUsd"])
            change_24h = float(asset["changePercent24Hr"])  # sudah dalam persen
            # CoinCap tidak memberikan change 7d, kita bisa estimasi dari history, tapi skip dulu
            # Kita akan hitung dari data historis jika ada
            market_cap = float(asset["marketCapUsd"]) if asset.get("marketCapUsd") else 0
            rank = int(asset.get("rank", 999))
            
            # Skor AI (sama seperti sebelumnya)
            score = 0
            # 24h momentum
            if change_24h > 10: score += 50
            elif change_24h > 5: score += 35
            elif change_24h > 2: score += 20
            elif change_24h > 0: score += 10
            
            # market cap rank
            if rank <= 20: score += 25
            elif rank <= 50: score += 20
            elif rank <= 100: score += 10
            
            # likuiditas (volume/market cap)
            if market_cap > 0:
                vol_ratio = volume_24h / market_cap
                if vol_ratio > 0.1: score += 20
                elif vol_ratio > 0.05: score += 10
                if vol_ratio > 0.15: score += 5
            
            # distance to ATH? CoinCap tidak berikan ATH, skip
            
            # signal
            if score >= 80: signal = "🔥 STRONG BUY"
            elif score >= 65: signal = "🟢 BUY"
            elif score >= 45: signal = "🟡 WAIT"
            else: signal = "🔴 AVOID"
            
            price = price_usd * (usd_to_idr if currency == "IDR" else 1)
            
            results.append({
                "Coin": name,
                "Symbol": symbol,
                "Price": round(price, 4),
                "24H %": round(change_24h, 2),
                "7D %": 0.0,  # akan diisi nanti jika ada data
                "Rank": rank,
                "Volume (M)": round(volume_24h / 1_000_000, 1),
                "Score": score,
                "Signal": signal,
                "asset_id": asset["id"]  # untuk ambil history
            })
        except Exception as e:
            continue
    return results

# =========================================================
# TAMBAHKAN VOLUME TREND (7-DAY AVG)
# =========================================================
def add_volume_trend(df):
    """Tambahkan kolom Volume Trend berdasarkan data historis CoinCap"""
    trend_data = {}
    # Gunakan thread pool untuk mempercepat
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_symbol = {}
        for _, row in df.iterrows():
            asset_id = row.get("asset_id")
            symbol = row["Symbol"]
            if asset_id:
                future = executor.submit(get_coincap_volume_history, asset_id)
                future_to_symbol[future] = symbol
        
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                volumes = future.result()
                if volumes:
                    avg_7d = sum(volumes) / len(volumes)
                    trend_data[symbol] = avg_7d
            except:
                pass
            time.sleep(0.1)  # hindari rate limit
    
    # Tambahkan kolom ke dataframe
    def get_trend(row):
        sym = row["Symbol"]
        current_vol = row["Volume (M)"] * 1_000_000
        avg = trend_data.get(sym)
        if avg is None or avg == 0:
            return "➡️ N/A"
        ratio = current_vol / avg
        if ratio > 1.3:
            return "🔼"
        elif ratio < 0.7:
            return "🔽"
        else:
            return "➡️"
    
    df["Volume Trend"] = df.apply(get_trend, axis=1)
    return df

# =========================================================
# MAIN
# =========================================================
assets = load_coincap_assets(limit=100)
if assets is None:
    st.warning("⚠️ Gagal mengambil data dari CoinCap. Coba refresh.")
    st.stop()

# Proses data
results = process_coincap_data(assets, currency, usd_to_idr)
if not results:
    st.error("Tidak ada data yang bisa diproses")
    st.stop()

df = pd.DataFrame(results)
df = df.sort_values("Score", ascending=False)

# Tambahkan volume trend
with st.spinner("📊 Mengambil data volume historis 7 hari..."):
    df = add_volume_trend(df)

# Update waktu
st.session_state.last_update_time = datetime.now()

# =========================================================
# TELEGRAM NOTIFICATION
# =========================================================
if BOT_TOKEN and CHAT_ID and send_notifications:
    new_signals = df[(df["Signal"].isin(["🟢 BUY", "🔥 STRONG BUY"])) & (df["Score"] >= notify_min_score)]
    notified = 0
    failed = 0
    for _, row in new_signals.iterrows():
        symbol = row["Symbol"]
        signal = row["Signal"]
        if st.session_state.last_notified.get(symbol) != signal:
            msg = format_telegram_message(row)
            ok, _ = send_telegram(BOT_TOKEN, CHAT_ID, msg)
            if ok:
                st.session_state.last_notified[symbol] = signal
                notified += 1
            else:
                failed += 1
            time.sleep(0.3)
    if notified: st.sidebar.success(f"✅ {notified} notifikasi terkirim!")
    if failed: st.sidebar.error(f"❌ {failed} gagal!")

# =========================================================
# METRICS
# =========================================================
avg_score = df["Score"].mean()
mood = "🟢 BULLISH" if avg_score >= 65 else "🟡 NEUTRAL" if avg_score >= 45 else "🔴 BEARISH"
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📊 Market Mood", mood)
c2.metric("🪙 Coins Scanned", len(df))
c3.metric("📈 Average Score", round(avg_score, 1))
c4.metric("🔥 Strong Buy", len(df[df["Signal"] == "🔥 STRONG BUY"]))
c5.metric("🟢 Buy", len(df[df["Signal"] == "🟢 BUY"]))

# =========================================================
# TOP 3
# =========================================================
st.subheader("🔥 Top 3 Opportunities")
top3 = df.head(3)
cols_top = st.columns(3)
for idx, (_, row) in enumerate(top3.iterrows()):
    with cols_top[idx]:
        cls = "signal-strong-buy" if "STRONG" in row["Signal"] else "signal-buy"
        st.markdown(f"""
        <div style="background: linear-gradient(145deg, #111827, #0b1220); border:1px solid #1e293b; border-radius:16px; padding:20px; margin:5px;">
            <h3 style="color:#f1f5f9; margin:0;">{row['Coin']} <span style="font-size:14px; color:#94a3b8;">{row['Symbol']}</span></h3>
            <div style="margin:10px 0;"><span class="{cls}">{row['Signal']}</span>
            <span style="float:right; color:#f1f5f9; font-size:20px; font-weight:700;">{row['Score']}</span></div>
            <div style="display:flex; gap:20px; color:#94a3b8; font-size:14px;">
                <span>24h: <span style="color:{'#00ff88' if row['24H %']>0 else '#ff3b5c'}">{row['24H %']}%</span></span>
                <span>Rank: #{row['Rank']}</span>
            </div>
            <div style="color:#94a3b8; font-size:14px; margin-top:8px;">
                Price: ${row['Price']:,.4f} | Volume: {row['Volume (M)']}M {row.get('Volume Trend', '')}
            </div>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# TABEL
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Breakout Watchlist", "💎 Strong Buy", "🟢 Buy", "📊 Full Scanner"])
with tab1:
    breakout = df[(df["24H %"] > 5) & (df["Score"] > 40)]
    if not breakout.empty:
        st.dataframe(breakout.head(20), use_container_width=True, hide_index=True,
                     column_config={"Price": st.column_config.NumberColumn(format="$%.4f"),
                                    "24H %": st.column_config.NumberColumn(format="%.2f%%"),
                                    "Score": st.column_config.NumberColumn(format="%.0f")})
    else:
        st.info("Tidak ada breakout")
with tab2:
    strong = df[df["Signal"] == "🔥 STRONG BUY"]
    if not strong.empty:
        st.dataframe(strong, use_container_width=True, hide_index=True,
                     column_config={"Price": st.column_config.NumberColumn(format="$%.4f"),
                                    "24H %": st.column_config.NumberColumn(format="%.2f%%"),
                                    "Score": st.column_config.NumberColumn(format="%.0f")})
    else:
        st.info("Tidak ada Strong Buy")
with tab3:
    buy = df[df["Signal"] == "🟢 BUY"]
    if not buy.empty:
        st.dataframe(buy, use_container_width=True, hide_index=True,
                     column_config={"Price": st.column_config.NumberColumn(format="$%.4f"),
                                    "24H %": st.column_config.NumberColumn(format="%.2f%%"),
                                    "Score": st.column_config.NumberColumn(format="%.0f")})
    else:
        st.info("Tidak ada Buy")
with tab4:
    st.dataframe(df, use_container_width=True, height=500, hide_index=True,
                 column_config={"Price": st.column_config.NumberColumn(format="$%.4f"),
                                "24H %": st.column_config.NumberColumn(format="%.2f%%"),
                                "Score": st.column_config.NumberColumn(format="%.0f")})
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", csv, f"crypto_scanner_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")

# =========================================================
# AVOID
# =========================================================
with st.expander("⚠️ Avoid List"):
    avoid = df[df["Signal"] == "🔴 AVOID"]
    if not avoid.empty:
        st.dataframe(avoid.head(30), use_container_width=True, hide_index=True)
    else:
        st.info("Tidak ada coin yang perlu dihindari")

# =========================================================
# COIN DETAIL
# =========================================================
st.divider()
st.subheader("📈 Coin Detail")
selected = st.selectbox("Select Coin", df["Symbol"].tolist(),
                        index=df["Symbol"].tolist().index(st.session_state.selected_symbol) if st.session_state.selected_symbol in df["Symbol"].values else 0)
st.session_state.selected_symbol = selected
row = df[df["Symbol"] == selected].iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("🪙 Coin", row["Coin"])
col1.metric("💰 Price", f"{row['Price']:,.4f} {currency}")
col2.metric("📈 24H Change", f"{row['24H %']}%", delta=f"{row['24H %']}%", delta_color="normal")
col3.metric("🏆 Rank", f"#{row['Rank']}")
col3.metric("🧠 Score", f"{row['Score']}/100")
col4.metric("📡 Signal", row["Signal"])
col4.metric("📊 Volume Trend", f"{row.get('Volume Trend', '➡️')}")

# =========================================================
# AUTO REFRESH
# =========================================================
st_autorefresh(interval=600000, key="refresh")

# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption(
    f"🔄 Last updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')} | "
    f"Total: {len(df)} | Telegram: {'✅' if BOT_TOKEN and CHAT_ID else '❌'} | Currency: {currency}"
)
