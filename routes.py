import os
# from distutils.command.config import config
from pyexpat.errors import messages

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from werkzeug.utils import secure_filename
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from flask_socketio import emit
from flask_socketio import join_room
from flask_socketio import leave_room
from google.oauth2 import id_token
from google.auth.transport import requests
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy import func
from geoalchemy2.functions import ST_DWithin, ST_MakePoint
from geoalchemy2.functions import ST_X, ST_Y
from geoalchemy2 import WKTElement

from models import db
from models import User
from models import Profile
from models import Message
from models import Match

from utils import haversine
from utils import allowed_file
from extensions import socketio
from utils import get_country_by_coordinates

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({'error': 'Missing fields'}), 400

    # Проверка уникальности email
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400

    # Создание нового пользователя
    new_user = User(username=username, email=email, name=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    token = create_access_token(identity=new_user.id)

    return jsonify({'token': token, 'user_id': new_user.id, 'message': 'User registered successfully!'}), 201

@main.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Missing fields'}), 400

    user = User.query.filter_by(email=email).first()

    if user and user.is_google_user:
        return jsonify({'error': 'Этот email зарегистрирован через Google. Войдите через Google.'}), 403

    go_to_profile = False
    if user and user.check_password(password):
        token = create_access_token(identity=user.id)
        if not user.profile:
            go_to_profile = False
            profile = Profile(user_id=user.id)
            db.session.add(profile)
            db.session.commit()
        if user.profile.questions_answers is not None:
            go_to_profile = True

        return jsonify({'token': token, 'user_id': user.id, 'go_to_profile': go_to_profile, 'message': 'Login successful!'}), 200
    else:
        return jsonify({'error': 'Invalid email or password'}), 401


@main.route('/google-login', methods=['POST'])
def google_login():
    googleToken = request.json.get('token')
    try:
        # Проверка и декодирование токена
        idinfo = id_token.verify_oauth2_token(googleToken, requests.Request(), current_app.config['GOOGLE_CLIENT_ID'])

        # Получение данных пользователя
        user_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name')

        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(username=name, email=email, is_google_user=True)
            db.session.add(user)
            db.session.commit()

        token = create_access_token(identity=user.id)

        return jsonify({'token': token, 'user_id': user.id})
    except ValueError:
        return jsonify({'error': 'Неверный токен'}), 401



@main.route('/create_profile', methods=['POST'])
@jwt_required()
def create_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found.'}), 404

    data = request.json
    profile = user.profile

    if not profile:
        profile = Profile(user_id=user.id)
        db.session.add(profile)

    # Проверка имени
    name = data.get('name')
    if name:
        profile.name = name
    else:
        return jsonify({'error': 'Name is required.'}), 400

    # Проверка возраста
    age = data.get('age')
    if age is not None and isinstance(age, int) and age > 0:
        profile.age = age
    else:
        return jsonify({'error': 'Invalid age.'}), 400

    # Проверка даты рождения
    birth_date = data.get('birthDate')
    if birth_date:
        try:
            profile.birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid birth date format.'}), 400
    else:
        return jsonify({'error': 'Birth date is required.'}), 400

    # Пол
    gender = data.get('gender')
    if gender is not None:
        profile.gender = gender

    # Вопросы и ответы
    questions_answers = data.get('questions_answers')
    if questions_answers:
        profile.questions_answers = questions_answers

    # Проверка и установка координат
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if not (latitude and longitude):
        return jsonify({'error': 'Latitude and longitude are required.'}), 400

    if not (isinstance(latitude, (int, float)) and isinstance(longitude, (int, float))):
        return jsonify({'error': 'Coordinates must be valid numbers.'}), 400

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify({'error': 'Invalid latitude or longitude range.'}), 400

    user.coordinates = WKTElement(f'POINT({longitude} {latitude})', srid=4326)

    # Сохранение профиля
    db.session.commit()

    return jsonify({'message': 'Profile created!'}), 201


# Профиль пользователя
@main.route('/profile', methods=['GET', 'POST'])
@jwt_required()
def profile():
    if request.method == 'POST':
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found.'}), 404

        profile = Profile.query.filter_by(user_id=user_id).first()

        if not profile:
            profile = Profile(user_id=user_id)
            db.session.add(profile)

        if 'avatar' in request.files:
            file = request.files['avatar']

            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                directory_path = os.path.join(current_app.config['UPLOAD_PROFILE_FOLDER'], str(user_id))

                if not os.path.exists(directory_path):
                    os.makedirs(directory_path, exist_ok=True)

                file_path = os.path.join(directory_path, filename)
                file.save(file_path)
                profile.profile_picture = filename
            else:
                return jsonify({'error': 'Invalid file type'}), 400

        bio = request.form.get('bio')
        if bio is not None and len(bio) > 0:
            profile.bio = bio

        age = request.form.get('age')
        if age is not None and age.isdigit() and int(age) > 0:
            profile.age = int(age)

        # birth_date = request.form.get('birthDate')
        # if birth_date is not None:
        #     profile.birth_date = birth_date
        #
        # gender = request.form.get('gender')
        # if gender is not None:
        #     profile.gender = gender
        #
        # questions_answers = request.form.get('questions_answers')
        # if questions_answers is not None:
        #     profile.questions_answers = questions_answers
        #
        # latitude = request.form.get('latitude')
        # longitude = request.form.get('longitude')
        #
        # if latitude is None or longitude is None:
        #     return jsonify({'error': 'Invalid coordinates.'}), 404

        # user.coordinates = WKTElement(f'POINT({longitude} {latitude})', srid=4326)

        db.session.commit()

        return jsonify({'message': 'Profile updated!'}), 200
    elif request.method == 'GET':
        user_id = request.args.get('user_id')
        user = User.query.get(user_id)
        profile = Profile.query.filter_by(user_id=user_id).first()
        if profile:
            profile_data = {
                'name': user.name,
                'bio': profile.bio,
                'age': profile.age,
                'gender': profile.gender,
                'questions_answers': profile.questions_answers,
                'profile_picture': profile.profile_picture
            }

            return jsonify(profile_data), 200
        return jsonify({'message': 'Profile not found.'}), 404


@main.route('/users', methods=['GET'])
@jwt_required()
def users():
    radius = float(request.args.get('radius', 10000)) # Радиус поиска в метрах
    limit = int(request.args.get('limit', 10))  # Количество пользователей на одну страницу
    offset = int(request.args.get('offset', 0))  # Смещение (с какой записи начинать)

    user_id = get_jwt_identity()
    curr_user = User.query.get(user_id)

    liked_users_subquery = (
        db.session.query(Match.liked_user_id)
        .filter(Match.user_id == user_id)  # Используем filter() для явного указания условия
        .subquery()
    )

    nearby_users_query = (
        db.session.query(User)
        .filter(
            func.ST_DWithin(
                func.ST_Transform(User.coordinates, 4326),
                func.ST_Transform(curr_user.coordinates, 4326),
                radius
            ),
            User.id != curr_user.id,  # Исключаем текущего пользователя
            ~User.id.in_(liked_users_subquery)  # Исключаем пользователей, которых текущий пользователь уже лайкал
        )
    )

    total_users = nearby_users_query.count()

    nearby_users = (
        nearby_users_query
        .limit(limit)
        .offset(offset)
        .all()
    )
    users_list = []

    for user in nearby_users:
        distance = db.session.query(
            func.ST_Distance(
                func.ST_Transform(user.coordinates, 4326),
                func.ST_Transform(curr_user.coordinates, 4326)
            )
        ).scalar()

        latitude = db.session.execute(func.ST_Y(user.coordinates)).scalar()
        longitude = db.session.execute(func.ST_X(user.coordinates)).scalar()

        user_info = {
            'id' : user.id,
            'username': user.username,
            'email': user.email,
            'bio': user.profile.bio,
            'age': user.profile.age,
            'gender': user.profile.gender,
            'profile_picture': user.profile.profile_picture,
            'latitude': latitude,
            'longitude': longitude,
            'distance': distance,
        }
        users_list.append(user_info)

    return jsonify({'users': users_list, 'total': total_users, 'limit': limit, 'offset': offset}), 200


@main.route('/send_message', methods=['POST'])
@jwt_required()
def send_message():
    user_id = get_jwt_identity()
    sender = User.query.get(user_id)
    recipient = User.query.get(request.form.get('recipient_id'))
    file = request.files.get('media')

    if not recipient:
        return jsonify({'error': 'Recipient not found.'}), 404

    if file is not None:
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            directory_path = os.path.join(current_app.config['UPLOAD_MEDIA_FOLDER'], str(user_id))

            if not os.path.exists(directory_path):
                os.makedirs(directory_path, exist_ok=True)

            file_path = os.path.join(directory_path, filename)
            file.save(file_path)
        else:
            return jsonify({'error': 'File type not allowed'}), 400

    message = Message(sender_id=sender.id, recipient_id=recipient.id, body=request.form.get('body') )
    if file is not None:
        message.media_url = file.filename

    db.session.add(message)
    db.session.commit()

    message_info = {
        'id': message.id,
        'timestamp': message.timestamp,
        'sender_id': message.sender_id,
        'recipient_id': message.recipient_id,
        'body': message.body
    }

    if file is not None:
        message_info['media_url'] = message.media_url

    return jsonify({'message': message_info}), 201


@main.route('/messages', methods=['GET'])
@jwt_required()
def get_messages():
    recipient_id = request.args.get('recipient_id')

    if not recipient_id:
        return jsonify({'error': 'recipient_id не указан'}), 400

    user = User.query.filter_by(id=get_jwt_identity()).first()
    recipient = User.query.filter_by(id=recipient_id).first()

    if user is None or recipient is None:
        return jsonify({'error': 'User or recipient is not found'}), 404

    messages = Message.query.filter(
        or_(
            (Message.sender == user) & (Message.recipient == recipient),
            (Message.sender == recipient) & (Message.recipient == user)
        )
    ).order_by(Message.timestamp.asc()).all()

    messages_list = []

    for message in messages:
        message_info = {
            'id': message.id,
            'timestamp': message.timestamp,
            'sender_id': message.sender_id,
            'recipient_id': message.recipient_id,
            'body': message.body,
            "media_url": message.media_url
        }
        messages_list.append(message_info)

    return jsonify({
        'messages': messages_list,
    }), 200


@main.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # JWT не имеет функционала для "выхода" (токены не уничтожаются сервером)
    # Однако, вы можете реализовать логику, такую как добавление токенов в черный список.
    return jsonify({'message': 'Logged out successfully.'}), 200


@socketio.on('like')
@jwt_required()
def like_user(data):
    user_id = get_jwt_identity()
    liked_user_id = data.get('liked_user_id')

    if not liked_user_id:
        emit('like_response', {'success': False, 'error': 'liked_user_id is required'})
        return

    # Проверяем, существует ли уже такой лайк
    existing_like = Match.query.filter_by(user_id=user_id, liked_user_id=liked_user_id).first()

    if existing_like:
        emit('like_response', {'success': False, 'error': 'You already liked this user'})
        return

    # Проверяем, лайкнул ли другой пользователь текущего пользователя
    reverse_like = Match.query.filter_by(user_id=liked_user_id, liked_user_id=user_id).first()

    if reverse_like:
        reverse_like.is_mutual = True
        db.session.commit()
        emit('new_match', {'message': 'It’s a match!'}, to=user_id)
        emit('new_match', {'message': 'It’s a match!'}, to=liked_user_id)
        emit('like_response', {'success': True, 'message': 'It’s a match!'})
        print(f"Отправляем match пользователю {user_id} и {liked_user_id}")
        return

    # Создаем лайк без взаимности
    match = Match(user_id=user_id, liked_user_id=liked_user_id)
    db.session.add(match)
    db.session.commit()
    # emit('new_like', {'message': 'User liked successfully'}, to=user_id)
    emit('new_like', {'message': 'You were liked'}, to=liked_user_id)
    emit('like_response', {'success': True, 'message': 'User liked successfully'})
    return


@main.route('/matches', methods=['GET'])
@jwt_required()
def get_matches():
    user_id = get_jwt_identity()

    # Получаем всех пользователей, с которыми есть совпадения
    matches = Match.query.filter_by(user_id=user_id, is_mutual=True).all()
    matched_users = []
    for match in matches:
        matched_info = {
            'id': match.liked_user.id,
            'username': match.liked_user.username,
            'email': match.liked_user.email,
            'bio': match.liked_user.profile.bio,
            'age': match.liked_user.profile.age,
            'gender': match.liked_user.profile.gender,
            'profile_picture': match.liked_user.profile.profile_picture
        }
        matched_users.append(matched_info)
    return jsonify({'matches': matched_users}), 200


@socketio.on('connect')
@jwt_required()
def handle_connect():
    user_id = get_jwt_identity()
    new_likes = Match.query.filter_by(liked_user_id=user_id, is_new=True).all()

    if user_id:
        # Добавляем пользователя в комнату с его user_id
        join_room(user_id)
        print(f"User {user_id} connected and joined room {user_id}")

        # Если есть новые лайки, отправляем их количество и обновляем статус
        if len(new_likes) > 0:
            socketio.emit('new_likes', {'new_likes': len(new_likes)}, room=user_id)

            for like in new_likes:
                like.is_new = False

            db.session.commit()
    else:
        print("Error: User ID not found during connection")


@socketio.on('disconnect')
@jwt_required()
def handle_disconnect():
    # Получаем user_id из токена
    user_id = get_jwt_identity()

    if user_id:
        # Удаляем пользователя из комнаты при отключении
        leave_room(user_id)
        print(f"User {user_id} disconnected and left room {user_id}")
    else:
        print("Error: User ID not found during disconnection")