"""
Client HTTP de base pour toutes les APIs CAMARA / Nokia Network-as-Code.
Centralise l'authentification, l'URL de base, et la gestion des erreurs.
Tous les modules (congestion.py, qod.py, location.py, ...) utilisent ce client.
"""
import httpx
from app.core.config import get_settings

settings = get_settings()


class CamaraAPIError(Exception):
    """Erreur levée quand un appel CAMARA échoue."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"CAMARA API error {status_code}: {detail}")


class CamaraClient:
    """
    Client HTTP asynchrone pour appeler les APIs CAMARA via Nokia Network-as-Code.
    Usage :
        client = CamaraClient()
        response = await client.post("/congestion-insights/v1/subscriptions", json=payload)
    """

    def __init__(self):
        self.base_url = settings.CAMARA_BASE_URL
        self.headers = {
            "Content-Type": "application/json",
            "x-rapidapi-key": settings.CAMARA_API_KEY,
            "x-rapidapi-host": settings.CAMARA_API_HOST,
        }

    async def post(self, path: str, json: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}{path}",
                headers=self.headers,
                json=json,
            )
        return self._handle_response(response)

    async def get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                params=params,
            )
        return self._handle_response(response)

    async def delete(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.delete(
                f"{self.base_url}{path}",
                headers=self.headers,
            )
        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict:
        if response.status_code >= 400:
            raise CamaraAPIError(response.status_code, response.text)
        if response.status_code == 204:  # No Content (souvent sur delete)
            return {}
        return response.json()


def get_camara_client() -> CamaraClient:
    return CamaraClient()