import os
import re
import time

import markdown as md
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")

# Strip CJK characters from displayed text (model sometimes interleaves Chinese)
_CJK_RE = re.compile(r"[\u3400-\u9FFF\uF900-\uFAFF]+")
def clean_text(text):
    return _CJK_RE.sub("", text).strip()


def _sources_html(sources):
    """Return HTML for collapsible sources block."""
    if not sources:
        return ""
    n = len(sources)
    parts = [f'<div class="sources-block"><details class="sources">']
    parts.append(f"<summary>{n} source chunk{'s' if n != 1 else ''}</summary>")
    for i, src in enumerate(sources, 1):
        safe = src.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(
            f'<div class="source-item">'
            f'<span class="src-label">Chunk {i}</span>'
            f'<div class="src-text">{safe}</div>'
            f"</div>"
        )
    parts.append("</details></div>")
    return "".join(parts)


def _render_chat_msg(role, content, sources=None, return_html=False):
    """Render a chat bubble as custom HTML — no st.chat_message()."""
    content_html = md.markdown(
        content, extensions=["fenced_code", "nl2br", "tables"]
    )
    parts = [
        f'<div class="msg msg-{role}">'
        f'<div class="msg-bubble msg-bubble-{role}">{content_html}</div>'
    ]
    if role == "assistant" and sources:
        parts.append(_sources_html(sources))
    parts.append("</div>")
    html = "".join(parts)
    if return_html:
        return html
    st.markdown(html, unsafe_allow_html=True)


st.set_page_config(page_title="RAGnamok", page_icon="🌿", layout="wide")

# ---------------------------------------------------------------------------
# CSS — calm stone palette, Fraunces + DM Sans, custom components
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* ===== 1. Fonts ===== */
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,400,50;9..144,500,50;9..144,600,50&family=DM+Sans:opsz,wght@9..40,400;9..40,500&family=JetBrains+Mono&display=swap');

/* ===== 2. Design Tokens ===== */
:root {
  --bg: #F3F2EE;
  --surface: #FAF9F7;
  --text: #1C1A17;
  --text-secondary: #6B6560;
  --text-tertiary: #96908B;
  --accent: #5B7B6A;
  --accent-soft: #E8EFEA;
  --accent-warm: #B58A6B;
  --border: #E1E0DA;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 2px 6px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.04);
}

/* ===== 3. Base & Layout ===== */
.stApp { background: var(--bg); }
.stApp > header { display: none; }
.stMarkdownContainer { margin: 0 !important; padding: 0 !important; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 8px !important; }
.stVerticalBlock { gap: 0; }
/* Constrain main content width ~900px centered */
.main .block-container {
  max-width: 920px !important;
  margin: 0 auto !important;
  padding-left: 28px !important;
  padding-right: 28px !important;
}

/* ===== 4. Sidebar ===== */
section[data-testid="stSidebar"] {
  background: var(--bg) !important;
  border-right: 1px solid var(--border);
  padding-top: 0 !important;
}
section[data-testid="stSidebar"] .block-container {
  padding: 24px 16px !important;
}

/* ===== 5. Top Bar ===== */
.topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 0 14px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}
.topbar-logo {
  font-family: 'Fraunces', serif;
  font-size: 22px;
  font-weight: 500;
  font-variation-settings: 'SOFT' 50;
  color: var(--text);
  letter-spacing: -0.02em;
  line-height: 1;
}
.topbar-leaf {
  display: inline-block;
  width: 18px;
  height: 18px;
  vertical-align: middle;
  margin-right: 6px;
  opacity: 0.8;
}
.topbar-tagline {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-left: auto;
}

