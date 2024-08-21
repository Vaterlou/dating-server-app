from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_MakePoint

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_google_user = db.Column(db.Boolean, default=False)
    coordinates = db.Column(Geometry(geometry_type='POINT', srid=4326), default=ST_MakePoint(0, 0), index=True)  # WGS 84
    profile = db.relationship('Profile', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password:
            return check_password_hash(self.password_hash, password)
        return False


class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    nationality = db.Column(db.Text, nullable=True)
    country = db.Column(db.Text, nullable=True)
    # city = db.Column(db.Text, nullable=True)
    age = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    profile_picture = db.Column(db.String(100), nullable=True, default='default.jpeg')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_msgs')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_msgs')


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    liked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_mutual = db.Column(db.Boolean, default=False)

    user = db.relationship('User', foreign_keys=[user_id], backref='likes_given')
    liked_user = db.relationship('User', foreign_keys=[liked_user_id], backref='likes_received')
