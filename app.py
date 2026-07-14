import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="AI Daily Crypto Scanner (YFinance)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# CUSTOM CSS (sama seperti sebelumnya)
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
        border: 1px solid #00ff88; border-radius: 8px; padding: 4px 12px; color: #00ff88; font-weight: 600;
    }
    .signal-buy {
        background: linear-gradient(135deg, rgba(0,200,255,0.2), rgba(0,200,255,0.05));
        border: 1px solid #00c8ff; border-radius: 8px; padding: 4px 12px; color: #00c8ff; font-weight: 600;
    }
    .signal-wait {
        background: linear-gradient(135deg, rgba(255,170,0,0.2), rgba(255,170,0,0.05));
        border: 1px solid #ffaa00; border-radius: 8px; padding: 4px 12px; color: #ffaa00; font-weight: 600;
    }
    .signal-avoid {
        background: linear-gradient(135deg, rgba(255,59,92,0.2), rgba(255,59,92,0.05));
        border: 1px solid #ff3b5c; border-radius: 8px; padding: 4px 12px; color: #ff3b5c; font-weight: 600;
    }
    .stButton > button {
        background: linear-gradient(145deg, #00ff88, #00cc66);
        color: #000; font-weight: 700; border: none; border-radius: 10px; padding: 10px 24px;
        transition: all 0.3s ease;
    }
    .stButton > button:hover { transform: scale(1.03); box-shadow: 0 0 30px rgba(0,255,136,0.3); }
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
st.title("🚀 AI Daily Crypto Scanner (YFinance)")
st.caption("Data from Yahoo Finance | Real-time OHLCV | Volume Trend 7-day")
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
    
    # Telegram (sama seperti sebelumnya)
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
                    r = requests.post(url, json={"chat_id": CHAT_ID, "text": "🚀 Scanner YFinance aktif!"}, timeout=10)
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
    st.metric("Coins Scanned", "20")  # default watchlist, nanti bisa tambah
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
# LOAD DATA DARI YFINANCE
# =========================================================
# Daftar coin yang umum di Yahoo Finance (bisa diperluas)
DEFAULT_SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "XRP-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD", "MATIC-USD",
    "UNI-USD", "ATOM-USD", "LTC-USD", "BCH-USD", "NEAR-USD",
    "APT-USD", "ARB-USD", "OP-USD", "INJ-USD", "RNDR-USD"
]

# Mapping ke ticker yang lebih pendek (untuk display)
def extract_symbol(ticker):
    return ticker.replace("-USD", "")

@st.cache_data(ttl=300)
def load_yfinance_data(symbols=DEFAULT_SYMBOLS, period="7d", interval="1d"):
    """
    Mengambil data harian (OHLCV) untuk daftar simbol.
    """
    data = {}
    for ticker in symbols:
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            if df.empty:
                continue
            # Pastikan kolom standar
            if "Close" in df.columns:
                # Ambil data terakhir (hari ini)
                last_row = df.iloc[-1]
                price = last_row["Close"]
                volume = last_row["Volume"]
                # Hitung perubahan 24h (dari close kemarin ke close hari ini)
                if len(df) >= 2:
                    prev_close = df["Close"].iloc[-2]
                    change_24h = ((price - prev_close) / prev_close) * 100
                else:
                    change_24h = 0.0
                
                # Hitung perubahan 7d (dari close 7 hari lalu ke close hari ini)
                if len(df) >= 7:
                    close_7d_ago = df["Close"].iloc[-7]
                    change_7d = ((price - close_7d_ago) / close_7d_ago) * 100
                else:
                    change_7d = 0.0
                
                # Simpan semua volume harian untuk trend
                volumes = df["Volume"].tolist()
                avg_7d_volume = sum(volumes[-7:]) / len(volumes[-7:]) if len(volumes) >= 7 else volume
                
                data[ticker] = {
                    "symbol": extract_symbol(ticker),
                    "price": price,
                    "volume": volume,
                    "change_24h": change_24h,
                    "change_7d": change_7d,
                    "avg_volume_7d": avg_7d_volume,
                    "rank": None,  # yfinance tidak punya rank
                }
        except Exception as e:
            st.warning(f"Gagal ambil {ticker}: {e}")
            continue
    return data

# =========================================================
# PROSES DATA DARI YFINANCE
# =========================================================
def process_yfinance_data(data, currency, usd_to_idr):
    results = []
    for ticker, info in data.items():
        try:
            price_usd = info["price"]
            volume_24h = info["volume"]
            change_24h = info["change_24h"]
            change_7d = info["change_7d"]
            avg_vol_7d = info["avg_volume_7d"]
            
            # Skor AI (sederhana)
            score = 0
            if change_24h > 10: score += 50
            elif change_24h > 5: score += 35
            elif change_24h > 2: score += 20
            elif change_24h > 0: score += 10
            
            if change_7d > 20: score += 20
            elif change_7d > 10 and change_24h > change_7d * 0.3: score += 15
            
            # rank? tidak ada, kita skip
            # volume ratio tidak bisa dihitung karena market cap tidak tersedia di yfinance (tanpa api tambahan)
            # kita bisa abaikan atau pakai volume/avg_volume sebagai indikator likuiditas
            if volume_24h > 0 and avg_vol_7d > 0:
                vol_ratio = volume_24h / avg_vol_7d
                if vol_ratio > 1.5: score += 10
                elif vol_ratio > 1.2: score += 5
            
            if score >= 80: signal = "🔥 STRONG BUY"
            elif score >= 65: signal = "🟢 BUY"
            elif score >= 45: signal = "🟡 WAIT"
            else: signal = "🔴 AVOID"
            
            price = price_usd * (usd_to_idr if currency == "IDR" else 1)
            
            # Volume trend
            volume_trend = "➡️"
            if avg_vol_7d > 0:
                ratio = volume_24h / avg_vol_7d
                if ratio > 1.3: volume_trend = "🔼"
                elif ratio < 0.7: volume_trend = "🔽"
            
            results.append({
                "Coin": info["symbol"],  # nama bisa dari mapping
                "Symbol": info["symbol"],
                "Price": round(price, 4),
                "24H %": round(change_24h, 2),
                "7D %": round(change_7d, 2),
                "Rank": 0,  # tidak ada
                "Volume (M)": round(volume_24h / 1_000_000, 1),
                "Score": score,
                "Signal": signal,
                "Volume Trend": volume_trend,
                "source": "YFinance"
            })
        except Exception as e:
            continue
    return results

# =========================================================
# MAIN
# =========================================================
# Ambil data dari yfinance
with st.spinner("📊 Mengambil data dari Yahoo Finance..."):
    yf_data = load_yfinance_data(DEFAULT_SYMBOLS, period="7d", interval="1d")

if not yf_data:
    st.error("Tidak ada data dari Yahoo Finance. Periksa koneksi atau simbol.")
    st.stop()

results = process_yfinance_data(yf_data, currency, usd_to_idr)

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
                <span>7d: <span style="color:{'#00ff88' if row['7D %']>0 else '#ff3b5c'}">{row['7D %']}%</span></span>
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
col3.metric("📈 7D Change", f"{row['7D %']}%")
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
    f"Total: {len(df)} | Sumber: Yahoo Finance | "
    f"Telegram: {'✅' if BOT_TOKEN and CHAT_ID else '❌'} | Currency: {currency}"
)