/* ===== 6. Welcome Screen ===== */
.welcome {
  max-width: 480px;
  margin: 80px auto;
  text-align: center;
  padding: 0 20px;
}
.welcome-leaf {
  margin: 0 auto 24px;
  display: block;
}
.welcome h1 {
  font-family: 'Fraunces', serif;
  font-weight: 500;
  font-variation-settings: 'SOFT' 50;
  font-size: 32px;
  line-height: 1.2;
  color: var(--text);
  margin-bottom: 8px;
  letter-spacing: -0.02em;
}
.welcome-tagline {
  font-size: 16px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 24px;
}
.welcome p {
  font-size: 14px;
  color: var(--text-tertiary);
  line-height: 1.6;
  margin-bottom: 32px;
}
.welcome-cards {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}
.welcome-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 22px;
  text-align: center;
  min-width: 120px;
  flex: 0 1 auto;
  cursor: default;
  transition: border-color 0.25s ease, transform 0.2s ease;
}
.welcome-card:hover {
  border-color: var(--accent);
  transform: translateY(-3px);
}
.welcome-card-icon {
  font-size: 22px;
  margin-bottom: 6px;
  display: block;
}
.welcome-card-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.welcome-card-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* ===== 7. Chat Messages (custom HTML — no more st.chat_message) ===== */
.msg {
  margin-bottom: 10px;
}
.msg-user {
  display: flex;
  justify-content: flex-end;
}
.msg-assistant {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.msg-bubble {
  border-radius: 14px;
  padding: 12px 20px;
  max-width: 88%;
  width: fit-content;
  word-wrap: break-word;
  overflow-wrap: break-word;
  line-height: 1.7;
  font-size: 15px;
  border: 1px solid var(--border);
}
.msg-bubble-user {
  background: var(--accent);
  color: #fff;
  border: none;
  border-bottom-right-radius: 4px;
}
.msg-bubble-assistant {
  background: #fff;
  color: var(--text);
  box-shadow: var(--shadow-md);
  border-bottom-left-radius: 4px;
}
/* Bubble typography */
.msg-bubble p { margin: 0 0 8px; }
.msg-bubble p:last-child { margin-bottom: 0; }
.msg-bubble ul,
.msg-bubble ol { margin: 6px 0; padding-left: 22px; }
.msg-bubble li { margin-bottom: 4px; }
.msg-bubble code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  background: var(--accent-soft);
  padding: 1px 5px;
  border-radius: 4px;
}
.msg-bubble pre {
  background: var(--accent-soft);
  border-radius: 8px;
  padding: 12px;
  overflow-x: auto;
  font-size: 13px;
  margin: 8px 0;
}

