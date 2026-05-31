import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

from binance_core import (
    get_top20_coins,
    get_klines,
    ai_score,
    ema
)

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="🚀 AI Crypto Scanner",
    layout="wide"
)

# =====================================================
# AUTO REFRESH
# =====================================================
st_autorefresh(
    interval=300000,
    key="refresh"
)

# =====================================================
# STYLE
# =====================================================
st.markdown("""
<style>

.stApp{
    background:#050816;
}

.buy{
    background:#0f172a;
    border-left:6px solid #00ff88;
    padding:15px;
    border-radius:15px;
}

.wait{
    background:#0f172a;
    border-left:6px solid orange;
    padding:15px;
    border-radius:15px;
}

.sell{
    background:#0f172a;
    border-left:6px solid red;
    padding:15px;
    border-radius:15px;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# HEADER
# =====================================================
st.title("🚀 Binance Spot AI Scanner")
st.caption("Top 20 Volume • 4H Trading Signal")

# =====================================================
# LOAD MARKET
# =====================================================
with st.spinner("Scanning Market..."):

    market = get_top20_coins()

if market.empty:

    st.error("❌ Binance Spot tidak mengembalikan data")

    st.stop()

# =====================================================
# SCAN
# =====================================================
signals = []

for symbol in market["symbol"].head(20):

    try:

        df = get_klines(
            symbol=symbol,
            interval="4h",
            limit=300
        )

        result = ai_score(df)

        if result:

            signals.append({

                "symbol": symbol,

                **result
            })

    except Exception as e:

        pass

if len(signals) == 0:

    st.warning("Tidak ada signal ditemukan")

    st.stop()

# =====================================================
# SORT
# =====================================================
signals = sorted(
    signals,
    key=lambda x: x["score"],
    reverse=True
)

# =====================================================
# MARKET MOOD
# =====================================================
avg_score = sum(
    x["score"]
    for x in signals
) / len(signals)

if avg_score >= 75:

    mood = "🟢 MARKET BULLISH"

elif avg_score >= 55:

    mood = "🟡 MARKET SIDEWAYS"

else:

    mood = "🔴 MARKET BEARISH"

col1,col2,col3 = st.columns(3)

col1.metric(
    "Market Mood",
    mood
)

col2.metric(
    "Scanned Coins",
    len(signals)
)

col3.metric(
    "Average Score",
    f"{avg_score:.1f}"
)

# =====================================================
# TABS
# =====================================================
tab1,tab2,tab3 = st.tabs([
    "🔥 Opportunities",
    "📊 Scanner",
    "📈 Chart"
])

# =====================================================
# OPPORTUNITY
# =====================================================
with tab1:

    st.subheader("Top Opportunity Today")

    for item in signals[:5]:

        if item["signal"] in ["BUY","STRONG BUY"]:

            css = "buy"

        elif item["signal"] == "WAIT":

            css = "wait"

        else:

            css = "sell"

        st.markdown(
            f"""
            <div class="{css}">
            <h3>{item['symbol']}</h3>
            <h2>{item['signal']}</h2>

            Score : {item['score']}<br>
            RSI : {item['rsi']}<br><br>

            Entry :
            {item['entry_low']:.6f}
            -
            {item['entry_high']:.6f}

            <br><br>

            TP :
            {item['tp']:.6f}

            <br>

            SL :
            {item['sl']:.6f}

            <br><br>

            {' | '.join(item['reason'])}

            </div>

            <br>
            """,
            unsafe_allow_html=True
        )

# =====================================================
# SCANNER
# =====================================================
with tab2:

    scanner = []

    for item in signals:

        scanner.append({

            "Symbol": item["symbol"],

            "Signal": item["signal"],

            "Score": item["score"],

            "RSI": item["rsi"],

            "Price": round(
                item["price"],
                6
            )
        })

    st.dataframe(
        pd.DataFrame(scanner),
        use_container_width=True
    )

# =====================================================
# CHART
# =====================================================
with tab3:

    selected = st.selectbox(

        "Select Coin",

        [x["symbol"] for x in signals]
    )

    df = get_klines(
        selected,
        "4h",
        300
    )

    df["EMA20"] = ema(
        df["Close"],
        20
    )

    df["EMA50"] = ema(
        df["Close"],
        50
    )

    support = (
        df["Low"]
        .tail(20)
        .min()
    )

    resistance = (
        df["High"]
        .tail(20)
        .max()
    )

    fig = make_subplots(

        rows=2,
        cols=1,

        shared_xaxes=True,

        vertical_spacing=0.03,

        row_heights=[0.8,0.2]
    )

    # =================================
    # CANDLE
    # =================================
    fig.add_trace(

        go.Candlestick(

            x=df["Time"],

            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],

            increasing_line_color="#00ff88",
            decreasing_line_color="#ff3b5c",

            name="Candle"
        ),

        row=1,
        col=1
    )

    # =================================
    # EMA20
    # =================================
    fig.add_trace(

        go.Scatter(

            x=df["Time"],

            y=df["EMA20"],

            name="EMA20",

            line=dict(
                color="cyan",
                width=2
            )
        ),

        row=1,
        col=1
    )

    # =================================
    # EMA50
    # =================================
    fig.add_trace(

        go.Scatter(

            x=df["Time"],

            y=df["EMA50"],

            name="EMA50",

            line=dict(
                color="orange",
                width=2
            )
        ),

        row=1,
        col=1
    )

    # =================================
    # SUPPORT
    # =================================
    fig.add_hline(

        y=support,

        line_dash="dash",

        line_color="green"
    )

    # =================================
    # RESISTANCE
    # =================================
    fig.add_hline(

        y=resistance,

        line_dash="dash",

        line_color="red"
    )

    # =================================
    # SUPPORT ZONE
    # =================================
    fig.add_hrect(

        y0=support,
        y1=support*1.01,

        fillcolor="green",

        opacity=0.10,

        line_width=0
    )

    # =================================
    # RESISTANCE ZONE
    # =================================
    fig.add_hrect(

        y0=resistance*0.99,
        y1=resistance,

        fillcolor="red",

        opacity=0.10,

        line_width=0
    )

    # =================================
    # VOLUME
    # =================================
    colors = [

        "#00ff88"

        if c >= o

        else "#ff3b5c"

        for c,o in zip(

            df["Close"],

            df["Open"]
        )
    ]

    fig.add_trace(

        go.Bar(

            x=df["Time"],

            y=df["Volume"],

            marker_color=colors,

            opacity=0.35,

            name="Volume"
        ),

        row=2,
        col=1
    )

    fig.update_layout(

        template="plotly_dark",

        paper_bgcolor="#050816",

        plot_bgcolor="#050816",

        height=850,

        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

st.caption(
    "🚀 AI Scanner Powered by Binance Spot"
)
