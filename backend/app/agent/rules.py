"""
Moteur de règles déterministe de l'agent SENTRY (Raased).

------------------------------------------------------------------------------
RÔLE ET LIMITES
------------------------------------------------------------------------------
Ce module est la SEULE autorité en matière de décision. Il est :

  * déterministe    : mêmes entrées -> même sortie, toujours ;
  * pur             : aucune requête SQL, aucun appel réseau, aucun LLM ;
  * auditable       : chaque conclusion est étiquetée par un identifiant de
                      règle (`rule_trace`), donc explicable sans LLM ;
  * conservateur    : en l'absence de donnée, il refuse de conclure au lieu de
                      supposer que « tout va bien ».

Le LLM (`reasoning.py`) n'a PAS le droit de contredire ce module : il produit
l'analyse contextuelle et la justification en langage naturel, et le garde-fou
de `reasoning.py` réaligne toute décision divergente sur celle calculée ici.
Cette séparation est la condition de la traçabilité exigée par le projet.

------------------------------------------------------------------------------
POURQUOI LES VOCABULAIRES SONT DÉFINIS ICI
------------------------------------------------------------------------------
Le schéma PostgreSQL stocke `criticality`, `risk_level`, `congestion_level`,
`decision`, `status`... comme de simples VARCHAR, SANS contrainte CHECK
(vérifié dans `migrations/versions/4ed9083ef452_initial_schema.py`). Il n'existe
donc aucune énumération côté base. Ce module est la source de vérité applicative
de ces vocabulaires, et les longueurs choisies respectent les colonnes réelles :

    agent_decisions.decision      String(40)   -> max utilisé : 27 caractères
    risk_assessments.risk_level    String(20)  -> max utilisé :  8 caractères
    risk_assessments.risk_score    DECIMAL(5,4) -> échelle 0.0 .. 1.0
    congestion_events.congestion_level String(30) -> valeur CATÉGORIELLE

------------------------------------------------------------------------------
AUCUNE DONNÉE FABRIQUÉE
------------------------------------------------------------------------------
Les fonctions de ce module retournent `None` quand l'entrée est indisponible.
Le score de risque est renormalisé sur les seuls facteurs réellement présents et
accompagné d'un taux de couverture (`coverage`) : sous le seuil
`MIN_RISK_DATA_COVERAGE`, l'agent bascule en REQUEST_MORE_INFORMATION plutôt que
de publier un score trompeur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.agent.state import AgentState, is_available
from app.core.config import get_settings

# ===========================================================================
# 1. VOCABULAIRES CANONIQUES
# ===========================================================================


class RiskLevel:
    """Niveaux de risque. Alimente `risk_assessments.risk_level` (String(20))."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    ALL = (LOW, MEDIUM, HIGH, CRITICAL)
    #: Ordre croissant, pour comparer deux niveaux sans repasser par le score.
    ORDER = {LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3}


class Criticality:
    """Criticité d'une cargaison. Alimente/lit `cargos.criticality` (String(20))."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    ALL = (LOW, MEDIUM, HIGH, CRITICAL)
    #: Criticités pour lesquelles toute action doit être validée par un humain.
    REQUIRING_HUMAN_OVERSIGHT = (HIGH, CRITICAL)


class CongestionLevel:
    """
    Niveaux de congestion.

    Vocabulaire de l'API CAMARA Congestion Insights, conservé EN MINUSCULES
    parce que c'est le format transporté par les webhooks et donc la valeur
    réellement écrite dans `congestion_events.congestion_level`. On normalise à
    la lecture (`normalize_congestion_level`) plutôt que de réécrire la donnée.
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    ALL = (NONE, LOW, MEDIUM, HIGH)


class Decision:
    """
    Les 7 décisions possibles de l'agent. Alimente `agent_decisions.decision`.

    Distinction importante avec le drapeau `requires_human_approval` :

      * `HUMAN_APPROVAL` comme DÉCISION signifie « l'agent ne tranche pas et
        remonte le cas au manager » (situation ambiguë, soupçon de fraude).
      * une décision précise (ex. `REQUEST_NETWORK_SLICE`) accompagnée de
        `requires_human_approval=True` signifie « l'agent sait quoi faire, mais
        l'action est coûteuse et attend le feu vert du manager ».

    Ces deux cas correspondent exactement aux deux colonnes distinctes
    `agent_decisions.decision` et `agent_decisions.requires_human_approval`.
    """

    MONITOR = "MONITOR"
    NOTIFY_MANAGER = "NOTIFY_MANAGER"
    RECOMMEND_ALTERNATIVE_ROUTE = "RECOMMEND_ALTERNATIVE_ROUTE"
    REQUEST_QOD = "REQUEST_QOD"
    REQUEST_NETWORK_SLICE = "REQUEST_NETWORK_SLICE"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    REQUEST_MORE_INFORMATION = "REQUEST_MORE_INFORMATION"

    ALL = (
        MONITOR,
        NOTIFY_MANAGER,
        RECOMMEND_ALTERNATIVE_ROUTE,
        REQUEST_QOD,
        REQUEST_NETWORK_SLICE,
        HUMAN_APPROVAL,
        REQUEST_MORE_INFORMATION,
    )

    #: Actions qui consomment une ressource réseau facturée ou qui modifient
    #: l'itinéraire physique : elles ne partent jamais sans supervision humaine
    #: au-delà d'un certain niveau de criticité.
    COSTLY = (RECOMMEND_ALTERNATIVE_ROUTE, REQUEST_QOD, REQUEST_NETWORK_SLICE)


