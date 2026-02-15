"""
Роуты для пользовательского интерфейса.
"""
from flask import Blueprint, render_template, request, jsonify, current_app, Response
import os
import datetime
from werkzeug.utils import secure_filename

from app.database import db
from app.services import photo_capture, face_recognition

bp = Blueprint('user', __name__)


@bp.route("/")
def home():
    """Главная страница пользователя."""
    events = db.query("SELECT id, title FROM events ORDER BY id DESC", fetch=True)
    return render_template("user.html", events=events, error=None, success=None)


@bp.route("/participant_photo/<int:pid>")
def participant_photo(pid: int):
    """Отдать фото участника из БД (для миниатюр)."""
    row = db.query(
        "SELECT photo_blob, photo_mime FROM participants WHERE id=?",
        (pid,),
        fetch=True
    )
    if not row:
        return "Not found", 404
    return Response(row[0]["photo_blob"], mimetype=row[0]["photo_mime"])


@bp.route("/register", methods=["POST"])
def register():
    """Регистрация пользователя на событие."""
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
    tmp_dir = current_app.config['TMP_DIR']
    tmp_path = os.path.join(tmp_dir, f"user_upload_{secure_filename(name)}{ext}")
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
        ref_path = os.path.join(tmp_dir, f"ref_{p['id']}{p['photo_ext']}")
        with open(ref_path, "wb") as out:
            out.write(p["photo_blob"])

        try:
            # Используем улучшенный алгоритм распознавания лиц
            score = face_recognition.compare_faces_advanced(tmp_path, ref_path)
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
