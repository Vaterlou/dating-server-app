# extensions.py
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

socketio = SocketIO()
db = SQLAlchemy()
jwt = JWTManager()
