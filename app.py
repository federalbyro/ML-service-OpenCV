from flask import Flask, render_template, request, redirect, session, jsonify, Response
import os
import datetime
import sqlite3
import db
from werkzeug.utils import secure_filename

import photo_capture
import photo_compare

app = Flask(__name__)
app.secret_key = "secret"

TMP_DIR = "tmp"
os.makedirs(TMP_DIR, exist_ok=True)


def require_admin():
    return session.get("is_admin") is True


# ---------- Главная: пользовательская страница ----------
@app.route("/")
def home():
    events = db.query("SELECT id, title FROM events ORDER BY id DESC", fetch=True)
    return render_template("user.html", events=events, error=None, success=None)


# ---------- Админ логин ----------
@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_admin():
    username = request.form["username"]
    password = request.form["password"]

    row = db.query(
        "SELECT 1 FROM admin WHERE username=? AND password=?",
        (username, password),
        fetch=True
    )
    if not row:
        return "Ошибка авторизации"

    session["is_admin"] = True
    return redirect("/admin")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- Отдать фото участника из БД (для миниатюр) ----------
@app.route("/participant_photo/<int:pid>")
def participant_photo(pid: int):
    row = db.query(
        "SELECT photo_blob, photo_mime FROM participants WHERE id=?",
        (pid,),
        fetch=True
    )
    if not row:
        return "Not found", 404
    return Response(row[0]["photo_blob"], mimetype=row[0]["photo_mime"])


# ---------- ADMIN ----------
@app.route("/admin")
def admin():
    if not require_admin():
        return redirect("/login")

    events = db.query("SELECT id, title FROM events ORDER BY id DESC", fetch=True)
    participants = db.query("SELECT id, login, name FROM participants ORDER BY id DESC", fetch=True)
    return render_template("admin.html", events=events, participants=participants)


@app.route("/admin/add_event", methods=["POST"])
def add_event():
    if not require_admin():
        return jsonify({"status": "forbidden"}), 403

    title = request.json.get("title", "").strip()
    if not title:
        return jsonify({"status": "error", "msg": "empty title"}), 400

    db.query("INSERT INTO events(title) VALUES (?)", (title,))
    return jsonify({"status": "ok"})


@app.route("/admin/add_participant", methods=["POST"])
def add_participant():
    """
    Создать участника: login + (name) + photo (обязательно)
    Фото хранится В БАЗЕ (BLOB).
    """
    if not require_admin():
        return jsonify({"status": "forbidden"}), 403

    login = request.form.get("login", "").strip()
    name = request.form.get("name", "").strip() or None

    if not login:
        return jsonify({"status": "error", "msg": "empty login"}), 400

    if "photo" not in request.files:
        return jsonify({"status": "error", "msg": "no photo"}), 400

    f = request.files["photo"]
    if f.filename == "":
        return jsonify({"status": "error", "msg": "empty filename"}), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png"]:
        return jsonify({"status": "error", "msg": "bad ext"}), 400

    raw = f.read()
    if not raw:
        return jsonify({"status": "error", "msg": "empty file"}), 400

    mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

    # --- проверка лица через временный файл ---
    tmp_path = os.path.join(TMP_DIR, f"admin_check_{login}{ext}")
    with open(tmp_path, "wb") as out:
        out.write(raw)

    try:
        ok = photo_capture.validate_face(tmp_path)
    except Exception as e:
        try:
            os.remove(tmp_path)
        except:
            pass
        return jsonify({
            "status": "error",
            "code": "FACE_CHECK_FAILED",
            "msg": f"Не удалось проверить фото: {str(e)}"
        }), 400

    try:
        os.remove(tmp_path)
    except:
        pass

    if not ok:
        return jsonify({
            "status": "error",
            "code": "NO_FACE",
            "msg": "На фото не обнаружено лицо человека (или лиц больше одного)."
        }), 400

    # --- сохраняем в БД ---
    try:
        db.query(
            "INSERT INTO participants(login,name,photo_blob,photo_ext,photo_mime) VALUES (?,?,?,?,?)",
            (login, name, sqlite3.Binary(raw), ext, mime)
        )
        return jsonify({"status": "ok"})
    except:
        return jsonify({"status": "error", "msg": "login exists"}), 400


@app.route("/admin/get_attendance")
def get_attendance():
    if not require_admin():
        return jsonify({"status": "forbidden"}), 403

    data = db.query("""
        SELECT p.login, COALESCE(p.name,''), e.title, a.timestamp, a.match_score
        FROM attendance a
        JOIN participants p ON p.id = a.participant_id
        JOIN events e ON e.id = a.event_id
        ORDER BY a.id DESC
    """, fetch=True)

    return jsonify([list(x) for x in data])


# ---------- USER: регистрация на событие ----------
@app.route("/register", methods=["POST"])
def register():
    # form-data (обычная HTML-форма)
    event_id = request.form.get("event_id", type=int)
    name = (request.form.get("name") or "").strip()

    if not event_id:
        return jsonify({"status": "error", "msg": "no event_id"}), 400
    if not name:
        return jsonify({"status": "error", "msg": "no name"}), 400

    if "photo" not in request.files:
        return jsonify({"status": "error", "msg": "no photo"}), 400

    f = request.files["photo"]
    if not f or f.filename == "":
        return jsonify({"status": "error", "msg": "empty filename"}), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        return jsonify({"status": "error", "msg": "bad ext"}), 400

    raw = f.read()
    if not raw:
        return jsonify({"status": "error", "msg": "empty file"}), 400

    # сохраняем во временный файл
    tmp_path = os.path.join(TMP_DIR, f"user_upload_{secure_filename(name)}{ext}")
    with open(tmp_path, "wb") as out:
        out.write(raw)

    # 1) проверка лица
    try:
        ok = photo_capture.validate_face(tmp_path)
    except Exception as e:
        try: os.remove(tmp_path)
        except: pass
        return jsonify({"status": "error", "msg": f"face check failed: {str(e)}"}), 400

    if not ok:
        try: os.remove(tmp_path)
        except: pass
        return jsonify({"status": "bad_photo", "msg": "no face / bad quality"}), 200

    # 2) сверяем со всеми эталонными фото из БД (как у тебя было)
    participants = db.query("SELECT id, login, name, photo_blob, photo_ext FROM participants", fetch=True)

    best = None
    for p in participants:
        ref_path = os.path.join(TMP_DIR, f"ref_{p['id']}{p['photo_ext']}")
        with open(ref_path, "wb") as out:
            out.write(p["photo_blob"])

        try:
            match, score = photo_compare.compare(tmp_path, ref_path)
        finally:
            try: os.remove(ref_path)
            except: pass

        if best is None or score > best[2]:
            best = (p["id"], p["login"], score)

        if match:
            try:
                db.query(
                    "INSERT INTO attendance(participant_id,event_id,timestamp,match_score) VALUES (?,?,?,?)",
                    (p["id"], event_id, str(datetime.datetime.now()), score)
                )
            except:
                try: os.remove(tmp_path)
                except: pass
                return jsonify({"status": "already_registered", "login": p["login"], "score": score})

            try: os.remove(tmp_path)
            except: pass
            return jsonify({"status": "registered", "login": p["login"], "name": p["name"], "score": score})

    try: os.remove(tmp_path)
    except: pass

    if best:
        return jsonify({"status": "not_found", "best_candidate": best[1], "best_score": best[2]})
    return jsonify({"status": "not_found", "msg": "no participants in db"})


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True)
