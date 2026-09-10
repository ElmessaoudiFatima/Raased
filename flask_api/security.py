from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import current_app, jsonify, request

from extensions import db
from models import User


def utcnow():
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _encode(payload: dict) -> str:
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=[current_app.config["JWT_ALGORITHM"]])
    except jwt.PyJWTError:
        return None


def create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "type": "access",
        "exp": utcnow() + timedelta(minutes=current_app.config["ACCESS_TOKEN_EXPIRE_MINUTES"]),
    }
    return _encode(payload)


def create_password_token(user_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "type": "password",
        "exp": utcnow() + timedelta(minutes=current_app.config["PASSWORD_TOKEN_EXPIRE_MINUTES"]),
    }
    return _encode(payload)


def current_user():
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        return None
    payload = _decode(token)
    if not payload or payload.get("type") != "access":
        return None
    try:
        uid = str(payload["sub"])
    except (KeyError, TypeError):
        return None
    return db.session.get(User, uid)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user.is_active:
            return jsonify(error="Authentification requise."), 401
        kwargs["current_user"] = user
        return fn(*args, **kwargs)

    return wrapper


def require_role(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or not user.is_active:
                return jsonify(error="Authentification requise."), 401
            if user.role not in roles:
                return jsonify(error="Vous n'avez pas les droits nécessaires."), 403
            kwargs["current_user"] = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator