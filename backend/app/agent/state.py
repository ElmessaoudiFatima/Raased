"""
État partagé de l'agent SENTRY (Raased) — couche LangGraph.

Ce module ne contient QUE la structure de données qui circule entre les noeuds
du graphe LangGraph. Il ne fait aucun appel réseau, aucune requête SQL, aucun
appel LLM : il est donc importable et testable même avec une base vide.

------------------------------------------------------------------------------
CONVENTION FONDAMENTALE — ABSENCE DE DONNÉE
------------------------------------------------------------------------------
La base PostgreSQL du projet est actuellement VIDE. L'agent doit donc être
capable de fonctionner sans jamais fabriquer de valeur.

    None  ==  « l'information n'est PAS disponible dans PostgreSQL »
    None  !=  « non »
    None  !=  0
    None  !=  "aucun"

Autrement dit : un champ à None signifie « je ne sais pas », jamais « il n'y a
rien ». Cette distinction est vitale pour la logistique : confondre
« aucun incident détecté » et « je n'ai pas pu vérifier s'il y a un incident »
produirait exactement le type de faux négatif que le projet cherche à éviter.

Pour exprimer explicitement un « non » vérifié, on utilise un booléen à trois
états (`Optional[bool]`) :

    True   -> la base a été interrogée, le fait est confirmé
    False  -> la base a été interrogée, le fait est infirmé
    None   -> la base n'a pas pu répondre / aucune donnée

Chaque champ manquant qui était nécessaire au raisonnement DOIT être ajouté à
`missing_information` (voir `record_missing`). C'est ce qui permet à l'agent de
répondre « information indisponible » au lieu d'inventer.

------------------------------------------------------------------------------
CORRESPONDANCE AVEC LE SCHÉMA POSTGRESQL RÉEL
------------------------------------------------------------------------------
Les sous-structures ci-dessous sont calquées sur les colonnes réellement
présentes dans `app/db/models/`. Aucun champ n'est inventé : si une donnée
n'existe pas encore en base, elle n'apparaît pas ici, ou elle est documentée
comme « non mappable aujourd'hui ». Un état ne conserve que les données
opérationnelles ou dérivées nécessaires à un cycle SENTRY.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from typing_extensions import Annotated, TypedDict
from langgraph.graph import add_messages

# ---------------------------------------------------------------------------
# Réducteurs LangGraph
# ---------------------------------------------------------------------------
# Sans réducteur, quand deux noeuds successifs renvoient la même clé, la
# seconde valeur ÉCRASE la première. Pour `missing_information`, ce comportement
# serait faux : chaque noeud découvre ses propres lacunes et elles doivent
# toutes être conservées. On fournit donc un réducteur d'accumulation.


def merge_missing(current: Optional[list[str]], update: Optional[list[str]]) -> list[str]:
    """
    Réducteur LangGraph pour `missing_information`.

    Concatène les lacunes signalées par les différents noeuds, en supprimant les
    doublons tout en préservant l'ordre de découverte (utile pour l'audit et
    pour l'affichage dans le dashboard manager).
    """
    merged: list[str] = []
    for source in (current or [], update or []):
        for item in source:
            if item and item not in merged:
                merged.append(item)
    return merged


def merge_trace(current: Optional[list[str]], update: Optional[list[str]]) -> list[str]:
    """
    Réducteur LangGraph pour `rule_trace` : accumule, sans dédoublonner.

    Contrairement aux lacunes, une même règle peut légitimement s'appliquer
    plusieurs fois dans un même cycle ; on garde donc la trace chronologique
    complète telle quelle (traçabilité réglementaire / couche d'audit).
    """
    return [*(current or []), *(update or [])]


# ---------------------------------------------------------------------------
# Sous-structures (miroirs des lignes PostgreSQL)
# ---------------------------------------------------------------------------


class LocationSnapshot(TypedDict, total=False):
    """
    Dernière position connue du tracker.

    Source : table `tracker_locations` (colonnes location POINT/4326, accuracy,
    source, timestamp). Les coordonnées sont extraites du POINT PostGIS ; elles
    ne sont JAMAIS estimées ni interpolées.
    """

    latitude: Optional[float]           # extrait de ST_Y(location)
    longitude: Optional[float]          # extrait de ST_X(location)
    accuracy_meters: Optional[float]    # tracker_locations.accuracy (Double)
    source: Optional[str]               # tracker_locations.source (ex. "CAMARA_LOCATION", "GPS")
    observed_at: Optional[str]          # tracker_locations.timestamp, sérialisé ISO-8601
    age_seconds: Optional[float]        # fraîcheur calculée ; None si timestamp absent


class CorridorSnapshot(TypedDict, total=False):
    """
    Corridor logistique emprunté.

    Source : table `corridors` (name, origin, destination, risk_level,
    is_active). La géométrie LINESTRING n'est pas transportée dans l'état :
    elle reste en base et est exploitée par les requêtes PostGIS.
    """

    id: Optional[str]                   # corridors.id (UUID sérialisé)
    name: Optional[str]                 # corridors.name
    origin: Optional[str]               # corridors.origin
    destination: Optional[str]          # corridors.destination
    risk_level: Optional[str]           # corridors.risk_level (niveau structurel du corridor)
    is_active: Optional[bool]           # corridors.is_active


class RiskZoneSnapshot(TypedDict, total=False):
    """
    Zone à risque dans laquelle se trouve le tracker, si la géométrie le confirme.

    Source : table `risk_zones` (POLYGON/4326) croisée avec la position via
    ST_Contains. `contains_current_position` reste None si la position OU la
    zone est indisponible : on ne suppose jamais qu'un véhicule est hors zone.
    """

    id: Optional[str]                          # risk_zones.id
    name: Optional[str]                        # risk_zones.name
    type: Optional[str]                        # risk_zones.type
    risk_level: Optional[str]                  # risk_zones.risk_level
    description: Optional[str]                 # risk_zones.description
    contains_current_position: Optional[bool]  # résultat ST_Contains ; None = non évaluable


class IncidentSnapshot(TypedDict, total=False):
    """
    Événement déclencheur du cycle d'analyse.

    Source : table `congestion_events`, alimentée par les webhooks CAMARA via la
    couche de vérification. L'agent NE construit PAS cet événement : il le lit.
    """

    id: Optional[str]                     # congestion_events.id (int sérialisé)
    congestion_level: Optional[str]       # congestion_events.congestion_level (catégoriel)
    confidence_level: Optional[float]     # congestion_events.confidence_level (DECIMAL 0..1)
    source: Optional[str]                 # congestion_events.source (provenance de la donnée)
    raw_event_id: Optional[str]           # congestion_events.raw_event_id (corrélation CAMARA)
    observed_at: Optional[str]            # congestion_events.timestamp, ISO-8601
    latitude: Optional[float]             # ST_Y(congestion_events.location) si présent
    longitude: Optional[float]            # ST_X(congestion_events.location) si présent


class NetworkCondition(TypedDict, total=False):
    """
    Condition réseau observée sur le tracker.

    Source : `congestion_events` (niveau + confiance) et, à terme,
    `network_actions` pour l'état des actions QoD / slicing déjà en cours.
    Sert à décider s'il faut sécuriser le lien (QoD / Network Slice).
    """

    congestion_level: Optional[str]        # niveau catégoriel observé
    confidence_level: Optional[float]      # confiance de la mesure (0..1)
    baseline_level: Optional[str]          # corridor_congestion_baselines.typical_congestion_level
    deviates_from_baseline: Optional[bool] # True/False si comparable ; None si baseline absente
    observed_at: Optional[str]             # horodatage de la mesure, ISO-8601
    active_qod_status: Optional[str]       # network_actions.status pour un QoD en cours
    active_slice_status: Optional[str]     # network_actions.status pour un slice en cours


class SecurityAlertSnapshot(TypedDict, total=False):
    """Alerte de sécurité non résolue concernant le tracker.

    Source : table `security_alerts`. Une alerte peut ne pas avoir de
    `security_check_id` : elle doit donc rester visible même si les contrôles
    agrégés ne permettent pas de conclure. Le noeud d'enrichissement ne place
    ici que les lignes dont `resolved_at IS NULL`; `None` signifie que cette
    information n'a pas pu être recherchée et `[]` qu'aucune alerte non
    résolue n'a été trouvée.
    """

    id: Optional[str]                 # security_alerts.id
    check_type: Optional[str]         # security_alerts.check_type
    severity: Optional[str]           # security_alerts.severity
    status: Optional[str]             # security_alerts.status
    created_at: Optional[str]         # security_alerts.created_at, ISO-8601
    security_check_id: Optional[str]  # security_alerts.security_check_id (nullable)


class CamaraRequestPlan(TypedDict, total=False):
    """Demandes CAMARA explicites apportées par un déclencheur fiable."""

    congestion: bool
    location: bool
    number_verification: bool
    sim_swap: bool
    device_swap: bool


class QoDParameters(TypedDict, total=False):
    """Paramètres réels requis par CAMARA QoD, fournis hors PostgreSQL."""

    device_public_ip: str
    device_private_ip: str
    application_server_ip: str
    qos_profile: str
    duration: int


class NetworkLocationArea(TypedDict, total=False):
    """Zone réellement retournée par CAMARA Location Retrieval, jamais un GPS."""

    latitude: Optional[float]
    longitude: Optional[float]
    radius_meters: Optional[float]
    observed_at: Optional[str]


class KnownContextSnapshot(TypedDict, total=False):
    """
    Événement de contexte connu (travaux, manifestation, fermeture planifiée).

    Source : table `known_context_events` liée à `risk_zones`.
    Rôle métier : c'est le principal réducteur de FAUX POSITIFS. Une congestion
    déjà expliquée par un événement planifié ne doit pas déclencher la même
    escalade qu'une congestion inexpliquée.
    """

    id: Optional[str]              # known_context_events.id
    event_type: Optional[str]      # known_context_events.event_type
    description: Optional[str]     # known_context_events.description
    starts_at: Optional[str]       # known_context_events.starts_at, ISO-8601
    ends_at: Optional[str]         # known_context_events.ends_at, ISO-8601
    is_active_now: Optional[bool]  # True si l'instant courant est dans la fenêtre


class WeatherSnapshot(TypedDict, total=False):
    """
    Conditions météo liées au corridor / à la position du cargo.

    Source : `weather_snapshots` (cache Open-Meteo, voir `app/weather/weather.py`).
    Contexte uniquement : n'est jamais un moteur de décision autonome.
    `from_cache=True` signifie un relevé récent réutilisé (< WEATHER_CACHE_MINUTES).
    `fetch_error` porte le message d'indisponibilité sans faire planter le cycle.
    """

    temperature_c: Optional[float]
    wind_speed_kmh: Optional[float]
    visibility_m: Optional[float]
    weather_code: Optional[int]
    degraded_conditions: Optional[bool]
    recorded_at: Optional[str]
    from_cache: Optional[bool]
    fetch_error: Optional[str]


class RouteProgressSnapshot(TypedDict, total=False):
    """
    Progression du cargo du départ vers la destination.

    Dérivé des données réelles (`current_location`, `origin/destination`,
    `remaining_time_hours`) : aucune table `routes/trips` n'est créée.
    `deviation_suspected` reste None si la comparaison est impossible.
    """

    origin: Optional[str]
    destination: Optional[str]
    progress_pct: Optional[float]
    deviation_suspected: Optional[bool]
    delay_risk: Optional[bool]
    corridor_closed: Optional[bool]
    road_closed: Optional[bool]


# ---------------------------------------------------------------------------
# État principal du graphe
# ---------------------------------------------------------------------------


class AgentState(TypedDict, total=False):
    """
    État partagé entre tous les noeuds du graphe LangGraph.

    `total=False` : aucune clé n'est obligatoire. Cela permet à chaque noeud de
    ne renvoyer QUE les clés qu'il a réellement pu renseigner (mise à jour
    partielle, comportement natif de LangGraph), et de construire un état
    initial minimal quand la base ne contient encore rien.
    """

    # === IDENTIFICATION =====================================================

    cargo_id: Optional[str]
    """`cargos.id`. Identifiant de la cargaison analysée. None si le cycle a été
    déclenché sans cargaison résoluble (ex. tracker non affecté)."""

    tracker_id: Optional[str]
    """`trackers.id`. Le tracker est l'entité réellement mesurée par CAMARA
    (device_id / msisdn) ; c'est la clé de jointure de tous les événements."""

    trip_id: Optional[str]
    """`cargo_trackers.id` — l'affectation active cargo <-> tracker.
    Il n'existe PAS de table `trips` dans le schéma : cette affectation est la
    seule notion de « trajet » réellement persistée. On ne crée pas d'identifiant
    synthétique."""

    organization_id: Optional[str]
    """`organizations.id`. Nécessaire au cloisonnement multi-tenant : un manager
    ne doit voir que les décisions de son organisation."""

    # === CARGAISON ==========================================================

    cargo_reference: Optional[str]
    """`cargos.reference`. Référence métier lisible, affichée au manager."""

    cargo_type: Optional[str]
    """`cargos.type`. Nature de la marchandise (déterminée en base, non déduite)."""

    criticality: Optional[str]
    """`cargos.criticality`. Criticité déclarée de la cargaison.
    Vocabulaire canonique défini dans `rules.Criticality`. Facteur de risque à
    plus fort poids : une même congestion n'a pas le même impact sur du
    matériel médical et sur du fret ordinaire."""

    cargo_status: Optional[str]
    """`cargos.status`. Statut du cycle de vie (permet d'ignorer une cargaison
    déjà livrée ou annulée)."""

    origin: Optional[str]
    """`cargos.origin`."""

    destination: Optional[str]
    """`cargos.destination`."""

    deadline: Optional[str]
    """`cargos.deadline`, sérialisé ISO-8601. Nullable en base : une cargaison
    peut légitimement ne pas avoir d'échéance."""

    remaining_time_hours: Optional[float]
    """Heures restantes avant `deadline`, calculées par `compute_remaining_time`.

    Valeur DÉRIVÉE d'une donnée réelle, jamais estimée : None si `deadline` est
    absente. Peut être négative si l'échéance est dépassée — on ne borne pas à
    zéro, car un retard constaté est une information à part entière."""

    # === POSITION / GÉOGRAPHIE ==============================================

    current_location: Optional[LocationSnapshot]
    """Dernière position connue (`tracker_locations`). None = aucune position en
    base. Ne JAMAIS substituer l'origine, la destination ou un centroïde de
    corridor à une position inconnue."""

    network_location_area: Optional[NetworkLocationArea]
    """Zone CAMARA de localisation réseau, distincte d'une position ponctuelle."""

    corridor: Optional[CorridorSnapshot]
    """Corridor emprunté (`corridors`)."""

    risk_zone: Optional[RiskZoneSnapshot]
    """Zone à risque contenant la position, si ST_Contains le confirme."""

    known_context: Optional[KnownContextSnapshot]
    """Événement de contexte connu expliquant éventuellement l'incident."""

    # === INCIDENT ===========================================================

    incident: Optional[IncidentSnapshot]
    """Événement déclencheur brut (`congestion_events`)."""

    incident_detected: Optional[bool]
    """Booléen à trois états :
    True  = un incident actif a été trouvé en base
    False = la base a été interrogée, aucun incident actif
    None  = la base n'a pas pu être interrogée / aucune donnée disponible"""

    incident_type: Optional[str]
    """Nature de l'incident, normalisée par `rules.IncidentType` à partir des
    données réelles (congestion, entrée en zone à risque, perte de signal...).
    None si l'incident existe mais que sa nature n'est pas déterminable."""

    incident_severity: Optional[str]
    """Sévérité de l'incident (`rules.Severity`), déduite du niveau de
    congestion réel et de la criticité de la zone. None si non calculable."""

    # === RÉSEAU / SÉCURITÉ ==================================================

    network_condition: Optional[NetworkCondition]
    """Condition réseau observée sur le tracker."""

    security_check_status: Optional[str]
    """Statut agrégé des vérifications de confiance (`security_checks.status`)
    consolidé par `rules.aggregate_security_status` :
    PASSED / FAILED / PENDING, ou None si aucune vérification en base.
    None ne vaut PAS « sécurité validée »."""

    security_checks: Optional[dict[str, str]]
    """Détail par type de contrôle, ex. {"SIM_SWAP": "PASSED", "DEVICE_SWAP": "FAILED"}.
    Construit depuis `security_checks.check_type` -> `security_checks.status`.
    Permet au dashboard admin de montrer QUEL contrôle a échoué."""

    unresolved_security_alerts: Optional[list[SecurityAlertSnapshot]]
    """Alertes `security_alerts` du tracker dont `resolved_at IS NULL`.

    Cette information ne remplace pas `security_checks` : elle couvre aussi les
    alertes sans contrôle lié. Elle est un signal de protection déterministe,
    mais ses valeurs textuelles restent celles réellement stockées en base.
    """

    # === RÉSULTAT DE L'ÉVALUATION DÉTERMINISTE ==============================

    risk_score: Optional[float]
    """Score de risque dans [0.0, 1.0], calculé par `rules.compute_risk_score`.

    Aligné sur `risk_assessments.risk_score` qui est un DECIMAL(5,4) : l'échelle
    est bien 0..1 et non 0..100. None si aucun facteur de risque n'est
    disponible — un score n'est jamais fabriqué à partir de rien."""

    risk_level: Optional[str]
    """Niveau de risque (`rules.RiskLevel`), obtenu par seuillage du score.
    None si `risk_score` est None."""

    risk_factors: Optional[dict[str, Any]]
    """Détail des facteurs ayant contribué au score : {nom: {"value", "weight",
    "contribution"}}. Alimentera `risk_assessments.factors` (JSON). C'est ce qui
    rend le score explicable au manager plutôt qu'opaque."""

    risk_data_coverage: Optional[float]
    """Part des facteurs de risque réellement disponibles, dans [0.0, 1.0].

    Garde-fou central contre l'invention : un score calculé sur 20 % des
    facteurs n'a pas la même valeur qu'un score calculé sur 100 %. En dessous du
    seuil `rules.MIN_RISK_DATA_COVERAGE`, l'agent refuse de conclure et demande
    des informations complémentaires."""

    # === DÉCISION ===========================================================

    decision: Optional[str]
    """Décision finale, parmi les 7 valeurs de `rules.Decision`.
    Contrainte base : `agent_decisions.decision` est un String(40)."""

    reasoning: Optional[str]
    """Raisonnement analytique produit par le LLM (analyse contextuelle).
    Destiné à l'audit et au dashboard admin."""

    justification: Optional[str]
    """Justification courte et lisible de la décision, destinée au manager et,
    sous forme simplifiée, au chauffeur. Alimentera
    `agent_decisions.reasoning_summary`."""

    confidence: Optional[float]
    """Confiance de l'agent dans sa décision, dans [0.0, 1.0].
    Alimentera `agent_decisions.confidence` (DECIMAL 5,4)."""

    requires_human_approval: Optional[bool]
    """True si la décision doit être validée par un MANAGER avant exécution
    (Human-in-the-Loop). Alimentera `agent_decisions.requires_human_approval`."""

    human_approved: Optional[bool]
    """Résultat de la validation humaine :
    True  = approuvée par un manager (`agent_decisions.approved_by`)
    False = refusée
    None  = en attente, ou validation non requise
    L'agent n'exécute JAMAIS une action coûteuse tant que ce champ est None
    alors que `requires_human_approval` vaut True."""

    # === ACTIONS RÉSEAU DEMANDÉES ===========================================

    qod_required: Optional[bool]
    """True si une session Quality on Demand doit être demandée (CAMARA QoD).
    Réponse ponctuelle : sécuriser le lien d'UN tracker pendant un incident."""

    network_slice_required: Optional[bool]
    """True si une tranche réseau dédiée doit être demandée (CAMARA Network
    Slicing). Réponse structurelle et plus coûteuse : garantir la connectivité
    d'une opération critique dans la durée."""

    camara_requests: Optional[CamaraRequestPlan]
    """Plan explicite des appels de perception/confiance nécessaires."""

    qod_parameters: Optional[QoDParameters]
    """Paramètres QoD réels ; leur absence interdit toute demande QoD."""

    slice_request_payload: Optional[dict[str, Any]]
    """Payload complet et réel d'une demande CAMARA Network Slice."""

    risk_assessment_id: Optional[str]
    """Identifiant de `risk_assessments` créé pendant ce cycle."""

    agent_decision_id: Optional[str]
    """Identifiant de `agent_decisions` créé pendant ce cycle."""

    # === CONTEXTE FUSIONNÉ / MÉTÉO / ROUTE ==================================

    weather: Optional[WeatherSnapshot]
    """Météo du corridor (contexte Open-Meteo). None = non consultée/indisponible."""

    route_progress: Optional[RouteProgressSnapshot]
    """Progression départ -> destination, dérivée sans table supplémentaire."""

    fused_context: Optional[str]
    """Résumé factuel multi-sources (cargo+route+location+weather+network)."""

    historical_cases: Optional[list[dict[str, Any]]]
    """Cas similaires retrouvés via `memory.py` (réutilisation, pas de 2e mémoire)."""

    # === NOTIFICATION / ALERTE / DESTINATAIRES ===============================

    notification_required: Optional[bool]
    """True = information à pousser (ex. changement météo sans danger immédiat)."""

    alert_required: Optional[bool]
    """True = attention particulière requise (risque avéré)."""

    alert_category: Optional[str]
    """Catégorie typée sans colonne DB : ROAD_CLOSED, DANGEROUS_WEATHER, etc."""

    recipients: Optional[list[str]]
    """Sous-ensemble de ["MANAGER", "DRIVER", "TRACKER"]. CANCEL -> ["MANAGER"]."""

    # === TRAÇABILITÉ / LACUNES ==============================================

    missing_information: Annotated[list[str], merge_missing]
    """Liste des informations nécessaires MAIS ABSENTES de PostgreSQL.

    Cœur du dispositif anti-invention. Alimentée par tous les noeuds via le
    réducteur `merge_missing`. Si elle n'est pas vide et que les données
    manquantes sont critiques, la décision devient REQUEST_MORE_INFORMATION
    (ou HUMAN_APPROVAL si la cargaison est elle-même critique)."""

    rule_trace: Annotated[list[str], merge_trace]
    """Identifiants des règles déterministes réellement appliquées, dans
    l'ordre. Permet de répondre « pourquoi cette décision ? » sans interroger le
    LLM, et alimentera `audit_logs`."""

    llm_available: Optional[bool]
    """True si le LLM a répondu, False s'il a été indisponible (clé absente,
    erreur SDK, JSON invalide). En mode dégradé, la décision reste celle du
    moteur de règles : l'agent continue de fonctionner sans le LLM."""

    evaluated_at: Optional[str]
    """Horodatage ISO-8601 (UTC) du cycle d'évaluation."""

    errors: Annotated[list[str], merge_trace]
    """Erreurs techniques non bloquantes rencontrées pendant le cycle
    (indisponibilité DB, timeout LLM...). Distinctes de `missing_information`,
    qui concerne l'absence de DONNÉE MÉTIER et non les pannes."""

    messages: Annotated[list, add_messages]
    """Canal de messages LangChain (réducteur `add_messages`).
    Optionnel : sert à conserver l'échange avec le LLM pour l'audit. SENTRY
    n'est pas un agent conversationnel, ce canal n'est donc pas requis pour que
    le graphe fonctionne."""


