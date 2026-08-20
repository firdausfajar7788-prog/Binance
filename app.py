import streamlit as st
import pandas as pd
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Daily - Bybit Scanner",
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
    st.session_state.selected_symbol = "BTCUSDT"
if "last_notified" not in st.session_state:
    st.session_state.last_notified = {}
if "last_update_time" not in st.session_state:
    st.session_state.last_update_time = datetime.now()

# =========================================================
# HEADER
# =========================================================
st.title("Daily - Bybit Scanner")
st.caption("Data dari Bybit API Indonesia | Volume Trend + Signal Scanner")
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
                    r = requests.post(url, json={"chat_id": CHAT_ID, "text": "🚀 Bybit Scanner aktif!"}, timeout=10)
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
# FUNGSI KURS IDR
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
# TELEGRAM FUNCTIONS
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
{emoji} <b>BYBIT SIGNAL!</b>

<b>Coin:</b> {row['Coin']}
<b>Signal:</b> {row['Signal']}
<b>Score:</b> {row['Score']}/100
<b>Price:</b> ${row['Price']:.4f}
<b>24H:</b> {row['24H %']}%
<b>7D:</b> {row['7D %']}%
<b>Volume:</b> {row['Volume (M)']}M {row.get('Volume Trend', '')}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

# =========================================================
# BYBIT API - INDONESIA
# =========================================================
BYBIT_URL = "https://api.bybit.id"

def bybit_request(endpoint, params=None):
    """Kirim request ke Bybit API Indonesia"""
    try:
        url = f"{BYBIT_URL}/v5/{endpoint}"
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

@st.cache_data(ttl=300)
def get_bybit_tickers(category="linear", limit=200):
    """Ambil semua ticker dari Bybit"""
    data = bybit_request("market/tickers", {"category": category})
    if data and data.get("retCode") == 0:
        return data["result"]["list"]
    return None

@st.cache_data(ttl=300)
def get_bybit_klines(symbol, interval="1d", limit=7):
    """Ambil kline harian untuk volume historis"""
    data = bybit_request(
        "market/kline",
        {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
    )
    if data and data.get("retCode") == 0:
        klines = data["result"]["list"]
        df = pd.DataFrame(klines, columns=["Time", "Open", "High", "Low", "Close", "Volume", "Turnover"])
        df["Volume"] = df["Volume"].astype(float)
        return df
    return None

# =========================================================
# PROSES DATA BYBIT
# =========================================================
def process_bybit_data(tickers, currency, usd_to_idr):
    results = []
    
    for ticker in tickers:
        try:
            symbol = ticker["symbol"]
            
            # Hanya ambil USDT pair
            if not symbol.endswith("USDT"):
                continue
            
            # Skip yang tidak populer (volume rendah)
            volume_24h = float(ticker.get("volume24h", 0) or 0)
            if volume_24h < 500000:  # Minimal $500k volume
                continue
            
            price = float(ticker.get("lastPrice", 0) or 0)
            change_24h = float(ticker.get("price24hPcnt", 0) or 0) * 100
            high_24h = float(ticker.get("highPrice24h", 0) or 0)
            low_24h = float(ticker.get("lowPrice24h", 0) or 0)
            turnover = float(ticker.get("turnover24h", 0) or 0)
            
            # Ambil volume 7 hari historis
            df = get_bybit_klines(symbol, "1d", 7)
            volume_avg_7d = None
            if df is not None and not df.empty:
                volumes = df["Volume"].tolist()
                if len(volumes) >= 3:
                    volume_avg_7d = sum(volumes) / len(volumes)
            
            # Hitung score
            score = 0
            
            # 1. 24H Change (0-50)
            if change_24h > 10:
                score += 50
            elif change_24h > 5:
                score += 35
            elif change_24h > 2:
                score += 20
            elif change_24h > 0:
                score += 10
            
            # 2. Volume/Market Cap proxy (pakai turnover)
            if turnover > 0 and volume_24h > 0:
                vol_ratio = volume_24h / turnover if turnover > 0 else 0
                if vol_ratio > 0.1:
                    score += 20
                elif vol_ratio > 0.05:
                    score += 10
                if vol_ratio > 0.15:
                    score += 5
            
            # 3. Price vs High/Low (momentum)
            if high_24h > 0 and low_24h > 0:
                range_pct = (high_24h - low_24h) / low_24h * 100
                if range_pct > 10:
                    score += 10
                elif range_pct > 5:
                    score += 5
            
            # Signal
            if score >= 80:
                signal = "🔥 STRONG BUY"
            elif score >= 65:
                signal = "🟢 BUY"
            elif score >= 45:
                signal = "🟡 WAIT"
            else:
                signal = "🔴 AVOID"
            
            # Volume trend
            if volume_avg_7d and volume_avg_7d > 0:
                ratio = volume_24h / volume_avg_7d
                if ratio > 1.3:
                    volume_trend = "🔼"
                elif ratio < 0.7:
                    volume_trend = "🔽"
                else:
                    volume_trend = "➡️"
            else:
                volume_trend = "➡️"
            
            # Price dalam currency
            price_display = price * (usd_to_idr if currency == "IDR" else 1)
            
            results.append({
                "Coin": symbol.replace("USDT", ""),
                "Symbol": symbol,
                "Price": round(price_display, 4),
                "24H %": round(change_24h, 2),
                "7D %": "N/A",  # Bybit tidak menyediakan 7D
                "24H High": round(high_24h, 4),
                "24H Low": round(low_24h, 4),
                "Volume (M)": round(volume_24h / 1_000_000, 1),
                "Turnover (M)": round(turnover / 1_000_000, 1),
                "Score": score,
                "Signal": signal,
                "Volume Trend": volume_trend,
                "Vol 7D Avg": round(volume_avg_7d / 1_000_000, 1) if volume_avg_7d else "N/A"
            })
            
        except Exception as e:
            continue
    
    # Sort by score
    results = sorted(results, key=lambda x: x["Score"], reverse=True)
    return results

# =========================================================
# MAIN
# =========================================================
with st.spinner("📊 Mengambil data dari Bybit Indonesia..."):
    tickers = get_bybit_tickers(limit=200)
    
    if tickers is None:
        st.warning("⚠️ Gagal mengambil data dari Bybit. Coba refresh.")
        st.stop()
    
    results = process_bybit_data(tickers, currency, usd_to_idr)

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
    if notified:
        st.sidebar.success(f"✅ {notified} notifikasi terkirim!")
    if failed:
        st.sidebar.error(f"❌ {failed} gagal!")

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
    st.download_button("📥 Download CSV", csv, f"bybit_scanner_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")

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
col2.metric("📊 24H High", f"${row['24H High']:,.4f}")
col3.metric("📉 24H Low", f"${row['24H Low']:,.4f}")
col3.metric("🧠 Score", f"{row['Score']}/100")
col4.metric("📡 Signal", row["Signal"])
col4.metric("📊 Volume Trend", row.get("Volume Trend", "➡️"))

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
    f"Total: {len(df)} | Sumber: Bybit API Indonesia | "
    f"Telegram: {'✅' if BOT_TOKEN and CHAT_ID else '❌'} | Currency: {currency}"
)
