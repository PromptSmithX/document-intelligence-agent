# 📄 Document Intelligence Agent

> An end-to-end **RAG-based Document Intelligence system** that allows users to upload PDF documents, ask natural-language questions, and receive **source-grounded answers with page-level citations**.

This project is built as an AI Engineering portfolio project, focusing on production-style architecture rather than a simple notebook demo.

---

## 🚀 Demo

> Replace these placeholders with your own screenshots / demo video.

- 🎥 Demo video: `Add your demo video link here`
- 🖼️ Screenshots: `docs/screenshots/`
- 📄 Sample document: `sample_data/sample_contract.pdf`

### Example Flow

1. Upload a PDF document.
2. The system extracts page-level text.
3. Text is split into overlapping chunks.
4. Chunks are embedded using `BAAI/bge-m3`.
5. Vectors are stored in Qdrant.
6. User asks a question.
7. Relevant chunks are retrieved from Qdrant.
8. LLM generates an answer using only retrieved context.
9. The answer is returned with source citations.

---

## ✨ Key Features

- ✅ PDF upload and document indexing
- ✅ Page-level text extraction
- ✅ Chunking with overlap for better context preservation
- ✅ Open-source multilingual embeddings using `BAAI/bge-m3`
- ✅ Qdrant vector database for semantic search
- ✅ Document-level filtering using `document_id`
- ✅ RAG-based question answering
- ✅ Source-grounded answers with citations
- ✅ No-answer handling to reduce hallucination
- ✅ FastAPI backend
- ✅ Streamlit frontend
- ✅ Docker Compose setup for reproducible local deployment

---

## 🧠 Why This Project?

Most beginner AI projects stop at a notebook or a simple chatbot. This project focuses on building a real AI application pipeline:

```text
Document Upload
    ↓
PDF Parsing
    ↓
Chunking
    ↓
Embedding
    ↓
Vector Database
    ↓
Semantic Retrieval
    ↓
LLM Answer Generation
    ↓
Source Citations
```

The goal is to demonstrate practical AI Engineering skills:

- Building APIs around AI workflows
- Designing a RAG pipeline
- Working with vector databases
- Handling document metadata
- Reducing hallucination with retrieval and citations
- Packaging services with Docker Compose

---

## 🏗️ System Architecture

```text
                    ┌─────────────────────┐
                    │   Streamlit UI       │
                    │ Upload + Chat        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   FastAPI Backend    │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐      ┌────────────────┐      ┌────────────────┐
│ PDF Parser    │      │ Chunking       │      │ Embedding      │
│ PyMuPDF       │      │ Overlap chunks │      │ BAAI/bge-m3    │
└───────┬───────┘      └───────┬────────┘      └───────┬────────┘
        │                      │                       │
        └──────────────────────┼───────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Qdrant Vector DB   │
                    │ Semantic Search      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   RAG Pipeline       │
                    │ Retrieval + Prompt   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   LLM API            │
                    │ Answer Generation    │
                    └─────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | FastAPI | REST API for upload, search, and chat |
| Frontend | Streamlit | Simple UI for document upload and Q&A |
| PDF Parsing | PyMuPDF | Extract text from PDF page by page |
| Embedding Model | BAAI/bge-m3 | Multilingual text embeddings for retrieval |
| Vector Database | Qdrant | Store and search document chunk vectors |
| LLM | Gemini API | Generate final answers from retrieved context |
| Containerization | Docker Compose | Run backend, frontend, and Qdrant together |
| Language | Python | Main programming language |

---

## 🔍 RAG Pipeline

### 1. Document Ingestion

When a PDF is uploaded, the backend saves it and extracts text page by page.

```text
PDF → page-level text
```

Each page keeps its page number, which is later used for citations.

### 2. Chunking

The extracted text is split into overlapping chunks.

```text
chunk_size = 1000 characters
chunk_overlap = 200 characters
```

Each chunk contains metadata:

```json
{
  "chunk_id": "doc_xxx_chunk_0001",
  "document_id": "doc_xxx",
  "page": 4,
  "chunk_index": 1,
  "content": "..."
}
```

### 3. Embedding

Each chunk is converted into a vector using:

```text
BAAI/bge-m3
```

The embedding dimension is:

```text
1024
```

### 4. Vector Storage

Vectors and metadata are stored in Qdrant.

Payload example:

```json
{
  "document_id": "doc_xxx",
  "chunk_id": "doc_xxx_chunk_0001",
  "page": 4,
  "chunk_index": 1,
  "content": "..."
}
```

### 5. Retrieval

When a user asks a question, the system embeds the question, searches Qdrant for top-k similar chunks, filters by `document_id`, and sends the retrieved chunks to the RAG pipeline.

### 6. Answer Generation

The LLM receives only retrieved chunks as context.

Prompt rule:

```text
Use only the provided context.
If the answer cannot be found in the context, say:
"I could not find this information in the document."
```

Citations are generated from retrieved chunks, not invented by the LLM.

---

## 📡 API Endpoints

### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

### Upload Document

```http
POST /documents/upload
```

Response:

```json
{
  "document_id": "doc_xxx",
  "file_name": "contract.pdf",
  "pages": 12,
  "chunks": 48,
  "status": "indexed"
}
```

### List Documents

```http
GET /documents
```

Response:

```json
[
  {
    "document_id": "doc_xxx",
    "file_name": "contract.pdf",
    "pages": 12,
    "chunks": 48,
    "created_at": "2026-06-14T10:00:00"
  }
]
```

### Semantic Search

```http
POST /documents/search
```

Request:

```json
{
  "document_id": "doc_xxx",
  "query": "What are the payment terms?",
  "top_k": 5
}
```

Response:

```json
{
  "results": [
    {
      "chunk_id": "doc_xxx_chunk_0007",
      "document_id": "doc_xxx",
      "page": 4,
      "chunk_index": 7,
      "score": 0.86,
      "content": "Payment shall be made within 30 days..."
    }
  ]
}
```

### Chat With Document

```http
POST /chat/query
```

Request:

```json
{
  "document_id": "doc_xxx",
  "question": "What are the payment terms?",
  "top_k": 5
}
```