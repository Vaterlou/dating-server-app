from flask import Flask
from flask_login import LoginManager

from models import db
from models import User
from models import Profile
from models import Message
from models import Match
from routes import main
from config import Config
from flask_cors import CORS
from flask_migrate import Migrate
from extensions import socketio, db, jwt

app = Flask(__name__)
app.config.from_object(Config)

migrate = Migrate(app, db)

db.init_app(app)
jwt.init_app(app)
socketio.init_app(app)

# Регистрация Blueprint
app.register_blueprint(main)


def create_user_copies(original_user_id, total_copies=10000, batch_size=1000):
    # Получите оригинального пользователя
    original_user = User.query.get(original_user_id)
    if not original_user:
        print(f"User with ID {original_user_id} not found.")
        return

    for i in range(total_copies // batch_size):
        for j in range(batch_size):
            new_user = User(
                username=original_user.username,
                name=original_user.name,
                password_hash=original_user.password_hash,
                is_google_user=original_user.is_google_user,
                coordinates=original_user.coordinates,
                email=f'new_email_{i * batch_size + j + 1}@example.com'  # Уникальный email
            )

            # Создание нового профиля для нового пользователя
            new_profile = Profile(
                user=new_user,  # Связываем новый профиль с новым пользователем
                bio=original_user.profile.bio,
                nationality=original_user.profile.nationality,
                country=original_user.profile.country,
                city=original_user.profile.city,
                age=original_user.profile.age,
                birth_date=original_user.profile.birth_date,
                height=original_user.profile.height,
                gender=original_user.profile.gender,
                profile_picture=original_user.profile.profile_picture,
                questions_answers=original_user.profile.questions_answers
            )

            db.session.add(new_user)  # Добавляем нового пользователя
            db.session.add(new_profile)  # Добавляем новый профиль

        db.session.commit()  # Сохраняем изменения в базе данных после каждого батча
    print(f"Successfully created {total_copies} copies of user ID {original_user_id}.")

# with app.app_context():
#     db.drop_all()

# @app.before_first_request
# def enable_postgis():
#     with db.engine.connect() as conn:
#         conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")

with app.app_context():
    db.create_all()  # Создание базы данных
    # create_user_copies(original_user_id=15)

# if __name__ == '__main__':
#      app.run(host="localhost", port=8000)