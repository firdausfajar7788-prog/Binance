import streamlit as st
import pandas as pd
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pybit.unified_trading import HTTP

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Bybit Scanner - Crypto Signals",
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
st.title("📊 Bybit Crypto Scanner")
st.caption("Data real-time dari Bybit API + Volume Trend + Telegram Alerts")
col_time, _ = st.columns([2, 3])
with col_time:
    st.caption(f"🕐 Last updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}")

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Pilihan kategori trading
    category = st.selectbox(
        "📊 Trading Category",
        ["spot", "linear", "inverse", "option"],
        help="Spot = trading biasa, Linear = USDT Perpetual, Inverse = Coin-M Futures"
    )
    
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
    st.metric("Coins Scanned", "~100")
    st.metric("Auto Refresh", "10 menit")
    st.divider()
    st.caption("📊 **Volume Trend Legend:**")
    st.caption("🔼 Volume > 130% rata-rata 7 hari (naik)")
    st.caption("🔽 Volume < 70% rata-rata 7 hari (turun)")
    st.caption("➡️ Volume stabil (70-130%)")

# =========================================================
# FUNGSI KURS IDR (Tetap pakai exchangerate-api)
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
# 1. AMBIL DATA DARI BYBIT (TICKERS + INSTRUMENTS INFO)
# =========================================================
@st.cache_data(ttl=300)
def load_bybit_data(category="spot", limit=150):
    """Ambil data ticker dari Bybit API"""
    try:
        # Inisialisasi session tanpa auth untuk public endpoint
        session = HTTP()
        
        # Ambil daftar instrumen untuk mendapatkan semua simbol aktif
        instruments = session.get_instruments_info(category=category, limit=limit)
        if instruments.get("retCode") != 0:
            st.error(f"Bybit API Error: {instruments.get('retMsg')}")
            return None
        
        # Ambil data ticker (harga, volume, perubahan)
        tickers = session.get_tickers(category=category)
        if tickers.get("retCode") != 0:
            st.error(f"Bybit API Error: {tickers.get('retMsg')}")
            return None
        
        # Gabungkan data
        inst_list = instruments["result"]["list"]
        ticker_list = tickers["result"]["list"]
        
        # Buat mapping ticker berdasarkan symbol
        ticker_map = {t["symbol"]: t for t in ticker_list}
        
        # Gabungkan data
        combined_data = []
        for inst in inst_list:
            symbol = inst["symbol"]
            ticker = ticker_map.get(symbol, {})
            
            # Filter: hanya yang aktif dan memiliki harga
            if inst.get("status") != "Trading":
                continue
            if not ticker.get("lastPrice") or float(ticker["lastPrice"]) <= 0:
                continue
            
            # Parse data
            price = float(ticker.get("lastPrice", 0))
            price_24h_pcnt = float(ticker.get("price24hPcnt", 0)) * 100  # Ubah ke persen
            volume_24h = float(ticker.get("volume24h", 0))
            
            # Ambil data dari instrumen jika ada
            rank = int(inst.get("rank", 999))
            market_cap = float(inst.get("marketCap", 0)) if inst.get("marketCap") else 0
            
            combined_data.append({
                "symbol": symbol,
                "name": symbol.replace("USDT", "").replace("USD", "").replace("USDC", ""),
                "price": price,
                "change_24h": price_24h_pcnt,
                "volume_24h": volume_24h,
                "rank": rank,
                "market_cap": market_cap,
                "ticker": ticker
            })
        
        return combined_data
    except Exception as e:
        st.error(f"Error loading Bybit data: {e}")
        return None

# =========================================================
# 2. AMBIL VOLUME HISTORIS 7 HARI DARI BYBIT KLINE
# =========================================================
@st.cache_data(ttl=300)
def get_bybit_volume_avg(symbol, category="spot"):
    """Ambil rata-rata volume 7 hari dari Bybit Kline API"""
    try:
        session = HTTP()
        response = session.get_kline(
            category=category,
            symbol=symbol,
            interval="D",
            limit=7
        )
        if response.get("retCode") != 0:
            return None
        
        klines = response["result"]["list"]
        if not klines or len(klines) < 3:
            return None
        
        # Kline format: [timestamp, open, high, low, close, volume, turnover]
        volumes = [float(k[5]) for k in klines]
        avg_volume = sum(volumes) / len(volumes)
        return avg_volume
    except Exception as e:
        return None

