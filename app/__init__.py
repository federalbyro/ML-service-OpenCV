"""
Инициализация Flask приложения.
"""
from flask import Flask
import os

def create_app():
    """Фабрика для создания Flask приложения."""
    app = Flask(__name__, 
                static_folder='../static',
                template_folder='../templates')
    
    app.secret_key = "secret"
    
    # Создание временной директории
    TMP_DIR = "tmp"
    os.makedirs(TMP_DIR, exist_ok=True)
    app.config['TMP_DIR'] = TMP_DIR
    
    # Регистрация blueprints
    from app.routes import auth, user, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(user.bp)
    app.register_blueprint(admin.bp)
    
    return app