/* ===== 8. Empty Chat State ===== */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  text-align: center;
  min-height: 360px;
}
.chat-empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
  opacity: 0.7;
}
.chat-empty-title {
  font-family: 'Fraunces', serif;
  font-size: 20px;
  font-weight: 500;
  font-variation-settings: 'SOFT' 50;
  color: var(--text);
  margin-bottom: 6px;
}
.chat-empty-hint {
  font-size: 14px;
  color: var(--text-tertiary);
  margin-bottom: 28px;
  line-height: 1.5;
}
.chat-empty-suggestions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}
.suggestion-chip {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 8px 18px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: default;
  transition: border-color 0.2s, color 0.2s;
}
.suggestion-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* ===== 9. Sources ===== */
.sources-block {
  margin-top: 8px;
  border-top: 1px solid var(--border);
  padding-top: 6px;
}
details.sources {
  margin: 0;
}
details.sources summary {
  font-size: 11px;
  color: var(--text-tertiary);
  cursor: pointer;
  font-weight: 500;
  padding: 4px 0;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 4px;
  user-select: none;
}
details.sources summary::before {
  content: "\\25B8";
  font-size: 10px;
  transition: transform 0.15s ease;
}
details.sources[open] summary::before {
  transform: rotate(90deg);
}
details.sources summary:hover {
  color: var(--text-secondary);
}
.source-item {
  border-left: 2px solid var(--border);
  padding: 5px 0 5px 12px;
  margin: 3px 0 3px 6px;
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
}
.source-item .src-label {
  font-size: 9px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  display: block;
  margin-bottom: 1px;
}
.source-item .src-text {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

/* ===== 10. Loading Pulse ===== */
.pulse-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
}
.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  animation: calmPulse 1.6s ease-in-out infinite;
}
@keyframes calmPulse {
  0%, 100% { opacity: 0.2; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
}
.pulse-text {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* ===== 11. Sidebar Components ===== */
.sidebar-heading {
  font-family: 'Fraunces', serif;
  font-weight: 500;
  font-variation-settings: 'SOFT' 50;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
  padding: 16px 0 6px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 10px;
  line-height: 1.3;
}
.sidebar-heading + .stButton {
  margin-bottom: 8px;
}
.doc-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 6px;
  cursor: default;
  margin-bottom: 1px;
  transition: background 0.12s ease;
}
.doc-row:hover {
  background: var(--accent-soft);
}
.doc-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 1px;
}
.doc-name {
  font-size: 14px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  line-height: 1.35;
}
.doc-meta {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

/* ===== 12. Buttons ===== */
.stButton button {
  border-radius: 8px !important;
  font-size: 13px !important;
  padding: 4px 12px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 500 !important;
  transition: all 0.12s ease !important;
  line-height: 1.4 !important;
  height: auto !important;
}
.stButton button[kind="primary"] {
  background: var(--accent) !important;
  border: 1px solid var(--accent) !important;
  color: #fff !important;
}
.stButton button[kind="primary"]:hover {
  opacity: 0.88 !important;
}
.stButton button[kind="secondary"] {
  background: transparent !important;
  border: 1px solid var(--border) !important;
  color: var(--text-secondary) !important;
}
.stButton button[kind="secondary"]:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}
.stButton button:active {
  transform: scale(0.97) !important;
}

/* ===== 13. Chat Input ===== */
[data-testid="stChatInput"] {
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  background: var(--surface) !important;
  padding: 8px 12px !important;
  margin-top: 16px !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stChatInput"] textarea {
  font-size: 15px !important;
  font-family: 'DM Sans', sans-serif !important;
  color: var(--text) !important;
  background: transparent !important;
  min-height: 24px !important;
}
[data-testid="stChatInput"] textarea::placeholder {
  color: var(--text-tertiary) !important;
}
[data-testid="stChatInput"] button {
  background: var(--accent) !important;
  color: #fff !important;
  border-radius: 8px !important;
  border: none !important;
  padding: 4px 12px !important;
}

/* ===== 14. File Uploader ===== */
[data-testid="stFileUploader"] {
  border: 1px dashed var(--border) !important;
  border-radius: 8px !important;
  padding: 10px !important;
  background: var(--surface) !important;
  font-size: 13px !important;
}
[data-testid="stFileUploader"] small {
  color: var(--text-tertiary) !important;
}

/* ===== 15. Checkbox ===== */
.stCheckbox label {
  font-size: 13px !important;
  color: var(--text-secondary) !important;
  gap: 6px !important;
}
.stCheckbox label p {
  font-size: 13px !important;
}

/* ===== 16. Divider ===== */
.stDivider {
  margin: 12px 0 !important;
  border-color: var(--border) !important;
}

/* ===== 17. Status Widget ===== */
div[data-testid="stStatusWidget"] {
  background: #fff !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  padding: 12px 16px !important;
  box-shadow: var(--shadow-sm) !important;
}
div[data-testid="stStatusWidget"] svg {
  stroke: var(--accent) !important;
}
div[data-testid="stStatusWidget"] div {
  font-size: 14px !important;
  color: var(--text-secondary) !important;
}

/* ===== 18. Info / Error ===== */
.stAlert {
  border-radius: 8px !important;
  font-size: 14px !important;
  border: none !important;
}
.stAlert.stInfo {
  background: var(--accent-soft) !important;
  color: var(--text) !important;
}
.stAlert.stError {
  background: #F5E8E8 !important;
  color: #8A4A4A !important;
}

