from flask import Flask
from flask_login import LoginManager

from models import db
from models import User
from models import Profile
from routes import main
from config import Config
from flask_cors import CORS
from flask_talisman import Talisman
from flask_jwt_extended import JWTManager

app = Flask(__name__)
CORS(app) #FOR DEBUG
# Talisman(app)
app.config.from_object(Config)
db.init_app(app)

app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = Config.ALLOWED_EXTENSIONS

app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # Замените на свой секретный ключ

# Инициализация JWTManager
jwt = JWTManager(app)

# Регистрация Blueprint
app.register_blueprint(main)

with app.app_context():
    User.__table__.drop(db.engine)
    Profile.__table__.drop(db.engine)

with app.app_context():
    db.create_all()  # Создание базы данных

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)