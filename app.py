"""
AI Student Assistant - web version (Flask)

Reuses the functions from study_assistant.py (build_system_prompt, ask_question,
explain_error) and wraps them in a small web app:

- GET  /                  the chat page
- GET  /api/state         current notes + conversation (so a page refresh doesn't lose them)
- POST /api/upload        upload a .txt / .md / .pdf notes file
- POST /api/chat          send a question, get an answer
- POST /api/clear         forget the conversation (notes stay loaded)
- POST /api/notes/remove  remove the loaded notes

Setup:
- pip install flask pypdf anthropic python-dotenv
- ANTHROPIC_API_KEY in your .env file (same as the CLI version)
- Keep this file in the same folder as study_assistant.py,
  and put index.html inside a folder called "templates".
- Run: python app.py   then open http://127.0.0.1:5000
"""

import os
import uuid

from anthropic import Anthropic
from flask import Flask, jsonify, render_template, request, session
from pypdf import PdfReader

# Importing study_assistant also runs load_dotenv(), so the key in .env is loaded.
from study_assistant import (
    MAX_HISTORY_MESSAGES,
    ask_question,
    build_system_prompt,
    explain_error,
)

# --- Config ---
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024   # reject files bigger than 5 MB
MAX_NOTES_CHARS = 60_000             # notes are sent with every question, so cap them
MAX_MESSAGE_CHARS = 4_000

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise SystemExit("ERROR: ANTHROPIC_API_KEY is not set. Add it to your .env file.")
client = Anthropic(api_key=api_key)

app = Flask(__name__)
# Signs the session cookie. A random key is fine locally (sessions reset when the
# server restarts). Set SECRET_KEY in .env if you want sessions to survive restarts.
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

# In-memory storage: one entry per browser session. Lost when the server stops.
SESSIONS = {}


def get_state() -> dict:
    """Return this browser's notes + conversation, creating them on first visit."""
    sid = session.get("sid")
    if sid not in SESSIONS:
        sid = uuid.uuid4().hex
        session["sid"] = sid
        SESSIONS[sid] = {"notes": "", "filename": None, "truncated": False, "history": []}
    return SESSIONS[sid]


def extract_text(file, ext: str) -> str:
    """Pull plain text out of an uploaded file."""
    if ext == ".pdf":
        reader = PdfReader(file.stream)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    return file.read().decode("utf-8", errors="replace")


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def state_info():
    state = get_state()
    return jsonify(
        filename=state["filename"],
        chars=len(state["notes"]),
        truncated=state["truncated"],
        history=state["history"],
    )


@app.post("/api/upload")
def upload():
    state = get_state()
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="No file was uploaded."), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify(error="Only .txt, .md and .pdf files are supported."), 400

    try:
        text = extract_text(file, ext).strip()
    except Exception:
        return jsonify(error="Couldn't read that file. Is it valid and not password-protected?"), 400

    if not text:
        return jsonify(error="No text found in that file. Scanned PDFs (images of pages) aren't supported."), 400

    state["truncated"] = len(text) > MAX_NOTES_CHARS
    state["notes"] = text[:MAX_NOTES_CHARS]
    state["filename"] = file.filename
    state["history"] = []  # new notes mean a fresh conversation

    return jsonify(
        filename=state["filename"],
        chars=len(state["notes"]),
        truncated=state["truncated"],
    )


@app.post("/api/chat")
def chat():
    state = get_state()
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify(error="Type a question first."), 400
    if len(message) > MAX_MESSAGE_CHARS:
        return jsonify(error=f"That message is too long (max {MAX_MESSAGE_CHARS} characters)."), 400

    history = state["history"]
    history.append({"role": "user", "content": message})

    try:
        answer = ask_question(client, build_system_prompt(state["notes"]), history)
    except Exception as err:
        history.pop()  # same rule as the CLI: a failed question must not stay in the history
        return jsonify(error=explain_error(err)), 502

    history.append({"role": "assistant", "content": answer})
    if len(history) > MAX_HISTORY_MESSAGES:
        state["history"] = history[-MAX_HISTORY_MESSAGES:]

    return jsonify(answer=answer)


@app.post("/api/clear")
def clear():
    get_state()["history"] = []
    return jsonify(ok=True)


@app.post("/api/notes/remove")
def remove_notes():
    state = get_state()
    state.update(notes="", filename=None, truncated=False, history=[])
    return jsonify(ok=True)


@app.errorhandler(413)
def too_large(_err):
    return jsonify(error="That file is too large (max 5 MB)."), 413


if __name__ == "__main__":
    # debug=True auto-reloads when you save and shows detailed errors.
    # It is for local development only; turn it off when you deploy.
    app.run(debug=True)
