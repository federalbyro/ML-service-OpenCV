"""
Роуты для административного интерфейса.
"""
from flask import Blueprint, render_template, request, jsonify, redirect, current_app
import os
import datetime
import sqlite3

from app.services import face_recognition
from app.database import db
from app.services import photo_capture
from app.routes.auth import require_admin

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route("/")
def admin():
    """Главная страница администратора."""
    if not require_admin():
        return redirect("/login")

    events = db.query("SELECT id, title FROM events ORDER BY id DESC", fetch=True)
    participants = db.query("SELECT id, login, name FROM participants ORDER BY id DESC", fetch=True)
    return render_template("admin.html", events=events, participants=participants)


@bp.route("/add_event", methods=["POST"])
def add_event():
    """Добавление нового мероприятия."""
    if not require_admin():
        return jsonify({"status": "forbidden"}), 403

    title = request.json.get("title", "").strip()
    if not title:
        return jsonify({"status": "error", "msg": "empty title"}), 400

    db.query("INSERT INTO events(title) VALUES (?)", (title,))
    return jsonify({"status": "ok"})


@bp.route("/add_participant", methods=["POST"])
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
    tmp_dir = current_app.config['TMP_DIR']
    tmp_path = os.path.join(tmp_dir, f"admin_check_{login}{ext}")
    with open(tmp_path, "wb") as out:
        out.write(raw)

    try:
        ok = photo_capture.validate_face(
            tmp_path,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(80, 80),
            require_single_face=True
        )
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


@bp.route("/get_attendance")
def get_attendance():
    """Получить журнал посещаемости."""
    if not require_admin():
        return jsonify({"status": "forbidden"}), 403

    data = db.query("""
        SELECT p.login, COALESCE(p.name,''), e.title, a.timestamp, a.match_score
        FROM attendance a
        JOIN participants p ON p.id = a.participant_id
        JOIN events e ON e.id = a.event_id
        ORDER BY a.id DESC
    """, fetch=True)

    return jsonify([list(x) for x in data] if data else [])


@bp.route("/export_attendance")
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
    
    if not data:
        data = []

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
