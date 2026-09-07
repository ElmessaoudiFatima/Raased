"""
Endpoint webhook recevant les événements Nokia CAMARA (Congestion Insights,
Geofencing area-entered / area-left).

Sécurité :
- Chaque requête doit porter une signature HMAC-SHA256 valide dans le header
  `X-Signature`, calculée sur le corps brut de la requête avec le secret
  partagé `CAMARA_WEBHOOK_SECRET`. Toute requête sans signature valide est
  rejetée avec 401 et journalisée dans `audit_logs` (organization_id=None,
  puisqu'aucune organisation n'est résolue à ce stade — voir
  app/db/models/audit_logs.py).
- L'endpoint est protégé par un rate limit (slowapi) pour limiter l'impact
  d'un flood ou d'un replay.

Les événements dont la signature EST valide ne sont pas encore traités
métier ici : leur résolution tracker/organisation (via
`GeofenceSubscription`, écriture de `TrackerLocation`, etc.) relève des
Tâches 2/3.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import AsyncSessionLocal
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)
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


@router.post("/camara", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute")
async def receive_camara_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    raw_body = await request.body()

    if not verify_signature(raw_body, x_signature, settings.CAMARA_WEBHOOK_SECRET):
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

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    event_type = payload.get("type") or payload.get("eventType") or "unknown"

    if event_type in _GEOFENCING_EVENT_TYPES:
        logger.info("Événement geofencing CAMARA reçu : %s", event_type)
        # TODO (Tâche 2/3) : résoudre GeofenceSubscription -> tracker -> org,
        # persister la position / déclencher la détection de spoofing.
    elif event_type in _CONGESTION_EVENT_TYPES:
        logger.info("Événement congestion CAMARA reçu : %s", event_type)
    else:
        logger.info("Type d'événement CAMARA non reconnu, ignoré : %s", event_type)

    return {"status": "received"}
