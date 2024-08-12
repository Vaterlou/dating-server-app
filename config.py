
import os

class Config:
    UPLOAD_FOLDER = 'static/profile_pics'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dating_app.db'  # Используем SQLite для простоты
    ALLOWED_COUNTRIES = ["Russia", "Indonesia"]
    # ALLOWED_CITIES
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.urandom(24)  # Секретный ключ для сессий