import os
from distutils.command.config import config
from pyexpat.errors import messages

import bp
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from sqlalchemy import or_

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
    if user and user.check_password(password):
        token = create_access_token(identity=user.id)
        if not user.profile:
            profile = Profile(user_id=user.id)
            db.session.add(profile)
            db.session.commit()
        return jsonify({'token': token, 'user_id': user.id, 'message': 'Login successful!'}), 200
    else:
        return jsonify({'error': 'Invalid email or password'}), 401


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

        if 'avatar' not in request.files:
            return jsonify({'error': 'No avatar part in the request'}), 400

        file = request.files['avatar']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_PROFILE_FOLDER'], filename)
            file.save(file_path)
            user.profile.profile_picture = filename
        else:
            return jsonify({'error': 'Invalid file type'}), 400

        profile.bio = request.form.get('bio')
        profile.age = request.form.get('age')
        # profile.nationality = data.get('nationality')
        # profile.height = data.get('height')
        profile.gender = request.form.get('gender')
        profile.latitude = request.form.get('latitude')
        profile.longitude = request.form.get('longitude')

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
                'latitude': profile.latitude,
                'longitude': profile.longitude,
                'profile_picture': profile.profile_picture
            }
            return jsonify(profile_data), 200
        return jsonify({'message': 'Profile not found.'}), 404


@main.route('/users', methods=['GET'])
@jwt_required()
def users():
    radius = float(request.args.get('radius', 0))

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    current_user_profile = user.profile

    if not current_user_profile:
        return jsonify({"error": "Profile not found"}), 404

    current_lat = current_user_profile.latitude
    current_lon = current_user_profile.longitude

    users = User.query.all()
    users_list = []

    for user in users:
        profile = user.profile  # Предполагается, что у пользователя есть связь с профилем
        if profile:
            # Фильтрация по радиусу
            if radius > 0:
                if current_lon is not None and current_lat is not None and profile.latitude is not None and profile.longitude is not None:
                    distance = haversine(current_lat, current_lon, profile.latitude, profile.longitude)
                    if distance > radius:
                        continue

            existing_like = Match.query.filter_by(user_id=user_id, liked_user_id=user.id).first()
            if existing_like:
                continue

            user_info = {
                'id' : user.id,
                'username': user.username,
                'email': user.email,
                'bio': profile.bio,
                'age': profile.age,
                'gender': profile.gender,
                'profile_picture': profile.profile_picture,
                'latitude': profile.latitude,
                'longitude': profile.longitude,
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
            file.save(os.path.join(current_app.config['UPLOAD_MEDIA_FOLDER'], filename))
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
    matches = Match.query.filter_by(user_id=user_id, is_mutual=False).all() #FOR DEBUF mutual FALSE
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