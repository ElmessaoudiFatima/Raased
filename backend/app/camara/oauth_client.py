"""
Client OAuth 2.0 pour Number Verification (flow CAMARA 3-legged).

Séparé de CamaraClient (client.py) : ce flow traverse TROIS hosts distincts,
confirmés empiriquement, jamais par analogie :

1. Découverte (client_credentials, well-known)
   → NUMBER_VERIFICATION_OAUTH_DISCOVERY_URL (network-as-code.p-eu.rapidapi.com)
2. Authorization / Token (retournés dynamiquement par well-known)
   → auth.eu.nac.nokia.io — CONFIRMÉ mais volontairement jamais codé en dur
   ici : toujours relire la réponse well-known à chaque flow, au cas où
   Nokia change cette valeur selon région/environnement.
3. Appel final verify/device-phone-number
   → CAMARA_BASE_URL (network-as-code.p-eu.apihub.nokia.io), via CamaraClient
   existant, avec header Authorization: Bearer ajouté en plus des headers
   habituels.

Le header x-rapidapi-key/x-rapidapi-host (CAMARA_API_KEY/CAMARA_API_HOST)
est identique sur les trois hosts — confirmé par test curl direct.

Statut de ce fichier :
- get_client_credentials() et get_well_known_config() : testés en live
  (Docker) contre Nokia, fonctionnels.
- build_fast_flow_authorization_url() : logique de construction pure,
  suit exactement la doc officielle Nokia (fast flow). Testable
  indépendamment du réseau, mais son USAGE réel (redirection utilisateur,
  réception du callback) dépend de NUMBER_VERIFICATION_REDIRECT_URI —
  non testé tant que Cloudflare Tunnel n'est pas en place.
- Rien d'autre n'est implémenté ici pour l'instant (exchange fast-flow,
  verify) : ajouté dans une session ultérieure une fois le tunnel actif.

Number Verification V2 (SIM-based, Android Credential Manager) est
volontairement hors scope : nécessite une app Android native avec Google
Play Services pour jouer le rôle de pass-through du SD-JWT. Raased n'a
pas d'app mobile utilisateur dans son architecture (trackers IoT, pas
d'app end-user) — V2 ne correspond à aucun cas d'usage réel du projet.
"""
import uuid
import httpx
from app.core.config import get_settings

settings = get_settings()


def _discovery_headers() -> dict:
    return {
        "X-RapidAPI-Host": settings.CAMARA_API_HOST,
        "X-RapidAPI-Key": settings.CAMARA_API_KEY,
    }


async def get_client_credentials() -> dict:
    """
    GET /oauth2/v1/auth/clientcredentials
    Retourne {"client_id": ..., "client_secret": ...}.
    Testé en live (Docker), voir commit.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.NUMBER_VERIFICATION_OAUTH_DISCOVERY_URL}/oauth2/v1/auth/clientcredentials",
            headers=_discovery_headers(),
        )
    response.raise_for_status()
    return response.json()


async def get_well_known_config() -> dict:
    """
    GET /.well-known/openid-configuration
    Retourne authorization_endpoint, token_endpoint, fast_flow_csp_auth_endpoint.
    Ces URLs pointent vers auth.eu.nac.nokia.io (confirmé empiriquement) —
    ne jamais coder ce host en dur ailleurs dans le code : toujours relire
    cette réponse en amont de chaque flow d'autorisation.
    Testé en live (Docker), voir commit.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.NUMBER_VERIFICATION_OAUTH_DISCOVERY_URL}/.well-known/openid-configuration",
            headers=_discovery_headers(),
        )
    response.raise_for_status()
    return response.json()


def build_fast_flow_authorization_url(
    fast_flow_csp_auth_endpoint: str,
    client_id: str,
    phone_number: str,
    state: str | None = None,
    nonce: str | None = None,
) -> tuple[str, str, str]:
    """
    Construit l'URL d'autorisation Fast flow, à ouvrir par l'utilisateur
    sur son appareil mobile (jamais appelée depuis le backend directement).

    Fast flow choisi plutôt que Standard : évite l'échange de token +
    décodage/validation du id_token côté nous (Nokia le fait pour nous
    quand on appelle verify avec code+state). Moins de surface d'erreur
    pour la Phase 1.

    state et nonce sont générés si non fournis (uuid4) — DOIVENT être
    stockés côté serveur (session) par l'appelant pour validation ultérieure
    au moment du callback. Cette fonction ne fait AUCUNE persistance elle-même.

    Retourne (url, state, nonce) — l'appelant est responsable de stocker
    state/nonce avant de rediriger l'utilisateur.

    NON TESTÉ EN CONDITIONS RÉELLES : la construction suit la doc officielle
    Nokia à la lettre, mais aucune redirection réelle n'a été effectuée
    (dépend de NUMBER_VERIFICATION_REDIRECT_URI, voir docstring du module).
    """
    if not settings.NUMBER_VERIFICATION_REDIRECT_URI:
        raise ValueError(
            "NUMBER_VERIFICATION_REDIRECT_URI n'est pas configuré. "
            "Ce flow nécessite une URL publique joignable (Cloudflare Tunnel) "
            "pour recevoir le callback OAuth. Voir docstring du module."
        )

    state = state or str(uuid.uuid4())
    nonce = nonce or str(uuid.uuid4())

    params = {
        "scope": "dpv:FraudPreventionAndDetection number-verification:verify",
        "state": state,
        "response_type": "code",
        "prompt": "none",
        "client_id": client_id,
        "redirect_uri": settings.NUMBER_VERIFICATION_REDIRECT_URI,
        "login_hint": phone_number,
        "nonce": nonce,
    }

    query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    url = f"{fast_flow_csp_auth_endpoint}?{query}"
    return url, state, nonce