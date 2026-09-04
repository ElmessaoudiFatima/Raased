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
"""

from typing import Any

from app.camara.client import get_camara_client

SLICE_BASE_PATH = "/slice/v1/slices"


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
    client = get_camara_client()
    return await client.post(SLICE_BASE_PATH, json=payload)


async def get_all_slices() -> list[dict[str, Any]]:
    """GET /slice/v1/slices — liste toutes les slices de l'application."""
    client = get_camara_client()
    return await client.get(SLICE_BASE_PATH)


async def get_slice(slice_id: str) -> dict[str, Any]:
    """
    GET /slice/v1/slices/{slice_id}

    slice_id = le champ `name` (UUID) renvoyé par create_slice, PAS csi_id.
    Confirmé empiriquement (voir docstring module).
    """
    client = get_camara_client()
    return await client.get(f"{SLICE_BASE_PATH}/{slice_id}")


async def activate_slice(slice_id: str) -> dict[str, Any]:
    """
    POST /slice/v1/slices/{slice_id}/activate

    Le schéma Nokia indique "no additional body", mais le curl du
    playground envoie quand même --data '{}'. On reproduit le
    comportement observé plutôt que de deviner.
    """
    client = get_camara_client()
    return await client.post(f"{SLICE_BASE_PATH}/{slice_id}/activate", json={})


async def deactivate_slice(slice_id: str) -> dict[str, Any]:
    """POST /slice/v1/slices/{slice_id}/deactivate — même remarque que activate_slice."""
    client = get_camara_client()
    return await client.post(f"{SLICE_BASE_PATH}/{slice_id}/deactivate", json={})


async def delete_slice(slice_id: str) -> dict[str, Any]:
    """
    DELETE /slice/v1/slices/{slice_id}

    Le curl playground envoie --data '{}' malgré la méthode DELETE
    (atypique en HTTP mais confirmé). Nécessite le fix de CamaraClient.delete()
    pour accepter un body.
    """
    client = get_camara_client()
    return await client.delete(f"{SLICE_BASE_PATH}/{slice_id}", json={})