"""
Wrapper pour l'API Congestion Insights (CAMARA / Nokia Network-as-Code).

Important (validé en sandbox, tests équipe) :
- La réponse est un TABLEAU d'intervalles temporels, pas une valeur unique.
  On doit toujours sélectionner l'intervalle le plus récent (timeIntervalStop max).
- confidenceLevel est un entier dont l'échelle exacte n'est pas documentée
  publiquement (valeurs observées en test : 1 à 99). Le seuil utilisé
  (CAMARA_RAW_CONFIDENCE_MIN) est un choix arbitraire de l'équipe pour la
  démo, pas une propriété universelle de CAMARA.
- confidenceLevel peut être absent de certains intervalles (observé en test
  sur +36719991000) -> le code doit gérer ce cas sans planter.
- Cette échelle brute (1-99) est distincte de CONGESTION_CONFIDENCE_MIN
  (0.0-1.0) utilisée par rules.py côté agent. normalize_confidence_level()
  fait la conversion avant toute écriture en base, pour respecter le schéma
  DECIMAL 0-1 de congestion_events.confidence_level.
"""
from datetime import datetime
from app.camara.client import get_camara_client
from app.core.config import get_settings

settings = get_settings()

CONGESTION_ENDPOINT = "/congestion-insights/v0/query"


async def fetch_congestion(
    phone_number: str,
    notification_url: str = "http://example.com/notify",
    notification_auth_token: str = "dummy-token",
) -> list[dict]:
    """
    Interroge Congestion Insights pour un tracker donné.
    Retourne la liste brute d'intervalles telle que renvoyée par l'API.
    """
    client = get_camara_client()
    payload = {
        "device": {"phoneNumber": phone_number},
        "webhook": {
            "notificationUrl": notification_url,
            "notificationAuthToken": notification_auth_token,
        },
        "subscriptionExpireTime": "2045-04-12T14:09:33+05:00",
    }
    response = await client.post(CONGESTION_ENDPOINT, json=payload)
    return response if isinstance(response, list) else response.get("data", [])


def get_most_recent_interval(intervals: list[dict]) -> dict | None:
    """
    Sélectionne l'intervalle le plus récent d'après timeIntervalStop.
    Retourne None si la liste est vide.
    """
    if not intervals:
        return None
    return max(
        intervals,
        key=lambda i: datetime.fromisoformat(
            i["timeIntervalStop"].replace("Z", "+00:00")
        ),
    )


def normalize_confidence_level(raw: int | None) -> float | None:
    """
    Convertit confidenceLevel CAMARA (entier 1-99, échelle non documentée
    publiquement) vers l'échelle 0.0-1.0 attendue par le schéma DB
    (congestion_events.confidence_level, DECIMAL) et par rules.py.

    Division par 99 (valeur max observée empiriquement en test), pas par 100 :
    choix arbitraire de l'équipe, documenté ici pour éviter toute ambiguïté
    future. Retourne None si raw est None (donnée absente, jamais substituée
    par une valeur par défaut).
    """
    if raw is None:
        return None
    return round(raw / 99, 4)


def is_high_risk(interval: dict | None) -> bool:
    """
    Applique le seuil métier défini par l'équipe :
    congestionLevel == High ET confidenceLevel >= seuil configuré
    (échelle brute CAMARA 1-99, voir CAMARA_RAW_CONFIDENCE_MIN dans config.py).
    Seuil arbitraire, voir config.py pour justification détaillée.
    """
    if interval is None:
        return False
    return (
        interval.get("congestionLevel") == "High"
        and interval.get("confidenceLevel", 0) >= settings.CAMARA_RAW_CONFIDENCE_MIN
    )


async def get_congestion_risk(phone_number: str) -> dict:
    """
    Fonction principale utilisée par le reste de l'agent :
    récupère, sélectionne le plus récent, évalue le risque.

    confidence_normalized est fourni en plus (échelle 0-1) pour toute
    écriture future en base ou consommation par rules.py, sans imposer
    cette conversion aux consommateurs qui n'en ont pas besoin.
    """
    intervals = await fetch_congestion(phone_number)
    latest = get_most_recent_interval(intervals)
    return {
        "raw_intervals": intervals,
        "latest_interval": latest,
        "is_high_risk": is_high_risk(latest),
        "confidence_normalized": normalize_confidence_level(
            latest.get("confidenceLevel") if latest else None
        ),
    }