"""
Роуты для аутентификации и авторизации.
"""
from flask import Blueprint, render_template, request, redirect, session
from app.database import db

bp = Blueprint('auth', __name__)


@bp.route("/login")
def login_page():
    """Отображение страницы логина."""
    return render_template("login.html")


@bp.route("/login", methods=["POST"])
def login_admin():
    """Обработка логина администратора."""
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


@bp.route("/logout")
def logout():
    """Выход из системы."""
    session.clear()
    return redirect("/")


def require_admin():
    """Проверка прав администратора."""
    return session.get("is_admin") is True
