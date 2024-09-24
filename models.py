from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import func
from geoalchemy2.functions import ST_MakePoint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index
from datetime import date
from sqlalchemy import or_
from extensions import db
import time

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_google_user = db.Column(db.Boolean, default=False)
    coordinates = db.Column(Geometry(geometry_type='POINT', srid=4326), default=func.ST_SetSRID(func.ST_MakePoint(0, 0), 4326), index=True)  # WGS 84
    profile = db.relationship('Profile', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False


class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    nationality = db.Column(db.Text, nullable=True)
    country = db.Column(db.Text, nullable=True)
    city = db.Column(db.Text, nullable=True)
    age = db.Column(db.Integer, nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    profile_picture = db.Column(db.String(100), nullable=True, default='default.jpeg')
    questions_answers = db.Column(JSONB, nullable=True)

    __table_args__ = (
        Index('idx_questions_answers', questions_answers, postgresql_using='gin'),
    )

    @staticmethod
    def search_by_any_answer(answers):
        filters = [Profile.questions_answers[(question)].astext == answer for question, answer in answers.items()]
        # Используем OR для фильтрации по любому совпадению
        results = Profile.query.filter(or_(*filters)).all()
        return results

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    liked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    is_mutual = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=True)

    user = db.relationship('User', foreign_keys=[user_id], backref='likes_given')
    liked_user = db.relationship('User', foreign_keys=[liked_user_id], backref='likes_received')

    __table_args__ = (
        Index('idx_user_liked_user', user_id, liked_user_id),
    )
