import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Binance Test",
    layout="wide"
)

st.title("🚀 Binance API Test")

try:

    url = "https://api.binance.com/api/v3/ticker/price"

    data = requests.get(
        url,
        timeout=10
    ).json()

    df = pd.DataFrame(data)

    st.success("Berhasil ambil data Binance")

    st.write(df.head(20))

except Exception as e:

    st.error(f"Error: {e}")
