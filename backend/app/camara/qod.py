"""
Wrapper pour l'API Quality on Demand (QoD) — CAMARA / Nokia Network-as-Code.

QoD est SYNCHRONE (contrairement à Network Slicing) : createSession renvoie
un sessionId immédiatement, avec qosStatus="REQUESTED". C'est l'action réseau
la plus sûre pour une démo live (pas de dépendance webhook).

Important (voir Explication_API.pdf section 4.4) :
- Le payload distingue DEUX IP différentes, pas une seule :
  * device.ipv4Address -> identifie le tracker (adresses publique/privée + port optionnel)
  * applicationServer.ipv4Address -> identifie le serveur de télémétrie qui reçoit
    les données du tracker
  QoD priorise donc le FLUX entre le tracker et son serveur applicatif,
  pas "la connexion du tracker en général".

NOTE SUR L'ENDPOINT (découverte empirique) :
Le playground Nokia expose DEUX versions de QoD : "/qod/v0/..." (nom abrégé,
probablement un ancien alias Nokia pré-CAMARA) et "/quality-on-demand/v1/..."
(nom complet, aligné sur le nom officiel du repo CAMARA QualityOnDemand).
On utilise v1 délibérément, pour rester cohérent avec la démarche
"intégration d'APIs CAMARA standardisées" du projet. v0 fonctionne
probablement aussi mais n'a pas été retenu.

DÉCOUVERTE EMPIRIQUE — comportement de extendQosSessionDuration (6 tests réels) :

1. SYSTÉMATIQUE (5/5 extends réussis) : la réponse de extend() contient un
   sessionId DIFFÉRENT de celui utilisé dans l'URL de la requête. Comportement
   stable et reproductible, pas un artefact ponctuel. CONSÉQUENCE : ne jamais
   réutiliser le sessionId renvoyé par extend() pour les appels suivants
   (get/delete) — toujours conserver le sessionId original obtenu à create().

2. OCCASIONNEL (1/6 tentatives) : extend() a échoué avec 404 "Session not
   found" alors qu'un get_qod_session() juste avant confirmait l'existence
   de la session. Cause non déterminée avec certitude sur un échantillon
   aussi restreint (vraie instabilité sandbox vs. latence de propagation
   interne chez Nokia). Un retry unique avec léger délai a été ajouté comme
   filet de sécurité pour la démo live — ce n'est PAS une correction
   validée scientifiquement, juste une mesure de robustesse pragmatique.

Cycle complet testé (6 exécutions réelles) : createSession -> getSession ->
extendQosSessionDuration -> deleteSession. L'agent doit toujours libérer
la session proprement une fois l'alerte terminée (ne pas laisser de
sessions QoD orphelines).
"""
import asyncio
from app.camara.client import get_camara_client, CamaraAPIError
from app.core.config import get_settings

settings = get_settings()

QOD_SESSIONS_ENDPOINT = "/quality-on-demand/v1/sessions"
QOD_RETRIEVE_SESSIONS_ENDPOINT = "/quality-on-demand/v1/retrieve-sessions"


async def create_qod_session(
    phone_number: str,
    device_public_ip: str,
    device_private_ip: str,
    application_server_ip: str,
    qos_profile: str = "QOS_E",
    duration: int = 3600,
    device_public_port: int | None = None,
) -> dict:
    """
    Crée une session QoD pour prioriser le flux tracker <-> serveur applicatif.
    Réponse confirmée en test réel :
    { "sessionId": "...", "qosStatus": "REQUESTED", "duration": ... , ... }
    """
    client = get_camara_client()
    device: dict = {
        "phoneNumber": phone_number,
        "ipv4Address": {
            "publicAddress": device_public_ip,
            "privateAddress": device_private_ip,
        },
    }
    if device_public_port is not None:
        device["ipv4Address"]["publicPort"] = device_public_port

    payload = {
        "device": device,
        "applicationServer": {"ipv4Address": application_server_ip},
        "qosProfile": qos_profile,
        "duration": duration,
    }
    return await client.post(QOD_SESSIONS_ENDPOINT, json=payload)


async def get_qod_session(session_id: str) -> dict:
    """Récupère l'état actuel d'une session QoD (qosStatus, expiresAt, ...)."""
    client = get_camara_client()
    return await client.get(f"{QOD_SESSIONS_ENDPOINT}/{session_id}")


async def get_qod_sessions_for_device(phone_number: str) -> dict:
    """
    Liste les sessions QoD actives d'un device donné.
    C'est un POST vers /retrieve-sessions avec le device dans le body
    (confirmé via le playground Nokia, pas un GET avec query params).
    """
    client = get_camara_client()
    payload = {"device": {"phoneNumber": phone_number}}
    return await client.post(QOD_RETRIEVE_SESSIONS_ENDPOINT, json=payload)


async def extend_qod_session(
    session_id: str,
    additional_duration: int,
    retry_on_404: bool = True,
) -> dict:
    """
    Prolonge une session QoD active de additional_duration secondes.
    Payload confirmé dans la doc Nokia : {"requestedAdditionalDuration": N}

    ⚠️ Le sessionId dans la RÉPONSE de cet appel peut différer du sessionId
    passé en paramètre (comportement du simulateur observé de façon
    reproductible sur 5/5 tests réussis). Ignorer ce champ dans la réponse ;
    continuer à utiliser le session_id d'origine pour tout appel ultérieur
    (get/delete).

    retry_on_404 : filet de sécurité pour la démo live. Un échec 404 isolé
    a été observé une fois sur 6 tests alors que la session existait
    (confirmée par get_qod_session juste avant). Non expliqué avec certitude ;
    un seul retry après court délai est tenté avant de laisser remonter
    l'erreur. Désactivable si on veut observer le comportement brut de l'API.
    """
    client = get_camara_client()
    payload = {"requestedAdditionalDuration": additional_duration}
    endpoint = f"{QOD_SESSIONS_ENDPOINT}/{session_id}/extend"

    try:
        return await client.post(endpoint, json=payload)
    except CamaraAPIError as exc:
        if retry_on_404 and exc.status_code == 404:
            await asyncio.sleep(1.0)
            return await client.post(endpoint, json=payload)
        raise


async def delete_qod_session(session_id: str) -> dict:
    """
    Termine une session QoD. À appeler systématiquement une fois l'alerte
    résolue, pour ne pas laisser une priorisation réseau active inutilement.
    """
    client = get_camara_client()
    return await client.delete(f"{QOD_SESSIONS_ENDPOINT}/{session_id}")


async def request_priority_for_tracker(
    phone_number: str,
    device_public_ip: str,
    device_private_ip: str,
    application_server_ip: str,
    qos_profile: str = "QOS_E",
    duration: int = 3600,
) -> dict:
    """
    Fonction principale exposée à l'agent : déclenche une priorisation QoD
    pour un tracker identifié comme à risque élevé (action D1 de la matrice
    de décision). Ne décide pas SI il faut agir — exécute l'action une fois
    la décision prise par le moteur de règles / l'agent.
    """
    return await create_qod_session(
        phone_number=phone_number,
        device_public_ip=device_public_ip,
        device_private_ip=device_private_ip,
        application_server_ip=application_server_ip,
        qos_profile=qos_profile,
        duration=duration,
    )