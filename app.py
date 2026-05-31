import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

from binance_core import (
    get_top20_futures,
    get_klines,
    ai_score
)

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="🚀 Binance AI Scanner",
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

.main {
    background:#050816;
}

.stApp{
    background:#050816;
}

.buy-card{
    background:#0f172a;
    border-left:6px solid #00ff88;
    padding:15px;
    border-radius:15px;
    margin-bottom:10px;
}

.wait-card{
    background:#0f172a;
    border-left:6px solid orange;
    padding:15px;
    border-radius:15px;
    margin-bottom:10px;
}

.sell-card{
    background:#0f172a;
    border-left:6px solid red;
    padding:15px;
    border-radius:15px;
    margin-bottom:10px;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# HEADER
# =====================================================
st.title("🚀 Binance Futures AI Scanner")
st.caption("Top 20 Futures Volume • 4H AI Signal")

# =====================================================
# LOAD MARKET
# =====================================================
with st.spinner("Scanning Binance Futures..."):

    market = get_top20_futures()
    if market.empty:

    st.error(
        "❌ Gagal mengambil data Binance Futures"
    )

    st.stop()

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

                "symbol":symbol,

                **result
            })

    except:
        pass

# =====================================================
# SORT
# =====================================================
signals = sorted(
    signals,
    key=lambda x:x["score"],
    reverse=True
)

# =====================================================
# MARKET MOOD
# =====================================================
avg_score = 0

if len(signals) > 0:

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

st.success(
    f"{mood} | Avg Score : {avg_score:.1f}"
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
# TAB 1
# =====================================================
with tab1:

    st.subheader("Top Opportunities")

    for item in signals[:5]:

        if item["signal"] == "STRONG BUY":

            card = "buy-card"

        elif item["signal"] == "BUY":

            card = "buy-card"

        elif item["signal"] == "WAIT":

            card = "wait-card"

        else:

            card = "sell-card"

        st.markdown(

            f"""
            <div class="{card}">

            <h3>{item['symbol']}</h3>

            <h2>{item['signal']}</h2>

            <b>Score :</b> {item['score']}

            <br>

            <b>RSI :</b> {item['rsi']}

            <br>

            <b>Entry :</b>

            {item['entry_low']:.4f}
            -
            {item['entry_high']:.4f}

            <br>

            <b>TP :</b>
            {item['tp']:.4f}

            <br>

            <b>SL :</b>
            {item['sl']:.4f}

            <br><br>

            {' | '.join(item['reason'])}

            </div>
            """,

            unsafe_allow_html=True
        )

# =====================================================
# TAB 2
# =====================================================
with tab2:

    st.subheader("Scanner")

    table = []

    for item in signals:

        table.append({

            "Symbol":item["symbol"],

            "Score":item["score"],

            "Signal":item["signal"],

            "RSI":item["rsi"],

            "Price":round(
                item["price"],
                4
            )
        })

    df_table = pd.DataFrame(table)

    st.dataframe(
        df_table,
        use_container_width=True,
        height=600
    )

# =====================================================
# TAB 3
# =====================================================
with tab3:

    symbols = [
        x["symbol"]
        for x in signals[:20]
    ]

    selected = st.selectbox(
        "Select Symbol",
        symbols
    )

    df = get_klines(
        selected,
        "4h",
        300
    )

    df["EMA20"] = (
        df["Close"]
        .ewm(span=20)
        .mean()
    )

    df["EMA50"] = (
        df["Close"]
        .ewm(span=50)
        .mean()
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

    # ==================================
    # CANDLE
    # ==================================
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

    # ==================================
    # EMA20
    # ==================================
    fig.add_trace(

        go.Scatter(

            x=df["Time"],

            y=df["EMA20"],

            line=dict(
                color="cyan",
                width=2
            ),

            name="EMA20"
        ),

        row=1,
        col=1
    )

    # ==================================
    # EMA50
    # ==================================
    fig.add_trace(

        go.Scatter(

            x=df["Time"],

            y=df["EMA50"],

            line=dict(
                color="orange",
                width=2
            ),

            name="EMA50"
        ),

        row=1,
        col=1
    )

    # ==================================
    # SUPPORT
    # ==================================
    fig.add_hline(

        y=support,

        line_color="green",

        line_dash="dash"
    )

    # ==================================
    # RESISTANCE
    # ==================================
    fig.add_hline(

        y=resistance,

        line_color="red",

        line_dash="dash"
    )

    # ==================================
    # ZONE
    # ==================================
    fig.add_hrect(

        y0=support,
        y1=support*1.01,

        fillcolor="green",

        opacity=0.10,

        line_width=0
    )

    fig.add_hrect(

        y0=resistance*0.99,
        y1=resistance,

        fillcolor="red",

        opacity=0.10,

        line_width=0
    )

    # ==================================
    # VOLUME
    # ==================================
    colors = [

        "#00ff88"

        if c>=o

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

# =====================================================
# FOOTER
# =====================================================
st.caption(
    "🚀 Binance Futures AI Scanner"
)
