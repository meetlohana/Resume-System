/* ══════════════════════════════════════════════
   AI Resume Screening System — script.js
   ══════════════════════════════════════════════ */

const API_BASE = (() => {
    const defaultUrl = "http://127.0.0.1:5000";
    if (window.location.protocol === "file:") return defaultUrl;
    if (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost") {
        return `${window.location.protocol}//${window.location.hostname}:5000`;
    }
    return defaultUrl;
})();

/* ══════════════════
   SPLASH SCREEN
   ══════════════════ */
window.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
        document.getElementById("splash").style.display = "none";
        document.getElementById("app").style.display = "flex";
    }, 2500);
});

/* ══════════════════
   DRAG & DROP
   ══════════════════ */
const dropZone   = document.getElementById("dropZone");
const fileInput  = document.getElementById("resumeFiles");
const fileList   = document.getElementById("fileList");

dropZone.addEventListener("dragover", e => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const dataTransfer = new DataTransfer();
    Array.from(e.dataTransfer.files).forEach(file => dataTransfer.items.add(file));
    fileInput.files = dataTransfer.files;
    renderFileList();
});
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", renderFileList);

function renderFileList() {
    const files = [...fileInput.files];
    fileList.innerHTML = "";
    if (!files.length) return;
    files.forEach(f => {
        const item = document.createElement("div");
        item.className = "file-item";
        item.innerHTML = `<span>📄 ${f.name}</span><small>${(f.size/1024).toFixed(1)} KB</small>`;
        fileList.appendChild(item);
    });
    const ok = document.createElement("p");
    ok.className = "file-success";
    ok.textContent = `✅ ${files.length} resume(s) ready`;
    fileList.appendChild(ok);
}

/* ══════════════════
   ANALYZE RESUMES
   ══════════════════ */
async function analyzeResumes() {
    const files = fileInput.files;
    const jd    = document.getElementById("jobDescription").value.trim();

    hideResults();
    clearError();

    if (!files.length) { showError("⚠️ Please upload at least one PDF resume."); return; }
    if (!jd)           { showError("⚠️ Please enter a job description."); return; }

    const btn = document.getElementById("analyzeBtn");
    btn.disabled = true;
    showSpinner(true);

    try {
        const formData = new FormData();
        [...files].forEach(f => formData.append("resumes", f));
        formData.append("job_description", jd);

        const response = await fetch(`${API_BASE}/analyze`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const text = await response.text();
            let message = "Server error";
            try {
                const json = JSON.parse(text);
                message = json.error || JSON.stringify(json);
            } catch {
                message = text || message;
            }
            throw new Error(message);
        }

        const data = await response.json();
        renderResults(data);

    } catch (err) {
        const fallback = /Failed to fetch|NetworkError/.test(err.message)
            ? "Could not reach the backend server. Make sure Flask is running at http://127.0.0.1:5000"
            : err.message;
        showError("❌ " + fallback);
    } finally {
        btn.disabled = false;
        showSpinner(false);
    }
}

/* ══════════════════
   RENDER RESULTS
   ══════════════════ */
function renderResults(data) {
    const { total, top_score, avg_score, results, keywords } = data;

    // ── Metrics ──
    document.getElementById("metricsRow").innerHTML = `
        <div class="metric-box">
            <div class="value">${total}</div>
            <div class="label">Resumes Analyzed</div>
        </div>
        <div class="metric-box">
            <div class="value">${top_score}%</div>
            <div class="label">Top ATS Score</div>
        </div>
        <div class="metric-box">
            <div class="value">${avg_score}%</div>
            <div class="label">Average Score</div>
        </div>
    `;

    // ── Table ──
    const tbody = document.getElementById("resultsBody");
    tbody.innerHTML = "";
    results.forEach((row, i) => {
        const cls = row.score >= 70 ? "score-high" : row.score >= 40 ? "score-medium" : "score-low";
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${i + 1}</td>
            <td>${escHtml(row.name)}</td>
            <td class="${cls}">${row.score}%</td>
        `;
        tbody.appendChild(tr);
    });

    // ── Keywords ──
    const kwSection = document.getElementById("keywordsSection");
    kwSection.innerHTML = "";
    keywords.forEach((item, idx) => {
        const card = document.createElement("div");
        card.className = "keyword-card";
        const scoreClass = item.score >= 70 ? "score-high" : item.score >= 40 ? "score-medium" : "score-low";
        const pills = item.keywords.length
            ? item.keywords.map(kw => `<span class="keyword-pill">${escHtml(kw)}</span>`).join("")
            : `<p class="no-keywords">No significant keyword overlap detected.</p>`;

        card.innerHTML = `
            <div class="keyword-header${idx === 0 ? ' open' : ''}" onclick="toggleKeyword(this)">
                <span class="fname">📄 ${escHtml(item.name)} — <span class="${scoreClass}">${item.score}%</span></span>
                <span class="chevron">▾</span>
            </div>
            <div class="keyword-body${idx === 0 ? ' visible' : ''}">
                ${pills}
            </div>
        `;
        kwSection.appendChild(card);
    });

    document.getElementById("results").style.display = "block";
}

function toggleKeyword(header) {
    header.classList.toggle("open");
    header.nextElementSibling.classList.toggle("visible");
}

/* ══════════════════
   DOWNLOAD PDF
   ══════════════════ */
async function downloadPDF() {
    const btn = document.getElementById("downloadBtn");
    btn.disabled = true;
    btn.textContent = "Generating PDF…";

    try {
        const response = await fetch(`${API_BASE}/download_pdf`, { method: "GET" });
        if (!response.ok) {
            const text = await response.text();
            let message = "Failed to generate PDF";
            try {
                const json = JSON.parse(text);
                message = json.error || JSON.stringify(json);
            } catch {
                message = text || message;
            }
            throw new Error(message);
        }
        const blob = await response.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement("a");
        a.href = url;
        a.download = "resume_screening_results.pdf";
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        showError("❌ " + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = "⬇️ Download Results as PDF";
    }
}

/* ══════════════════
   HELPERS
   ══════════════════ */
function showSpinner(on) {
    document.getElementById("loadingSpinner").style.display = on ? "block" : "none";
}
function showError(msg) {
    const el = document.getElementById("errorBanner");
    el.textContent = msg;
    el.style.display = "block";
}
function clearError() {
    document.getElementById("errorBanner").style.display = "none";
}
function hideResults() {
    document.getElementById("results").style.display = "none";
}
function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
