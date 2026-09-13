"""Nœuds LangGraph de SENTRY.

Les nœuds orchestrent PostgreSQL et CAMARA ; ils ne prennent jamais de
décision métier. Les appels CAMARA sont tous conditionnés par le plan explicite
``camara_requests`` et par la présence de paramètres réels.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, func

from app.agent import reasoning, rules
from app.agent.memory import build_situation_text, get_agent_memory
from app.agent.rules import RuleEvaluation
from app.agent.state import AgentState, compute_remaining_time, utc_now_iso
from app.camara.client import CamaraAPIError
from app.camara.congestion import get_congestion_risk
from app.camara.location import fetch_location
from app.camara.qod import request_priority_for_tracker
from app.camara.slicing import create_slice
from app.camara.trust import check_device_swap, check_sim_swap, verify_number
from app.core.config import get_settings
from app.db.models.agent_decisions import AgentDecision
from app.db.models.alerts import Alert
from app.db.models.cargo_trackers import CargoTracker
from app.db.models.cargos import Cargo
from app.db.models.congestion_events import CongestionEvent
from app.db.models.corridor_congestion_baselines import CorridorCongestionBaseline
from app.db.models.corridors import Corridor
from app.db.models.known_context_events import KnownContextEvent
from app.db.models.network_actions import NetworkAction
from app.db.models.risk_assessments import RiskAssessment
from app.db.models.risk_zones import RiskZone
from app.db.models.security_alerts import SecurityAlert
from app.db.models.security_checks import SecurityCheck
from app.db.models.tracker_locations import TrackerLocation
from app.db.models.trackers import Tracker
from app.db.session import AsyncSessionLocal
from app.services.audit import write_audit_log


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _with_missing(update: dict[str, Any], message: str) -> dict[str, Any]:
    """Ajoute une lacune sans écraser celles déjà trouvées dans ce nœud."""
    update.setdefault("missing_information", []).append(message)
    return update


def _security_status(raw: str | None) -> str | None:
    """Traduit explicitement les statuts réellement écrits par trust.py."""
    mapping = {
        "verified": "PASSED", "clean": "PASSED",
        "mismatch": "FAILED", "swap_detected": "FAILED",
        "error": "PENDING",
    }
    return mapping.get((raw or "").lower())


def _evaluation_from_state(state: AgentState) -> RuleEvaluation:
    return RuleEvaluation(
        decision=state.get("decision") or rules.Decision.REQUEST_MORE_INFORMATION,
        risk_score=state.get("risk_score"), risk_level=state.get("risk_level"),
        risk_factors=state.get("risk_factors") or {},
        risk_data_coverage=state.get("risk_data_coverage") or 0.0,
        incident_type=state.get("incident_type"), incident_severity=state.get("incident_severity"),
        requires_human_approval=bool(state.get("requires_human_approval")),
        qod_required=bool(state.get("qod_required")),
        network_slice_required=bool(state.get("network_slice_required")),
        confidence=state.get("confidence"),
        missing_information=list(state.get("missing_information") or []),
        rule_trace=list(state.get("rule_trace") or []),
        notification_required=bool(state.get("notification_required")),
        alert_required=bool(state.get("alert_required")),
        alert_category=state.get("alert_category"),
        recipients=list(state.get("recipients") or []),
    )


async def load_context_node(state: AgentState) -> dict[str, Any]:
    """Charge le contexte disponible sans compléter les données absentes."""
    tracker_id = _uuid(state.get("tracker_id"))
    cargo_id = _uuid(state.get("cargo_id"))
    update: dict[str, Any] = {"evaluated_at": utc_now_iso()}
    missing: list[str] = []

    async with AsyncSessionLocal() as db:
        tracker = await db.get(Tracker, tracker_id) if tracker_id else None
        if tracker is None:
            missing.append("tracker indisponible")
        else:
            update["tracker_id"] = str(tracker.id)
            update["organization_id"] = str(tracker.organization_id)

        assignment = None
        if tracker is not None:
            query = select(CargoTracker).where(
                CargoTracker.tracker_id == tracker.id,
                CargoTracker.unassigned_at.is_(None),
            )
            if cargo_id is not None:
                query = query.where(CargoTracker.cargo_id == cargo_id)
            assignment = (await db.execute(query.order_by(CargoTracker.assigned_at.desc()).limit(1))).scalar_one_or_none()

        cargo = await db.get(Cargo, cargo_id) if cargo_id else None
        if assignment is not None:
            cargo = await db.get(Cargo, assignment.cargo_id)
            update["trip_id"] = str(assignment.id)
        if cargo is None:
            missing.append("cargo indisponible")
        else:
            update.update({
                "cargo_id": str(cargo.id), "cargo_reference": cargo.reference,
                "cargo_type": cargo.type, "criticality": cargo.criticality,
                "cargo_status": cargo.status, "origin": cargo.origin,
                "destination": cargo.destination, "deadline": _iso(cargo.deadline),
                "remaining_time_hours": compute_remaining_time(_iso(cargo.deadline)),
            })

        location = None
        if tracker is not None:
            row = (await db.execute(
                select(TrackerLocation, func.ST_Y(TrackerLocation.location), func.ST_X(TrackerLocation.location))
                .where(TrackerLocation.tracker_id == tracker.id)
                .order_by(TrackerLocation.timestamp.desc()).limit(1)
            )).first()
            if row:
                location, lat, lon = row
                age = (datetime.now(timezone.utc) - location.timestamp).total_seconds()
                update["current_location"] = {
                    "latitude": float(lat), "longitude": float(lon), "accuracy_meters": location.accuracy,
                    "source": location.source, "observed_at": _iso(location.timestamp), "age_seconds": age,
                }
            else:
                missing.append("current_location indisponible")

        event = None
        if tracker is not None:
            event = (await db.execute(
                select(CongestionEvent).where(CongestionEvent.tracker_id == tracker.id)
                .order_by(CongestionEvent.timestamp.desc()).limit(1)
            )).scalar_one_or_none()
        update["incident_detected"] = event is not None
        corridor = None
        if event is not None:
            corridor = await db.get(Corridor, event.corridor_id)
            update["incident"] = {
                "id": str(event.id), "congestion_level": event.congestion_level,
                "confidence_level": float(event.confidence_level) if event.confidence_level is not None else None,
                "source": event.source, "raw_event_id": event.raw_event_id,
                "observed_at": _iso(event.timestamp), "latitude": None, "longitude": None,
            }
            update["network_condition"] = {
                "congestion_level": event.congestion_level,
                "confidence_level": float(event.confidence_level) if event.confidence_level is not None else None,
                "observed_at": _iso(event.timestamp),
            }

        zone = None
        if location is not None:
            zone = (await db.execute(
                select(RiskZone).where(RiskZone.is_active.is_(True), func.ST_Contains(RiskZone.geometry, location.location))
                .order_by(RiskZone.updated_at.desc()).limit(1)
            )).scalar_one_or_none()
            if zone is not None and corridor is None:
                corridor = await db.get(Corridor, zone.corridor_id)
            if zone is not None:
                update["risk_zone"] = {"id": str(zone.id), "name": zone.name, "type": zone.type,
                    "risk_level": zone.risk_level, "description": zone.description, "contains_current_position": True}

        if corridor is None:
            missing.append("corridor indisponible")
        else:
            update["corridor"] = {"id": str(corridor.id), "name": corridor.name, "origin": corridor.origin,
                "destination": corridor.destination, "risk_level": corridor.risk_level, "is_active": corridor.is_active}
            when = event.timestamp if event is not None else datetime.now(timezone.utc)
            baseline = (await db.execute(select(CorridorCongestionBaseline).where(
                CorridorCongestionBaseline.corridor_id == corridor.id,
                CorridorCongestionBaseline.hour_of_day == when.hour,
                CorridorCongestionBaseline.day_of_week == when.weekday(),
            ))).scalar_one_or_none()
            if baseline is not None:
                network = dict(update.get("network_condition") or {})
                network["baseline_level"] = baseline.typical_congestion_level
                network["deviates_from_baseline"] = (
                    event is not None and event.congestion_level != baseline.typical_congestion_level
                )
                update["network_condition"] = network

        if zone is not None:
            known = (await db.execute(select(KnownContextEvent).where(
                KnownContextEvent.zone_id == zone.id,
                KnownContextEvent.starts_at <= datetime.now(timezone.utc),
                KnownContextEvent.ends_at >= datetime.now(timezone.utc),
            ).order_by(KnownContextEvent.starts_at.desc()).limit(1))).scalar_one_or_none()
            if known is not None:
                update["known_context"] = {"id": str(known.id), "event_type": known.event_type,
                    "description": known.description, "starts_at": _iso(known.starts_at),
                    "ends_at": _iso(known.ends_at), "is_active_now": True}

        if tracker is not None:
            checks = (await db.execute(select(SecurityCheck).where(SecurityCheck.tracker_id == tracker.id)
                .order_by(SecurityCheck.timestamp.desc()))).scalars().all()
            latest: dict[str, str] = {}
            for check in checks:
                latest.setdefault(check.check_type.upper(), _security_status(check.status) or check.status)
            update["security_checks"] = latest
            update["security_check_status"] = rules.aggregate_security_status(latest)
            alerts = (await db.execute(select(SecurityAlert).where(
                SecurityAlert.tracker_id == tracker.id, SecurityAlert.resolved_at.is_(None)
            ).order_by(SecurityAlert.created_at.desc()))).scalars().all()
            update["unresolved_security_alerts"] = [{"id": str(a.id), "check_type": a.check_type,
                "severity": a.severity, "status": a.status, "created_at": _iso(a.created_at),
                "security_check_id": str(a.security_check_id) if a.security_check_id else None} for a in alerts]
            actions = (await db.execute(select(NetworkAction).where(
                NetworkAction.tracker_id == tracker.id, NetworkAction.executed_at.is_(None)
            ).order_by(NetworkAction.requested_at.desc()))).scalars().all()
            network = dict(update.get("network_condition") or {})
            for action in actions:
                if action.action_type == rules.Decision.REQUEST_QOD:
                    network["active_qod_status"] = action.status
                elif action.action_type == rules.Decision.REQUEST_NETWORK_SLICE:
                    network["active_slice_status"] = action.status
            if network:
                update["network_condition"] = network

    if missing:
        update["missing_information"] = missing
    return update


async def camara_perception_node(state: AgentState) -> dict[str, Any]:
    """Collecte les signaux CAMARA uniquement sur demande explicite et complète."""
    plan = state.get("camara_requests") or {}
    if not (plan.get("congestion") or plan.get("location")):
        return {}
    tracker_id = _uuid(state.get("tracker_id"))
    corridor_id = _uuid((state.get("corridor") or {}).get("id"))
    settings = get_settings()
    if tracker_id is None:
        return {"missing_information": ["tracker_id indisponible pour la perception CAMARA"]}
    async with AsyncSessionLocal() as db:
        tracker = await db.get(Tracker, tracker_id)
    if tracker is None or not tracker.msisdn:
        return {"missing_information": ["msisdn indisponible pour la perception CAMARA"]}
    update: dict[str, Any] = {}
    location = state.get("current_location") or {}
    try:
        location_is_usable = (
            state.get("current_location") is not None
            and location.get("age_seconds") is not None
            and float(location["age_seconds"]) <= rules.STALE_LOCATION_SECONDS
        )
    except (TypeError, ValueError):
        location_is_usable = False
    if plan.get("location") and not location_is_usable:
        try:
            raw_location = await fetch_location(tracker.msisdn)
        except CamaraAPIError as exc:
            update["errors"] = [f"Location Retrieval indisponible: {exc}"]
        else:
            area = raw_location.get("area") if isinstance(raw_location, dict) else None
            center = area.get("center") if isinstance(area, dict) else None
            if isinstance(center, dict):
                update["network_location_area"] = {
                    "latitude": center.get("latitude"), "longitude": center.get("longitude"),
                    "radius_meters": area.get("radius"), "observed_at": raw_location.get("lastLocationTime"),
                }
            else:
                update["missing_information"] = ["zone retournée par Location Retrieval indisponible"]
    if not plan.get("congestion"):
        return update
    if corridor_id is None:
        update.setdefault("missing_information", []).append("corridor_id indisponible pour Congestion Insights")
        return update
    if not settings.CAMARA_WEBHOOK_SINK_URL or not settings.CAMARA_CONGESTION_NOTIFICATION_AUTH_TOKEN:
        update.setdefault("missing_information", []).append("credentials webhook Congestion Insights indisponibles")
        return update
    try:
        result = await get_congestion_risk(tracker.msisdn, settings.CAMARA_WEBHOOK_SINK_URL,
            settings.CAMARA_CONGESTION_NOTIFICATION_AUTH_TOKEN)
    except CamaraAPIError as exc:
        update.setdefault("errors", []).append(f"Congestion Insights indisponible: {exc}")
        return update
    latest = result.get("latest_interval")
    if not isinstance(latest, dict) or not latest.get("congestionLevel"):
        update.setdefault("missing_information", []).append("intervalle CAMARA de congestion indisponible")
        return update
    observed = latest.get("timeIntervalStop")
    if not observed:
        return _with_missing(update, "horodatage CAMARA de congestion requis pour persister l'événement")
    try:
        timestamp = datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return _with_missing(update, "horodatage CAMARA de congestion illisible")
    event = CongestionEvent(tracker_id=tracker_id, corridor_id=corridor_id,
        congestion_level=str(latest["congestionLevel"]).lower(),
        confidence_level=result.get("confidence_normalized"), timestamp=timestamp,
        source="CAMARA_CONGESTION_INSIGHTS", raw_event_id=latest.get("id"))
    async with AsyncSessionLocal() as db:
        db.add(event)
        await db.commit()
        await db.refresh(event)
    update.update({"incident_detected": True, "incident": {"id": str(event.id),
        "congestion_level": event.congestion_level, "confidence_level": result.get("confidence_normalized"),
        "source": event.source, "raw_event_id": event.raw_event_id, "observed_at": _iso(timestamp)},
        "network_condition": {"congestion_level": event.congestion_level,
            "confidence_level": result.get("confidence_normalized"), "observed_at": _iso(timestamp)}})
    return update


async def trust_checks_node(state: AgentState) -> dict[str, Any]:
    """Exécute seulement les vérifications CAMARA explicitement demandées."""
    plan = state.get("camara_requests") or {}
    tracker_id = _uuid(state.get("tracker_id"))
    requested_checks = any(plan.get(key) for key in (
        "number_verification", "sim_swap", "device_swap",
    ))
    if tracker_id is None:
        return {"missing_information": ["tracker_id indisponible pour les contrôles CAMARA"]} if requested_checks else {}
    performed: dict[str, str] = {}
    try:
        async with AsyncSessionLocal() as db:
            if plan.get("number_verification"):
                performed["NUMBER_VERIFICATION"] = _security_status((await verify_number(db, tracker_id)).status) or "PENDING"
            if plan.get("sim_swap"):
                performed["SIM_SWAP"] = _security_status((await check_sim_swap(db, tracker_id)).status) or "PENDING"
            if plan.get("device_swap"):
                performed["DEVICE_SWAP"] = _security_status((await check_device_swap(db, tracker_id)).status) or "PENDING"
    except (CamaraAPIError, ValueError) as exc:
        return {"errors": [f"Contrôle de confiance CAMARA indisponible: {exc}"]}
    if not performed:
        return {}
    merged = {**(state.get("security_checks") or {}), **performed}
    return {"security_checks": merged, "security_check_status": rules.aggregate_security_status(merged)}


async def weather_node(state: AgentState) -> dict[str, Any]:
    """CHECK_WEATHER conditionnel : nouvelle zone, intervalle dépassé ou risque déjà détecté.

    Réutilise `app/weather/weather.py` (cache WEATHER_CACHE_MINUTES).
    Fallback propre : WeatherAPIError -> `weather.fetch_error`, jamais de crash.
    """
    corridor = state.get("corridor") or {}
    corridor_id = _uuid(corridor.get("id"))
    if corridor_id is None:
        return {}
    # Déjà une météo fraîche dans l'état ? Inutile de rappeler l'API.
    existing = state.get("weather") or {}
    if existing and not existing.get("fetch_error") and existing.get("recorded_at"):
        try:
            recorded = datetime.fromisoformat(str(existing["recorded_at"]).replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - recorded).total_seconds() / 60.0
            if age_min < get_settings().WEATHER_CACHE_MINUTES and not state.get("incident_detected"):
                return {}
        except (TypeError, ValueError):
            pass
    try:
        from app.weather.weather import get_corridor_weather
        async with AsyncSessionLocal() as db:
            result = await get_corridor_weather(db, corridor_id)
        return {"weather": {
            "temperature_c": result.get("temperature_c"),
            "wind_speed_kmh": result.get("wind_speed_kmh"),
            "visibility_m": result.get("visibility_m"),
            "weather_code": result.get("weather_code"),
            "degraded_conditions": result.get("degraded_conditions"),
            "recorded_at": result.get("recorded_at"),
            "from_cache": result.get("from_cache"),
        }}
    except Exception as exc:  # WeatherAPIError, DB, centroid : fallback sans planter
        return {"weather": {"fetch_error": str(exc)[:300]},
                "errors": [f"Weather API indisponible: {exc}"]}


async def fuse_context_node(state: AgentState) -> dict[str, Any]:
    """FUSE_CONTEXT : croise cargo+route+location+weather+network sans inventer.

    Construit `route_progress` (dérivé) et `fused_context` (texte factuel pour
    le LLM et l'audit). Ne décide pas : prépare `rules_node`.
    """
    corridor = state.get("corridor") or {}
    remaining = state.get("remaining_time_hours")
    location = state.get("current_location") or {}
    weather = state.get("weather") or {}
    route: dict[str, Any] = {
        "origin": state.get("origin"),
        "destination": state.get("destination"),
        "progress_pct": None,
        "deviation_suspected": None,
        "delay_risk": (remaining is not None and remaining <= rules.DEADLINE_WARNING_HOURS
                       and state.get("incident_detected") is True),
        "corridor_closed": (corridor.get("is_active") is False
                            if corridor else None),
        "road_closed": None,
    }
    parts: list[str] = []
    if state.get("cargo_reference"):
        parts.append(f"cargo {state.get('cargo_reference')} ({state.get('criticality')})")
    if corridor.get("name"):
        parts.append(f"corridor {corridor.get('name')}")
    if location.get("latitude") is not None:
        parts.append(f"position {location.get('latitude')},{location.get('longitude')}")
    zone = state.get("risk_zone") or {}
    if zone.get("name"):
        parts.append(f"zone {zone.get('name')}")
    if weather.get("degraded_conditions") is True:
        parts.append(f"météo dégradée code {weather.get('weather_code')}")
    network = state.get("network_condition") or {}
    if network.get("congestion_level"):
        parts.append(f"congestion {network.get('congestion_level')}")
    if remaining is not None:
        parts.append(f"reste {remaining:.1f}h")
    fused = " | ".join(parts) if parts else "Contexte partiel : informations indisponibles."
    return {"route_progress": route, "fused_context": fused}


async def similar_cases_node(state: AgentState) -> dict[str, Any]:
    """SEARCH_SIMILAR_CASES : réutilise `memory.py`, jamais de 2e mémoire."""
    try:
        query = build_situation_text(state)
        results = get_agent_memory().search_similar(query, n_results=3)
        return {"historical_cases": results}
    except Exception as exc:
        return {"errors": [f"Mémoire indisponible pour la recherche: {exc}"]}


async def rules_node(state: AgentState) -> dict[str, Any]:
    return rules.evaluate(state).as_state_update()


async def reasoning_node(state: AgentState) -> dict[str, Any]:
    return (await reasoning.aanalyze(state, _evaluation_from_state(state))).as_state_update()


async def persist_assessment_node(state: AgentState) -> dict[str, Any]:
    """Persiste seulement une évaluation dont toutes les FK obligatoires existent."""
    tracker_id, cargo_id = _uuid(state.get("tracker_id")), _uuid(state.get("cargo_id"))
    organization_id = _uuid(state.get("organization_id"))
    corridor_id = _uuid((state.get("corridor") or {}).get("id"))
    # congestion_events.id est un entier, pas un UUID.
    try:
        congestion_event_id = int((state.get("incident") or {}).get("id"))
    except (TypeError, ValueError):
        congestion_event_id = None
    if not all((tracker_id, cargo_id, organization_id, corridor_id, congestion_event_id is not None,
                state.get("risk_level"), state.get("risk_score") is not None, state.get("decision"))):
        return {"missing_information": ["FK ou évaluation requis pour persister la décision indisponible"]}
    async with AsyncSessionLocal() as db:
        assessment = RiskAssessment(tracker_id=tracker_id, cargo_id=cargo_id, corridor_id=corridor_id,
            congestion_event_id=congestion_event_id, risk_level=state["risk_level"],
            risk_score=state["risk_score"], confidence_score=state.get("confidence"),
            reason=state.get("justification"), factors=state.get("risk_factors"),
            security_snapshot=state.get("security_checks"))
        db.add(assessment)
        await db.flush()
        decision = AgentDecision(risk_assessment_id=assessment.id, tracker_id=tracker_id, cargo_id=cargo_id,
            decision=state["decision"], reasoning_summary=state.get("justification"),
            confidence=state.get("confidence"), requires_human_approval=bool(state.get("requires_human_approval")))
        db.add(decision)
        await db.flush()
        if state["decision"] != rules.Decision.MONITOR:
            category = state.get("alert_category")
            prefix = f"[{category}] " if category else ""
            recipients = state.get("recipients") or []
            db.add(Alert(
                organization_id=organization_id,
                cargo_id=cargo_id,
                tracker_id=tracker_id,
                risk_assessment_id=assessment.id,
                severity=state.get("risk_level") or "UNKNOWN",
                title=f"Décision SENTRY : {state['decision']}",
                message=prefix + (state.get("justification") or "Décision déterministe SENTRY enregistrée."),
                status="OPEN",
            ))
        else:
            recipients = []
        await write_audit_log(db, organization_id=organization_id,
            action="agent_decision_created", entity_type="agent_decision", entity_id=decision.id,
            result=state["decision"], payload={"risk_assessment_id": str(assessment.id),
                "recipients": state.get("recipients") or recipients,
                "notification_required": state.get("notification_required"),
                "alert_required": state.get("alert_required"),
                "alert_category": state.get("alert_category")}, commit=False)
        await db.commit()
    return {"risk_assessment_id": str(assessment.id), "agent_decision_id": str(decision.id)}


async def network_action_node(state: AgentState) -> dict[str, Any]:
    """Exécute une seule action réseau autorisée, sans valeurs de démonstration."""
    if state.get("requires_human_approval") and state.get("human_approved") is not True:
        return {}
    tracker_id, assessment_id = _uuid(state.get("tracker_id")), _uuid(state.get("risk_assessment_id"))
    if tracker_id is None or assessment_id is None:
        return {"missing_information": ["identifiants requis pour network_actions indisponibles"]}
    async with AsyncSessionLocal() as db:
        tracker = await db.get(Tracker, tracker_id)
    if tracker is None or not tracker.msisdn:
        return {"missing_information": ["msisdn indisponible pour action CAMARA"]}

    async def record_failure(action_type: str, error: str, response: dict[str, Any] | None = None) -> None:
        """Conserve l'échec réel d'un appel déjà tenté dans network_actions."""
        async with AsyncSessionLocal() as db:
            db.add(NetworkAction(
                tracker_id=tracker_id,
                risk_assessment_id=assessment_id,
                action_type=action_type,
                status="ERROR",
                executed_at=datetime.now(timezone.utc),
                response=response,
                error_message=error,
            ))
            await db.commit()

    if state.get("decision") in (rules.Decision.REQUEST_QOD, rules.Decision.IMPROVE_CONNECTIVITY) and state.get("qod_required"):
        if (state.get("network_condition") or {}).get("active_qod_status"):
            return {"missing_information": ["action QoD équivalente déjà active"]}
        params = state.get("qod_parameters") or {}
        required = ("device_public_ip", "device_private_ip", "application_server_ip", "qos_profile", "duration")
        if any(not params.get(name) for name in required):
            return {"missing_information": ["paramètres QoD réels indisponibles"]}
        try:
            response = await request_priority_for_tracker(tracker.msisdn, params["device_public_ip"],
                params["device_private_ip"], params["application_server_ip"], params["qos_profile"], params["duration"])
        except CamaraAPIError as exc:
            await record_failure(rules.Decision.REQUEST_QOD, str(exc))
            return {"errors": [f"QoD CAMARA indisponible: {exc}"]}
        status = response.get("qosStatus")
        if not status:
            await record_failure(rules.Decision.REQUEST_QOD, "Réponse QoD sans qosStatus", response)
            return {"missing_information": ["statut de réponse QoD indisponible"]}
        action_type = rules.Decision.REQUEST_QOD
    elif state.get("decision") == rules.Decision.REQUEST_NETWORK_SLICE and state.get("network_slice_required"):
        if (state.get("network_condition") or {}).get("active_slice_status"):
            return {"missing_information": ["Network Slice équivalent déjà actif"]}
        payload = state.get("slice_request_payload")
        required_slice_fields = (
            "notificationUrl", "notificationAuthToken", "networkIdentifier", "sliceInfo",
            "maxDataConnections", "maxDevices", "sliceUplinkThroughput", "deviceUplinkThroughput",
        )
        if (not isinstance(payload, dict) or not payload
                or any(not payload.get(name) for name in required_slice_fields)):
            return {"missing_information": ["payload Network Slice réel indisponible"]}
        try:
            response = await create_slice(payload)
        except CamaraAPIError as exc:
            await record_failure(rules.Decision.REQUEST_NETWORK_SLICE, str(exc))
            return {"errors": [f"Network Slice CAMARA indisponible: {exc}"]}
        status = response.get("state") or response.get("status")
        if not status:
            await record_failure(rules.Decision.REQUEST_NETWORK_SLICE, "Réponse Network Slice sans statut", response)
            return {"missing_information": ["statut de réponse Network Slice indisponible"]}
        action_type = rules.Decision.REQUEST_NETWORK_SLICE
    else:
        return {}
    async with AsyncSessionLocal() as db:
        action = NetworkAction(tracker_id=tracker_id, risk_assessment_id=assessment_id,
            action_type=action_type, status=str(status), request_id=response.get("sessionId") or response.get("name"),
            response=response)
        db.add(action)
        await db.commit()
    return {}


async def memory_node(state: AgentState) -> dict[str, Any]:
    """Mémorise seulement une décision déjà persistée, sans recopier PostgreSQL."""
    decision_id = state.get("agent_decision_id")
    if not decision_id:
        return {}
    try:
        weather = state.get("weather") or {}
        get_agent_memory().store_memory(str(decision_id), build_situation_text(state), {
            "cargo_id": state.get("cargo_id"), "trip_id": state.get("trip_id"),
            "criticality": state.get("criticality"), "incident_type": state.get("incident_type"),
            "risk_level": state.get("risk_level"), "decision": state.get("decision"),
            "human_approval": state.get("requires_human_approval"),
            "alert_category": state.get("alert_category"),
            "weather_code": weather.get("weather_code"),
            "timestamp": state.get("evaluated_at"),
        })
    except Exception as exc:
        return {"errors": [f"Mémoire ChromaDB indisponible: {exc}"]}
    return {}


__all__ = ["camara_perception_node", "load_context_node", "memory_node", "network_action_node",
           "persist_assessment_node", "reasoning_node", "rules_node", "trust_checks_node",
           "weather_node", "fuse_context_node", "similar_cases_node"]
