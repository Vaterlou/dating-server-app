import os
from distutils.command.config import config
from pyexpat.errors import messages

import bp
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from google.oauth2 import id_token
from google.auth.transport import requests

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
    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully!'}), 201

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

    if user and user.check_password(password):
        token = create_access_token(identity=user.id)
        if not user.profile:
            profile = Profile(user_id=user.id)
            db.session.add(profile)
            db.session.commit()
        return jsonify({'token': token, 'user_id': user.id, 'message': 'Login successful!'}), 200
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
            profile.bio = request.form.get('bio')

        age = request.form.get('age')
        if age is not None and age.isdigit() and int(age) > 0:
            profile.age = int(age)
        # profile.nationality = data.get('nationality')
        # profile.height = data.get('height')
        if request.form.get('gender') is not None:
            profile.gender = request.form.get('gender')

        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        user.coordinates = WKTElement(f'POINT({longitude} {latitude})', srid=4326)

        # country = data.get('country')
        # if country is not None and profile.latitude is not None and profile.longitude is not None:
        #     if country == get_country_by_coordinates(profile.latitude, profile.longitude):
        #         if country in Config.ALLOWED_COUNTRIES:
        #             profile.country = country
        #         else:
        #             return jsonify({'message': 'This country is not supported.'}), 404
        #     return jsonify({'message': 'Country does not match location.'}), 404
        # else:
        #     return jsonify({'message': 'Impossible to determine geolocation.'}), 404

        db.session.commit()

        return jsonify({'message': 'Profile updated!'}), 200

    elif request.method == 'GET':
        user_id = request.args.get('user_id')
        if user_id is not None:
            user_id = get_jwt_identity()
        profile = Profile.query.filter_by(user_id=user_id).first()
        if profile:
            profile_data = {
                'bio': profile.bio,
                'age': profile.age,
                'gender': profile.gender,
                'profile_picture': profile.profile_picture
            }
            return jsonify(profile_data), 200
        return jsonify({'message': 'Profile not found.'}), 404


@main.route('/users', methods=['GET'])
@jwt_required()
def users():
    radius = float(request.args.get('radius', 10000)) # Радиус поиска в метрах

    user_id = get_jwt_identity()
    curr_user = User.query.get(user_id)

    nearby_users = (
        db.session.query(User)
        .filter(
            func.ST_DWithin(
                func.ST_Transform(User.coordinates, 4326),
                func.ST_Transform(curr_user.coordinates, 4326),
                radius
            )
        )
        .all()
    )
    users_list = []

    for user in nearby_users:
        if user.id == curr_user.id:
            continue

        existing_like = Match.query.filter_by(user_id=user_id, liked_user_id=user.id).first()
        if existing_like:
            continue

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

    return jsonify({'users': users_list}), 200


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


@main.route('/like', methods=['POST'])
@jwt_required()
def like_user():
    user_id = get_jwt_identity()
    liked_user_id = request.json.get('liked_user_id')

    if not liked_user_id:
        return jsonify({'error': 'liked_user_id is required'}), 400

    # Проверяем, существует ли уже такой лайк
    existing_like = Match.query.filter_by(user_id=user_id, liked_user_id=liked_user_id).first()

    if existing_like:
        return jsonify({'error': 'You already liked this user'}), 400

    # Проверяем, лайкнул ли другой пользователь текущего пользователя
    reverse_like = Match.query.filter_by(user_id=liked_user_id, liked_user_id=user_id).first()

    if reverse_like:
        # Создаем взаимное совпадение
        match = Match(user_id=user_id, liked_user_id=liked_user_id, is_mutual=True)
        reverse_like.is_mutual = True
        db.session.add(match)
        db.session.commit()
        return jsonify({'message': 'It’s a match!'}), 200

    # Создаем лайк без взаимности
    match = Match(user_id=user_id, liked_user_id=liked_user_id)
    db.session.add(match)
    db.session.commit()
    return jsonify({'message': 'User liked'}), 200


@main.route('/matches', methods=['GET'])
@jwt_required()
def get_matches():
    user_id = get_jwt_identity()

    # Получаем всех пользователей, с которыми есть совпадения
    matches = Match.query.filter_by(user_id=user_id, is_mutual=True).all() #FOR DEBUF mutual FALSE
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