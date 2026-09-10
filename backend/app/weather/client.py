"""
Client HTTP générique pour Open-Meteo.

Open-Meteo ne nécessite aucune clé API — juste latitude/longitude. Même
pattern de retry/erreur que app/camara/client.py, pour rester cohérent
avec le reste du projet.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.open-meteo.com/v1/forecast"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_TIMEOUT_SECONDS = 10.0


class WeatherAPIError(Exception):
    """Levée quand un appel Open-Meteo échoue après retries."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class _RetryableStatusError(Exception):
    """Erreur interne utilisée uniquement pour déclencher un retry tenacity."""


def _raise_if_retryable(response: httpx.Response) -> None:
    if response.status_code in _RETRYABLE_STATUS_CODES:
        raise _RetryableStatusError(f"Open-Meteo a répondu {response.status_code}, retry")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, _RetryableStatusError)),
)
async def _request(params: dict[str, Any]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        response = await client.get(_BASE_URL, params=params)
    _raise_if_retryable(response)
    return response


async def get_forecast(latitude: float, longitude: float) -> dict[str, Any]:
    """
    Récupère les conditions météo actuelles pour un point donné.

    Champs demandés : température, vitesse du vent, visibilité (utile pour
    détecter des conditions type tempête de sable), et code météo général.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,wind_speed_10m,visibility,weather_code",
        "timezone": "auto",
    }
    try:
        response = await _request(params)
    except _RetryableStatusError as exc:
        raise WeatherAPIError(f"Échec Open-Meteo après retries : {exc}") from exc
    except httpx.TransportError as exc:
        raise WeatherAPIError(f"Erreur réseau Open-Meteo : {exc}") from exc

    if response.status_code >= 400:
        logger.warning("Open-Meteo a renvoyé %s : %s", response.status_code, response.text)
        raise WeatherAPIError(f"Open-Meteo a renvoyé {response.status_code}", status_code=response.status_code)

    return response.json()
