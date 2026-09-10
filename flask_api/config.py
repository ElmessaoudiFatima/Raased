import os
from datetime import timedelta


class Config:
    APP_NAME = os.getenv("APP_NAME", "Raased Platform API")
    ENV = os.getenv("ENV", "development")

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://raased:raased@localhost:5432/raased_platform",
    )
    AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "1") == "1"
    AUTO_SEED = os.getenv("AUTO_SEED", "1") == "1"

    SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    PASSWORD_TOKEN_EXPIRE_MINUTES = int(os.getenv("PASSWORD_TOKEN_EXPIRE_MINUTES", "15"))

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", "10"))
    OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    INVITATION_TTL_HOURS = int(os.getenv("INVITATION_TTL_HOURS", "48"))

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") == "1"
    EMAIL_FROM = os.getenv("EMAIL_FROM", "no-reply@raased.ma")
    EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Raased")

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(os.path.dirname(__file__), "uploads"))

    CORS_ORIGINS = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if o.strip()
    ]