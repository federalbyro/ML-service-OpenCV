"""
Точка входа для запуска Flask приложения.
"""
from app import create_app
from app.database import db

if __name__ == "__main__":
    app = create_app()
    db.init_db()
    app.run(debug=True)
