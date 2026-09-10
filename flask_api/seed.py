import json
from datetime import timedelta

from extensions import db
from models import (
    AccountInvitation,
    Alert,
    AuditLog,
    Cargo,
    Corridor,
    Organization,
    RiskZone,
    Tracker,
    User,
)
from security import hash_password, utcnow


def _user(org_id, first, last, email, role, password=None, status="ACTIVE", title=None, phone=None, verified=True):
    return User(
        organization_id=org_id,
        first_name=first,
        last_name=last,
        job_title=title,
        phone=phone,
        email=email,
        password=hash_password(password) if password else None,
        role=role,
        email_verified=verified,
        email_verified_at=utcnow() if verified else None,
        account_status=status,
        is_active=True,
    )


def _tracker(org_id, device, msisdn, vehicle):
    return Tracker(
        organization_id=org_id,
        device_id=device,
        msisdn=msisdn,
        vehicle_registration=vehicle,
        status="ACTIVE",
        last_seen_at=utcnow() - timedelta(minutes=2),
    )


def _cargo(org_id, tracker_id, ref, ctype, criticality, origin, dest, olat, olng, dlat, dlng, status, driver_id=None, speed=80, minutes_ago=90, deadline_hours=24):
    return Cargo(
        organization_id=org_id,
        tracker_id=tracker_id,
        reference=ref,
        type=ctype,
        criticality=criticality,
        status=status,
        origin=origin,
        destination=dest,
        origin_lat=olat,
        origin_lng=olng,
        destination_lat=dlat,
        destination_lng=dlng,
        departed_at=utcnow() - timedelta(minutes=minutes_ago) if status == "IN_TRANSIT" else None,
        speed_kmh=speed,
        deadline=utcnow() + timedelta(hours=deadline_hours),
        assigned_driver_id=driver_id,
    )


def _alert(org_id, cargo, severity, title, message):
    return Alert(
        organization_id=org_id,
        cargo_id=cargo.id,
        tracker_id=cargo.tracker_id,
        severity=severity,
        title=title,
        message=message,
        status="OPEN",
    )


def _corridor(name, origin, dest, points, risk):
    return Corridor(name=name, origin=origin, destination=dest, points_json=json.dumps(points), risk_level=risk)


def _risk_zone(name, type_, risk, points, description):
    return RiskZone(name=name, type=type_, risk_level=risk, points_json=json.dumps(points), description=description)


def _polygon(cx, cy, r):
    pts = []
    import math

    for i in range(30):
        a = 2 * math.pi * i / 30
        pts.append([round(cx + r * math.cos(a), 6), round(cy + r * math.sin(a), 6)])
    return pts


