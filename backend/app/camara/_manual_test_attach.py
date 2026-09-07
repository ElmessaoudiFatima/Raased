"""
Test empirique du cycle Device Attach — version 5.

Deux angles morts identifiés dans les runs précédents :
1. On n'a jamais affiché la réponse COMPLÈTE de get_slice() — on
   filtrait uniquement sur "state". Un autre champ a peut-être changé
   après activate_slice() sans qu'on le voie.
2. On n'a jamais testé manage_subscriber() (POST .../subscribers/create)
   comme étape préalable à attach_device() — le message d'erreur répété
   ("invalid state for subscriber management operations") pourrait
   indiquer qu'un subscriber doit exister avant l'attach, pas
   seulement que l'état de la slice est en cause.

Ce run réutilise le "state" déjà confirmé accessible (AVAILABLE
atteint ~90-120s dans les runs précédents) et teste manage_subscriber
avant un nouvel essai d'attach, tout en affichant l'objet get_slice()
complet à chaque étape clé.
"""
import asyncio
import json
import httpx
from app.camara.slicing import (
    create_slice,
    get_slice,
    delete_slice,
    activate_slice,
    attach_device,
    manage_subscriber,
    detach_device,
    get_attachment_status,
)
from app.camara.client import CamaraAPIError

TEST_PHONE_NUMBER = "+99999991000"
TEST_IMSI = 99999991000
POLL_INTERVAL_S = 15
AVAILABLE_TIMEOUT_S = 200

CREATE_SLICE_PAYLOAD = {
    "networkIdentifier": {"mcc": "236", "mnc": "30"},
    "sliceInfo": {"serviceType": 1, "differentiator": "0003E8"},
    "maxDataConnections": 42312,
    "maxDevices": 33,
    "sliceUplinkThroughput": {"guaranteed": 15, "maximum": 999999},
    "deviceUplinkThroughput": {"guaranteed": 10, "maximum": 20},
    "notificationUrl": "https://example.com/notify",
    "notificationAuthToken": "c8974e592f9fh683d4a3960714",
}


def dump(label: str, obj) -> None:
    print(f"{label} : {json.dumps(obj, indent=2, default=str)}")


async def try_attach(slice_id: str, label: str) -> str | None:
    print(f"\n--- Tentative attach_device avec {label} ---")
    try:
        result = await attach_device(
            phone_number=TEST_PHONE_NUMBER,
            imsi=TEST_IMSI,
            slice_id=slice_id,
        )
        dump("SUCCÈS", result)
        return result.get("id") or result.get("attachmentId") or result.get("attachment_id")
    except CamaraAPIError as exc:
        print(f"ÉCHEC status={exc.status_code} detail={exc.detail}")
        return None


async def poll_until_available(name: str, timeout_s: int) -> dict:
    """Retourne l'objet get_slice() COMPLET, pas juste le state."""
    elapsed = 0
    current = {"state": "PENDING"}
    while current.get("state") != "AVAILABLE" and elapsed < timeout_s:
        await asyncio.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S
        try:
            current = await get_slice(name)
            print(f"  [{elapsed}s] state={current.get('state')}")
        except (httpx.TransportError, CamaraAPIError) as exc:
            print(f"  [{elapsed}s] erreur transitoire, on continue : {exc}")
    return current


async def main():
    print("=== Création de la slice de test ===")
    slice_data = await create_slice(CREATE_SLICE_PAYLOAD)
    name = slice_data["name"]
    dump("Réponse create_slice complète", slice_data)

    attachment_id = None

    try:
        print(f"\n=== Poll jusqu'à AVAILABLE (timeout {AVAILABLE_TIMEOUT_S}s) ===")
        slice_state_obj = await poll_until_available(name, AVAILABLE_TIMEOUT_S)
        dump("Objet get_slice() complet une fois AVAILABLE", slice_state_obj)

        if slice_state_obj.get("state") != "AVAILABLE":
            print("AVAILABLE non atteint, arrêt du test.")
        else:
            print("\n=== activate_slice() sur slice AVAILABLE ===")
            try:
                activate_result = await activate_slice(name)
                dump("Réponse activate_slice", activate_result)
            except CamaraAPIError as exc:
                print(f"activate_slice ÉCHEC status={exc.status_code} detail={exc.detail}")

            print("\n=== Attente 30s puis inspection COMPLÈTE de get_slice() ===")
            await asyncio.sleep(30)
            post_activate_obj = await get_slice(name)
            dump("Objet get_slice() complet APRÈS activate_slice", post_activate_obj)

            # NOUVELLE PISTE : tester manage_subscriber avant l'attach
            print("\n=== Tentative manage_subscriber() (jamais testé jusqu'ici) ===")
            try:
                subscriber_result = await manage_subscriber(
                    phone_number=TEST_PHONE_NUMBER,
                    imsi=TEST_IMSI,
                    slice_id=name,
                )
                dump("manage_subscriber SUCCÈS", subscriber_result)
            except CamaraAPIError as exc:
                print(f"manage_subscriber ÉCHEC status={exc.status_code} detail={exc.detail}")

            print("\n=== Tentative attach_device() après manage_subscriber ===")
            attachment_id = await try_attach(name, f"name (UUID), post-manage_subscriber")

        if attachment_id:
            dump("get_attachment_status", await get_attachment_status(attachment_id))
            dump("detach_device", await detach_device(attachment_id))
        else:
            print("\n=== Toujours aucun attach réussi ===")

    finally:
        print(f"\n=== Nettoyage : suppression de la slice {name} ===")
        try:
            await delete_slice(name)
            print("Slice supprimée.")
        except (CamaraAPIError, httpx.TransportError) as exc:
            print(f"ATTENTION : vérifier manuellement slice {name} "
                  f"(csi_id={slice_data['csi_id']}) : {exc}")


if __name__ == "__main__":
    asyncio.run(main())