"""
Wrapper pour Geofencing (CAMARA Geofencing Subscriptions).

Endpoint confirmé empiriquement via le playground Nokia (RapidAPI) :
POST/GET/DELETE sur /geofencing-subscriptions/v0.3/subscriptions
(noter le v0.3, différent des autres APIs qui utilisent v0/v1).

Point critique confirmé :
Nokia exige un `sink` (URL de webhook) réellement joignable publiquement.
Un domaine fictif est rejeté immédiatement avec 400 INVALID_SINK, AVANT
même que le device ne soit vérifié.

Champ identifiant confirmé par la réponse réelle du playground : `id`
(pas `name`, pas `subscriptionId` — contrairement à Slicing où c'était `name`).

DELETE nécessite un body vide explicite {} (confirmé par le curl officiel
avec --data '{}'), même pattern que delete_slice().

Authentification des notifications — sinkCredential :
Le payload de création accepte un champ optionnel `sinkCredential`
(credentialType/identifier/secret). Testé empiriquement : Nokia répercute
alors ce secret sous forme d'un header `Authorization: Basic
base64(identifier:secret)` sur chaque notification envoyée au sink. Ce
mécanisme, propre à chaque subscription, constitue une alternative plus
granulaire que la vérification HMAC générique appliquée par défaut sur
l'endpoint webhook (voir app/api/v1/webhooks.py pour la documentation
complète du comportement observé et de la conception d'intégration
associée). Le paramètre n'est pas exposé dans
build_geofence_subscription_payload() dans cette version.
"""
from typing import Any

from app.camara.client import camara_post, camara_get, camara_delete
from app.core.config import get_settings

settings = get_settings()

GEOFENCING_BASE_PATH = "/geofencing-subscriptions/v0.3/subscriptions"


def build_geofence_subscription_payload(
    phone_number: str,
    latitude: float,
    longitude: float,
    radius: int,
    event_types: list[str] | None = None,
    subscription_max_events: int = 10,
    subscription_expire_time: str = "2045-03-22T05:40:58.469Z",
    initial_event: bool = True,
) -> dict[str, Any]:
    """
    Construit le payload de création de subscription geofencing.

    event_types par défaut : area-entered uniquement (cas d'usage principal
    pour Raased — détecter l'entrée dans une zone à risque). Un seul type
    d'événement par subscription semble être la norme (doc Nokia : "only
    one event type per subscription is enforced").

    initial_event=True déclenche un événement immédiat reflétant l'état
    actuel dès la création — utile pour valider la réception webhook sans
    attendre un vrai déplacement du device.
    """
    if event_types is None:
        event_types = ["org.camaraproject.geofencing-subscriptions.v0.area-entered"]

    return {
        "protocol": "HTTP",
        "sink": settings.CAMARA_WEBHOOK_SINK_URL,
        "types": event_types,
        "config": {
            "subscriptionDetail": {
                "device": {"phoneNumber": phone_number},
                "area": {
                    "areaType": "CIRCLE",
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius,
                },
            },
            "initialEvent": initial_event,
            "subscriptionMaxEvents": subscription_max_events,
            "subscriptionExpireTime": subscription_expire_time,
        },
    }


async def create_geofence_subscription(payload: dict[str, Any]) -> dict[str, Any]:
    """
    POST /geofencing-subscriptions/v0.3/subscriptions

    Réponse confirmée (playground) : contient un champ `id` (UUID) à utiliser
    pour get/delete, ainsi que `startsAt`. En cas de sink non résolvable
    publiquement, Nokia renvoie 400 INVALID_SINK avant toute vérification
    du device (confirmé empiriquement).
    """
    return await camara_post(GEOFENCING_BASE_PATH, payload)


async def get_geofence_subscription(subscription_id: str) -> dict[str, Any]:
    """GET /geofencing-subscriptions/v0.3/subscriptions/{id}"""
    return await camara_get(f"{GEOFENCING_BASE_PATH}/{subscription_id}")


async def get_all_geofence_subscriptions() -> Any:
    """GET /geofencing-subscriptions/v0.3/subscriptions — liste toutes les subscriptions actives."""
    return await camara_get(GEOFENCING_BASE_PATH)


async def delete_geofence_subscription(subscription_id: str) -> dict[str, Any]:
    """
    DELETE /geofencing-subscriptions/v0.3/subscriptions/{id}

    Body vide explicite {} requis (confirmé par le curl officiel Nokia
    --data '{}'), même pattern que delete_slice().
    """
    return await camara_delete(f"{GEOFENCING_BASE_PATH}/{subscription_id}", json_body={})