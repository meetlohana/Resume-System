# AI Resume Screening System

A full-stack web app that scores and ranks PDF resumes against a job description using **TF-IDF** and **Cosine Similarity** — no Streamlit, pure HTML/CSS/JS + Flask.

---

## 📁 Project Structure

```
project/
├── Frontend/
│   ├── index.html   ← Main UI (splash, upload form, results table, keywords)
│   ├── style.css    ← All styling (dark glassmorphism theme)
│   └── script.js    ← All interactivity (fetch API, drag-drop, render)
│
└── Backend/
    ├── app.py           ← Flask REST API (analyze + PDF download)
    └── requirements.txt ← Python dependencies
```

---

## 🚀 Setup & Run

### 1. Backend

```bash
cd Backend
pip install -r requirements.txt
python app.py
# Runs at http://127.0.0.1:5000
```

### 2. Frontend

Open `Frontend/index.html` directly in your browser, **or** serve it with any static server:

```bash
cd Frontend
python -m http.server 8080
# Open http://localhost:8080
```

> ⚠️ Make sure the backend is running before you click **Analyze Resumes**.

---

## 🔌 API Reference

### `POST /analyze`
| Field            | Type          | Description                  |
|------------------|---------------|------------------------------|
| `resumes`        | File(s) — PDF | One or more PDF resume files |
| `job_description`| Text          | Plain-text job description   |

**Response JSON:**
```json
{
  "total": 3,
  "top_score": 72.5,
  "avg_score": 51.2,
  "results": [{"name": "alice.pdf", "score": 72.5}, ...],
  "keywords": [{"name": "alice.pdf", "score": 72.5, "keywords": ["python", "django"]}, ...]
}
```

### `GET /download_pdf`
Returns a PDF report of the last `/analyze` run as a file download.

---

## ⚙️ How It Works

1. **PDF text extraction** — PyMuPDF reads each uploaded resume
2. **TF-IDF vectorisation** — Job description + resumes converted to vectors
3. **Cosine similarity** — Each resume vector compared to the JD vector
4. **Ranking** — Resumes sorted by score (highest first)
5. **Keyword overlap** — Top shared meaningful tokens highlighted per resume  
