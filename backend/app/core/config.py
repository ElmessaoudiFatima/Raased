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
    FRONTEND_URL: str = "https://app.raased.ma"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://raased:raased@localhost:5432/raased"

    # --- CAMARA / Nokia Network-as-Code ---
    CAMARA_BASE_URL: str = "https://network-as-code.p-eu.apihub.nokia.io"
    CAMARA_API_KEY: str = "CHANGE_ME"
    CAMARA_API_HOST: str = "network-as-code.nokia.rapidapi.com"
    CAMARA_SANDBOX_MODE: bool = True
    CAMARA_WEBHOOK_SECRET: str = "CHANGE_ME"


    # --- Number Verification (OAuth 2.0 3-legged) ---
    # Host de DÉCOUVERTE uniquement (clientcredentials + well-known config).
    # Distinct de CAMARA_BASE_URL par nécessité : confirmé empiriquement que
    # ces deux endpoints vivent sur network-as-code.p-eu.rapidapi.com, alors
    # que tous les autres wrappers (congestion, qod, sim_swap, device_swap...)
    # et le verify final de Number Verification lui-même appellent
    # CAMARA_BASE_URL (...apihub.nokia.io). Ne pas fusionner ces deux valeurs.
    # Le header CAMARA_API_KEY/CAMARA_API_HOST reste identique sur les trois
    # hosts impliqués dans ce flow (confirmé par test curl direct).
    NUMBER_VERIFICATION_OAUTH_DISCOVERY_URL: str = "https://network-as-code.p-eu.rapidapi.com"

    # URL publique (Cloudflare Tunnel) où Nokia redirige après consentement
    # utilisateur sur mobile. Vide par défaut : toute fonction qui en dépend
    # doit lever une erreur explicite si non configurée, plutôt que d'échouer
    # silencieusement ou de planter avec une erreur réseau confuse.
    NUMBER_VERIFICATION_REDIRECT_URI: str = ""


    # --- LLM providers (agent reasoning layer) ---
    LLM_PROVIDER: str = "gemini"  # groq | openai | gemini
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # --- Agent thresholds (business rules, deterministic layer) ---
    CONGESTION_ALERT_THRESHOLD: float = 0.7
    CONGESTION_CONFIDENCE_MIN: float = 0.6
    FALSE_POSITIVE_MAX_RATE: float = 0.15


    # Seuil interne au wrapper Congestion Insights (congestion.py) : filtre
    # appliqué DIRECTEMENT sur confidenceLevel brut renvoyé par CAMARA, échelle
    # entière 1-99 (non documentée publiquement, confirmée empiriquement en
    # sandbox). Distinct de CONGESTION_CONFIDENCE_MIN ci-dessus par nécessité :
    # les deux variables ne partagent ni l'échelle ni le type, et les confondre
    # casse silencieusement soit le filtre de démo, soit rules.py.
    CAMARA_RAW_CONFIDENCE_MIN: int = 40

    # --- Sécurité : détection d'usurpation de position ---
    POSITION_SPOOFING_THRESHOLD_KM: float = 5.0


    # --- Email / SMTP ---
    SMTP_HOST: str = ""              # vide = mode log (dev)
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM_NAME: str = "Raased"

    # --- Security ---
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
