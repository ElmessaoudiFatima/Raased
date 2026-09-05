"""
Wrapper pour l'API SIM Swap (CAMARA / Nokia Network-as-Code).

Particularités confirmées en sandbox (tests équipe, doc officielle Nokia) :

- Path différent du pattern utilisé par congestion.py : cette API passe par
  /passthrough/camara/v1/sim-swap/sim-swap/v0/... (segment "sim-swap" doublé,
  confirmé par la doc officielle Nokia, pas une erreur de copier-coller).
  Ne pas supposer que tous les wrappers CAMARA suivent le même pattern
  d'URL sur ce host -- à vérifier individuellement pour chaque nouvelle API.

- Payload à plat : {"phoneNumber": ..., "maxAge": ...}, SANS le wrapper
  "device": {...} utilisé par congestion.py / location.py / qod.py.
  Erreur silencieuse garantie si on copie ce pattern par réflexe.

- maxAge est exprimé en HEURES (confirmé par la doc officielle Nokia :
  "past N hours"), pas en secondes comme pour Location Retrieval. Un
  maxAge=240 signifie "swap survenu dans les 240 dernières heures" (10 jours).

- Testé avec maxAge=1 (1 heure) sur +99999991000 : renvoie toujours
  swapped=true. Comme pour Congestion Insights, ça suggère une donnée
  canned/statique du sandbox plutôt qu'un calcul dynamique réel -- à ne
  pas présenter comme "temps réel" sans réserve. Point non bloquant pour
  la Phase 1.

- Erreur device inconnu confirmée en test :
  {"status": 404, "code": "IDENTIFIER_NOT_FOUND", "message": "Device
  identifier not found."} -- levée par CamaraClient sous forme de
  CamaraAPIError(404, ...). Cette fonction ne catch pas l'erreur : c'est
  au code appelant (rules.py / trust logic) de décider quoi en faire.



Endpoints d'abonnement/webhook NON codés dans ce fichier (volontaire) :
  - createSimSwapSubscription (POST, avec "sink" pour webhook)
  - retrieveSubscription / retrieveSubscriptionList (GET)
  - deleteSubscription (DELETE)

Raison : ces endpoints nécessitent un sink (URL publique joignable) pour
recevoir les événements CAMARA -- infrastructure pas encore en place
(même blocage que Geofencing).
Confirmé en test que Nokia rejette un sink non résolvable avant même de
vérifier le device (400 INVALID_SINK).

À reprendre quand Cloudflare Tunnel sera en place pour exposer une URL
publique -- prévu au moment de coder Number Verification (qui a un besoin
similaire de callback public via redirect_uri OAuth, mécanisme différent
du webhook CAMARA mais même dépendance infra).
"""
from app.camara.client import get_camara_client

SIM_SWAP_CHECK_ENDPOINT = "/passthrough/camara/v1/sim-swap/sim-swap/v0/check"
SIM_SWAP_DATE_ENDPOINT = "/passthrough/camara/v1/sim-swap/sim-swap/v0/retrieve-date"


async def check_sim_swap(phone_number: str, max_age_hours: int = 240) -> bool:
    """
    Vérifie si un SIM swap a eu lieu pour ce numéro dans les max_age_hours
    dernières heures.

    Retourne le booléen brut renvoyé par l'API (clé "swapped").
    Ne catch pas CamaraAPIError : si le device n'est pas reconnu (404
    IDENTIFIER_NOT_FOUND), l'exception remonte telle quelle.
    """
    client = get_camara_client()
    payload = {"phoneNumber": phone_number, "maxAge": max_age_hours}
    response = await client.post(SIM_SWAP_CHECK_ENDPOINT, json=payload)
    return response["swapped"]


async def get_last_sim_swap_date(phone_number: str) -> str | None:
    """
    Récupère le timestamp ISO 8601 du dernier SIM swap connu pour ce numéro.

    Retourne la chaîne brute telle que renvoyée par l'API (ex.
    "2026-09-05T16:52:12.443036Z"), ou None si l'API ne renvoie pas de
    valeur pour ce champ. Pas de parsing datetime ici : la conversion,
    si nécessaire, est la responsabilité du code appelant (comme pour
    get_most_recent_interval() dans congestion.py, qu'on ne veut pas
    dupliquer ici sans besoin confirmé).

    Ne catch pas CamaraAPIError : device inconnu -> 404 IDENTIFIER_NOT_FOUND
    remonte tel quel.
    """
    client = get_camara_client()
    payload = {"phoneNumber": phone_number}
    response = await client.post(SIM_SWAP_DATE_ENDPOINT, json=payload)
    return response.get("latestSimChange")