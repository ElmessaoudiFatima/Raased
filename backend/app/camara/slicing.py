"""
CAMARA Network Slicing API wrapper.

Base path confirmé via Nokia playground (vrais curl, pas deviné) :
    https://network-as-code.p-eu.apihub.nokia.io/slice/v1/slices

Ce module suit le même pattern que congestion.py : toute la logique HTTP
passe par get_camara_client() (client.py), aucune duplication d'auth.

RÉSOLU (test empirique du 2026 — voir _manual_test_slicing.py, supprimé
après validation) : create_slice() renvoie deux identifiants différents :
    - csi_id  (ex: "csi_691")   -> identifiant interne de provisioning
    - name    (ex: UUID)         -> identifiant API réel

Test réalisé : appel de get_slice avec les deux.
    - csi_id  -> 422 string_pattern_mismatch (contient un "_", interdit
                 par le pattern d'URL Nokia ^[a-zA-Z0-9][a-zA-Z0-9-]{3,63}[a-zA-Z0-9]$)
    - name    -> 200 OK, slice retournée correctement

CONCLUSION : `name` est le sliceId à utiliser partout où un {id} est
attendu dans le path (get_slice, activate_slice, deactivate_slice,
delete_slice, et probablement attachDevice — à confirmer quand le
payload de cet endpoint sera obtenu).

COMPORTEMENT ASYNCHRONE CONFIRMÉ EMPIRIQUEMENT (3 tests répétés) :
Le délai de transition PENDING -> AVAILABLE après create_slice est
VARIABLE et NON DÉTERMINISTE en sandbox : observé entre ~80s et plus de
180s selon les essais. Ce n'est pas une donnée statique/canned (contrairement
à la suspicion documentée sur Congestion Insights) — le sandbox simule un
vrai comportement de provisioning avec latence variable.

De plus, activate_slice() déclenche LUI-MÊME un nouveau "service order"
asynchrone : appeler deactivate_slice() ou toute autre action juste après
un activate_slice() renvoie une erreur 409 "A service order is already
in progress" tant que ce nouvel ordre n'est pas résolu.

CONSÉQUENCE POUR LA DÉMO : ce timing imprévisible rend Network Slicing
inadapté à une démonstration live synchrone. QoD (section qod.py) reste
l'action réseau démontrée en direct. Slicing est présenté comme capacité
validée en sandbox (cycle CRUD complet fonctionnel), pas comme scénario
temps réel devant jury.

---

DEVICE ATTACH (device-attach/v0) — TESTÉ, NON VALIDÉ (résultat empirique).

Endpoint distinct de Network Slicing lui-même (/device-attach/v0/...
vs /slice/v1/...), regroupé dans ce fichier car ces fonctions sont
inutilisables sans un sliceId produit par create_slice() ci-dessus.

RÉSOLU : sliceId = `name` (UUID), PAS csi_id.
Confirmé sur 3 tentatives distinctes : csi_id renvoie systématiquement
un 422 string_pattern_mismatch (même erreur de format que get_slice,
l'underscore viole le pattern Nokia). `name` est toujours accepté
structurellement (jamais rejeté sur le format), cohérent avec le reste
du cycle de vie de la slice.

NON RÉSOLU après 5 tests empiriques (voir historique de session,
_manual_test_attach.py supprimé après tests) : aucun état de la slice
testé ne permet un attach_device() réussi.
    - state=PENDING  -> 409 "Slice is in invalid state for subscriber
                        management operations."
    - state=AVAILABLE (atteint et confirmé à 2 reprises, ~90-120s)
                     -> 409 IDENTIQUE, même message exact
    - activate_slice() appelé sur AVAILABLE -> réponse {"status":
      "Accepted"}, mais aucun changement d'état observé sur 210s de
      polling post-activation (state reste "AVAILABLE" dans get_slice)
    - manage_subscriber() comme étape préalable -> jamais testé
      jusqu'au bout : le timing PENDING->AVAILABLE s'est révélé encore
      plus variable que documenté (2 runs sur 5 n'ont pas atteint
      AVAILABLE même après 210-225s), empêchant d'atteindre cette
      étape du protocole de test dans le temps disponible.

HYPOTHÈSES NON ÉLIMINÉES, À REPRENDRE SI LE TEMPS LE PERMET :
    1. manage_subscriber() (POST .../subscribers/create) pourrait être
       un prérequis avant attach_device() -- le message d'erreur répété
       ("invalid state for SUBSCRIBER MANAGEMENT operations") est un
       indice non exploité en faveur de cette piste.
    2. Un état intermédiaire non documenté (ex: "ACTIVE" avec un délai
       propre après activate_slice(), distinct du délai PENDING->
       AVAILABLE) pourrait exister mais n'a pas pu être observé --
       210s de polling post-activation n'ont montré aucun changement,
       mais on ne peut pas exclure un délai encore plus long.
    3. Le payload attach_device() (customer/mobile_services/
       traffic_categories, valeurs par défaut de l'exemple Nokia)
       n'a jamais été testé avec des valeurs alternatives -- possible
       qu'un champ soit incorrect indépendamment de l'état de la slice.

DÉCISION : non bloquant pour la Phase 1 (cf. Explication_API.pdf,
section 9, Priorité 3). QoD reste l'action réseau démontrée en direct.
Network Slicing est présenté au jury comme capacité validée en sandbox
pour son cycle de vie CRUD principal (create/get/activate/deactivate/
delete), PAS comme scénario d'attachement device-à-slice fonctionnel
-- formulation honnête à conserver dans toute présentation.
"""

