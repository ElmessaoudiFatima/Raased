"""
Wrapper pour l'API Device Swap (CAMARA / Nokia Network-as-Code).

Structure identique à sim_swap.py (payload à plat, maxAge en heures,
même format d'erreur 404), à une différence près : version v1 (pas v0).
Voir doc officielle Nokia Network-as-Code, page Device Swap.

Particularités confirmées :

- Path : /passthrough/camara/v1/device-swap/device-swap/v1/... (v1, pas v0
  comme SIM Swap -- vérifié individuellement, ne pas supposer la version
  d'une nouvelle API CAMARA par analogie avec une autre déjà codée).

- Payload à plat : {"phoneNumber": ..., "maxAge": ...}, sans wrapper
  "device". Identique à sim_swap.py.

- maxAge en heures, range documenté 1-2400, défaut 240 si omis
  (confirmé par doc officielle Nokia, pas juste observé empiriquement
  comme pour sim_swap.py).

- Device de test +99999991001 confirmé renvoyer swapped=false (voir doc
  officielle) -- contrairement à sim_swap.py où on n'a testé que le cas
  swapped=true sur le device disponible.

- Erreur 404 IDENTIFIER_NOT_FOUND confirmée en test pour device totalement
  inconnu du simulateur (même comportement que sim_swap.py).

- Erreur 422 documentée par Nokia (numéro jamais associé à un device /
  aucune donnée disponible) mais PAS testée en sandbox par l'équipe --
  à traiter comme une hypothèse de la doc officielle, pas un fait
  vérifié empiriquement. CamaraAPIError la propagera si elle survient,
  aucune gestion spéciale ajoutée sans l'avoir observée.

- retrieve_date peut renvoyer null (jamais swappé) ou la date
  d'installation initiale de la SIM (pas nécessairement une vraie date
  de swap) -- selon la doc officielle Nokia. Le code ne fait aucune
  distinction entre ces deux cas, il retourne la valeur brute.
"""
from app.camara.client import get_camara_client

DEVICE_SWAP_CHECK_ENDPOINT = "/passthrough/camara/v1/device-swap/device-swap/v1/check"
DEVICE_SWAP_DATE_ENDPOINT = "/passthrough/camara/v1/device-swap/device-swap/v1/retrieve-date"


async def check_device_swap(phone_number: str, max_age_hours: int = 240) -> bool:
    """
    Vérifie si un Device Swap (changement d'IMEI associé à ce numéro) a eu
    lieu dans les max_age_hours dernières heures (1-2400, défaut 240 selon
    doc officielle Nokia).

    Retourne le booléen brut renvoyé par l'API (clé "swapped").
    Ne catch pas CamaraAPIError : device inconnu (404) ou aucune donnée
    disponible (422, non testé) remontent tels quels.
    """
    client = get_camara_client()
    payload = {"phoneNumber": phone_number, "maxAge": max_age_hours}
    response = await client.post(DEVICE_SWAP_CHECK_ENDPOINT, json=payload)
    return response["swapped"]


async def get_last_device_swap_date(phone_number: str) -> str | None:
    """
    Récupère le timestamp ISO 8601 du dernier Device Swap connu pour ce
    numéro.

    Selon la doc officielle Nokia, peut retourner None (jamais swappé) ou
    la date d'installation initiale de la SIM -- ces deux cas ne sont PAS
    distingués ici, la valeur brute est retournée telle quelle.

    Ne catch pas CamaraAPIError.
    """
    client = get_camara_client()
    payload = {"phoneNumber": phone_number}
    response = await client.post(DEVICE_SWAP_DATE_ENDPOINT, json=payload)
    return response.get("latestDeviceChange")