/* ===== 19. Sidebar Session Buttons ===== */
section[data-testid="stSidebar"] .stButton button[kind="secondary"] {
  background: transparent !important;
  border: none !important;
  color: var(--text-secondary) !important;
  padding: 5px 8px !important;
  font-size: 13px !important;
  text-align: left !important;
  justify-content: flex-start !important;
  font-weight: 400 !important;
  border-radius: 6px !important;
}
section[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover {
  background: var(--accent-soft) !important;
  color: var(--text) !important;
}
section[data-testid="stSidebar"] .stButton button[kind="primary"] {
  background: var(--accent-soft) !important;
  border: none !important;
  color: var(--text) !important;
  font-weight: 500 !important;
  padding: 5px 8px !important;
  font-size: 13px !important;
  text-align: left !important;
  justify-content: flex-start !important;
  border-radius: 6px !important;
}

/* ===== 20. Sidebar Compact Columns ===== */
section[data-testid="stSidebar"] div[data-testid="column"] {
  padding: 0 2px !important;
}
section[data-testid="stSidebar"] div[data-testid="column"] .stButton button {
  padding: 2px 6px !important;
  font-size: 12px !important;
  min-height: 0 !important;
}

/* ===== 21. Chat header ===== */
.chat-header {
  font-family: 'Fraunces', serif;
  font-size: 16px;
  font-weight: 500;
  font-variation-settings: 'SOFT' 50;
  color: var(--text);
  padding: 0 0 8px;
  margin-top: 4px;
}

/* ===== 22. Responsive ===== */
@media (max-width: 768px) {
  .main .block-container {
    padding-left: 16px !important;
    padding-right: 16px !important;
  }
  .welcome { margin: 40px auto; }
  .welcome h1 { font-size: 24px; }
  .welcome-cards { flex-direction: column; align-items: center; }
  .topbar { padding: 14px 0 10px; flex-wrap: wrap; }
  .topbar-tagline { margin-left: 0; width: 100%; }
  [data-testid="stChatMessageContent"] { max-width: 92% !important; }
  section[data-testid="stSidebar"] .block-container { padding: 16px 12px !important; }
}

/* ===== 23. Reduced Motion ===== */
@media (prefers-reduced-motion: reduce) {
  .pulse-dot { animation: none !important; }
  .welcome-card { transition: none !important; }
  .stButton button { transition: none !important; }
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------

st.markdown(f"""
<div class="topbar">
  <span class="topbar-logo">
    <svg class="topbar-leaf" viewBox="0 0 18 18" fill="none">
      <path d="M9 2C9 2 3 5.5 3 10.5C3 14 6.5 16 9 16C11.5 16 15 14 15 10.5C15 5.5 9 2 9 2Z"
            stroke="#5B7B6A" stroke-width="1.3" fill="none"/>
      <path d="M9 2V16" stroke="#5B7B6A" stroke-width="0.7" opacity="0.3"/>
      <path d="M4 7.5C4 7.5 6 9 9 9C12 9 14 7.5 14 7.5"
            stroke="#5B7B6A" stroke-width="0.6" opacity="0.2" fill="none"/>
    </svg>
    RAGnamok
  </span>
  <span class="topbar-tagline">private knowledge &mdash; locally</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_get(path, **kwargs):
    try:
        r = requests.get(f"{BACKEND_URL}{path}", timeout=10, **kwargs)
        return r.json() if r.ok else None
    except Exception:
        return None

def api_post(path, json=None, files=None, params=None):
    try:
        r = requests.post(
            f"{BACKEND_URL}{path}", json=json, files=files, params=params, timeout=30
        )
        return r.json() if r.ok else None
    except Exception:
        return None

def api_delete(path):
    try:
        r = requests.delete(f"{BACKEND_URL}{path}", timeout=10)
        return r.ok
    except Exception:
        return False

# --- Sessions ---

def fetch_sessions():
    return api_get("/chat/sessions") or []

def fetch_messages(session_id):
    return api_get(f"/chat/sessions/{session_id}/messages", params={"limit": 50}) or []

def delete_session_api(session_id):
    api_delete(f"/chat/sessions/{session_id}")

def create_session_api():
    return api_post("/chat/sessions", json={"title": "New Chat"})

def send_message_api(session_id, query):
    try:
        r = requests.post(
            f"{BACKEND_URL}/chat/sessions/{session_id}/messages",
            json={"query": query, "top_k": 5},
            timeout=1000,
        )
        return r.json() if r.ok else None
    except Exception:
        return None

# --- Documents ---

def fetch_documents():
    return api_get("/documents") or []

def delete_document_api(doc_id):
    api_delete(f"/documents/{doc_id}")

def index_document_api(doc_id):
    return api_post(f"/documents/{doc_id}/index")

def toggle_document_api(doc_id):
    return api_post(f"/documents/{doc_id}/toggle")

# --- Tasks ---

def get_task_api(task_id):
    return api_get(f"/tasks/{task_id}")

def cancel_task_api(task_id):
    try:
        r = requests.post(f"{BACKEND_URL}/tasks/{task_id}/cancel", timeout=10)
        return r.ok
    except Exception:
        return False

def get_active_task_for_doc_api(doc_id):
    return api_get(f"/tasks/active-for-doc/{doc_id}")

# --- Upload ---

def upload_file(file, auto_index):
    return api_post(
        "/upload",
        files={"file": (file.name, file.getvalue(), "application/pdf")},
        params={"auto_index": str(auto_index).lower()},
    )

# ---------------------------------------------------------------------------
# Poll active tasks
# ---------------------------------------------------------------------------

def poll_active_tasks():
    if "active_tasks" not in st.session_state:
        st.session_state.active_tasks = {}
    resolved = []
    for doc_id, task_id in st.session_state.active_tasks.items():
        data = get_task_api(task_id)
        if data and data["status"] in ("completed", "failed", "cancelled"):
            resolved.append(doc_id)
    for doc_id in resolved:
        del st.session_state.active_tasks[doc_id]
    return len(resolved) > 0

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "sessions" not in st.session_state:
    st.session_state.sessions = fetch_sessions()
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "current_messages" not in st.session_state:
    st.session_state.current_messages = []
if "active_tasks" not in st.session_state:
    st.session_state.active_tasks = {}
if "new_session_created" not in st.session_state:
    st.session_state.new_session_created = False

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    # --- Upload ---
    st.markdown('<div class="sidebar-heading">Upload</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Choose PDF files", type=["pdf"], accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded_files:
        auto_index = st.checkbox("Auto-index after upload", value=True)
        if st.button("Upload", type="primary", use_container_width=True):
            successes = []
            failures = []
            for f in uploaded_files:
                result = upload_file(f, auto_index)
                if result:
                    successes.append(f.name)
                    if auto_index and "task_id" in result:
                        st.session_state.active_tasks[result["doc_id"]] = result["task_id"]
                else:
                    failures.append(f.name)
            if successes:
                st.success(f"Uploaded: {', '.join(successes)}")
            if failures:
                st.error(f"Failed: {', '.join(failures)}")
            st.rerun()

    # --- Documents ---
    st.markdown('<div class="sidebar-heading">Documents</div>', unsafe_allow_html=True)
    poll_active_tasks()
    docs = fetch_documents()

    if not docs:
        st.caption("No documents yet.")
    else:
        for d in docs:
            doc_id = d["id"]
            status = d["status"]
            enabled = d["enabled"]
            filename = d["filename"]
            chunks = d["chunk_count"]
            is_processing = status == "processing"
            is_completed = status == "completed"
            active_task_id = st.session_state.active_tasks.get(doc_id)

            dot_colors = {
                "uploaded": "#96908B",
                "processing": "#B58A6B",
                "completed": "#5B7B6A",
                "failed": "#B45A5A",
                "cancelled": "#CCC",
            }
            dot_color = dot_colors.get(status, "#CCC")

            status_label = {
                "processing": "indexing",
                "completed": "indexed",
                "uploaded": "uploaded",
                "failed": "failed",
                "cancelled": "cancelled",
            }.get(status, status)

            safe_filename = filename.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            st.markdown(
                f"""<div class="doc-row">
                    <span class="doc-dot" style="background:{dot_color}"></span>
                    <span class="doc-name" title="{safe_filename}">{safe_filename}</span>
                    <span class="doc-meta">{chunks}ch &middot; {status_label}</span>
                </div>""",
                unsafe_allow_html=True,
            )

            cols = st.columns(4)
            if is_completed:
                cols[0].button(
                    "\u2713 Indexed", disabled=True,
                    key=f"idx_{doc_id}", use_container_width=True,
                )
                label = "\u25C9 On" if enabled else "\u25CB Off"
                if cols[1].button(
                    label, key=f"tog_{doc_id}", use_container_width=True,
                ):
                    toggle_document_api(doc_id)
                    st.rerun()
            elif status in ("uploaded", "failed") and not active_task_id:
                if cols[0].button(
                    "📄 Index", key=f"idx_{doc_id}",
                    use_container_width=True,
                ):
                    result = index_document_api(doc_id)
                    if result:
                        st.session_state.active_tasks[doc_id] = result["task_id"]
                        st.rerun()
                    else:
                        st.error("Failed to start indexing")

            if is_processing or active_task_id:
                if cols[2].button(
                    "\u2715 Cancel", key=f"can_{doc_id}",
                    use_container_width=True,
                ):
                    if active_task_id:
                        cancel_task_api(active_task_id)
                        del st.session_state.active_tasks[doc_id]
                    else:
                        task_info = get_active_task_for_doc_api(doc_id)
                        if task_info:
                            cancel_task_api(task_info["task_id"])
                    st.rerun()

            if cols[3].button(
                "\u2715", key=f"del_{doc_id}",
                use_container_width=True,
            ):
                if active_task_id:
                    cancel_task_api(active_task_id)
                delete_document_api(doc_id)
                st.session_state.active_tasks.pop(doc_id, None)
                st.rerun()

    # --- Chat Sessions ---
    st.markdown('<div class="sidebar-heading">Chats</div>', unsafe_allow_html=True)

    if st.button(
        "+ New Chat", use_container_width=True,
        type="secondary",
    ):
        doc = create_session_api()
        if doc:
            st.session_state.sessions = fetch_sessions()
            st.session_state.current_session_id = doc["id"]
            st.session_state.current_messages = []
            st.session_state.new_session_created = True
            st.rerun()

    for s in st.session_state.sessions:
        is_active = s["id"] == st.session_state.current_session_id
        count = s.get("message_count", 0)
        title = s["title"][:32] + ("..." if len(s["title"]) > 32 else "")
        if count:
            title += f" ({count})"

        col1, col2 = st.columns([0.82, 0.18])
        if col1.button(
            title, key=f"sel_{s['id']}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state.current_session_id = s["id"]
            st.session_state.current_messages = fetch_messages(s["id"])
            st.rerun()
        if col2.button("\u2715", key=f"del_{s['id']}"):
            delete_session_api(s["id"])
            st.session_state.sessions = fetch_sessions()
            if st.session_state.current_session_id == s["id"]:
                st.session_state.current_session_id = None
                st.session_state.current_messages = []
            st.rerun()

# ===========================================================================
# Main — Chat
# ===========================================================================

def render_sources(sources):
    """Legacy wrapper — delegates to _sources_html()."""
    html = _sources_html(sources)
    if html:
        st.markdown(html, unsafe_allow_html=True)


def show_welcome():
    st.markdown(
        f"""<div class="welcome">
            <svg class="welcome-leaf" width="44" height="44" viewBox="0 0 44 44" fill="none">
                <path d="M22 4C22 4 7 11 7 24C7 33 14 39 22 39C30 39 37 33 37 24C37 11 22 4 22 4Z"
                      stroke="#5B7B6A" stroke-width="1.8" fill="none" opacity="0.7"/>
                <path d="M22 4V39" stroke="#5B7B6A" stroke-width="0.8" opacity="0.15"/>
                <path d="M9 18C9 18 14 21 22 21C30 21 35 18 35 18"
                      stroke="#5B7B6A" stroke-width="0.8" opacity="0.12" fill="none"/>
            </svg>
            <h1>RAGnamok</h1>
            <p class="welcome-tagline">Your private knowledge, instantly accessible.</p>
            <p>Upload a PDF to get started, or select an existing chat session from the sidebar.</p>
            <div class="welcome-cards">
                <div class="welcome-card">
                    <span class="welcome-card-icon">📄</span>
                    <span class="welcome-card-label">Upload PDFs</span>
                    <span class="welcome-card-desc">Add documents</span>
                </div>
                <div class="welcome-card">
                    <span class="welcome-card-icon">🔍</span>
                    <span class="welcome-card-label">Index Documents</span>
                    <span class="welcome-card-desc">Extract &amp; embed</span>
                </div>
                <div class="welcome-card">
                    <span class="welcome-card-icon">💬</span>
                    <span class="welcome-card-label">Ask Questions</span>
                    <span class="welcome-card-desc">Get answers</span>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


if not st.session_state.current_session_id:
    show_welcome()
    st.stop()

# -- Chat header ---

chat_title = "Chat"
for s in st.session_state.sessions:
    if s["id"] == st.session_state.current_session_id:
        chat_title = s["title"]
        break

chat_title_escaped = (chat_title
    .replace("&", "&amp;").replace("<", "&lt;")
    .replace(">", "&gt;").replace('"', "&quot;"))
st.markdown(
    f'<div class="chat-header">{chat_title_escaped}</div>',
    unsafe_allow_html=True,
)

# -- Empty state (first chat, no messages yet) ---

if not st.session_state.current_messages:
    st.markdown(
        """<div class="chat-empty">
            <div class="chat-empty-icon">💬</div>
            <div class="chat-empty-title">Start a conversation</div>
            <div class="chat-empty-hint">Ask anything about your documents below.</div>
            <div class="chat-empty-suggestions">
                <div class="suggestion-chip">Summarize my documents</div>
                <div class="suggestion-chip">What are the key findings?</div>
                <div class="suggestion-chip">Explain this concept</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

# -- Render messages ---

for msg in st.session_state.current_messages:
    role = "user" if msg["role"] == "user" else "assistant"
    content = clean_text(msg.get("content", ""))
    _render_chat_msg(role, content, msg.get("sources"))

# -- Chat input ---

if prompt := st.chat_input("Ask about your documents..."):
    cleaned_prompt = clean_text(prompt)
    _render_chat_msg("user", cleaned_prompt)
    st.session_state.current_messages.append(
        {"role": "user", "content": cleaned_prompt}
    )

    pulse = st.empty()
    pulse.markdown(
        """<div class="msg msg-assistant">
            <div class="msg-bubble msg-bubble-assistant">
                <div class="pulse-row">
                    <span class="pulse-dot"></span>
                    <span class="pulse-text">Retrieving</span>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    result = send_message_api(st.session_state.current_session_id, cleaned_prompt)

    if result:
        answer = clean_text(result.get("answer", ""))
        sources = result.get("sources", [])
        pulse.markdown(
            _render_chat_msg("assistant", answer, sources, return_html=True),
            unsafe_allow_html=True,
        )

        st.session_state.current_messages.append(
            {"role": "assistant", "content": answer, "sources": sources}
        )
        st.session_state.sessions = fetch_sessions()
    else:
        pulse.empty()
        st.error("Failed to get an answer.")
        st.session_state.current_messages.append(
            {"role": "assistant", "content": "_Failed to get an answer._"}
            )
