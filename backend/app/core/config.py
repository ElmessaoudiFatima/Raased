"""
Application configuration.
Loaded from environment variables (.env) via pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "Raased API"
    ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://raased:raased@localhost:5432/raased"

    # --- CAMARA / Nokia Network-as-Code ---
    CAMARA_BASE_URL: str = "https://network-as-code.p-eu.apihub.nokia.io"
    CAMARA_API_KEY: str = "CHANGE_ME"
    CAMARA_API_HOST: str = "network-as-code.nokia.rapidapi.com"
    CAMARA_SANDBOX_MODE: bool = True

    # --- LLM providers (agent reasoning layer) ---
    LLM_PROVIDER: str = "gemini"  # groq | openai | gemini
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # --- Agent thresholds (business rules, deterministic layer) ---
    CONGESTION_ALERT_THRESHOLD: float = 0.7
    CONGESTION_CONFIDENCE_MIN: float = 0.6
    FALSE_POSITIVE_MAX_RATE: float = 0.15

    # --- Security ---
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()