# ---------------------------------------------------------------------------
# Fabrique et utilitaires
# ---------------------------------------------------------------------------


def create_initial_state(
    *,
    tracker_id: Optional[str] = None,
    cargo_id: Optional[str] = None,
    trip_id: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> AgentState:
    """
    Construit un état initial minimal, sans aucune donnée métier inventée.

    Seuls les identifiants du déclencheur sont fournis (par un webhook CAMARA,
    un endpoint FastAPI ou une tâche planifiée). Tout le reste sera renseigné
    par les noeuds à partir de PostgreSQL — ou restera à None.

    On initialise explicitement les listes à accumulation : LangGraph accepte
    des canaux vides, mais un état de départ explicite évite toute ambiguïté
    lors des tests unitaires.
    """
    return AgentState(
        tracker_id=tracker_id,
        cargo_id=cargo_id,
        trip_id=trip_id,
        organization_id=organization_id,
        missing_information=[],
        rule_trace=[],
        errors=[],
        messages=[],
        evaluated_at=utc_now_iso(),
    )


def utc_now_iso() -> str:
    """Horodatage courant UTC en ISO-8601. Centralisé pour rester testable."""
    return datetime.now(timezone.utc).isoformat()


def is_available(state: AgentState, field: str) -> bool:
    """
    Indique si `field` porte une information réellement disponible.

    Une liste ou un dictionnaire vide compte comme indisponible : c'est le
    résultat typique d'une requête SQL sans résultat.
    """
    value = state.get(field)
    if value is None:
        return False
    if isinstance(value, (list, dict, str)) and len(value) == 0:
        return False
    return True


def record_missing(state: AgentState, *fields: str) -> list[str]:
    """
    Retourne la liste des `fields` indisponibles, à renvoyer par un noeud sous
    la clé `missing_information` (le réducteur `merge_missing` fera la fusion).

    Usage typique dans un noeud :

        return {"missing_information": record_missing(state, "current_location",
                                                      "criticality")}
    """
    return [field for field in fields if not is_available(state, field)]


def compute_remaining_time(deadline_iso: Optional[str]) -> Optional[float]:
    """
    Calcule les heures restantes avant l'échéance.

    Retourne None si `deadline_iso` est absent ou illisible : on ne substitue
    jamais une échéance par défaut. Une valeur négative signifie que l'échéance
    est dépassée, information conservée telle quelle.
    """
    if not deadline_iso:
        return None
    try:
        deadline = datetime.fromisoformat(deadline_iso)
    except (TypeError, ValueError):
        return None
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - datetime.now(timezone.utc)
    return delta.total_seconds() / 3600.0


def state_summary(state: AgentState) -> dict[str, Any]:
    """
    Vue condensée de l'état, prête à être sérialisée par l'API (dashboard) ou
    journalisée.

    Ne renvoie que des champs présents dans l'état : aucune valeur par défaut
    n'est injectée, afin que le front puisse afficher « information
    indisponible » de façon fidèle.
    """
    keys = (
        "cargo_id",
        "tracker_id",
        "cargo_reference",
        "criticality",
        "origin",
        "destination",
        "remaining_time_hours",
        "incident_detected",
        "incident_type",
        "incident_severity",
        "unresolved_security_alerts",
        "weather",
        "route_progress",
        "fused_context",
        "historical_cases",
        "risk_score",
        "risk_level",
        "risk_data_coverage",
        "decision",
        "justification",
        "confidence",
        "requires_human_approval",
        "human_approved",
        "notification_required",
        "alert_required",
        "alert_category",
        "recipients",
        "qod_required",
        "network_slice_required",
        "risk_assessment_id",
        "agent_decision_id",
        "missing_information",
        "llm_available",
        "evaluated_at",
    )
    return {key: state.get(key) for key in keys if key in state}


__all__ = [
    "AgentState",
    "CamaraRequestPlan",
    "CorridorSnapshot",
    "IncidentSnapshot",
    "KnownContextSnapshot",
    "LocationSnapshot",
    "NetworkCondition",
    "NetworkLocationArea",
    "QoDParameters",
    "RiskZoneSnapshot",
    "SecurityAlertSnapshot",
    "compute_remaining_time",
    "create_initial_state",
    "is_available",
    "merge_missing",
    "merge_trace",
    "record_missing",
    "state_summary",
    "utc_now_iso",
]
