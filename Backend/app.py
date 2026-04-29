"""
AI Resume Screening System — Backend (Flask)
============================================
REST API that accepts PDF resumes + a job description,
scores them with TF-IDF / cosine similarity, and returns
ranked results with matched keywords.

Endpoints
---------
POST /analyze          → analyse resumes, return JSON
GET  /download_pdf     → download last-analysis PDF report

Usage
-----
    pip install flask flask-cors pymupdf scikit-learn pandas fpdf2
    python app.py
"""

import io
import re
from collections import Counter
from datetime import datetime

import fitz  # PyMuPDF
import pandas as pd
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from fpdf import FPDF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ─────────────────────────────────────────────
# Flask App Setup
# ─────────────────────────────────────────────

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from the Frontend

# In-memory store for the last analysis result (used for PDF download)
_last_results: pd.DataFrame | None = None


# ─────────────────────────────────────────────
# NLP / Analysis Helpers
# ─────────────────────────────────────────────

def extract_text(pdf_bytes: bytes) -> str:
    """
    Extract clean text from raw PDF bytes using PyMuPDF.

    Args:
        pdf_bytes: Raw bytes of a PDF file.

    Returns:
        Cleaned text string, or empty string on failure.
    """
    text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception:
        return ""

    text = re.sub(r"\s+", " ", text).strip()
    return text


def vectorize(texts: list[str]) -> tuple:
    """
    Convert text documents into TF-IDF vectors.

    Args:
        texts: List where index 0 is the job description,
               remaining elements are resume texts.

    Returns:
        Tuple of (sparse TF-IDF matrix, feature name array).
    """
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        max_features=5000,
    )
    matrix = vectorizer.fit_transform(texts)
    return matrix, vectorizer.get_feature_names_out()


def calculate_similarity(matrix) -> list[float]:
    """
    Cosine similarity between the JD vector (row 0) and resume vectors.

    Args:
        matrix: Sparse TF-IDF matrix (row 0 = JD).

    Returns:
        List of percentage scores (0–100), one per resume.
    """
    jd_vec      = matrix[0:1]
    resume_vecs = matrix[1:]
    sims = cosine_similarity(jd_vec, resume_vecs).flatten()
    return [round(float(s) * 100, 2) for s in sims]


def rank_resumes(names: list[str], scores: list[float]) -> pd.DataFrame:
    """
    Build a ranked DataFrame sorted by ATS score (descending).

    Args:
        names:  Resume file names.
        scores: Corresponding ATS scores.

    Returns:
        Sorted DataFrame with columns: Resume File Name, ATS Score (%).
    """
    df = pd.DataFrame({
        "Resume File Name": names,
        "ATS Score (%)":   scores,
    })
    df = df.sort_values("ATS Score (%)", ascending=False).reset_index(drop=True)
    df.index     += 1          # 1-based rank
    df.index.name = "Rank"
    return df


def get_matched_keywords(resume_text: str, jd_text: str, top_n: int = 15) -> list[str]:
    """
    Return the top overlapping meaningful keywords between a resume and the JD.

    Args:
        resume_text: Cleaned resume text.
        jd_text:     Cleaned job description.
        top_n:       Max keywords to return.

    Returns:
        Sorted list of keyword strings.
    """
    stop = ENGLISH_STOP_WORDS

    def _tokens(text: str) -> list[str]:
        return [
            t for t in re.findall(r"[a-z][a-z0-9+#]+", text.lower())
            if t not in stop and len(t) > 2
        ]

    resume_counts = Counter(_tokens(resume_text))
    jd_counts     = Counter(_tokens(jd_text))

    common = {w: jd_counts[w] for w in resume_counts if w in jd_counts}
    return sorted(common, key=common.get, reverse=True)[:top_n]


