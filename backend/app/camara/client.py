"""
Client HTTP générique pour les API CAMARA (Nokia Network-as-Code).

Centralise :
- l'authentification (clé API),
- les retries (tenacity) sur erreurs réseau / statuts 5xx / 429,
- le logging des appels sortants,
- la traduction des erreurs en `CamaraAPIError`.

Les wrappers métier (trust.py, congestion.py, geofencing.py, etc.) doivent
passer par `camara_post` / `camara_get` plutôt que d'instancier httpx
directement, pour garder ce comportement homogène partout.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_TIMEOUT_SECONDS = 10.0


class CamaraAPIError(Exception):
    """Levée quand un appel CAMARA échoue après retries, ou renvoie une erreur non retryable."""

    def __init__(self, message: str, status_code: int | None = None, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class _RetryableStatusError(Exception):
    """Erreur interne utilisée uniquement pour déclencher un retry tenacity sur certains status codes."""


def _raise_if_retryable(response: httpx.Response) -> None:
    if response.status_code in _RETRYABLE_STATUS_CODES:
        raise _RetryableStatusError(f"CAMARA a répondu {response.status_code}, retry")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, _RetryableStatusError)),
)
async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-key": settings.CAMARA_API_KEY,
        "x-rapidapi-host": settings.CAMARA_API_HOST,
    }
    async with httpx.AsyncClient(base_url=settings.CAMARA_BASE_URL, timeout=_TIMEOUT_SECONDS) as client:
        response = await client.request(method, path, json=json_body, params=params, headers=headers)

    _raise_if_retryable(response)
    return response


async def _handle_response(response: httpx.Response, path: str) -> dict[str, Any]:
    if response.status_code >= 400:
        logger.warning("CAMARA a renvoyé %s pour %s : %s", response.status_code, path, response.text)
        raise CamaraAPIError(
            f"CAMARA a renvoyé {response.status_code} pour {path}",
            status_code=response.status_code,
            response_body=response.text,
        )
    return response.json()


async def camara_post(path: str, json_body: dict[str, Any]) -> dict[str, Any]:
    """POST générique vers un endpoint CAMARA. Lève CamaraAPIError sur échec définitif."""
    if settings.CAMARA_SANDBOX_MODE:
        logger.debug("CAMARA_SANDBOX_MODE actif : appel vers le sandbox pour %s", path)

    try:
        response = await _request("POST", path, json_body=json_body)
    except _RetryableStatusError as exc:
        raise CamaraAPIError(f"Échec CAMARA après retries sur {path}: {exc}") from exc
    except httpx.TransportError as exc:
        raise CamaraAPIError(f"Erreur réseau CAMARA sur {path}: {exc}") from exc

    return await _handle_response(response, path)


async def camara_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET générique vers un endpoint CAMARA. Lève CamaraAPIError sur échec définitif."""
    try:
        response = await _request("GET", path, params=params)
    except _RetryableStatusError as exc:
        raise CamaraAPIError(f"Échec CAMARA après retries sur {path}: {exc}") from exc
    except httpx.TransportError as exc:
        raise CamaraAPIError(f"Erreur réseau CAMARA sur {path}: {exc}") from exc

    return await _handle_response(response, path)


async def camara_delete(path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    DELETE générique vers un endpoint CAMARA. Lève CamaraAPIError sur échec définitif.

    json_body optionnel : certains endpoints CAMARA (ex: slice deletion sur
    Nokia NaC) exigent un body même sur une requête DELETE, ce qui est
    atypique en HTTP mais confirmé par les curl réels du playground
    (--data '{}'). On le rend optionnel pour ne pas forcer un body sur les
    appels DELETE qui n'en ont pas besoin (ex: QoD deleteSession).
    """
    try:
        response = await _request("DELETE", path, json_body=json_body)
    except _RetryableStatusError as exc:
        raise CamaraAPIError(f"Échec CAMARA après retries sur {path}: {exc}") from exc
    except httpx.TransportError as exc:
        raise CamaraAPIError(f"Erreur réseau CAMARA sur {path}: {exc}") from exc

    if response.status_code == 204:
        return {}
    return await _handle_response(response, path)