# =========================================================
# 3. PROSES DATA GABUNGAN
# =========================================================
def process_combined_data(bybit_data, currency, usd_to_idr, category="spot"):
    results = []
    
    # Ambil volume rata-rata 7 hari secara paralel
    volume_avg_dict = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_symbol = {
            executor.submit(get_bybit_volume_avg, item["symbol"], category): item["symbol"]
            for item in bybit_data
        }
        for future in as_completed(future_to_symbol):
            sym = future_to_symbol[future]
            try:
                avg = future.result()
                if avg is not None:
                    volume_avg_dict[sym] = avg
            except:
                pass
            time.sleep(0.05)
    
    # Proses setiap coin
    for item in bybit_data:
        try:
            symbol = item["symbol"]
            name = item["name"]
            price_usd = item["price"]
            volume_24h = item["volume_24h"]
            change_24h = item["change_24h"]
            rank = item["rank"]
            market_cap = item["market_cap"]
            
            # Hitung score (diadaptasi untuk Bybit)
            score = 0
            
            # Skor dari perubahan 24h
            if change_24h > 10: score += 50
            elif change_24h > 5: score += 35
            elif change_24h > 2: score += 20
            elif change_24h > 0: score += 10
            
            # Skor dari peringkat
            if rank <= 20: score += 25
            elif rank <= 50: score += 20
            elif rank <= 100: score += 10
            
            # Skor dari rasio volume terhadap market cap
            if market_cap > 0:
                vol_ratio = volume_24h / market_cap
                if vol_ratio > 0.1: score += 20
                elif vol_ratio > 0.05: score += 10
                if vol_ratio > 0.15: score += 5
            
            # Signal
            if score >= 80: signal = "🔥 STRONG BUY"
            elif score >= 65: signal = "🟢 BUY"
            elif score >= 45: signal = "🟡 WAIT"
            else: signal = "🔴 AVOID"
            
            # Harga dalam mata uang pilihan
            price = price_usd * (usd_to_idr if currency == "IDR" else 1)
            
            # Volume trend dari Bybit Kline
            avg_volume_7d = volume_avg_dict.get(symbol)
            if avg_volume_7d and avg_volume_7d > 0:
                ratio = volume_24h / avg_volume_7d
                if ratio > 1.3:
                    volume_trend = "🔼"
                elif ratio < 0.7:
                    volume_trend = "🔽"
                else:
                    volume_trend = "➡️"
            else:
                volume_trend = "➡️ N/A"
            
            results.append({
                "Coin": name,
                "Symbol": symbol,
                "Price": round(price, 4),
                "24H %": round(change_24h, 2),
                "Rank": rank,
                "Volume (M)": round(volume_24h / 1_000_000, 1),
                "Score": score,
                "Signal": signal,
                "Volume Trend": volume_trend
            })
        except Exception as e:
            continue
    
    return results

# =========================================================
# MAIN EXECUTION
# =========================================================
with st.spinner(f"📊 Mengambil data dari Bybit ({category})..."):
    bybit_data = load_bybit_data(category=category, limit=150)

if bybit_data is None:
    st.warning("⚠️ Gagal mengambil data dari Bybit. Coba refresh atau pilih kategori lain.")
    st.stop()

with st.spinner("📈 Memproses data dan menghitung sinyal..."):
    results = process_combined_data(bybit_data, currency, usd_to_idr, category=category)

if not results:
    st.error("Tidak ada data yang bisa diproses. Coba kategori lain.")
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
col3.metric("🏆 Rank", f"#{row['Rank']}")
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
    f"Total: {len(df)} | Sumber: Bybit API | "
    f"Telegram: {'✅' if BOT_TOKEN and CHAT_ID else '❌'} | Currency: {currency} | Category: {category}"
)
