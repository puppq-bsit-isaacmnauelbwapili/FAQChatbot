"""
PUP Parañaque IT FAQ Chatbot - Web App
Run:  python app.py then open  http://127.0.0.1:5000
"""
import os
import re
import csv
import json
import secrets
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, jsonify, session,
                   redirect, url_for)

from chatbot import FAQEngine, log_chat, KB_PATH, LOG_PATH, BASE_DIR

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")   # CHANGE THIS!
FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback_log.csv")

engine = FAQEngine()


# ------------------------------------------------------------ helpers
def read_kb():
    with open(KB_PATH, encoding="utf-8") as f:
        return json.load(f)


def write_kb(kb):
    tmp = KB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)
    os.replace(tmp, KB_PATH)
    engine.load()


def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            if request.path.startswith("/admin/api"):
                return jsonify(error="Hindi po kayo naka-login."), 401
            return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------ public pages
@app.route("/")
def index():
    kb = read_kb()
    return render_template("index.html", suggestions=kb.get("suggestions", []))


@app.post("/api/ask")
def api_ask():
    data = request.get_json(silent=True) or {}
    question = str(data.get("question", ""))[:500]
    answer, entry_id = engine.ask(question)
    if question.strip():
        log_chat(question, answer, entry_id)
    category = next((e["category"] for e in engine.entries if e["id"] == entry_id), None)
    return jsonify(answer=answer, entry_id=entry_id, category=category)


@app.post("/api/feedback")
def api_feedback():
    data = request.get_json(silent=True) or {}
    new = not os.path.exists(FEEDBACK_PATH)
    with open(FEEDBACK_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "question", "matched_entry", "helpful"])
        w.writerow([datetime.now().isoformat(timespec="seconds"),
                    str(data.get("question", ""))[:500],
                    data.get("entry_id") or "FALLBACK",
                    "yes" if data.get("helpful") else "no"])
    return jsonify(ok=True)


# ------------------------------------------------------------ admin
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Maling password po."
    return render_template("login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html", default_password=(ADMIN_PASSWORD == "admin123"))


@app.get("/admin/api/entries")
@admin_required
def admin_entries():
    return jsonify(read_kb()["entries"])


@app.post("/admin/api/entries")
@admin_required
def admin_save_entry():
    """Add a new entry or update an existing one (matched by id)."""
    d = request.get_json(silent=True) or {}
    eid = str(d.get("id", "")).strip()
    category = str(d.get("category", "")).strip()
    answer = str(d.get("answer", "")).strip()
    raw_patterns = d.get("patterns", "")

    if not re.fullmatch(r"[a-z0-9_]{2,40}", eid):
        return jsonify(error="ID: lowercase letters, numbers, underscore lang (hal. enroll_how)."), 400
    if not category or not answer:
        return jsonify(error="Kailangan po ng category at answer."), 400

    # patterns typed as:  enroll+how, enroll+when
    patterns = []
    for chunk in str(raw_patterns).split(","):
        words = [w.strip().lower() for w in chunk.split("+") if w.strip()]
        if words:
            patterns.append(words)
    if not patterns:
        return jsonify(error="Maglagay po ng kahit isang pattern (hal. enroll+how)."), 400

    kb = read_kb()
    # unknown keywords become their own keyword so the rule still works
    for pat in patterns:
        for w in pat:
            kb["synonyms"].setdefault(w, [w])

    entry = {"id": eid, "category": category, "patterns": patterns,
             "verified": bool(d.get("verified", False)), "answer": answer}
    for i, e in enumerate(kb["entries"]):
        if e["id"] == eid:
            kb["entries"][i] = entry
            break
    else:
        kb["entries"].append(entry)
    write_kb(kb)
    return jsonify(ok=True)


@app.delete("/admin/api/entries/<eid>")
@admin_required
def admin_delete_entry(eid):
    kb = read_kb()
    kb["entries"] = [e for e in kb["entries"] if e["id"] != eid]
    write_kb(kb)
    return jsonify(ok=True)


@app.get("/admin/api/stats")
@admin_required
def admin_stats():
    chats = read_csv(LOG_PATH)
    fb = read_csv(FEEDBACK_PATH)
    fallbacks = [c["question"] for c in chats if c["matched_entry"] == "FALLBACK"]
    total = len(chats)
    helpful = sum(1 for f in fb if f["helpful"] == "yes")
    return jsonify(
        total_questions=total,
        answered=total - len(fallbacks),
        fallbacks=len(fallbacks),
        fallback_rate=round(len(fallbacks) / total * 100, 1) if total else 0,
        feedback_total=len(fb),
        helpful_rate=round(helpful / len(fb) * 100, 1) if fb else 0,
        recent_fallbacks=list(dict.fromkeys(reversed(fallbacks)))[:15],
        unverified=engine.unverified(),
    )


if __name__ == "__main__":
    if ADMIN_PASSWORD == "admin123":
        print("⚠  Default admin password in use. Set ADMIN_PASSWORD before deploying.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
