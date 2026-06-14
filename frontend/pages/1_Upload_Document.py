import os

import requests
import streamlit as st


def get_backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def format_backend_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"Request failed with status {response.status_code}"

    detail = payload.get("detail")
    if detail:
        return str(detail)

    return response.text or f"Request failed with status {response.status_code}"


st.set_page_config(
    page_title="Upload Document",
    layout="centered",
)

st.title("Upload Document")

backend_url = get_backend_url()
uploaded_file = st.file_uploader("PDF file", type=["pdf"])

if st.button("Upload", type="primary", disabled=uploaded_file is None):
    if uploaded_file is None:
        st.warning("Select a PDF file first.")
    else:
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "application/pdf",
            )
        }

        with st.spinner("Uploading and indexing document..."):
            try:
                response = requests.post(
                    f"{backend_url}/documents/upload",
                    files=files,
                    timeout=300,
                )
            except requests.exceptions.RequestException:
                st.error(f"Backend is not running or not reachable at {backend_url}.")
            else:
                if response.ok:
                    try:
                        payload = response.json()
                    except ValueError:
                        st.error("Backend upload response is not valid JSON.")
                        st.stop()

                    st.session_state["last_uploaded_document_id"] = payload.get("document_id")
                    st.session_state["last_uploaded_document"] = payload

                    st.success("Document uploaded successfully.")
                    st.write(f"Document ID: `{payload.get('document_id', '')}`")
                    st.write(f"File name: `{payload.get('file_name', '')}`")
                    st.write(f"Pages: `{payload.get('pages', 0)}`")
                    st.write(f"Chunks: `{payload.get('chunks', 0)}`")
                    st.write(f"Status: `{payload.get('status', '')}`")
                else:
                    st.error(format_backend_error(response))