class SecurityStatus:
    """Statuts de vérification de confiance. Lit `security_checks.status` (String(30))."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"

    ALL = (PASSED, FAILED, PENDING)


class SecurityCheckType:
    """
    Types de contrôle de confiance, correspondant aux 3 APIs CAMARA de confiance.
    Lit `security_checks.check_type` (String(30)).
    """

    NUMBER_VERIFICATION = "NUMBER_VERIFICATION"
    SIM_SWAP = "SIM_SWAP"
    DEVICE_SWAP = "DEVICE_SWAP"

    ALL = (NUMBER_VERIFICATION, SIM_SWAP, DEVICE_SWAP)


class IncidentType:
    """Nature normalisée d'un incident, déduite des données réelles disponibles."""

    CONGESTION = "CONGESTION"
    RISK_ZONE_ENTRY = "RISK_ZONE_ENTRY"
    SIGNAL_LOSS = "SIGNAL_LOSS"
    DEADLINE_RISK = "DEADLINE_RISK"
    SECURITY_ANOMALY = "SECURITY_ANOMALY"

    ALL = (CONGESTION, RISK_ZONE_ENTRY, SIGNAL_LOSS, DEADLINE_RISK, SECURITY_ANOMALY)


class Severity:
    """Sévérité d'un incident. Alimente `alerts.severity` (String(20))."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    ALL = (LOW, MEDIUM, HIGH, CRITICAL)


class TerminalCargoStatus:
    """
    Statuts de `cargos.status` pour lesquels toute analyse est sans objet.
    Évite d'alerter un manager sur une cargaison déjà livrée.
    """

    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

    ALL = (DELIVERED, CANCELLED)


# ===========================================================================
# 2. SEUILS CONFIGURABLES
# ===========================================================================
# Trois de ces seuils existent DÉJÀ dans `app/core/config.Settings` et sont donc
# lus depuis l'environnement, pas redéfinis ici :
#     CONGESTION_ALERT_THRESHOLD  (défaut 0.7)
#     CONGESTION_CONFIDENCE_MIN   (défaut 0.6)
#     FALSE_POSITIVE_MAX_RATE     (défaut 0.15)
# Les autres sont des constantes de module, ajustables par un ADMIN via un futur
# endpoint de configuration. Chacune est documentée avec sa raison d'être.

#: Bornes de seuillage du score de risque -> niveau de risque.
#: Lecture : score < 0.25 => LOW ; < 0.50 => MEDIUM ; < 0.75 => HIGH ; sinon CRITICAL.
RISK_LEVEL_THRESHOLDS: dict[str, float] = {
    RiskLevel.LOW: 0.25,
    RiskLevel.MEDIUM: 0.50,
    RiskLevel.HIGH: 0.75,
}

#: Encodage ordinal -> scalaire des niveaux de congestion.
#: Nécessaire parce que la base stocke un niveau CATÉGORIEL alors que le seuil
#: `CONGESTION_ALERT_THRESHOLD` de Settings est un flottant. Cet encodage n'est
#: pas une estimation : il traduit une valeur connue sur une échelle documentée.
CONGESTION_SCALE: dict[str, float] = {
    CongestionLevel.NONE: 0.0,
    CongestionLevel.LOW: 0.30,
    CongestionLevel.MEDIUM: 0.60,
    CongestionLevel.HIGH: 0.90,
}

#: Poids des facteurs de risque. La somme vaut 1.0 lorsque TOUS les facteurs
#: sont disponibles ; sinon le score est renormalisé sur les poids présents.
RISK_FACTOR_WEIGHTS: dict[str, float] = {
    "congestion": 0.25,        # sévérité réseau/trafic observée
    "cargo_criticality": 0.25, # enjeu métier de la cargaison
    "deadline_pressure": 0.20, # marge temporelle restante
    "zone_risk": 0.15,         # dangerosité de la zone traversée
    "security": 0.10,          # intégrité SIM/appareil/numéro
    "corridor_risk": 0.05,     # risque structurel du corridor
}

#: Couverture minimale des facteurs de risque pour qu'un score soit publiable.
#: En dessous, l'agent considère qu'il ne sait pas et demande des informations.
#: 0.50 = au moins la moitié du poids total des facteurs doit être renseignée.
MIN_RISK_DATA_COVERAGE: float = 0.50

#: Marges temporelles (en heures) avant échéance.
#: 2 h : plus aucune marge de manoeuvre logistique -> pression maximale.
#: 6 h : borne basse du délai d'anticipation visé par le projet (6 à 12 h).
#: 12 h : borne haute du même objectif -> pression déjà notable.
DEADLINE_CRITICAL_HOURS: float = 2.0
DEADLINE_WARNING_HOURS: float = 6.0
DEADLINE_ATTENTION_HOURS: float = 12.0

#: Atténuation appliquée au facteur de congestion lorsqu'un événement de
#: contexte connu (travaux, manifestation planifiée) explique déjà la situation.
#: C'est le levier principal de réduction des faux positifs : la congestion est
#: réelle, mais elle était prévisible, donc moins alarmante.
KNOWN_CONTEXT_ATTENUATION: float = 0.5

#: Fraîcheur maximale d'une position avant de considérer le signal comme perdu.
#: 1800 s = 30 min sans point GPS/réseau sur un corridor critique.
STALE_LOCATION_SECONDS: float = 1800.0

#: Poids ordinal des niveaux de risque textuels (`corridors.risk_level`,
#: `risk_zones.risk_level`) vers l'échelle 0..1 utilisée par le scoring.
TEXT_RISK_SCALE: dict[str, float] = {
    "LOW": 0.25,
    "MEDIUM": 0.50,
    "HIGH": 0.75,
    "CRITICAL": 1.0,
}

#: Poids ordinal de la criticité cargaison vers l'échelle 0..1.
CRITICALITY_SCALE: dict[str, float] = {
    Criticality.LOW: 0.20,
    Criticality.MEDIUM: 0.45,
    Criticality.HIGH: 0.75,
    Criticality.CRITICAL: 1.0,
}

#: Champs sans lesquels aucune évaluation de risque n'a de sens.
#: Leur absence déclenche directement REQUEST_MORE_INFORMATION.
BLOCKING_FIELDS: tuple[str, ...] = ("cargo_id", "tracker_id")

#: Champs nécessaires à une évaluation complète, mais dont l'absence est
#: dégradante et non bloquante : l'agent conclut avec une couverture réduite.
DEGRADING_FIELDS: tuple[str, ...] = (
    "criticality",
    "current_location",
    "corridor",
    "network_condition",
    "deadline",
    "security_check_status",
)


# ===========================================================================
# 3. NORMALISATION DES VALEURS LUES EN BASE
# ===========================================================================
# Les colonnes étant des VARCHAR libres, la donnée réellement écrite par les
# webhooks peut varier en casse ou en espaces. On normalise SANS jamais
# remplacer une valeur inconnue par une valeur par défaut : une valeur non
# reconnue retourne None (= indisponible), pas une valeur arbitraire.


def normalize_congestion_level(raw: Optional[str]) -> Optional[str]:
    """Normalise un niveau de congestion vers le vocabulaire CAMARA, sinon None."""
    if not raw:
        return None
    value = raw.strip().lower()
    return value if value in CongestionLevel.ALL else None


def normalize_upper(raw: Optional[str], allowed: tuple[str, ...]) -> Optional[str]:
    """Normalise une valeur textuelle en majuscules si elle est reconnue, sinon None."""
    if not raw:
        return None
    value = raw.strip().upper()
    return value if value in allowed else None


def aggregate_security_status(checks: Optional[dict[str, str]]) -> Optional[str]:
    """
    Consolide les contrôles de confiance en un statut unique.

    Règle : un seul échec suffit à faire échouer l'ensemble (principe du maillon
    faible — un SIM swap récent invalide la confiance globale). En l'absence de
    tout contrôle, retourne None : « non vérifié » n'est PAS « validé ».
    """
    if not checks:
        return None
    statuses = {
        normalize_upper(status, SecurityStatus.ALL)
        for status in checks.values()
    }
    statuses.discard(None)
    if not statuses:
        return None
    if SecurityStatus.FAILED in statuses:
        return SecurityStatus.FAILED
    if SecurityStatus.PENDING in statuses:
        return SecurityStatus.PENDING
    return SecurityStatus.PASSED


# ===========================================================================
# 4. CLASSIFICATION DU RISQUE
# ===========================================================================


def classify_risk_level(score: Optional[float]) -> Optional[str]:
    """
    Convertit un score [0..1] en niveau de risque par seuillage.

    Retourne None si le score est None : sans score, il n'y a pas de niveau, et
    surtout pas LOW par défaut.
    """
    if score is None:
        return None
    if score < RISK_LEVEL_THRESHOLDS[RiskLevel.LOW]:
        return RiskLevel.LOW
    if score < RISK_LEVEL_THRESHOLDS[RiskLevel.MEDIUM]:
        return RiskLevel.MEDIUM
    if score < RISK_LEVEL_THRESHOLDS[RiskLevel.HIGH]:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def is_at_least(level: Optional[str], minimum: str) -> bool:
    """
    Compare deux niveaux de risque sur leur ordre canonique.

    Retourne False si `level` est None : une comparaison sur une donnée absente
    ne doit jamais déclencher une escalade.
    """
    if level is None:
        return False
    return RiskLevel.ORDER.get(level, -1) >= RiskLevel.ORDER.get(minimum, 99)


def congestion_factor(state: AgentState) -> tuple[Optional[float], dict[str, Any]]:
    """
    Facteur « congestion » (poids 0.25).

    Lit `network_condition.congestion_level` (valeur catégorielle réelle) et
    l'encode sur l'échelle `CONGESTION_SCALE`. Deux ajustements documentés :

      1. si un événement de contexte connu est actif, la valeur est atténuée par
         `KNOWN_CONTEXT_ATTENUATION` (réduction des faux positifs) ;
      2. si la mesure diverge de la baseline horaire du corridor, aucune
         atténuation n'est appliquée même en présence de contexte connu, car
         l'écart signale un phénomène non prévu.

    Retourne (None, détail) si aucun niveau exploitable n'est disponible.
    """
    network = state.get("network_condition") or {}
    level = normalize_congestion_level(network.get("congestion_level"))
    if level is None:
        return None, {"available": False, "reason": "congestion_level indisponible"}

    value = CONGESTION_SCALE[level]
    detail: dict[str, Any] = {
        "available": True,
        "level": level,
        "raw_value": value,
        "confidence_level": network.get("confidence_level"),
    }

    known = state.get("known_context") or {}
    deviates = network.get("deviates_from_baseline")
    if known.get("is_active_now") is True and deviates is not True:
        value *= KNOWN_CONTEXT_ATTENUATION
        detail["attenuated_by_known_context"] = known.get("event_type")

    detail["value"] = value
    return value, detail


def criticality_factor(state: AgentState) -> tuple[Optional[float], dict[str, Any]]:
    """
    Facteur « criticité cargaison » (poids 0.25).

    Lit `cargos.criticality`. Une criticité non reconnue est traitée comme
    indisponible, jamais rabattue sur LOW.
    """
    criticality = normalize_upper(state.get("criticality"), Criticality.ALL)
    if criticality is None:
        return None, {"available": False, "reason": "criticality indisponible"}
    value = CRITICALITY_SCALE[criticality]
    return value, {"available": True, "criticality": criticality, "value": value}


def deadline_factor(state: AgentState) -> tuple[Optional[float], dict[str, Any]]:
    """
    Facteur « pression temporelle » (poids 0.20).

    Fonction par paliers du temps restant avant `cargos.deadline` :
      échéance dépassée ou < 2 h  -> 1.00
      < 6 h                       -> 0.75
      < 12 h                      -> 0.50
      au-delà                     -> 0.20

    Ces paliers reprennent l'objectif d'anticipation de 6 à 12 h du projet.
    Retourne None si aucune échéance n'est enregistrée — ce qui est un cas
    légitime en base (`cargos.deadline` est nullable), pas une anomalie.
    """
    remaining = state.get("remaining_time_hours")
    if remaining is None:
        return None, {"available": False, "reason": "deadline / remaining_time indisponible"}

    if remaining <= DEADLINE_CRITICAL_HOURS:
        value = 1.0
    elif remaining <= DEADLINE_WARNING_HOURS:
        value = 0.75
    elif remaining <= DEADLINE_ATTENTION_HOURS:
        value = 0.50
    else:
        value = 0.20

    return value, {
        "available": True,
        "remaining_time_hours": round(remaining, 2),
        "overdue": remaining < 0,
        "value": value,
    }


def zone_risk_factor(state: AgentState) -> tuple[Optional[float], dict[str, Any]]:
    """
    Facteur « zone à risque » (poids 0.15).

    N'est retenu que si PostGIS a effectivement confirmé que la position est
    contenue dans la zone (`contains_current_position is True`). Si la
    vérification n'a pas pu être faite (position ou zone absente), le facteur est
    indisponible — on ne conclut pas que le véhicule est hors zone.
    """
    zone = state.get("risk_zone") or {}
    if not zone:
        return None, {"available": False, "reason": "risk_zone indisponible"}

    contains = zone.get("contains_current_position")
    if contains is None:
        return None, {"available": False, "reason": "appartenance à la zone non évaluée"}
    if contains is False:
        return 0.0, {"available": True, "inside_zone": False, "value": 0.0}

    level = normalize_upper(zone.get("risk_level"), tuple(TEXT_RISK_SCALE))
    if level is None:
        return None, {"available": False, "reason": "risk_zone.risk_level indisponible"}

    value = TEXT_RISK_SCALE[level]
    return value, {
        "available": True,
        "inside_zone": True,
        "zone_name": zone.get("name"),
        "zone_risk_level": level,
        "value": value,
    }


def corridor_risk_factor(state: AgentState) -> tuple[Optional[float], dict[str, Any]]:
    """
    Facteur « risque structurel du corridor » (poids 0.05).

    Lit `corridors.risk_level` : dangerosité intrinsèque de l'axe, indépendante
    de l'incident courant. Poids faible car c'est un risque de fond.
    """
    corridor = state.get("corridor") or {}
    level = normalize_upper(corridor.get("risk_level"), tuple(TEXT_RISK_SCALE))
    if level is None:
        return None, {"available": False, "reason": "corridor.risk_level indisponible"}
    value = TEXT_RISK_SCALE[level]
    return value, {
        "available": True,
        "corridor_name": corridor.get("name"),
        "corridor_risk_level": level,
        "value": value,
    }


def security_factor(state: AgentState) -> tuple[Optional[float], dict[str, Any]]:
    """
    Facteur « intégrité de la chaîne de confiance » (poids 0.10).

    PASSED  -> 0.0 (aucun risque ajouté)
    PENDING -> 0.5 (doute non levé)
    FAILED  -> 1.0 (soupçon de compromission SIM / appareil / numéro)

    Un statut absent rend le facteur indisponible : ne jamais interpréter
    « aucun contrôle en base » comme « contrôle réussi ».
    """
    status = normalize_upper(state.get("security_check_status"), SecurityStatus.ALL)
    if status is None:
        return None, {"available": False, "reason": "security_check_status indisponible"}

    value = {SecurityStatus.PASSED: 0.0, SecurityStatus.PENDING: 0.5, SecurityStatus.FAILED: 1.0}[status]
    return value, {
        "available": True,
        "status": status,
        "checks": state.get("security_checks"),
        "value": value,
    }


#: Table de dispatch facteur -> fonction de calcul. Rend l'ajout d'un futur
#: facteur trivial : une entrée dans RISK_FACTOR_WEIGHTS + une entrée ici.
RISK_FACTOR_FUNCTIONS = {
    "congestion": congestion_factor,
    "cargo_criticality": criticality_factor,
    "deadline_pressure": deadline_factor,
    "zone_risk": zone_risk_factor,
    "security": security_factor,
    "corridor_risk": corridor_risk_factor,
}


def compute_risk_score(state: AgentState) -> tuple[Optional[float], dict[str, Any], float]:
    """
    Calcule le score de risque global sur l'échelle [0.0, 1.0].

    Méthode : somme pondérée des facteurs DISPONIBLES, divisée par la somme des
    poids de ces mêmes facteurs (renormalisation).

    Pourquoi renormaliser plutôt que traiter les facteurs absents comme 0 ?
    Parce qu'un facteur absent traité comme 0 abaisserait mécaniquement le score
    et produirait un faux sentiment de sécurité — exactement ce que le projet
    interdit. Avec la renormalisation, une donnée absente n'influence pas le
    score : elle réduit seulement la COUVERTURE, information rendue explicite.

    Retourne (score, facteurs, couverture) :
      * score      : None si aucun facteur n'est disponible ;
      * facteurs   : détail par facteur, destiné à `risk_assessments.factors` ;
      * couverture : part du poids total réellement couverte, dans [0.0, 1.0].
    """
    factors: dict[str, Any] = {}
    weighted_sum = 0.0
    available_weight = 0.0
    total_weight = sum(RISK_FACTOR_WEIGHTS.values())

    for name, weight in RISK_FACTOR_WEIGHTS.items():
        value, detail = RISK_FACTOR_FUNCTIONS[name](state)
        detail["weight"] = weight
        if value is None:
            detail["contribution"] = None
            factors[name] = detail
            continue
        contribution = value * weight
        detail["contribution"] = round(contribution, 4)
        factors[name] = detail
        weighted_sum += contribution
        available_weight += weight

    coverage = round(available_weight / total_weight, 4) if total_weight else 0.0

    if available_weight == 0.0:
        # Aucun facteur exploitable : on ne produit PAS de score.
        return None, factors, 0.0

    # DECIMAL(5,4) en base -> 4 décimales suffisent et évitent toute perte.
    score = round(weighted_sum / available_weight, 4)
    return score, factors, coverage


# ===========================================================================
# 5. QUALIFICATION DE L'INCIDENT
# ===========================================================================


def classify_incident(state: AgentState) -> tuple[Optional[str], Optional[str]]:
    """
    Détermine (type, sévérité) de l'incident à partir des seules données réelles.

    Ordre de priorité, du signal le plus grave au moins grave :
      1. anomalie de sécurité confirmée (contrôle de confiance en échec) ;
      2. perte de signal (dernière position trop ancienne) ;
      3. présence confirmée dans une zone à risque ;
      4. congestion mesurée ;
      5. échéance sous pression sans autre signal.

    Retourne (None, None) si aucun signal exploitable n'est disponible : cela
    signifie « je n'ai rien pu qualifier », pas « aucun incident ».
    """
    # 1. Sécurité : le seul cas où l'incident ne vient pas du terrain.
    if normalize_upper(state.get("security_check_status"), SecurityStatus.ALL) == SecurityStatus.FAILED:
        return IncidentType.SECURITY_ANOMALY, Severity.CRITICAL

    # 2. Perte de signal : détectée sur la fraîcheur réelle du dernier point.
    location = state.get("current_location") or {}
    age = location.get("age_seconds")
    if age is not None and age > STALE_LOCATION_SECONDS:
        return IncidentType.SIGNAL_LOSS, Severity.HIGH

    # 3. Zone à risque : uniquement si PostGIS a confirmé l'appartenance.
    zone = state.get("risk_zone") or {}
    if zone.get("contains_current_position") is True:
        zone_level = normalize_upper(zone.get("risk_level"), tuple(TEXT_RISK_SCALE))
        severity = {
            "LOW": Severity.LOW,
            "MEDIUM": Severity.MEDIUM,
            "HIGH": Severity.HIGH,
            "CRITICAL": Severity.CRITICAL,
        }.get(zone_level or "", Severity.MEDIUM)
        return IncidentType.RISK_ZONE_ENTRY, severity

    # 4. Congestion mesurée.
    network = state.get("network_condition") or {}
    level = normalize_congestion_level(network.get("congestion_level"))
    if level is not None and level != CongestionLevel.NONE:
        severity = {
            CongestionLevel.LOW: Severity.LOW,
            CongestionLevel.MEDIUM: Severity.MEDIUM,
            CongestionLevel.HIGH: Severity.HIGH,
        }[level]
        return IncidentType.CONGESTION, severity

    # 5. Pression d'échéance seule.
    remaining = state.get("remaining_time_hours")
    if remaining is not None and remaining <= DEADLINE_WARNING_HOURS:
        severity = Severity.CRITICAL if remaining <= DEADLINE_CRITICAL_HOURS else Severity.HIGH
        return IncidentType.DEADLINE_RISK, severity

    return None, None


# ===========================================================================
# 6. RÈGLES DE COLLECTE DES LACUNES
# ===========================================================================


def collect_missing_information(state: AgentState) -> tuple[list[str], list[str]]:
    """
    Sépare les informations manquantes en deux catégories.

    Retourne (bloquantes, dégradantes) :
      * bloquantes  : sans elles, aucune décision métier n'est possible ;
      * dégradantes : leur absence réduit la couverture mais laisse conclure.

    Les libellés sont explicites afin d'être affichés tels quels dans le
    dashboard manager (« information indisponible : criticality »).
    """
    blocking = [f"{name} indisponible" for name in BLOCKING_FIELDS if not is_available(state, name)]
    degrading = [f"{name} indisponible" for name in DEGRADING_FIELDS if not is_available(state, name)]
    return blocking, degrading


# ===========================================================================
# 7. RÈGLES D'ACTION RÉSEAU — QoD vs NETWORK SLICE
# ===========================================================================
# Distinction structurante, souvent confondue :
#
#   QoD (Quality on Demand)  = réponse PONCTUELLE et RÉVERSIBLE sur UN tracker.
#       On garantit temporairement la qualité du lien pour ne pas perdre le
#       suivi pendant un incident. Coût modéré, durée limitée à l'incident.
#
#   Network Slice            = réponse STRUCTURELLE sur une OPÉRATION.
#       On réserve une tranche réseau dédiée pour une opération critique dans la
#       durée. Coût élevé, engagement long -> validation humaine systématique.
#
# On ne demande jamais les deux simultanément : le slice couvre déjà le besoin
# du QoD.


def needs_qod(state: AgentState, risk_level: Optional[str]) -> bool:
    """
    R-QOD : demander une session QoD.

    Conditions cumulatives :
      * le risque est au moins ÉLEVÉ (l'incident menace réellement le suivi) ;
      * la congestion mesurée atteint le seuil `CONGESTION_ALERT_THRESHOLD` OU
        le signal est perdu (dans les deux cas, le LIEN est le problème) ;
      * la confiance de la mesure atteint `CONGESTION_CONFIDENCE_MIN`, afin de
        ne pas consommer une ressource réseau payante sur un signal douteux ;
      * aucune session QoD n'est déjà active sur ce tracker.
    """
    settings = get_settings()
    if not is_at_least(risk_level, RiskLevel.HIGH):
        return False

    network = state.get("network_condition") or {}
    if normalize_upper(network.get("active_qod_status"), ("ACTIVE", "REQUESTED", "PENDING")):
        return False  # déjà en cours : pas de doublon

    level = normalize_congestion_level(network.get("congestion_level"))
    congestion_high = (
        level is not None and CONGESTION_SCALE[level] >= settings.CONGESTION_ALERT_THRESHOLD
    )

    confidence = network.get("confidence_level")
    confident_enough = confidence is None or float(confidence) >= settings.CONGESTION_CONFIDENCE_MIN

    location = state.get("current_location") or {}
    age = location.get("age_seconds")
    signal_lost = age is not None and age > STALE_LOCATION_SECONDS

    if signal_lost:
        return True
    return congestion_high and confident_enough


def needs_network_slice(state: AgentState, risk_level: Optional[str]) -> bool:
    """
    R-SLICE : demander une tranche réseau dédiée.

    Conditions cumulatives, volontairement restrictives :
      * la cargaison est HIGH ou CRITICAL (l'enjeu justifie le coût) ;
      * le risque global est CRITIQUE ;
      * aucune tranche n'est déjà active.

    Une congestion élevée sur une cargaison ordinaire ne justifie JAMAIS un
    slice : elle relève du QoD ou du reroutage.
    """
    criticality = normalize_upper(state.get("criticality"), Criticality.ALL)
    if criticality not in Criticality.REQUIRING_HUMAN_OVERSIGHT:
        return False
    if risk_level != RiskLevel.CRITICAL:
        return False

    network = state.get("network_condition") or {}
    if normalize_upper(network.get("active_slice_status"), ("ACTIVE", "REQUESTED", "PENDING")):
        return False
    return True


def should_recommend_alternative_route(state: AgentState, risk_level: Optional[str]) -> bool:
    """
    R-ROUTE : proposer un itinéraire alternatif.

    Le reroutage traite un problème de TRAJET, pas de lien réseau. Conditions :
      * risque au moins ÉLEVÉ ;
      * l'incident est une congestion ou une entrée en zone à risque (un
        problème localisé sur l'axe, donc contournable) ;
      * il reste assez de temps pour qu'un détour ait du sens : au-delà de
        `DEADLINE_CRITICAL_HOURS`. À moins de 2 h de l'échéance, changer
        d'itinéraire aggrave généralement le retard ;
      * le corridor courant est identifié — sans corridor d'origine, aucune
        alternative ne peut être proposée (`route_suggestions` exige
        `original_corridor_id`).
    """
    if not is_at_least(risk_level, RiskLevel.HIGH):
        return False
    if not is_available(state, "corridor"):
        return False

    incident_type = state.get("incident_type")
    if incident_type not in (IncidentType.CONGESTION, IncidentType.RISK_ZONE_ENTRY):
        return False

    remaining = state.get("remaining_time_hours")
    if remaining is not None and remaining <= DEADLINE_CRITICAL_HOURS:
        return False
    return True


def should_notify_manager(state: AgentState, risk_level: Optional[str]) -> bool:
    """
    R-NOTIFY : notifier le manager.

    Déclencheurs :
      * risque au moins MOYEN ; ou
      * cargaison HIGH/CRITICAL dès qu'un incident est confirmé, même à risque
        faible (le manager doit garder la visibilité sur ses cargaisons
        sensibles) ; ou
      * contrôle de sécurité en échec ou en attente.

    Volontairement plus permissive que les règles d'action réseau : notifier ne
    coûte rien, agir sur le réseau coûte de l'argent.
    """
    if is_at_least(risk_level, RiskLevel.MEDIUM):
        return True

    criticality = normalize_upper(state.get("criticality"), Criticality.ALL)
    if criticality in Criticality.REQUIRING_HUMAN_OVERSIGHT and state.get("incident_detected") is True:
        return True

    security = normalize_upper(state.get("security_check_status"), SecurityStatus.ALL)
    return security in (SecurityStatus.FAILED, SecurityStatus.PENDING)


# ===========================================================================
# 8. RÈGLES DE VALIDATION HUMAINE (HUMAN-IN-THE-LOOP)
# ===========================================================================


def requires_human_approval(state: AgentState, decision: str, risk_level: Optional[str]) -> bool:
    """
    R-HITL : l'action doit-elle être validée par un MANAGER avant exécution ?

    Cas de validation obligatoire :
      * H1 — l'action est coûteuse (réseau facturé ou changement d'itinéraire)
             ET la cargaison est HIGH/CRITICAL ;
      * H2 — toute demande de tranche réseau dédiée, quelle que soit la
             cargaison : engagement long et coûteux ;
      * H3 — risque CRITIQUE avec une action coûteuse ;
      * H4 — soupçon de compromission (contrôle de confiance en échec) : on ne
             laisse jamais l'agent agir seul sur un tracker potentiellement
             détourné ;
      * H5 — couverture de données insuffisante alors qu'une action coûteuse est
             envisagée : agir sur une image partielle exige un arbitrage humain.

    MONITOR, NOTIFY_MANAGER et REQUEST_MORE_INFORMATION ne requièrent jamais de
    validation : ils n'ont aucun effet de bord sur le terrain.
    """
    criticality = normalize_upper(state.get("criticality"), Criticality.ALL)
    security = normalize_upper(state.get("security_check_status"), SecurityStatus.ALL)
    coverage = state.get("risk_data_coverage")

    if security == SecurityStatus.FAILED:
        return True  # H4
    if decision == Decision.REQUEST_NETWORK_SLICE:
        return True  # H2
    if decision not in Decision.COSTLY:
        return False

    if criticality in Criticality.REQUIRING_HUMAN_OVERSIGHT:
        return True  # H1
    if risk_level == RiskLevel.CRITICAL:
        return True  # H3
    if coverage is not None and coverage < MIN_RISK_DATA_COVERAGE:
        return True  # H5
    return False


# ===========================================================================
# 9. DÉCISION FINALE
# ===========================================================================


@dataclass
class RuleEvaluation:
    """
    Résultat complet du moteur de règles.

    Cet objet est la « vérité » du cycle : `reasoning.py` peut l'enrichir d'une
    justification, mais pas en modifier les conclusions.
    """

    decision: str
    risk_score: Optional[float]
    risk_level: Optional[str]
    risk_factors: dict[str, Any]
    risk_data_coverage: float
    incident_type: Optional[str]
    incident_severity: Optional[str]
    requires_human_approval: bool
    qod_required: bool
    network_slice_required: bool
    confidence: Optional[float]
    missing_information: list[str] = field(default_factory=list)
    rule_trace: list[str] = field(default_factory=list)

    def as_state_update(self) -> dict[str, Any]:
        """
        Projette l'évaluation en mise à jour partielle d'`AgentState`.

        Les clés correspondent exactement aux champs d'`AgentState` ; les
        réducteurs LangGraph se chargent de fusionner `missing_information` et
        `rule_trace` avec ce qu'ont déjà signalé les noeuds précédents.
        """
        return {
            "decision": self.decision,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "risk_factors": self.risk_factors,
            "risk_data_coverage": self.risk_data_coverage,
            "incident_type": self.incident_type,
            "incident_severity": self.incident_severity,
            "requires_human_approval": self.requires_human_approval,
            "qod_required": self.qod_required,
            "network_slice_required": self.network_slice_required,
            "confidence": self.confidence,
            "missing_information": self.missing_information,
            "rule_trace": self.rule_trace,
        }


def compute_confidence(coverage: float, state: AgentState) -> Optional[float]:
    """
    Confiance de l'agent dans sa propre décision, dans [0.0, 1.0].

    Part de la couverture des données, puis applique une pénalité si la mesure
    de congestion est peu fiable (sous `CONGESTION_CONFIDENCE_MIN`). Cette
    confiance alimente `agent_decisions.confidence` et sert d'indicateur de
    qualité pour le suivi du taux de faux positifs.

    Retourne None si aucune donnée n'est disponible : pas de confiance sans base.
    """
    if coverage <= 0.0:
        return None

    settings = get_settings()
    confidence = coverage
    network = state.get("network_condition") or {}
    measured = network.get("confidence_level")
    if measured is not None and float(measured) < settings.CONGESTION_CONFIDENCE_MIN:
        confidence *= 0.75  # mesure douteuse -> confiance réduite, pas annulée
    return round(min(confidence, 1.0), 4)


def evaluate(state: AgentState) -> RuleEvaluation:
    """
    Point d'entrée du moteur de règles : produit LA décision du cycle.

    Ordre de précédence, appliqué strictement de haut en bas. Le premier bloc
    qui s'applique fixe la décision ; c'est ce qui garantit le déterminisme.

      R-00  cargaison dans un statut terminal (livrée/annulée) -> MONITOR
      R-01  information BLOQUANTE absente                      -> REQUEST_MORE_INFORMATION
      R-02  contrôle de confiance en ÉCHEC                     -> HUMAN_APPROVAL
      R-03  couverture de données insuffisante                 -> REQUEST_MORE_INFORMATION
      R-04  aucun score calculable                             -> REQUEST_MORE_INFORMATION
      R-05  tranche réseau justifiée                           -> REQUEST_NETWORK_SLICE
      R-06  session QoD justifiée                              -> REQUEST_QOD
      R-07  itinéraire alternatif pertinent                    -> RECOMMEND_ALTERNATIVE_ROUTE
      R-08  notification manager justifiée                     -> NOTIFY_MANAGER
      R-09  aucun des cas précédents                           -> MONITOR

    Les drapeaux `qod_required` / `network_slice_required` sont positionnés
    indépendamment de la décision retenue : l'agent peut décider
    RECOMMEND_ALTERNATIVE_ROUTE tout en signalant qu'un QoD serait utile, ce que
    le manager verra dans le dashboard.
    """
    trace: list[str] = []
    missing: list[str] = []

    # --- Préalable : qualification et scoring, sur les seules données réelles.
    incident_type, incident_severity = classify_incident(state)
    risk_score, risk_factors, coverage = compute_risk_score(state)
    risk_level = classify_risk_level(risk_score)
    confidence = compute_confidence(coverage, state)

    # La couverture doit être visible des règles suivantes (cf. R-HITL / H5).
    scored_state: AgentState = {**state, "risk_data_coverage": coverage}
    if incident_type is not None:
        scored_state["incident_type"] = incident_type

    blocking, degrading = collect_missing_information(scored_state)
    missing.extend(blocking)
    missing.extend(degrading)

    qod = needs_qod(scored_state, risk_level)
    slice_needed = needs_network_slice(scored_state, risk_level)
    # Un slice couvre déjà le besoin d'un QoD : on ne cumule pas les deux.
    if slice_needed:
        qod = False

    def build(decision: str) -> RuleEvaluation:
        """Assemble le résultat en appliquant la règle HITL à la décision retenue."""
        return RuleEvaluation(
            decision=decision,
            risk_score=risk_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            risk_data_coverage=coverage,
            incident_type=incident_type,
            incident_severity=incident_severity,
            requires_human_approval=requires_human_approval(scored_state, decision, risk_level),
            qod_required=qod,
            network_slice_required=slice_needed,
            confidence=confidence,
            missing_information=missing,
            rule_trace=trace,
        )

    # --- R-00 : cargaison hors périmètre d'analyse.
    cargo_status = normalize_upper(state.get("cargo_status"), TerminalCargoStatus.ALL)
    if cargo_status is not None:
        trace.append(f"R-00:cargo_status={cargo_status}:aucune_action_requise")
        return build(Decision.MONITOR)

    # --- R-01 : sans identifiants, rien n'est rattachable en base.
    if blocking:
        trace.append(f"R-01:informations_bloquantes_absentes:{len(blocking)}")
        return build(Decision.REQUEST_MORE_INFORMATION)

    # --- R-02 : soupçon de compromission -> arbitrage humain, jamais d'automatisme.
    if normalize_upper(state.get("security_check_status"), SecurityStatus.ALL) == SecurityStatus.FAILED:
        trace.append("R-02:security_check=FAILED:escalade_humaine")
        return build(Decision.HUMAN_APPROVAL)

    # --- R-03 : trop peu de données pour qu'un score soit honnête.
    if coverage < MIN_RISK_DATA_COVERAGE:
        trace.append(f"R-03:couverture_insuffisante:{coverage}<{MIN_RISK_DATA_COVERAGE}")
        # Sur une cargaison sensible, l'incertitude elle-même doit être arbitrée.
        criticality = normalize_upper(state.get("criticality"), Criticality.ALL)
        if criticality in Criticality.REQUIRING_HUMAN_OVERSIGHT:
            trace.append("R-03b:cargaison_sensible_sous_incertitude:escalade_humaine")
            return build(Decision.HUMAN_APPROVAL)
        return build(Decision.REQUEST_MORE_INFORMATION)

    # --- R-04 : aucun facteur exploitable -> aucun score, donc aucune conclusion.
    if risk_score is None:
        trace.append("R-04:aucun_facteur_de_risque_disponible")
        return build(Decision.REQUEST_MORE_INFORMATION)

    trace.append(f"R-SCORE:risk_score={risk_score}:risk_level={risk_level}:couverture={coverage}")
    if incident_type is not None:
        trace.append(f"R-INCIDENT:type={incident_type}:severite={incident_severity}")

    # --- R-05 : réponse structurelle pour une opération critique.
    if slice_needed:
        trace.append("R-05:slice_justifie:criticite_elevee_et_risque_critique")
        return build(Decision.REQUEST_NETWORK_SLICE)

    # --- R-06 : réponse ponctuelle pour sécuriser le lien de suivi.
    if qod:
        trace.append("R-06:qod_justifie:lien_de_suivi_menace")
        return build(Decision.REQUEST_QOD)

    # --- R-07 : le problème est le trajet, pas le réseau.
    if should_recommend_alternative_route(scored_state, risk_level):
        trace.append("R-07:reroutage_pertinent:incident_localise_et_marge_suffisante")
        return build(Decision.RECOMMEND_ALTERNATIVE_ROUTE)

    # --- R-08 : informer sans agir.
    if should_notify_manager(scored_state, risk_level):
        trace.append("R-08:notification_manager_justifiee")
        return build(Decision.NOTIFY_MANAGER)

    # --- R-09 : situation nominale, surveillance passive.
    trace.append("R-09:situation_nominale:surveillance")
    return build(Decision.MONITOR)


__all__ = [
    "CONGESTION_SCALE",
    "CRITICALITY_SCALE",
    "DEADLINE_ATTENTION_HOURS",
    "DEADLINE_CRITICAL_HOURS",
    "DEADLINE_WARNING_HOURS",
    "KNOWN_CONTEXT_ATTENUATION",
    "MIN_RISK_DATA_COVERAGE",
    "RISK_FACTOR_WEIGHTS",
    "RISK_LEVEL_THRESHOLDS",
    "STALE_LOCATION_SECONDS",
    "TEXT_RISK_SCALE",
    "CongestionLevel",
    "Criticality",
    "Decision",
    "IncidentType",
    "RiskLevel",
    "RuleEvaluation",
    "SecurityCheckType",
    "SecurityStatus",
    "Severity",
    "TerminalCargoStatus",
    "aggregate_security_status",
    "classify_incident",
    "classify_risk_level",
    "collect_missing_information",
    "compute_confidence",
    "compute_risk_score",
    "evaluate",
    "is_at_least",
    "needs_network_slice",
    "needs_qod",
    "normalize_congestion_level",
    "normalize_upper",
    "requires_human_approval",
    "should_notify_manager",
    "should_recommend_alternative_route",
]
