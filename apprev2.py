import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Crypto Scanner Pro V3",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# PREMIUM DARK CSS
# =========================================================
st.markdown("""
<style>
.stApp { background: #070b14; }
.block-container { padding-top: 1.5rem; }

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #111827, #0b1220);
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 14px;
}

.signal-strong {
    color:#00ff88;
    border:1px solid #00ff88;
    background:rgba(0,255,136,.10);
    border-radius:20px;
    padding:4px 12px;
    font-weight:700;
}
.signal-buy {
    color:#00c8ff;
    border:1px solid #00c8ff;
    background:rgba(0,200,255,.10);
    border-radius:20px;
    padding:4px 12px;
    font-weight:700;
}
.signal-early {
    color:#a855f7;
    border:1px solid #a855f7;
    background:rgba(168,85,247,.10);
    border-radius:20px;
    padding:4px 12px;
    font-weight:700;
}
.signal-wait {
    color:#fbbf24;
    border:1px solid #fbbf24;
    background:rgba(251,191,36,.10);
    border-radius:20px;
    padding:4px 12px;
    font-weight:700;
}
.signal-avoid {
    color:#ff3b5c;
    border:1px solid #ff3b5c;
    background:rgba(255,59,92,.10);
    border-radius:20px;
    padding:4px 12px;
    font-weight:700;
}

.stButton > button {
    border-radius:10px;
    font-weight:700;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# CONSTANTS
# =========================================================
SKIP_SYMBOLS = {
    # Stablecoins
    "USDT","USDC","DAI","USDE","FDUSD","USDS","TUSD","USDD","PYUSD","GUSD",
    "BUSD","USDP","FRAX","LUSD","USD1","EURC","EURT","USDT0",
    # Wrapped / staked
    "WBTC","WETH","WSTETH","STETH","WBT","WBETH","RETH","CBETH","WEETH",
    "CBBTC","SOLVBTC","LBTC","WBNB","WMATIC","WAVAX",
}

# =========================================================
# SESSION STATE
# =========================================================
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "BTC"
if "last_notified" not in st.session_state:
    st.session_state.last_notified = {}
if "last_notified_time" not in st.session_state:
    st.session_state.last_notified_time = {}
if "last_update_time" not in st.session_state:
    st.session_state.last_update_time = datetime.now()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("⚙️ Scanner Settings")

    currency = st.selectbox("Currency", ["USD", "IDR"])

    scan_limit = st.selectbox(
        "Coins to scan",
        [50, 100],
        index=1
    )

    interval = st.selectbox(
        "Analysis timeframe",
        ["1d", "1h"],
        index=0,
        help="1d is more stable. 1h is more responsive but Yahoo Finance data availability can vary."
    )

    lookback = st.slider(
        "Breakout lookback",
        10, 50, 20,
        help="Number of candles used to detect the previous resistance."
    )

    min_volume_ratio = st.slider(
        "Minimum RVOL",
        1.0, 3.0, 1.5, 0.1
    )

    st.divider()

    st.subheader("📱 Telegram")
    default_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "") if hasattr(st, "secrets") else ""
    default_chat = st.secrets.get("TELEGRAM_CHAT_ID", "") if hasattr(st, "secrets") else ""

    BOT_TOKEN = st.text_input(
        "Bot Token",
        value=default_token,
        type="password"
    )
    CHAT_ID = st.text_input(
        "Chat ID",
        value=default_chat
    )
    send_notifications = st.checkbox(
        "Enable alerts",
        value=True
    )
    notify_min_score = st.slider(
        "Minimum alert score",
        60, 100, 80
    )

    if st.button("🔄 Force Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# =========================================================
# FX
# =========================================================
@st.cache_data(ttl=3600, show_spinner=False)
def get_usd_to_idr():
    try:
        r = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=10
        )
        if r.ok:
            return float(r.json()["rates"]["IDR"])
    except Exception:
        pass
    return 15500.0

usd_to_idr = get_usd_to_idr()

# =========================================================
# TELEGRAM
# =========================================================
def send_telegram(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        r = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        return r.ok
    except Exception:
        return False


def format_telegram_message(row):
    return (
        f"🚀 <b>CRYPTO SCANNER SIGNAL</b>\n\n"
        f"<b>{row['Coin']} ({row['Symbol']})</b>\n"
        f"Signal: {row['Signal']}\n"
        f"Score: <b>{row['Score']}/100</b>\n\n"
        f"Price: ${row['Price USD']:,.6f}\n"
        f"24H: {row['24H %']:.2f}%\n"
        f"7D: {row['7D %']:.2f}%\n"
        f"RSI: {row['RSI']:.1f}\n"
        f"RVOL: {row['RVOL']:.2f}x\n"
        f"Trend: {row['Trend']}\n"
        f"Breakout: {row['Breakout']}\n\n"
        f"Entry: ${row['Entry']:,.6f}\n"
        f"SL: ${row['Stop Loss']:,.6f}\n"
        f"TP1: ${row['TP1']:,.6f}\n"
        f"TP2: ${row['TP2']:,.6f}\n"
        f"R:R: {row['Risk/Reward']:.2f}\n\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

# =========================================================
# COINGECKO
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_coingecko(limit=100):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h,7d"
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return []


# =========================================================
# YAHOO HISTORICAL DATA
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def get_history(symbol, interval="1d"):
    """
    Historical OHLCV for indicators.
    Daily: 1y
    Hourly: 60d
    """
    try:
        ticker = yf.Ticker(f"{symbol}-USD")

        if interval == "1h":
            hist = ticker.history(
                period="60d",
                interval="1h",
                auto_adjust=False
            )
        else:
            hist = ticker.history(
                period="2y",
                interval="1d",
                auto_adjust=False
            )

        if hist is None or hist.empty:
            return None

        hist = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
        hist = hist.dropna()

        # Buang baris tanpa volume (penyebab RVOL aneh: 20x, 15x)
        hist = hist[hist["Volume"] > 0]

        # Minimal 60 candle untuk EMA200-ish / indikator stabil
        if len(hist) < (300 if interval == "1d" else 250):
            return None

        return hist

    except Exception:
        return None


# =========================================================
# INDICATORS
# =========================================================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def add_indicators(df, breakout_lookback=20):
    x = df.copy()

    # EMA
    x["EMA9"] = x["Close"].ewm(span=9, adjust=False).mean()
    x["EMA21"] = x["Close"].ewm(span=21, adjust=False).mean()
    x["EMA50"] = x["Close"].ewm(span=50, adjust=False).mean()
    x["EMA200"] = x["Close"].ewm(span=200, adjust=False).mean()

    # RSI
    x["RSI"] = calculate_rsi(x["Close"])

    # MACD
    ema12 = x["Close"].ewm(span=12, adjust=False).mean()
    ema26 = x["Close"].ewm(span=26, adjust=False).mean()
    x["MACD"] = ema12 - ema26
    x["MACD_Signal"] = x["MACD"].ewm(span=9, adjust=False).mean()
    x["MACD_Hist"] = x["MACD"] - x["MACD_Signal"]

    # ATR
    prev_close = x["Close"].shift(1)
    tr = pd.concat([
        x["High"] - x["Low"],
        (x["High"] - prev_close).abs(),
        (x["Low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    x["ATR"] = tr.ewm(span=14, adjust=False).mean()

    # Relative volume (dengan guard)
    x["VolumeAvg20"] = x["Volume"].shift(1).rolling(20).mean()
    x["RVOL"] = np.where(
        x["VolumeAvg20"] > 0,
        x["Volume"] / x["VolumeAvg20"],
        1.0
    )
    # Cap supaya tidak absurd
    x["RVOL"] = np.clip(x["RVOL"], 0, 10)

    # Previous resistance/support
    x["Resistance"] = x["High"].shift(1).rolling(breakout_lookback).max()

    x["Support"] = x["Low"].shift(1).rolling(breakout_lookback).min()

    # Momentum
    x["ROC7"] = x["Close"].pct_change(7) * 100
    x["ROC20"] = x["Close"].pct_change(20) * 100

    return x


# =========================================================
# MARKET STRUCTURE
# =========================================================
def get_pivots(df, left=3, right=3):
    h=df["High"]; l=df["Low"]
    ph=(h==h.rolling(left+right+1,center=True).max()).fillna(False)
    pl=(l==l.rolling(left+right+1,center=True).min()).fillna(False)
    return ph, pl

def get_structure(df):
    if len(df)<30: return "N/A"
    ph,pl=get_pivots(df)
    hs=df.loc[ph,"High"].tail(3).tolist(); ls=df.loc[pl,"Low"].tail(3).tolist()
    if len(hs)<2 or len(ls)<2: return "Mixed"
    if hs[-1]>hs[-2] and ls[-1]>ls[-2]: return "HH/HL Bullish"
    if hs[-1]<hs[-2] and ls[-1]<ls[-2]: return "LH/LL Bearish"
    return "Mixed"

def get_pivot_sr(df):
    ph,pl=get_pivots(df); price=float(df["Close"].iloc[-1])
    rs=sorted({float(v) for v in df.loc[ph,"High"] if v>price})
    ss=sorted({float(v) for v in df.loc[pl,"Low"] if v<price},reverse=True)
    return (ss[0] if ss else np.nan),(rs[0] if rs else np.nan)


# =========================================================
# FIBONACCI
# =========================================================
def fibonacci_levels(df, window=50):
    recent = df.tail(window)
    swing_high = recent["High"].max()
    swing_low = recent["Low"].min()
    diff = swing_high - swing_low

    if diff <= 0:
        return {}

    return {
        "0.236": swing_high - diff * 0.236,
        "0.382": swing_high - diff * 0.382,
        "0.500": swing_high - diff * 0.500,
        "0.618": swing_high - diff * 0.618,
        "0.786": swing_high - diff * 0.786
    }


# =========================================================
# SCORE ENGINE
# =========================================================
def calculate_setup(row):
    score = 0
    reasons = []

    price = row["Price USD"]
    ema9 = row["EMA9"]
    ema21 = row["EMA21"]
    ema50 = row["EMA50"]
    ema200 = row["EMA200"]
    rsi = row["RSI"]
    macd = row["MACD"]
    macd_signal = row["MACD Signal"]
    rvol = row["RVOL"]
    resistance = row["Resistance"]
    support = row["Support"]
    roc7 = row["ROC7"]
    roc20 = row["ROC20"]

    # 1. TREND = 20 points
    if price > ema9 > ema21 > ema50:
        score += 12
        reasons.append("EMA bullish alignment")
    elif price > ema21 > ema50:
        score += 8
        reasons.append("EMA bullish")
    elif price > ema50:
        score += 4

    if price > ema200:
        score += 8
        reasons.append("Above EMA200")

    # 2. MOMENTUM = 20 points
    if roc7 > 10:
        score += 10
        reasons.append("Strong 7D momentum")
    elif roc7 > 5:
        score += 7
    elif roc7 > 2:
        score += 4

    if roc20 > 15:
        score += 10
        reasons.append("Strong 20D momentum")
    elif roc20 > 5:
        score += 6
    elif roc20 > 0:
        score += 3

    # 3. VOLUME = 20 points
    if rvol >= 3:
        score += 20
        reasons.append("Extreme volume")
    elif rvol >= 2:
        score += 15
        reasons.append("Strong volume")
    elif rvol >= 1.5:
        score += 10
        reasons.append("Volume confirmation")
    elif rvol >= 1.2:
        score += 5

    # 4. BREAKOUT = 20 points
    breakout = False
    near_breakout = False

    if pd.notna(resistance) and resistance > 0:
        if price > resistance:
            breakout = True
            if rvol >= 1.5:
                score += 20
                reasons.append("Confirmed breakout")
            else:
                score += 12
                reasons.append("Breakout without strong volume")
        elif price >= resistance * 0.98:
            near_breakout = True
            score += 10
            reasons.append("Near breakout")

    # 5. RSI + MACD = 10 points
    if pd.notna(rsi):
        if 50 <= rsi <= 68:
            score += 5
            reasons.append("Healthy RSI")
        elif 40 <= rsi < 50:
            score += 2
        elif rsi > 75:
            score -= 5
            reasons.append("RSI overextended")
        elif rsi < 30:
            score += 3
            reasons.append("RSI oversold")

    if macd > macd_signal:
        score += 5
        reasons.append("MACD bullish")
    elif macd < macd_signal:
        score -= 2

    # 6. STRUCTURE = 10 points
    structure = row["Structure"]
    if structure == "HH/HL Bullish":
        score += 10
        reasons.append("Bullish market structure")
    elif structure == "LH/LL Bearish":
        score -= 5

    # Penalize extreme short-term acceleration so already-pumped coins do not dominate.
    if roc7 > 25: score -= 6
    if rsi > 78: score -= 4
    # Normalize
    score = max(0, min(100, int(round(score))))

    # TREND LABEL
    if price > ema9 > ema21 > ema50:
        trend = "🟢 Strong Bullish"
    elif price > ema21 > ema50:
        trend = "🟢 Bullish"
    elif price > ema50:
        trend = "🟡 Recovering"
    else:
        trend = "🔴 Bearish"

    # SIGNAL (urutan prioritas diperbaiki)
    if breakout and rvol >= 1.5 and score >= 80:
        signal = "🔥 STRONG BREAKOUT"
        badge = "signal-strong"
    elif breakout and rvol >= 1.5:
        signal = "🟢 BREAKOUT"
        badge = "signal-buy"
    elif score >= 80:
        signal = "🔥 STRONG BUY"
        badge = "signal-strong"
    elif score >= 70 and (breakout or near_breakout):
        signal = "🟢 MOMENTUM BUY"
        badge = "signal-buy"
    elif score >= 65:
        signal = "🟣 EARLY MOMENTUM"
        badge = "signal-early"
    elif score >= 45:
        signal = "🟡 WAIT"
        badge = "signal-wait"
    else:
        signal = "🔴 AVOID"
        badge = "signal-avoid"

    # ENTRY / SL / TP
    atr = row["ATR"]
    if pd.isna(atr) or atr <= 0:
        atr = price * 0.02

    if breakout and pd.notna(resistance):
        entry = resistance * 1.002
        stop_loss = resistance - atr * 1.2
    elif pd.notna(ema21) and ema21 > 0:
        entry = price
        stop_loss = min(price - atr * 1.2, ema21 * 0.985)
    else:
        entry = price
        stop_loss = price - atr * 1.2

    risk = max(entry - stop_loss, price * 0.005)
    tp1 = entry + risk * 1.5
    tp2 = entry + risk * 2.5
    tp3 = entry + risk * 4.0
    rr = (tp2 - entry) / risk if risk > 0 else 0

    # Override: jangan rekomendasi BUY kalau upside ke resistance < 2%
    if (not breakout) and pd.notna(resistance) and resistance > 0:
        upside = (resistance - price) / price * 100
        if upside < 2 and signal in (
            "🔥 STRONG BUY", "🟢 MOMENTUM BUY", "🟣 EARLY MOMENTUM"
        ):
            signal = "🟡 WAIT RESISTANCE"
            badge = "signal-wait"

    return {
        "Score": score,
        "Signal": signal,
        "Badge": badge,
        "Trend": trend,
        "Breakout": "🔥 YES" if breakout else "⚠️ NEAR" if near_breakout else "NO",
        "Entry": float(entry),
        "Stop Loss": float(stop_loss),
        "TP1": float(tp1),
        "TP2": float(tp2),
        "TP3": float(tp3),
        "Risk/Reward": float(rr),
        "Reasons": reasons
    }


# =========================================================
# PROCESS ONE COIN
# =========================================================
def analyze_coin(coin, interval, breakout_lookback):
    symbol = coin["symbol"].upper()

    if symbol in SKIP_SYMBOLS:
        return None

    hist = get_history(symbol, interval)

    if hist is None or len(hist) < 60:
        return None

    data = add_indicators(hist, breakout_lookback=breakout_lookback)
    latest = data.iloc[-1]

    # CoinGecko metadata
    price_usd = float(coin.get("current_price", 0) or 0)
    if price_usd <= 0:
        return None

    change_24h = float(coin.get("price_change_percentage_24h", 0) or 0)
    change_7d = float(coin.get("price_change_percentage_7d_in_currency", 0) or 0)
    rank = int(coin.get("market_cap_rank", 999) or 999)
    market_cap = float(coin.get("market_cap", 0) or 0)
    volume_24h = float(coin.get("total_volume", 0) or 0)

    structure = get_structure(data)
    pivot_support, pivot_resistance = get_pivot_sr(data)

    # Validasi RSI
    rsi_val = float(latest["RSI"]) if pd.notna(latest["RSI"]) else 50.0
    if not (0 <= rsi_val <= 100):
        rsi_val = 50.0

    row = {
        "Coin": coin["name"],
        "Symbol": symbol,
        "Price USD": float(latest["Close"]),
        "Live Price USD": price_usd,
        "24H %": change_24h,
        "7D %": change_7d,
        "Rank": rank,
        "Market Cap": market_cap,
        "Volume 24H USD": volume_24h,
        "EMA9": float(latest["EMA9"]),
        "EMA21": float(latest["EMA21"]),
        "EMA50": float(latest["EMA50"]),
        "EMA200": float(latest["EMA200"]),
        "RSI": rsi_val,
        "MACD": float(latest["MACD"]),
        "MACD Signal": float(latest["MACD_Signal"]),
        "MACD Hist": float(latest["MACD_Hist"]),
        "ATR": float(latest["ATR"]) if pd.notna(latest["ATR"]) else price_usd * 0.02,
        "RVOL": float(latest["RVOL"]) if pd.notna(latest["RVOL"]) else 1.0,
        "EMA21 Slope": float(latest["EMA21"].__float__() and data["EMA21"].pct_change(5).iloc[-1]) if pd.notna(data["EMA21"].pct_change(5).iloc[-1]) else 0.0,
        "EMA50 Slope": float(data["EMA50"].pct_change(10).iloc[-1]) if pd.notna(data["EMA50"].pct_change(10).iloc[-1]) else 0.0,
        "Resistance": float(pivot_resistance) if pd.notna(pivot_resistance) else (float(latest["Resistance"]) if pd.notna(latest["Resistance"]) else float(latest["Close"])),
        "Support": float(pivot_support) if pd.notna(pivot_support) else (float(latest["Support"]) if pd.notna(latest["Support"]) else float(latest["Close"])),
        "ROC7": float(latest["ROC7"]) if pd.notna(latest["ROC7"]) else change_7d,
        "ROC20": float(latest["ROC20"]) if pd.notna(latest["ROC20"]) else change_7d,
        "Structure": structure,
        "History": data
    }

    setup = calculate_setup(row)
    row.update(setup)

    row["Price IDR"] = price_usd * usd_to_idr
    row["Volume (M)"] = volume_24h / 1_000_000

    return row


# =========================================================
# HISTORICAL BACKTEST
# =========================================================
def backtest_coin(history, lookback=20, horizon=5, target_pct=5.0, stop_pct=3.0, min_score=65):
    if history is None or len(history)<350: return pd.DataFrame(), {}
    x=add_indicators(history,lookback); rows=[]
    for i in range(max(250,lookback+30),len(x)-horizon-1):
        w=x.iloc[:i+1]; r=w.iloc[-1]; price=float(r.Close)
        ps,pr=get_pivot_sr(w); resistance=pr if pd.notna(pr) else float(r.Resistance); support=ps if pd.notna(ps) else float(r.Support)
        row={"Price USD":price,"EMA9":float(r.EMA9),"EMA21":float(r.EMA21),"EMA50":float(r.EMA50),"EMA200":float(r.EMA200),"RSI":float(r.RSI) if pd.notna(r.RSI) else 50.0,"MACD":float(r.MACD),"MACD Signal":float(r.MACD_Signal),"MACD Hist":float(r.MACD_Hist),"ATR":float(r.ATR) if pd.notna(r.ATR) else price*.02,"RVOL":float(r.RVOL) if pd.notna(r.RVOL) else 1.0,"Resistance":resistance,"Support":support,"ROC7":float(r.ROC7) if pd.notna(r.ROC7) else 0,"ROC20":float(r.ROC20) if pd.notna(r.ROC20) else 0,"Structure":get_structure(w),"History":w}
        setup=calculate_setup(row)
        if setup["Score"]<min_score or "WAIT" in setup["Signal"] or setup["Signal"]=="🔴 AVOID": continue
        f=x.iloc[i+1:i+1+horizon]; entry=float(x["Open"].iloc[i+1]); tp=entry*(1+target_pct/100); sl=entry*(1-stop_pct/100)
        ht=bool((f.High>=tp).any()); hs=bool((f.Low<=sl).any()); outcome="AMBIGUOUS" if ht and hs else "WIN" if ht else "LOSS" if hs else ("WIN" if float(f.Close.iloc[-1])>entry else "LOSS")
        rows.append({"Date":x.index[i],"Signal":setup["Signal"],"Score":setup["Score"],"Entry":entry,"Target":tp,"Stop":sl,"Max Gain %":(float(f.High.max())/entry-1)*100,"Max Drawdown %":(float(f.Low.min())/entry-1)*100,"Outcome":outcome})
    bt=pd.DataFrame(rows)
    if bt.empty:return bt,{}
    valid=bt[bt.Outcome.isin(["WIN","LOSS"])]
    return bt,{"signals":len(bt),"valid":len(valid),"wins":int((valid.Outcome=="WIN").sum()),"win_rate":float((valid.Outcome=="WIN").mean()*100) if len(valid) else 0.0,"avg_gain":float(bt["Max Gain %"].mean()),"avg_dd":float(bt["Max Drawdown %"].mean())}

# =========================================================
# HEADER
# =========================================================
st.markdown("""
<h1 style="margin-bottom:0;">
🚀 Crypto Scanner <span style="color:#00ff88;">Pro V3</span>
</h1>
<p style="color:#64748b;">
CoinGecko market data + Yahoo Finance OHLCV + Trend + Momentum +
Volume + Breakout + S/R + Fibonacci + Risk Management
</p>
""", unsafe_allow_html=True)

# =========================================================
# LOAD DATA
# =========================================================
coins = load_coingecko(scan_limit)

if not coins:
    st.error("❌ Gagal mengambil data CoinGecko.")
    st.stop()

with st.spinner(f"🔎 Menganalisis {len(coins)} coins..."):
    results = []

    # Turunkan max_workers untuk hindari rate-limit + race condition cache
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(analyze_coin, coin, interval, lookback): coin
            for coin in coins
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                continue

if not results:
    st.error(
        "Tidak ada data OHLCV yang berhasil dianalisis. "
        "Coba ganti timeframe atau refresh."
    )
    st.stop()

df = pd.DataFrame(results)
df = df.sort_values(["Score", "RVOL"], ascending=[False, False]).reset_index(drop=True)
df["Scanner Rank"] = df.index + 1
st.session_state.last_update_time = datetime.now()

# =========================================================
# MARKET METRICS
# =========================================================
avg_score = df["Score"].mean()
bullish_count = len(df[df["Trend"].str.contains("Bullish", na=False)])
breakout_count = len(df[df["Breakout"] == "🔥 YES"])
strong_count = len(df[df["Signal"].str.contains("STRONG", na=False)])

if avg_score >= 65:
    market_mood = "🟢 BULLISH"
elif avg_score >= 45:
    market_mood = "🟡 NEUTRAL"
else:
    market_mood = "🔴 BEARISH"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Market Mood", market_mood)
c2.metric("Coins", len(df))
c3.metric("Avg Score", f"{avg_score:.1f}")
c4.metric("Breakouts", breakout_count)
c5.metric("Strong Signals", strong_count)

# =========================================================
# TELEGRAM ALERT (dengan cooldown 1 jam per simbol)
# =========================================================
if BOT_TOKEN and CHAT_ID and send_notifications:
    alerts = df[
        (df["Score"] >= notify_min_score) &
        (df["Signal"].isin([
            "🔥 STRONG BREAKOUT",
            "🔥 STRONG BUY",
            "🟢 BREAKOUT",
            "🟢 MOMENTUM BUY"
        ]))
    ]

    sent = 0
    now_ts = time.time()

    for _, row in alerts.iterrows():
        key = f"{row['Symbol']}_{row['Signal']}"
        last_key = st.session_state.last_notified.get(row["Symbol"])
        last_time = st.session_state.last_notified_time.get(row["Symbol"], 0)

        if last_key != key and (now_ts - last_time) > 3600:
            if send_telegram(BOT_TOKEN, CHAT_ID, format_telegram_message(row)):
                st.session_state.last_notified[row["Symbol"]] = key
                st.session_state.last_notified_time[row["Symbol"]] = now_ts
                sent += 1
            time.sleep(0.25)

    if sent:
        st.sidebar.success(f"📱 {sent} alert terkirim")

# =========================================================
# TOP OPPORTUNITIES  ← FIX UTAMA: HTML tanpa indentasi
# =========================================================
st.divider()
st.subheader("🔥 Top Opportunities")

top = df.head(5)
cols = st.columns(min(5, len(top)))

for i, (_, row) in enumerate(top.iterrows()):
    with cols[i]:
        badge = row["Badge"]
        color_24h = "#00ff88" if row["24H %"] >= 0 else "#ff3b5c"

        html = f"""
<div style="background:linear-gradient(145deg,#111827,#0b1220);border:1px solid #1e293b;border-radius:16px;padding:18px;min-height:240px;">
<div style="font-size:20px;font-weight:800;">{row['Coin']}</div>
<div style="color:#64748b;">{row['Symbol']} &middot; Rank #{row['Rank']}</div>
<div style="margin:12px 0;"><span class="{badge}">{row['Signal']}</span></div>
<div style="font-size:28px;font-weight:800;">{row['Score']}<span style="font-size:12px;color:#64748b;">/100</span></div>
<div style="margin-top:10px;color:#94a3b8;">24H: <span style="color:{color_24h};">{row['24H %']:.2f}%</span></div>
<div style="color:#94a3b8;">RSI: {row['RSI']:.1f}</div>
<div style="color:#94a3b8;">RVOL: {row['RVOL']:.2f}x</div>
<div style="color:#94a3b8;">Breakout: {row['Breakout']}</div>
</div>
"""
        st.markdown(html, unsafe_allow_html=True)

# =========================================================
# FILTER TABS
# =========================================================
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔥 Breakout",
    "🚀 Strong",
    "🟢 Momentum",
    "📊 Full Scanner",
    "📈 Chart",
    "🧪 Backtest"
])

display_columns = [
    "Scanner Rank", "Coin", "Symbol", "Score", "Signal", "Trend",
    "24H %", "7D %", "RSI", "RVOL", "Breakout", "Structure",
    "Resistance", "Support", "Risk/Reward"
]


def show_table(data):
    if data.empty:
        st.info("Tidak ada setup saat ini.")
        return

    available = [c for c in display_columns if c in data.columns]
    view = data[available].copy()

    st.dataframe(
        view.style.format({
            "Score": "{:.0f}",
            "24H %": "{:+.2f}%",
            "7D %": "{:+.2f}%",
            "RSI": "{:.1f}",
            "RVOL": "{:.2f}x",
            "Resistance": "${:,.6f}",
            "Support": "${:,.6f}",
            "Risk/Reward": "1:{:.2f}",
        }, na_rep="-"),
        use_container_width=True,
        hide_index=True,
        height=500
    )


with tab1:
    breakout_df = df[
        (df["Breakout"] == "🔥 YES") |
        ((df["Breakout"] == "⚠️ NEAR") & (df["RVOL"] >= min_volume_ratio))
    ]
    show_table(breakout_df)

with tab2:
    strong_df = df[
        df["Signal"].isin([
            "🔥 STRONG BREAKOUT",
            "🔥 STRONG BUY"
        ])
    ]
    show_table(strong_df)

with tab3:
    momentum_df = df[
        df["Signal"].isin([
            "🟢 BREAKOUT",
            "🟢 MOMENTUM BUY",
            "🟣 EARLY MOMENTUM"
        ])
    ]
    show_table(momentum_df)

with tab4:
    show_table(df)

# =========================================================
# CHART / COIN DETAIL
# =========================================================
with tab5:
    symbols = df["Symbol"].tolist()

    if st.session_state.selected_symbol in symbols:
        default_index = symbols.index(st.session_state.selected_symbol)
    else:
        default_index = 0

    selected = st.selectbox("Select Coin", symbols, index=default_index)
    st.session_state.selected_symbol = selected

    selected_row = df[df["Symbol"] == selected].iloc[0]
    history = selected_row["History"].copy()
    fib = fibonacci_levels(history, 100)

    st.subheader(f"{selected_row['Coin']} ({selected})")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Price", f"${selected_row['Price USD']:,.6f}")
    m2.metric("Score", f"{selected_row['Score']}/100")
    m3.metric("RSI", f"{selected_row['RSI']:.1f}")
    m4.metric("RVOL", f"{selected_row['RVOL']:.2f}x")
    m5.metric("Breakout", selected_row["Breakout"])
    m6.metric("R:R", f"1:{selected_row['Risk/Reward']:.2f}")

    st.markdown(
        f"**Signal:** {selected_row['Signal']}  \n"
        f"**Trend:** {selected_row['Trend']}  \n"
        f"**Structure:** {selected_row['Structure']}"
    )

    # PRICE CHART
    chart_df = history.tail(120)

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=chart_df.index,
            open=chart_df["Open"],
            high=chart_df["High"],
            low=chart_df["Low"],
            close=chart_df["Close"],
            name="Price"
        )
    )

    for col, name in [
        ("EMA9", "EMA 9"),
        ("EMA21", "EMA 21"),
        ("EMA50", "EMA 50"),
        ("EMA200", "EMA 200")
    ]:
        if col in chart_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=chart_df.index,
                    y=chart_df[col],
                    mode="lines",
                    name=name
                )
            )

    fig.add_hline(
        y=selected_row["Resistance"],
        line_dash="dash",
        annotation_text="Resistance"
    )
    fig.add_hline(
        y=selected_row["Support"],
        line_dash="dash",
        annotation_text="Support"
    )

    fig.update_layout(
        template="plotly_dark",
        height=600,
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )

    st.plotly_chart(fig, use_container_width=True)

    # TRADE PLAN
    st.subheader("🎯 Trade Plan")

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Entry", f"${selected_row['Entry']:,.6f}")
    p2.metric("Stop Loss", f"${selected_row['Stop Loss']:,.6f}")
    p3.metric("TP1", f"${selected_row['TP1']:,.6f}")
    p4.metric("TP2", f"${selected_row['TP2']:,.6f}")

    p5, p6, p7 = st.columns(3)
    p5.metric("TP3", f"${selected_row['TP3']:,.6f}")
    p6.metric("Resistance", f"${selected_row['Resistance']:,.6f}")
    p7.metric("Support", f"${selected_row['Support']:,.6f}")

    # FIBONACCI
    st.subheader("📐 Fibonacci")
    if fib:
        fib_df = pd.DataFrame(
            [{"Level": k, "Price": v} for k, v in fib.items()]
        )
        st.dataframe(fib_df, use_container_width=True, hide_index=True)

    # REASONS
    st.subheader("🧠 Why this coin scored this way")
    reasons = selected_row["Reasons"]
    if reasons:
        for reason in reasons:
            st.write(f"• {reason}")
    else:
        st.write("Tidak ada alasan tambahan.")


with tab6:
    st.subheader("🧪 Historical Rule Backtest")
    st.caption("Entry = open candle berikutnya. Target/stop diuji selama horizon candle. Ini validasi rule, bukan jaminan profit.")
    b1,b2,b3,b4=st.columns(4)
    bt_h=b1.slider("Horizon",3,20,5); bt_t=b2.slider("Target %",2.0,15.0,5.0,0.5); bt_s=b3.slider("Stop %",1.0,10.0,3.0,0.5); bt_min=b4.slider("Min Score",50,85,65)
    if st.button("▶️ Run Backtest",use_container_width=True):
        with st.spinner("Running walk-forward backtest..."):
            bt,stats=backtest_coin(history,lookback,bt_h,bt_t,bt_s,bt_min)
        if bt.empty: st.warning("Sample belum cukup atau tidak ada sinyal dengan parameter ini.")
        else:
            q1,q2,q3,q4=st.columns(4); q1.metric("Signals",stats["signals"]); q2.metric("Valid",stats["valid"]); q3.metric("Win Rate",f"{stats['win_rate']:.1f}%"); q4.metric("Avg Max Gain",f"{stats['avg_gain']:.2f}%")
            st.dataframe(bt.sort_values("Date",ascending=False),use_container_width=True,hide_index=True)
            if stats["valid"]<20: st.warning("Sample masih kecil; jangan gunakan win rate ini sebagai dasar trading.")

# =========================================================
# EXPORT
# =========================================================
st.divider()
st.subheader("📥 Export")

export_cols = [
    c for c in df.columns
    if c not in ["History", "Reasons", "Badge"]
]
export_df = df[export_cols].copy()

csv = export_df.to_csv(index=False).encode("utf-8")

st.download_button(
    "📥 Download CSV",
    csv,
    f"crypto_scanner_v3_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
    "text/csv"
)

# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption(
    f"Last updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')} | "
    f"Coins analyzed: {len(df)} | "
    f"Source: CoinGecko + Yahoo Finance | "
    f"Timeframe: {interval}"
)

# Auto refresh setiap 10 menit
st_autorefresh(interval=600000, key="scanner_refresh")
