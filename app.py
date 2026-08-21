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
# BASE URL UNTUK INDONESIA
# =========================================================
BYBIT_URL = "https://api.bybit.id"

# =========================================================
# HEADERS UNTUK MENGHINDARI BLOKIR
# =========================================================
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
# FUNGSI AMBIL DATA DENGAN RETRY DAN BETTER HANDLING
# =========================================================
def fetch_bybit_data(endpoint, params=None, max_retries=3):
    """Fungsi generic untuk fetch data dari Bybit dengan retry"""
    for attempt in range(max_retries):
        try:
            # Gunakan session untuk persistent connection
            session = requests.Session()
            session.headers.update(HEADERS)
            
            # Tambahkan timeout
            response = session.get(
                f"{BYBIT_URL}{endpoint}",
                params=params,
                timeout=15
            )
            
            # Cek status code
            if response.status_code == 200:
                # Coba parse JSON
                try:
                    data = response.json()
                    if data.get("retCode") == 0:
                        return data["result"]["list"] if "result" in data else data
                    else:
                        st.warning(f"Bybit API Error: {data.get('retMsg', 'Unknown error')}")
                        return None
                except json.JSONDecodeError as e:
                    # Jika JSON error, coba lihat response text
                    st.error(f"JSON Error: {e}")
                    st.text(f"Response preview: {response.text[:200]}...")
                    return None
            else:
                st.warning(f"HTTP Error {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
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

# =========================================================
# FUNGSI AMBIL DATA DARI BYBIT INDONESIA
# =========================================================
@st.cache_data(ttl=300)
def get_tickers(category="linear"):
    """Ambil data ticker dari Bybit Indonesia dengan retry"""
    return fetch_bybit_data(
        "/v5/market/tickers",
        params={"category": category}
    )

@st.cache_data(ttl=300)
def get_instruments_info(category="linear", limit=200):
    """Ambil informasi instrumen dari Bybit Indonesia dengan retry"""
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
                df["Volume"] = df["Volume"].astype(float)
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
# FALLBACK: AMBIL DARI ENDPOINT ALTERNATIF
# =========================================================
@st.cache_data(ttl=300)
def get_tickers_fallback(category="linear"):
    """Fallback: Gunakan endpoint demo/testnet jika endpoint utama gagal"""
    try:
        # Coba endpoint demo
        response = requests.get(
            "https://api-demo.bybit.com/v5/market/tickers",
            params={"category": category},
            headers=HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("retCode") == 0:
                return data["result"]["list"]
        return None
    except:
        return None

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
    
    # Siapkan daftar simbol untuk ambil volume 7 hari (batasi 50 untuk kecepatan)
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
# PAGE CONFIG & CSS
# =========================================================
st.set_page_config(
    page_title="Bybit Scanner ID - Crypto Signals",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ... (sisa CSS sama seperti sebelumnya, lanjutkan dari kode sebelumnya)

# =========================================================
# MAIN
# =========================================================

# ... (sisa kode sama, tapi bagian MAIN diubah)

# =========================================================
# AMBIL DATA DENGAN FALLBACK
# =========================================================
with st.spinner(f"📊 Mengambil data dari Bybit Indonesia ({category})..."):
    tickers = get_tickers(category=category)
    
    # Jika gagal, coba fallback
    if tickers is None:
        st.warning("⚠️ Gagal dari endpoint utama, mencoba endpoint demo...")
        tickers = get_tickers_fallback(category=category)
    
    # Jika masih gagal, gunakan data dummy untuk testing
    if tickers is None:
        st.warning("⚠️ Tidak bisa mengambil data dari Bybit. Gunakan data sample untuk testing.")
        # Data dummy untuk testing
        tickers = [
            {"symbol": "BTCUSDT", "lastPrice": "60000", "price24hPcnt": "0.05", "volume24h": "1000000"},
            {"symbol": "ETHUSDT", "lastPrice": "3000", "price24hPcnt": "0.03", "volume24h": "500000"},
            {"symbol": "BNBUSDT", "lastPrice": "500", "price24hPcnt": "0.02", "volume24h": "200000"},
        ]
    
    instruments = get_instruments_info(category=category)

# ... (sisa kode MAIN sama seperti sebelumnya)