def generate_pdf(df: pd.DataFrame) -> bytes:
    """
    Generate a professional PDF report from the ranked results DataFrame.

    Args:
        df: DataFrame with columns Resume File Name, ATS Score (%).

    Returns:
        Raw PDF bytes.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 14, "AI Resume Screening Report", ln=True, align="C")
    pdf.ln(2)

    # Date
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8,
             f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
             ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    # Summary
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Total Resumes Analyzed: {len(df)}", ln=True)
    pdf.cell(0, 8, f"Top ATS Score: {df['ATS Score (%)'].max()}%", ln=True)
    pdf.cell(0, 8, f"Average ATS Score: {round(df['ATS Score (%)'].mean(), 1)}%", ln=True)
    pdf.ln(8)

    # Horizontal rule
    pdf.set_draw_color(108, 99, 255)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Table header
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(108, 99, 255)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(25,  10, "Rank",             border=1, align="C", fill=True)
    pdf.cell(120, 10, "Resume File Name", border=1, align="C", fill=True)
    pdf.cell(45,  10, "ATS Score (%)",    border=1, align="C", fill=True)
    pdf.ln()

    # Table rows
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(0, 0, 0)
    for rank, row in df.iterrows():
        fill_color = (240, 240, 255) if rank % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_color)
        pdf.cell(25,  10, str(rank),                       border=1, align="C", fill=True)
        pdf.cell(120, 10, str(row["Resume File Name"]),    border=1, align="L", fill=True)
        pdf.cell(45,  10, f"{row['ATS Score (%)']}%",     border=1, align="C", fill=True)
        pdf.ln()

    pdf.ln(10)

    # Footer
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 8,
             "Report generated by AI Resume Screening System using TF-IDF & Cosine Similarity.",
             ln=True, align="C")

    return bytes(pdf.output())


# ─────────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    POST /analyze
    Form data:
        resumes          — one or more PDF files
        job_description  — plain-text job description

    Returns JSON:
    {
        "total":     int,
        "top_score": float,
        "avg_score": float,
        "results":   [{"name": str, "score": float}, ...],
        "keywords":  [{"name": str, "score": float, "keywords": [str]}, ...]
    }
    """
    global _last_results

    pdf_files      = request.files.getlist("resumes")
    job_description = request.form.get("job_description", "").strip()

    # ── Validation ──
    if not pdf_files:
        return jsonify({"error": "No resume files uploaded."}), 400
    if not job_description:
        return jsonify({"error": "Job description is required."}), 400

    # ── Extract text from each PDF ──
    file_names:   list[str] = []
    resume_texts: list[str] = []

    for f in pdf_files:
        text = extract_text(f.read())
        if text:
            file_names.append(f.filename)
            resume_texts.append(text)

    if not resume_texts:
        return jsonify({"error": "Could not extract text from any uploaded PDF."}), 422

    # ── TF-IDF + cosine similarity ──
    all_texts            = [job_description] + resume_texts
    tfidf_matrix, _      = vectorize(all_texts)
    scores               = calculate_similarity(tfidf_matrix)
    results_df           = rank_resumes(file_names, scores)

    # Cache for PDF download
    _last_results = results_df.copy()

    # ── Build keyword breakdown (preserving original order) ──
    score_map = dict(zip(file_names, scores))
    keywords_out = []
    for name, text, score in zip(file_names, resume_texts, scores):
        kws = get_matched_keywords(text, job_description, top_n=15)
        keywords_out.append({"name": name, "score": score, "keywords": kws})

    # Sort keywords list by score desc to match ranked order
    keywords_out.sort(key=lambda x: x["score"], reverse=True)

    avg_score = round(float(results_df["ATS Score (%)"].mean()), 1)
    top_score = float(results_df["ATS Score (%)"].max())

    return jsonify({
        "total":     len(results_df),
        "top_score": top_score,
        "avg_score": avg_score,
        "results":   [
            {"name": row["Resume File Name"], "score": row["ATS Score (%)"]}
            for _, row in results_df.reset_index().iterrows()
        ],
        "keywords": keywords_out,
    })


@app.route("/download_pdf", methods=["GET"])
def download_pdf():
    """
    GET /download_pdf
    Generates and streams a PDF of the last analysis results.
    """
    global _last_results
    if _last_results is None:
        return jsonify({"error": "No analysis results available. Run /analyze first."}), 400

    pdf_bytes = generate_pdf(_last_results)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="resume_screening_results.pdf",
    )


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