from typing import Any

from app.camara.client import camara_post, camara_get, camara_delete

SLICE_BASE_PATH = "/slice/v1/slices"
DEVICE_ATTACH_BASE_PATH = "/device-attach/v0/attachments"
DEVICE_ATTACH_SUBSCRIBER_PATH = "/device-attach/v0/attachments/subscribers/create"


# ============================================================
# NETWORK SLICING — cycle CRUD (validé empiriquement)
# ============================================================

async def create_slice(payload: dict[str, Any]) -> dict[str, Any]:
    """
    POST /slice/v1/slices

    Payload minimal requis (confirmé empiriquement) :
        notificationUrl, notificationAuthToken, networkIdentifier,
        sliceInfo, maxDataConnections, maxDevices,
        sliceUplinkThroughput, deviceUplinkThroughput

    Réponse asynchrone (state: PENDING). Contient `csi_id` ET `name` —
    utiliser `name` pour tous les appels suivants (voir docstring module).

    ⚠️ notificationUrl fictif (ex: https://example.com/notify) est ACCEPTÉ
    par Nokia à la création, contrairement à Geofencing qui rejette
    immédiatement un sink invalide (INVALID_SINK). Comportement différent
    entre les deux APIs asynchrones — à noter pour la présentation.
    """
    return await camara_post(SLICE_BASE_PATH, payload)


async def get_all_slices() -> list[dict[str, Any]]:
    """GET /slice/v1/slices — liste toutes les slices de l'application."""
    return await camara_get(SLICE_BASE_PATH)


async def get_slice(slice_id: str) -> dict[str, Any]:
    """
    GET /slice/v1/slices/{slice_id}

    slice_id = le champ `name` (UUID) renvoyé par create_slice, PAS csi_id.
    Confirmé empiriquement (voir docstring module).
    """
    return await camara_get(f"{SLICE_BASE_PATH}/{slice_id}")


async def activate_slice(slice_id: str) -> dict[str, Any]:
    """
    POST /slice/v1/slices/{slice_id}/activate

    Le schéma Nokia indique "no additional body", mais le curl du
    playground envoie quand même --data '{}'. On reproduit le
    comportement observé plutôt que de deviner.
    """
    return await camara_post(f"{SLICE_BASE_PATH}/{slice_id}/activate", {})


async def deactivate_slice(slice_id: str) -> dict[str, Any]:
    """POST /slice/v1/slices/{slice_id}/deactivate — même remarque que activate_slice."""
    return await camara_post(f"{SLICE_BASE_PATH}/{slice_id}/deactivate", {})


async def delete_slice(slice_id: str) -> dict[str, Any]:
    """
    DELETE /slice/v1/slices/{slice_id}

    Le curl playground envoie --data '{}' malgré la méthode DELETE
    (atypique en HTTP mais confirmé). Nécessite le fix de CamaraClient.delete()
    pour accepter un body.
    """
    return await camara_delete(f"{SLICE_BASE_PATH}/{slice_id}", json_body={})


# ============================================================
# DEVICE ATTACH — TESTÉ, NON VALIDÉ (résultat empirique)
# ============================================================

