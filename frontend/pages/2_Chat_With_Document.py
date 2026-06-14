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


def document_label(document: dict) -> str:
    file_name = document.get("file_name", "Untitled document")
    document_id = document.get("document_id", "")
    return f"{file_name} | {document_id}"


st.set_page_config(
    page_title="Chat With Document",
    layout="centered",
)

st.title("Chat With Document")

backend_url = get_backend_url()

try:
    response = requests.get(f"{backend_url}/documents", timeout=15)
except requests.exceptions.RequestException:
    st.error(f"Backend is not running or not reachable at {backend_url}.")
    st.stop()

if not response.ok:
    st.error(format_backend_error(response))
    st.stop()

try:
    documents = response.json()
except ValueError:
    st.error("Backend /documents response is not valid JSON.")
    st.stop()

if not isinstance(documents, list):
    st.error(
        "Backend /documents response does not match the expected contract. "
        "Expected a list of documents."
    )
    st.stop()

if not documents:
    st.info("No documents found. Upload a PDF document first.")
    st.stop()

last_uploaded_document_id = st.session_state.get("last_uploaded_document_id")
default_index = 0
if last_uploaded_document_id:
    for index, document in enumerate(documents):
        if document.get("document_id") == last_uploaded_document_id:
            default_index = index
            break

selected_document = st.selectbox(
    "Document",
    documents,
    index=default_index,
    format_func=document_label,
)

question = st.text_area("Question", placeholder="What are the payment terms?")
top_k = st.slider("top_k", min_value=1, max_value=10, value=5)

if st.button("Ask", type="primary"):
    cleaned_question = question.strip()
    if not cleaned_question:
        st.warning("Enter a question first.")
        st.stop()

    payload = {
        "document_id": selected_document.get("document_id"),
        "question": cleaned_question,
        "top_k": top_k,
    }

    with st.spinner("Retrieving context and generating answer..."):
        try:
            chat_response = requests.post(
                f"{backend_url}/chat/query",
                json=payload,
                timeout=300,
            )
        except requests.exceptions.RequestException:
            st.error(f"Backend is not running or not reachable at {backend_url}.")
            st.stop()

    if not chat_response.ok:
        st.error(format_backend_error(chat_response))
        st.stop()

    try:
        result = chat_response.json()
    except ValueError:
        st.error("Backend chat response is not valid JSON.")
        st.stop()

    st.subheader("Answer")
    st.write(result.get("answer", ""))

    latency_seconds = result.get("latency_seconds")
    if latency_seconds is not None:
        st.caption(f"Latency: {latency_seconds} seconds")

    citations = result.get("citations", [])
    if citations:
        st.subheader("Citations")
        for index, citation in enumerate(citations, start=1):
            title = (
                f"Citation {index} | Page {citation.get('page')} | "
                f"Score {citation.get('score')}"
            )
            with st.expander(title):
                st.write(f"Chunk ID: `{citation.get('chunk_id', '')}`")
                st.write(citation.get("text", ""))
    else:
        st.info("No citations returned.")
