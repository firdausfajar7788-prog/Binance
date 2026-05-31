import requests
import pandas as pd
import numpy as np

BASE_URL = "https://fapi.binance.com"


# =====================================================
# TOP 20 FUTURES
# =====================================================
def get_top20_futures():

    url = f"{BASE_URL}/fapi/v1/ticker/24hr"

    try:

        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        data = response.json()

        print("BINANCE RESPONSE:")
        print(data)

        # Jika Binance balas error dict
        if not isinstance(data, list):

            return pd.DataFrame()

        df = pd.DataFrame(data)

        if df.empty:
            return pd.DataFrame()

        if "symbol" not in df.columns:
            return pd.DataFrame()

        df = df[
            df["symbol"].str.endswith("USDT")
        ]

        blacklist = [
            "USDCUSDT",
            "BUSDUSDT",
            "TUSDUSDT"
        ]

        df = df[
            ~df["symbol"].isin(blacklist)
        ]

        df["quoteVolume"] = pd.to_numeric(
            df["quoteVolume"],
            errors="coerce"
        )

        df = df.sort_values(
            "quoteVolume",
            ascending=False
        )

        return df.head(20)

    except Exception as e:

        print("TOP20 ERROR:")
        print(e)

        return pd.DataFrame()


# =====================================================
# GET KLINES
# =====================================================
def get_klines(
    symbol,
    interval="4h",
    limit=300
):

    try:

        url = f"{BASE_URL}/fapi/v1/klines"

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        response = requests.get(
            url,
            params=params,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        data = response.json()

        if not isinstance(data, list):
            return pd.DataFrame()

        if len(data) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(
            data,
            columns=[
                "OpenTime",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "CloseTime",
                "QuoteAssetVolume",
                "Trades",
                "TakerBase",
                "TakerQuote",
                "Ignore"
            ]
        )

        df["Time"] = pd.to_datetime(
            df["OpenTime"],
            unit="ms"
        )

        numeric_cols = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        for col in numeric_cols:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        df = df.dropna()

        return df

    except Exception as e:

        print("KLINE ERROR:")
        print(e)

        return pd.DataFrame()


# =====================================================
# EMA
# =====================================================
def ema(series, period):

    return (
        series
        .ewm(
            span=period,
            adjust=False
        )
        .mean()
    )


# =====================================================
# RSI
# =====================================================
def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# =====================================================
# AI SCORE
# =====================================================
def ai_score(df):

    try:

        if df.empty:
            return None

        if len(df) < 60:
            return None

        df = df.copy()

        df["EMA20"] = ema(
            df["Close"],
            20
        )

        df["EMA50"] = ema(
            df["Close"],
            50
        )

        df["RSI"] = rsi(
            df["Close"]
        )

        df = df.dropna()

        if len(df) < 60:
            return None

        price = float(
            df["Close"].iloc[-1]
        )

        ema20 = float(
            df["EMA20"].iloc[-1]
        )

        ema50 = float(
            df["EMA50"].iloc[-1]
        )

        rsi_now = float(
            df["RSI"].iloc[-1]
        )

        volume = float(
            df["Volume"].iloc[-1]
        )

        avg_volume = float(
            df["Volume"]
            .tail(50)
            .mean()
        )

        resistance = float(
            df["High"]
            .tail(20)
            .max()
        )

        support = float(
            df["Low"]
            .tail(20)
            .min()
        )

        score = 0

        reasons = []

        if ema20 > ema50:

            score += 25

            reasons.append(
                "EMA Bullish"
            )

        if price > ema20:

            score += 20

            reasons.append(
                "Price > EMA20"
            )

        if 55 <= rsi_now <= 75:

            score += 20

            reasons.append(
                "Healthy RSI"
            )

        if volume > avg_volume * 1.5:

            score += 20

            reasons.append(
                "Volume Spike"
            )

        if price >= resistance * 0.995:

            score += 15

            reasons.append(
                "Near Breakout"
            )

        if score >= 85:

            signal = "STRONG BUY"

        elif score >= 70:

            signal = "BUY"

        elif score >= 50:

            signal = "WAIT"

        else:

            signal = "AVOID"

        return {

            "score": score,

            "signal": signal,

            "price": price,

            "support": support,

            "resistance": resistance,

            "entry_low": support * 1.01,

            "entry_high": ema20,

            "tp": resistance * 1.05,

            "sl": support * 0.97,

            "rsi": round(
                rsi_now,
                2
            ),

            "reason": reasons
        }

    except Exception as e:

        print("AI SCORE ERROR:")
        print(e)

        return None
