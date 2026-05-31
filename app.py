import streamlit as st
import requests

st.title("Internet Test")

r = requests.get(
    "https://api.coingecko.com/api/v3/ping"
)

st.write(r.status_code)

st.json(r.json())
