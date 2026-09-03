"""
Wrapper pour l'API Location Retrieval — CAMARA / Nokia Network-as-Code.

Contrairement à QoD (cycle stateful avec sessionId), Location Retrieval est
un appel unique, sans état à maintenir entre les requêtes.

Endpoint confirmé via playground Nokia (Code Snippets / cURL) :
POST /location-retrieval/v0/retrieve

Important (voir Explication_API.pdf section 4.2) :
- L'API ne renvoie PAS un point GPS exact, mais un CERCLE (area.center +
  area.radius). Toute la logique de "zone à risque" doit raisonner en
  intersection de cercles, pas en coordonnées ponctuelles (voir section 8
  du document de référence : distance(centre1, centre2) <= rayon1 + rayon2).
- Le rayon observé en test Phase 1 (hackathon, un seul device testé) était
  de 1000 mètres, présenté explicitement comme "valeur observée", pas comme
  une constante universelle. À reconfirmer ici sur plusieurs numéros sandbox :
  le rayon est-il fixe, ou varie-t-il comme confidenceLevel sur Congestion
  Insights (pseudo-aléatoire) ?
- maxAge borne l'ancienneté acceptable de la dernière position connue —
  sans ce paramètre, la position pourrait dater de plusieurs minutes/heures.

⚠️ NON VALIDÉ EMPIRIQUEMENT (à confirmer par test réel) :
Les noms de champs exacts de la réponse (area.center.latitude/longitude,
area.radius, lastLocationTime) proviennent du document de référence Phase 1
mais doivent être reconfirmés par un appel réel dans CE sandbox.

DÉCOUVERTE EMPIRIQUE — réponse statique sur tous les devices (10 numéros testés) :
Les 10 numéros sandbox disponibles (+99999991000 à +99999990504, +36719991000)
renvoient TOUS exactement les mêmes coordonnées (lat 47.486276..., lon
19.079156...) et le même rayon (1000m). Seul lastLocationTime varie, mais son
écart entre appels correspond exactement au délai entre les requêtes du script
de test (~0.3-0.6s) — ce n'est donc pas une position mise à jour par device,
c'est l'horodatage du traitement de la requête.

CONCLUSION : le sandbox Nokia renvoie une réponse canned/statique pour
Location Retrieval, indépendamment du device interrogé. Comportement cohérent
avec l'observation déjà documentée sur Congestion Insights (section 4.1 du
document de référence Phase 1 : fetch et createSubscription renvoyaient une
réponse identique). Ne JAMAIS présenter cette donnée comme une "localisation
en temps réel différenciée par tracker" dans la démo ou devant le jury —
formuler plutôt : "nous avons validé que l'appel fonctionne et que le format
de réponse (cercle + timestamp) est correctement exploité par notre pipeline ;
la variation réelle par device serait observable uniquement en production
avec de vrais devices sur un vrai réseau."
"""
from app.camara.client import get_camara_client

LOCATION_RETRIEVAL_ENDPOINT = "/location-retrieval/v0/retrieve"


async def fetch_location(phone_number: str, max_age: int = 60) -> dict:
    """
    Récupère la dernière position réseau connue d'un tracker, sous forme
    de cercle (pas un point GPS exact).

    max_age : ancienneté maximale acceptable de la position, en secondes.

    Retourne le dict brut tel que renvoyé par l'API (structure à confirmer
    empiriquement, voir avertissement en tête de fichier).
    """
    client = get_camara_client()
    payload = {
        "device": {"phoneNumber": phone_number},
        "maxAge": max_age,
    }
    return await client.post(LOCATION_RETRIEVAL_ENDPOINT, json=payload)