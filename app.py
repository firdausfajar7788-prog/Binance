import streamlit as st
import requests

st.title("Binance Debug")

url = "https://api.binance.com/api/v3/ticker/price"

response = requests.get(
    url,
    timeout=10
)

st.write("STATUS")
st.write(response.status_code)

st.write("TEXT")
st.code(response.text[:1000])
