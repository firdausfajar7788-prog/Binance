import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Bybit Scanner ID - Crypto Signals",
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
st.title("📊 Bybit Crypto Scanner - Indonesia")
st.caption("Data real-time dari Bybit Indonesia | 🇮🇩 Regional Endpoint")
col_time, _ = st.columns([2, 3])
with col_time:
    st.caption(f"🕐 Last updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}")

# =========================================================
# BASE URL DAN HEADERS UNTUK INDONESIA
# =========================================================
BYBIT_URL = "https://api.bybit.id"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Referer": "https://www.bybit.com/",
    "Origin": "https://www.bybit.com"
}

# =========================================================
# FUNGSI AMBIL DATA DARI BYBIT
# =========================================================
def fetch_bybit_data(endpoint, params=None, max_retries=3):
    """Fungsi generic untuk fetch data dari Bybit dengan retry"""
    for attempt in range(max_retries):
        try:
            session = requests.Session()
            session.headers.update(HEADERS)
            
            response = session.get(
                f"{BYBIT_URL}{endpoint}",
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("retCode") == 0:
                        return data["result"]["list"] if "result" in data else data
                    else:
                        st.warning(f"Bybit API Error: {data.get('retMsg', 'Unknown error')}")
                        return None
                except json.JSONDecodeError as e:
                    st.error(f"JSON Error: {e}")
                    st.text(f"Response preview: {response.text[:200]}...")
                    return None
            else:
                st.warning(f"HTTP Error {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
                
        except requests.exceptions.Timeout:
            st.warning(f"Timeout attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
        except requests.exceptions.ConnectionError:
            st.warning(f"Connection error attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            return None
    
    return None

@st.cache_data(ttl=300)
def get_tickers(category="linear"):
    """Ambil data ticker dari Bybit Indonesia"""
    return fetch_bybit_data("/v5/market/tickers", params={"category": category})

@st.cache_data(ttl=300)
def get_instruments_info(category="linear", limit=200):
    """Ambil informasi instrumen dari Bybit Indonesia"""
    return fetch_bybit_data(
        "/v5/market/instruments-info",
        params={"category": category, "limit": limit}
    )

@st.cache_data(ttl=300)
def get_klines(symbol, interval="D", limit=7):
    """Ambil data candlestick historis"""
    try:
        response = requests.get(
            f"{BYBIT_URL}/v5/market/kline",
            params={
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            },
            headers=HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("retCode") == 0:
                klines = data["result"]["list"]
                df = pd.DataFrame(klines, columns=["Time", "Open", "High", "Low", "Close", "Volume", "Turnover"])
                df["Time"] = pd.to_datetime(df["Time"].astype(int), unit='ms')
                df[["Open", "High", "Low", "Close", "Volume"]] = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
                return df
        return None
    except Exception as e:
        return None

def get_volume_avg_7d(symbol):
    """Ambil rata-rata volume 7 hari"""
    df = get_klines(symbol, interval="D", limit=7)
    if df is not None and len(df) >= 3:
        return df["Volume"].mean()
    return None

# =========================================================
# FALLBACK: DATA DUMMY UNTUK TESTING
# =========================================================
def get_dummy_data():
    """Data dummy untuk testing jika API gagal"""
    return [
        {"symbol": "BTCUSDT", "lastPrice": "60000", "price24hPcnt": "0.052", "volume24h": "1500000"},
        {"symbol": "ETHUSDT", "lastPrice": "3000", "price24hPcnt": "0.035", "volume24h": "800000"},
        {"symbol": "BNBUSDT", "lastPrice": "580", "price24hPcnt": "0.028", "volume24h": "300000"},
        {"symbol": "SOLUSDT", "lastPrice": "150", "price24hPcnt": "0.042", "volume24h": "250000"},
        {"symbol": "XRPUSDT", "lastPrice": "0.60", "price24hPcnt": "0.015", "volume24h": "400000"},
        {"symbol": "ADAUSDT", "lastPrice": "0.45", "price24hPcnt": "0.022", "volume24h": "200000"},
        {"symbol": "DOTUSDT", "lastPrice": "7.50", "price24hPcnt": "0.018", "volume24h": "150000"},
        {"symbol": "LINKUSDT", "lastPrice": "14.20", "price24hPcnt": "0.025", "volume24h": "180000"},
        {"symbol": "MATICUSDT", "lastPrice": "0.55", "price24hPcnt": "0.012", "volume24h": "120000"},
        {"symbol": "AVAXUSDT", "lastPrice": "35.00", "price24hPcnt": "0.038", "volume24h": "220000"},
    ]

def get_dummy_instruments():
    """Data dummy instruments untuk testing"""
    return [
        {"symbol": "BTCUSDT", "rank": "1", "marketCap": "1200000000000"},
        {"symbol": "ETHUSDT", "rank": "2", "marketCap": "400000000000"},
        {"symbol": "BNBUSDT", "rank": "4", "marketCap": "80000000000"},
        {"symbol": "SOLUSDT", "rank": "5", "marketCap": "60000000000"},
        {"symbol": "XRPUSDT", "rank": "6", "marketCap": "30000000000"},
        {"symbol": "ADAUSDT", "rank": "8", "marketCap": "15000000000"},
        {"symbol": "DOTUSDT", "rank": "11", "marketCap": "10000000000"},
        {"symbol": "LINKUSDT", "rank": "12", "marketCap": "8000000000"},
        {"symbol": "MATICUSDT", "rank": "14", "marketCap": "6000000000"},
        {"symbol": "AVAXUSDT", "rank": "10", "marketCap": "12000000000"},
    ]

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
<b>Volume:</b> {row['Volume (M)']}M {row.get('Volume Trend', '')}
<b>Rank:</b> #{row['Rank']}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

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

# =========================================================
# PROSES DATA GABUNGAN
# =========================================================
def process_combined_data(tickers, instruments, currency, usd_to_idr):
    """Proses data ticker dan instrumen menjadi dataframe signal"""
    results = []
    
    # Buat mapping untuk rank dan market cap
    inst_map = {inst["symbol"]: inst for inst in instruments} if instruments else {}
    
    # Siapkan daftar simbol untuk ambil volume 7 hari
    symbols = [t["symbol"] for t in tickers[:50]]
    
    # Ambil volume rata-rata 7 hari secara paralel
    volume_avg_dict = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_symbol = {
            executor.submit(get_volume_avg_7d, sym): sym
            for sym in symbols
        }
        for future in as_completed(future_to_symbol):
            sym = future_to_symbol[future]
            try:
                avg = future.result()
                if avg is not None:
                    volume_avg_dict[sym] = avg
            except:
                pass
            time.sleep(0.1)
    
    # Proses setiap ticker
    for ticker in tickers:
        try:
            symbol = ticker["symbol"]
            inst = inst_map.get(symbol, {})
            
            # Filter: hanya yang aktif dan memiliki harga
            if inst.get("status") and inst.get("status") != "Trading":
                continue
            if not ticker.get("lastPrice") or float(ticker["lastPrice"]) <= 0:
                continue
            
            # Ambil data
            price = float(ticker["lastPrice"])
            price_24h_pcnt = float(ticker.get("price24hPcnt", 0)) * 100
            volume_24h = float(ticker.get("volume24h", 0))
            rank = int(inst.get("rank", 999)) if inst else 999
            market_cap = float(inst.get("marketCap", 0)) if inst and inst.get("marketCap") else 0
            
            # Nama coin
            name = symbol.replace("USDT", "").replace("PERP", "").replace("USD", "")
            
            # Hitung score
            score = 0
            
            if price_24h_pcnt > 10: score += 50
            elif price_24h_pcnt > 5: score += 35
            elif price_24h_pcnt > 2: score += 20
            elif price_24h_pcnt > 0: score += 10
            
            if rank <= 20: score += 25
            elif rank <= 50: score += 20
            elif rank <= 100: score += 10
            
            if market_cap > 0:
                vol_ratio = volume_24h / market_cap
                if vol_ratio > 0.1: score += 20
                elif vol_ratio > 0.05: score += 10
                if vol_ratio > 0.15: score += 5
            
            if score >= 80: signal = "🔥 STRONG BUY"
            elif score >= 65: signal = "🟢 BUY"
            elif score >= 45: signal = "🟡 WAIT"
            else: signal = "🔴 AVOID"
            
            display_price = price * (usd_to_idr if currency == "IDR" else 1)
            
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
                volume_trend = "➡️"
            
            results.append({
                "Coin": name,
                "Symbol": symbol,
                "Price": round(display_price, 4),
                "24H %": round(price_24h_pcnt, 2),
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
# MAIN
# =========================================================

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Settings")
    
    category = st.selectbox(
        "📊 Trading Category",
        ["linear", "spot", "inverse"],
        help="linear = USDT Perpetual, spot = Spot Trading, inverse = Coin-M Futures"
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
                    r = requests.post(url, json={"chat_id": CHAT_ID, "text": "🚀 Bybit Scanner ID aktif!"}, timeout=10)
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
    st.metric("Auto Refresh", "10 menit")
    st.divider()
    st.caption("📊 **Volume Trend Legend:**")
    st.caption("🔼 Volume > 130% rata-rata 7 hari")
    st.caption("🔽 Volume < 70% rata-rata 7 hari")
    st.caption("➡️ Volume stabil (70-130%)")

# Ambil kurs IDR
usd_to_idr = get_usd_to_idr()
if currency == "IDR":
    st.sidebar.info(f"💱 1 USD = {usd_to_idr:,.0f} IDR")

# =========================================================
# AMBIL DATA DARI BYBIT
# =========================================================
with st.spinner(f"📊 Mengambil data dari Bybit Indonesia ({category})..."):
    tickers = get_tickers(category=category)
    
    # Jika gagal, coba fallback dengan data dummy
    if tickers is None:
        st.warning("⚠️ Gagal mengambil data dari Bybit. Menggunakan data sample untuk testing...")
        tickers = get_dummy_data()
        instruments = get_dummy_instruments()
    else:
        instruments = get_instruments_info(category=category)
        if instruments is None:
            instruments = get_dummy_instruments()

if tickers is None:
    st.error("Tidak bisa mengambil data. Coba refresh halaman.")
    st.stop()

# Filter ticker yang memiliki volume dan harga valid
tickers = [t for t in tickers if float(t.get("volume24h", 0)) > 0 and float(t.get("lastPrice", 0)) > 0]

if not tickers:
    st.warning("Tidak ada ticker dengan data valid. Coba kategori lain.")
    st.stop()

with st.spinner("📈 Memproses data dan menghitung sinyal..."):
    results = process_combined_data(tickers, instruments, currency, usd_to_idr)

if not results:
    st.error("Tidak ada data yang bisa diproses.")
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
# CHART: Price Chart dengan Plotly
# =========================================================
st.divider()
st.subheader("📈 Price Chart - 7 Days")

klines_data = get_klines(selected, interval="D", limit=7)
if klines_data is not None and not klines_data.empty:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, 
                        row_heights=[0.7, 0.3])
    
    fig.add_trace(go.Candlestick(
        x=klines_data["Time"],
        open=klines_data["Open"],
        high=klines_data["High"],
        low=klines_data["Low"],
        close=klines_data["Close"],
        name="Price"
    ), row=1, col=1)
    
    colors = ['#00ff88' if close >= open else '#ff3b5c' 
              for close, open in zip(klines_data["Close"], klines_data["Open"])]
    fig.add_trace(go.Bar(
        x=klines_data["Time"],
        y=klines_data["Volume"],
        name="Volume",
        marker_color=colors
    ), row=2, col=1)
    
    fig.update_layout(
        template="plotly_dark",
        height=500,
        showlegend=False,
        plot_bgcolor='#0a0a1a',
        paper_bgcolor='#0a0a1a'
    )
    fig.update_xaxes(gridcolor='#1e293b')
    fig.update_yaxes(gridcolor='#1e293b')
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("📊 Data kline tidak tersedia untuk simbol ini")

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
    f"Total: {len(df)} | Sumber: Bybit Indonesia | "
    f"Telegram: {'✅' if BOT_TOKEN and CHAT_ID else '❌'} | Currency: {currency} | Category: {category}"
)
