from flask import Flask, render_template, request, redirect, session, jsonify, Response
import os
import datetime
import sqlite3
import db
from werkzeug.utils import secure_filename

import photo_capture
import photo_compare
import face_recognition_module

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


@app.route("/admin/export_attendance")
def export_attendance():
    """
    Выгрузка журнала посещаемости в JSON-файл с фильтрами.
    Параметры (опционально):
      - participant_id: ID участника
      - event_id: ID мероприятия
      - date_from: дата начала (YYYY-MM-DD)
      - date_to: дата окончания (YYYY-MM-DD)
    """
    if not require_admin():
        return jsonify({"status": "forbidden"}), 403

    # Получаем параметры фильтров
    participant_id = request.args.get("participant_id", type=int)
    event_id = request.args.get("event_id", type=int)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    # Строим SQL-запрос с учётом фильтров
    sql = """
        SELECT 
            a.id,
            p.id as participant_id,
            p.login,
            p.name,
            e.id as event_id,
            e.title as event_title,
            a.timestamp,
            a.match_score
        FROM attendance a
        JOIN participants p ON p.id = a.participant_id
        JOIN events e ON e.id = a.event_id
        WHERE 1=1
    """
    params = []

    if participant_id:
        sql += " AND p.id = ?"
        params.append(participant_id)
    
    if event_id:
        sql += " AND e.id = ?"
        params.append(event_id)
    
    if date_from:
        sql += " AND DATE(a.timestamp) >= ?"
        params.append(date_from)
    
    if date_to:
        sql += " AND DATE(a.timestamp) <= ?"
        params.append(date_to)

    sql += " ORDER BY a.timestamp DESC"

    data = db.query(sql, params, fetch=True)

    # Формируем JSON-структуру
    result = {
        "export_date": str(datetime.datetime.now()),
        "filters": {
            "participant_id": participant_id,
            "event_id": event_id,
            "date_from": date_from,
            "date_to": date_to
        },
        "total_records": len(data),
        "records": [
            {
                "id": row["id"],
                "participant": {
                    "id": row["participant_id"],
                    "login": row["login"],
                    "name": row["name"]
                },
                "event": {
                    "id": row["event_id"],
                    "title": row["event_title"]
                },
                "timestamp": row["timestamp"],
                "match_score": row["match_score"]
            }
            for row in data
        ]
    }

    # Сохраняем в файл
    export_filename = f"attendance_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    export_path = os.path.join("tmp", export_filename)
    
    import json
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return jsonify({
        "status": "ok",
        "filename": export_filename,
        "path": export_path,
        "total_records": len(data)
    })


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

    # 2) сверяем со ВСЕМИ эталонными фото из БД и находим лучшее совпадение
    participants = db.query("SELECT id, login, name, photo_blob, photo_ext FROM participants", fetch=True)

    if not participants:
        try: os.remove(tmp_path)
        except: pass
        return jsonify({"status": "not_found", "msg": "no participants in db"})

    # Проходим по ВСЕМ участникам и собираем результаты
    all_scores = []
    for p in participants:
        ref_path = os.path.join(TMP_DIR, f"ref_{p['id']}{p['photo_ext']}")
        with open(ref_path, "wb") as out:
            out.write(p["photo_blob"])

        try:
            # Используем улучшенный алгоритм распознавания лиц
            score = face_recognition_module.compare_faces_advanced(tmp_path, ref_path)
            all_scores.append({
                "participant_id": p["id"],
                "login": p["login"],
                "name": p["name"],
                "score": score
            })
            print(f"✓ {p['login']}: {score:.1f}%")
        except Exception as e:
            print(f"✗ Ошибка сравнения с {p['login']}: {e}")
            # Добавляем с нулевым score чтобы не пропустить участника
            all_scores.append({
                "participant_id": p["id"],
                "login": p["login"],
                "name": p["name"],
                "score": 0.0
            })
        finally:
            try: os.remove(ref_path)
            except: pass

    try: os.remove(tmp_path)
    except: pass

    # Находим участника с максимальным score
    best_match = max(all_scores, key=lambda x: x["score"])
    
    # Порог совпадения: 70%
    THRESHOLD = 70.0
    
    if best_match["score"] >= THRESHOLD:
        # Пытаемся зарегистрировать
        try:
            db.query(
                "INSERT INTO attendance(participant_id,event_id,timestamp,match_score) VALUES (?,?,?,?)",
                (best_match["participant_id"], event_id, str(datetime.datetime.now()), best_match["score"])
            )
            return jsonify({
                "status": "registered",
                "login": best_match["login"],
                "name": best_match["name"],
                "score": best_match["score"]
            })
        except:
            # Уже зарегистрирован
            return jsonify({
                "status": "already_registered",
                "login": best_match["login"],
                "score": best_match["score"]
            })
    else:
        # Не найдено достаточного совпадения
        return jsonify({
            "status": "not_found",
            "best_candidate": best_match["login"],
            "best_score": best_match["score"]
        })


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True)
