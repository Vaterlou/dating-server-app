
import os

class Config:
    UPLOAD_PROFILE_FOLDER = 'static/profile_pics'
    UPLOAD_MEDIA_FOLDER = 'static/uploads/'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov'}
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dating_app.db'  # Используем SQLite для простоты
    ALLOWED_COUNTRIES = ["Russia", "Indonesia"]
    # ALLOWED_CITIES
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.urandom(24)  # Секретный ключ для сессий