async def attach_device(
    phone_number: str,
    imsi: int,
    slice_id: str,
    customer_name: str = "DefaultAttachOperationCustomer",
    customer_description: str = "I Am Default Who Order The Device Attach Operation",
    customer_address: str = "Dummy Customer Address",
    customer_contact: str = "My Contact Should Be Here",
    mobile_services: list[str] | None = None,
    traffic_app_os: str = "09078034-07db-4b13-a970-ab80235f7369",
    traffic_apps: list[str] | None = None,
    notification_url: str = "https://application-server.com",
    notification_auth_token: str = "c8974e592fa383d4a396071",
) -> dict[str, Any]:
    """
    POST /device-attach/v0/attachments

    Payload structurellement identique à l'exemple curl Nokia fourni
    par le playground RapidAPI. slice_id : voir résolution dans le
    docstring module — `name` (UUID) confirmé comme sliceId correct.
    """
    payload = {
        "device": {"phoneNumber": phone_number, "imsi": imsi},
        "customer": {
            "name": customer_name,
            "description": customer_description,
            "address": customer_address,
            "contact": customer_contact,
        },
        "sliceId": slice_id,
        "mobile_services": mobile_services or ["Voice", "Voicemail", "5G-Data"],
        "traffic_categories": {
            "apps": {
                "os": traffic_app_os,
                "apps": traffic_apps or ["Daedalus"],
            }
        },
        "webhook": {
            "notificationUrl": notification_url,
            "notificationAuthToken": notification_auth_token,
        },
    }
    return await camara_post(DEVICE_ATTACH_BASE_PATH, payload)


async def detach_device(attachment_id: str) -> dict[str, Any]:
    """
    DELETE /device-attach/v0/attachments/{attachment_id}

    attachment_id : identifiant DISTINCT du sliceId (csi_id/name),
    généré par Nokia à la création de l'attachment lui-même — voir
    inconnue #5 en tête de fichier, nom exact du champ à confirmer
    dans la réponse de attach_device().

    Body vide explicite ({}), reproduction fidèle de l'exemple curl
    Nokia (--data '{}'), même pattern que delete_slice() ci-dessus.
    """
    return await camara_delete(f"{DEVICE_ATTACH_BASE_PATH}/{attachment_id}", json_body={})


async def get_all_attachments_status() -> Any:
    """
    GET /device-attach/v0/attachments

    Type de retour non confirmé (dict englobant ou liste brute) — le
    précédent avec get_all_slices() a surpris en renvoyant une liste
    brute plutôt qu'un dict. À vérifier empiriquement avant de figer
    un type de retour strict ici.
    """
    return await camara_get(DEVICE_ATTACH_BASE_PATH)


async def get_attachment_status(attachment_id: str) -> dict[str, Any]:
    """GET /device-attach/v0/attachments/{attachment_id}"""
    return await camara_get(f"{DEVICE_ATTACH_BASE_PATH}/{attachment_id}")


async def manage_subscriber(
    phone_number: str,
    imsi: int,
    slice_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    POST /device-attach/v0/attachments/subscribers/create

    Payload identique à attach_device() dans l'exemple Nokia fourni.

    NON TESTÉ. Relation exacte avec attach_device() inconnue : alias
    du même service, étape préalable obligatoire, ou fonction
    totalement différente (ex: enregistrer un abonné avant de pouvoir
    l'attacher) ? À tester séparément si le temps le permet — pas
    bloquant pour valider le cycle attach/detach principal.
    """
    payload = {
        "device": {"phoneNumber": phone_number, "imsi": imsi},
        "customer": {
            "name": kwargs.get("customer_name", "DefaultAttachOperationCustomer"),
            "description": kwargs.get(
                "customer_description",
                "I Am Default Who Order The Device Attach Operation",
            ),
            "address": kwargs.get("customer_address", "Dummy Customer Address"),
            "contact": kwargs.get("customer_contact", "My Contact Should Be Here"),
        },
        "sliceId": slice_id,
        "mobile_services": kwargs.get(
            "mobile_services", ["Voice", "Voicemail", "5G-Data"]
        ),
        "traffic_categories": {
            "apps": {
                "os": kwargs.get(
                    "traffic_app_os", "09078034-07db-4b13-a970-ab80235f7369"
                ),
                "apps": kwargs.get("traffic_apps", ["Daedalus"]),
            }
        },
        "webhook": {
            "notificationUrl": kwargs.get(
                "notification_url", "https://application-server.com"
            ),
            "notificationAuthToken": kwargs.get(
                "notification_auth_token", "c8974e592fa383d4a396071"
            ),
        },
    }
    return await camara_post(DEVICE_ATTACH_SUBSCRIBER_PATH, payload)