def seed_if_empty():
    if User.query.count() > 0:
        return

    admin = _user(None, "Système", "Raased", "admin@raased.ma", "ADMIN", "Admin@123", title="Administrateur plateforme")
    db.session.add(admin)

    logitrans = Organization(
        name="LogiTrans Maroc",
        legal_id="IC00012345",
        country="Maroc",
        city="Casablanca",
        phone="+212 522 45 67 89",
        address="12 Bvd Moulay Youssef, Casablanca",
        website="https://logitrans.ma",
        email="contact@logitrans.ma",
        status="APPROVED",
        reviewed_at=utcnow(),
    )
    medicargo = Organization(
        name="MediCargo Santé",
        legal_id="IC00067890",
        country="Maroc",
        city="Rabat",
        phone="+212 537 12 34 56",
        address="45 Avenue Annakhil, Rabat",
        website="https://medicargo.ma",
        email="contact@medicargo.ma",
        status="APPROVED",
        reviewed_at=utcnow(),
    )
    atlasexpress = Organization(
        name="Atlas Express",
        legal_id="IC00011223",
        country="Maroc",
        city="Marrakech",
        phone="+212 524 33 22 11",
        address="Route de l'Ourika, Marrakech",
        email="contact@atlasexpress.ma",
        status="PENDING",
    )
    db.session.add_all([logitrans, medicargo, atlasexpress])
    db.session.flush()

    amina = _user(
        logitrans.id, "Amina", "Benali", "manager@logitrans.ma", "MANAGER",
        "Manager@123", title="Directrice des opérations", phone="+212 661 22 33 44",
    )
    yassine = _user(
        medicargo.id, "Yassine", "Tazi", "manager@medicargo.ma", "MANAGER",
        "Manager@123", title="Responsable logistique", phone="+212 662 55 66 77",
    )
    karim = _user(
        atlasexpress.id, "Karim", "El Fassi", "manager@atlasexpress.ma", "MANAGER",
        "Manager@123", title="Gérant", phone="+212 663 88 99 00",
    )
    salma = _user(
        logitrans.id, "Salma", "Idrissi", "salma.idrissi@logitrans.ma", "MANAGER",
        None, status="INVITED", title="Directrice commerciale", phone="+212 664 10 20 30", verified=False,
    )
    db.session.add_all([amina, yassine, karim, salma])

    mehdi = _user(logitrans.id, "Mehdi", "Alaoui", "driver@logitrans.ma", "DRIVER", "Driver@123", phone="+212 665 11 22 33")
    omar = _user(logitrans.id, "Omar", "Bennis", "driver2@logitrans.ma", "DRIVER", "Driver@123", phone="+212 666 22 33 44")
    rachid = _user(logitrans.id, "Rachid", "Naciri", "rachid.naciri@logitrans.ma", "DRIVER", None, status="INVITED", phone="+212 667 33 44 55", verified=False)
    hicham = _user(medicargo.id, "Hicham", "Lahlou", "driver@medicargo.ma", "DRIVER", "Driver@123", phone="+212 668 44 55 66")
    db.session.add_all([mehdi, omar, rachid, hicham])
    db.session.flush()

    inv = AccountInvitation(
        user_id=salma.id,
        token="demo-invite-salma-logitrans",
        expires_at=utcnow() + timedelta(hours=48),
    )
    db.session.add(inv)

    t1 = _tracker(logitrans.id, "LGT-TRK-001", "+212600000001", "12345-A-6")
    t2 = _tracker(logitrans.id, "LGT-TRK-002", "+212600000002", "78901-B-7")
    t3 = _tracker(logitrans.id, "LGT-TRK-003", "+212600000003", "34567-C-8")
    t4 = _tracker(medicargo.id, "MED-TRK-001", "+212610000001", "90123-D-9")
    t5 = _tracker(medicargo.id, "MED-TRK-002", "+212610000002", "45678-E-1")
    t6 = _tracker(atlasexpress.id, "ATL-TRK-001", "+212620000001", "23456-F-2")
    db.session.add_all([t1, t2, t3, t4, t5, t6])
    db.session.flush()

    CAS = (33.5731, -7.5898)
    MAR = (31.6295, -7.9811)
    AGA = (30.4278, -9.5981)
    TAN = (35.7595, -5.8340)
    RAB = (34.0209, -6.8416)

    c1 = _cargo(logitrans.id, t1.id, "CARGO-LGT-001", "ELECTRONICS", "HIGH", "Casablanca", "Marrakech", CAS[0], CAS[1], MAR[0], MAR[1], "IN_TRANSIT", driver_id=mehdi.id, speed=82, minutes_ago=90, deadline_hours=20)
    c2 = _cargo(logitrans.id, t2.id, "CARGO-LGT-002", "FMCG", "MEDIUM", "Tanger", "Casablanca", TAN[0], TAN[1], CAS[0], CAS[1], "IN_TRANSIT", driver_id=omar.id, speed=90, minutes_ago=210, deadline_hours=12)
    c3 = _cargo(logitrans.id, t3.id, "CARGO-LGT-003", "TEXTILE", "LOW", "Casablanca", "Rabat", CAS[0], CAS[1], RAB[0], RAB[1], "DELIVERED", driver_id=mehdi.id, deadline_hours=0)
    c4 = _cargo(medicargo.id, t4.id, "CARGO-MED-001", "PHARMACEUTICAL", "CRITICAL", "Casablanca", "Agadir", CAS[0], CAS[1], AGA[0], AGA[1], "IN_TRANSIT", driver_id=hicham.id, speed=88, minutes_ago=150, deadline_hours=30)
    c5 = _cargo(medicargo.id, t5.id, "CARGO-MED-002", "MEDICAL_DEVICES", "HIGH", "Rabat", "Marrakech", RAB[0], RAB[1], MAR[0], MAR[1], "PENDING", deadline_hours=48)
    db.session.add_all([c1, c2, c3, c4, c5])
    db.session.flush()

    db.session.add_all(
        [
            _alert(logitrans.id, c1, "HIGH", "Congestion détectée près de Settat", "Le corridor A3 présente un niveau de congestion élevé. Le trajet pourrait être ralenti de 30 à 45 minutes."),
            _alert(logitrans.id, c2, "MEDIUM", "Incident signalé sur la route nationale", "Un incident a été signalé avant l'entrée de Rabat. Suivi renforcé du tracker LGT-TRK-002."),
            _alert(logitrans.id, c3, "LOW", "Livraison confirmée", "La cargaison CARGO-LGT-003 a été livrée avec succès à Rabat."),
            _alert(medicargo.id, c4, "CRITICAL", "Température hors plage", "La chaîne du froid de la cargaison CARGO-MED-001 dépasse le seuil de +2°C. Attention à la stabilité du produit."),
            _alert(medicargo.id, c4, "HIGH", "Franchissement de zone à risque", "Le camion MED-TRK-001 approche d'une zone à risque. Vérification de la trajectoire recommandée."),
        ]
    )

    db.session.add_all(
        [
            _corridor("A3 Casablanca → Marrakech", "Casablanca", "Marrakech", [[33.5731, -7.5898], [33.0313, -7.6199], [32.3361, -7.9099], [31.6295, -7.9811]], "MEDIUM"),
            _corridor("A7 Casablanca → Agadir", "Casablanca", "Agadir", [[33.5731, -7.5898], [33.2641, -8.5085], [31.9863, -8.8832], [30.4278, -9.5981]], "HIGH"),
            _corridor("A1 Tanger → Casablanca", "Tanger", "Casablanca", [[35.7595, -5.8340], [34.8804, -5.9058], [33.5731, -7.5898]], "LOW"),
        ]
    )
    db.session.add_all(
        [
            _risk_zone("Agglomération Settat", "INCIDENT", "HIGH", _polygon(33.0010, -7.6166, 0.10), "Zone d'incidents fréquents sur l'A3."),
            _risk_zone("Rocade Casablanca", "CUSTOMS", "MEDIUM", _polygon(33.5930, -7.6562, 0.08), "Point de contrôle douanier."),
            _risk_zone("Approche Agadir nord", "SECURITY", "HIGH", _polygon(30.5500, -9.5500, 0.09), "Sensibilité sécuritaire signalée."),
        ]
    )

    if AuditLog.query.count() == 0:
        db.session.add_all(
            [
                AuditLog(
                    actor_email="admin@raased.ma",
                    action="SYSTEM_INIT",
                    target_type="SYSTEM",
                    details="Initialisation sécurisée du socle opérationnel Raased MENA",
                    ip_address="127.0.0.1",
                ),
                AuditLog(
                    actor_email="admin@raased.ma",
                    action="ORG_APPROVED",
                    target_type="ORGANIZATION",
                    details="Organisation LogiTrans Maroc approuvée par l'administrateur",
                    ip_address="196.200.140.22",
                ),
                AuditLog(
                    actor_email="manager@logitrans.ma",
                    action="CAMARA_QOD_SESSION",
                    target_type="DEVICE",
                    target_id="LGT-TRK-001",
                    details="Allocation dynamique bande passante garantie QoD (5G)",
                    ip_address="105.158.42.11",
                ),
                AuditLog(
                    actor_email="manager@logitrans.ma",
                    action="SIM_SWAP_CHECK",
                    target_type="USER",
                    details="Vérification intégrité SIM réussie pour Mehdi Alaoui (Driver)",
                    ip_address="105.158.42.11",
                ),
            ]
        )

    db.session.commit()