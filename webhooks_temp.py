"""
Endpoint webhook recevant les événements Nokia CAMARA (Congestion Insights,
Geofencing area-entered / area-left).

Sécurité — mécanisme HMAC générique :
- Chaque requête peut porter une signature HMAC-SHA256 dans le header
  `X-Signature`, calculée sur le corps brut de la requête avec le secret
  partagé `CAMARA_WEBHOOK_SECRET`. Ce mécanisme est générique : il n'est
  pas spécifique à CAMARA et sert de filet de sécurité valable pour tout
  appelant externe utilisant ce même endpoint.
- Toute requête sans signature valide est rejetée avec 401 et journalisée
  dans `audit_logs` (organization_id=None, puisqu'aucune organisation
  n'est résolue à ce stade — voir app/db/models/audit_logs.py).
- L'endpoint est protégé par un rate limit (slowapi) pour limiter l'impact
  d'un flood ou d'un replay.
- CAMARA_WEBHOOK_VERIFY_SIGNATURE=False (dev uniquement) permet de
  bypasser cette vérification : testé empiriquement, le sandbox Nokia
  n'envoie aucun header `X-Signature` lors de la création standard d'une
  subscription. Ce bypass est tracé dans audit_logs
  (action=camara_webhook_signature_bypassed) et loggé en WARNING pour ne
  jamais passer inaperçu.

Mécanisme alternatif validé — sinkCredential (spécifique CAMARA) :
- Le schéma CAMARA de création de subscription (Geofencing, Congestion
  Insights) accepte un champ optionnel `sinkCredential` dans le payload
  de création :
      "sinkCredential": {
          "credentialType": "PLAIN",
          "identifier": "<identifiant>",
          "secret": "<secret>"
      }
  Testé empiriquement contre le sandbox Nokia : la subscription est créée
  normalement (id retourné), et Nokia envoie alors sur chaque notification
  un header `Authorization: Basic base64(identifier:secret)`
  (format RFC 7617) — confirmé par inspection directe des headers reçus
  sur cet endpoint.
- Ce mécanisme est plus fin que le HMAC partagé ci-dessus : le secret est
  propre à chaque subscription plutôt que global à l'application. Une
  fuite de secret n'affecte qu'une seule subscription, et chaque secret
  peut être révoqué individuellement sans impacter les autres.
- Conception de l'intégration (non câblée dans cette version) :
    1. Génération d'un secret aléatoire (`secrets.token_urlsafe`) à la
       création de chaque GeofenceSubscription, transmis dans
       `sinkCredential` et stocké hashé (jamais en clair) dans une colonne
       dédiée du modèle GeofenceSubscription.
    2. Dans ce webhook, résolution de la subscription visée via
       `data.subscriptionId` avant toute vérification d'authenticité,
       puis comparaison en temps constant du secret reçu (décodé du
       header `Authorization: Basic`) avec le hash stocké pour cette
       subscription précise.
    3. Le mécanisme HMAC générique décrit ci-dessus reste disponible en
       parallèle comme couche de défense pour tout appelant non-CAMARA du
       même endpoint.
  Le comportement protocolaire de Nokia (envoi effectif du header
  attendu) a été validé ; le câblage complet de la vérification par
  subscription nécessite une migration de schéma additionnelle
  (colonnes de stockage du secret hashé) non incluse dans la version
  actuelle du backend.

Résolution métier des événements geofencing (Tâche 2/3) :
- L'identifiant `data.subscriptionId` du payload CloudEvents est recherché
  dans `GeofenceSubscription.external_subscription_id`.
- Si trouvé, le tracker et l'organisation associés sont résolus et tracés
  dans audit_logs (action=camara_geofence_event_resolved).
- Si absent, l'événement est journalisé comme non résolu
  (action=camara_webhook_unknown_subscription) sans lever d'erreur : un
  événement Nokia inconnu de notre base ne doit pas faire planter le
  webhook (idempotence / robustesse).
- La persistance de la position réelle (TrackerLocation) et la détection
  de spoofing restent un TODO (Tâche 3).
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.models.geofence_subscriptions import GeofenceSubscription
from app.db.models.trackers import Tracker
from app.db.session import AsyncSessionLocal
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
settings = get_settings()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_GEOFENCING_EVENT_TYPES = {
    "org.camaraproject.geofencing-subscriptions.v0.area-entered",
    "org.camaraproject.geofencing-subscriptions.v0.area-left",
}
_CONGESTION_EVENT_TYPES = {
    "org.camaraproject.congestion-insights.v0.congestion-info",
}


def verify_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """
    Vérifie en temps constant la signature HMAC-SHA256 du corps de requête.

    Accepte soit un digest hex brut, soit le format préfixé `sha256=<hex>`
    (convention courante côté fournisseurs de webhooks).
    """
    if not signature_header or not secret:
        return False

    received = signature_header.strip()
    if received.lower().startswith("sha256="):
        received = received[len("sha256="):]

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


async def _resolve_geofence_event(
    db,
    subscription_id: str | None,
    event_type: str,
) -> None:
    """
    Résout un événement geofencing vers son tracker/organisation et
    journalise le résultat. N'échoue jamais bruyamment : un événement
    Nokia orphelin (subscription inconnue) est journalisé et ignoré.
    """
    if not subscription_id:
        logger.warning("Événement geofencing sans subscriptionId dans le payload")
        await write_audit_log(
            db,
            organization_id=None,
            actor_type="webhook",
            action="camara_webhook_missing_subscription_id",
            entity_type="camara_event",
            result="malformed",
            payload={"event_type": event_type},
        )
        return

    result = await db.execute(
        select(GeofenceSubscription).where(
            GeofenceSubscription.external_subscription_id == subscription_id
        )
    )
    geofence_sub = result.scalar_one_or_none()

    if geofence_sub is None:
        logger.warning(
            "Subscription CAMARA inconnue en base : subscription_id=%s", subscription_id
        )
        await write_audit_log(
            db,
            organization_id=None,
            actor_type="webhook",
            action="camara_webhook_unknown_subscription",
            entity_type="camara_event",
            result="unresolved",
            payload={"subscription_id": subscription_id, "event_type": event_type},
        )
        return

    tracker = await db.get(Tracker, geofence_sub.tracker_id)

    if tracker is None:
        # Cas anormal : la FK existe en base mais l'objet n'est pas résolu.
        # Ne devrait jamais arriver si les contraintes FK sont respectées.
        logger.error(
            "GeofenceSubscription %s référence un tracker_id introuvable : %s",
            geofence_sub.id, geofence_sub.tracker_id,
        )
        await write_audit_log(
            db,
            organization_id=None,
            actor_type="webhook",
            action="camara_webhook_orphan_tracker",
            entity_type="geofence_subscription",
            entity_id=geofence_sub.id,
            result="data_integrity_error",
            payload={"subscription_id": subscription_id, "event_type": event_type},
        )
        return

    logger.info(
        "Événement geofencing résolu : subscription_id=%s -> tracker_id=%s, organization_id=%s, type=%s",
        subscription_id, tracker.id, tracker.organization_id, event_type,
    )

    await write_audit_log(
        db,
        organization_id=tracker.organization_id,
        actor_type="webhook",
        action="camara_geofence_event_resolved",
        entity_type="tracker",
        entity_id=tracker.id,
        result="resolved",
        payload={
            "event_type": event_type,
            "subscription_id": subscription_id,
            "zone_id": str(geofence_sub.zone_id),
        },
    )

    # TODO (Tâche 3) : persister la position reçue dans TrackerLocation
    # et déclencher la détection de spoofing (comparaison avec la dernière
    # position connue via Location Retrieval).


@router.post("/camara", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute")
async def receive_camara_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    raw_body = await request.body()

    signature_valid = verify_signature(raw_body, x_signature, settings.CAMARA_WEBHOOK_SECRET)

    if not signature_valid:
        if settings.CAMARA_WEBHOOK_VERIFY_SIGNATURE:
            client_ip = request.client.host if request.client else "unknown"
            logger.warning(
                "Webhook CAMARA rejeté : signature absente ou invalide (ip=%s, path=%s)",
                client_ip,
                request.url.path,
            )
            async with AsyncSessionLocal() as db:
                await write_audit_log(
                    db,
                    organization_id=None,
                    actor_type="webhook",
                    action="camara_webhook_rejected",
                    entity_type="camara_event",
                    result="rejected_invalid_signature",
                    payload={"client_ip": client_ip, "path": request.url.path},
                )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
        else:
            logger.warning(
                "⚠️  CAMARA_WEBHOOK_VERIFY_SIGNATURE=False : signature absente acceptée "
                "(mode dev, ip=%s, path=%s)",
                request.client.host if request.client else "unknown",
                request.url.path,
            )
            async with AsyncSessionLocal() as db:
                await write_audit_log(
                    db,
                    organization_id=None,
                    actor_type="webhook",
                    action="camara_webhook_signature_bypassed",
                    entity_type="camara_event",
                    result="accepted_dev_bypass",
                    payload={"path": request.url.path},
                )

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    event_type = payload.get("type") or payload.get("eventType") or "unknown"

    if event_type in _GEOFENCING_EVENT_TYPES:
        logger.info("Événement geofencing CAMARA reçu : %s", event_type)
        subscription_id = payload.get("data", {}).get("subscriptionId")
        async with AsyncSessionLocal() as db:
            await _resolve_geofence_event(db, subscription_id, event_type)
    elif event_type in _CONGESTION_EVENT_TYPES:
        logger.info("Événement congestion CAMARA reçu : %s", event_type)
    else:
        logger.info("Type d'événement CAMARA non reconnu, ignoré : %s", event_type)

    return {"status": "received"}