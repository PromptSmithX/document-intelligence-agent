import os

import requests
import streamlit as st


def get_backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


st.set_page_config(
    page_title="Document Intelligence Agent",
    layout="centered",
)

st.title("Document Intelligence Agent")
st.write(
    "Upload PDF documents, index their content, and ask questions grounded in "
    "the uploaded document."
)

backend_url = get_backend_url()
st.caption(f"Backend: {backend_url}")

try:
    response = requests.get(f"{backend_url}/health", timeout=5)
    response.raise_for_status()
    health = response.json()

    if health.get("status") == "ok":
        st.success("Backend health: ok")
    else:
        st.warning(f"Backend responded, but health status is unexpected: {health}")
except requests.exceptions.RequestException:
    st.error(f"Backend is not running or not reachable at {backend_url}.")
except ValueError:
    st.error("Backend health response is not valid JSON.")
