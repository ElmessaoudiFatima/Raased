"""
Couche de raisonnement LLM de l'agent SENTRY (Raased).

------------------------------------------------------------------------------
RÔLE EXACT DU LLM DANS CETTE ARCHITECTURE
------------------------------------------------------------------------------
Le LLM N'EST PAS le décideur. La décision est calculée par le moteur de règles
déterministe (`rules.evaluate`). Le LLM sert à :

  1. produire une ANALYSE CONTEXTUELLE lisible (`reasoning`) ;
  2. produire une JUSTIFICATION courte destinée au manager (`justification`) ;
  3. signaler d'éventuelles lacunes d'information que les règles n'avaient pas
     énumérées (`missing_information`) ;
  4. proposer une ESCALADE vers la validation humaine — jamais une désescalade.

Un garde-fou (`_enforce_rule_authority`) réaligne systématiquement toute sortie
LLM divergente sur la décision des règles, et journalise l'écart. Cette
asymétrie est volontaire : le LLM peut rendre l'agent plus prudent, jamais moins.

------------------------------------------------------------------------------
FOURNISSEUR UNIQUE : GOOGLE GEMINI
------------------------------------------------------------------------------
Ce module utilise EXCLUSIVEMENT Google Gemini, via le SDK natif
`google-generativeai 0.8.2` déjà présent dans `requirements.txt`.

`langchain-google-genai` n'est PAS installé dans ce projet : on passe donc par le
SDK Google directement, sans ajouter de dépendance. Le mode JSON natif
(`response_mime_type="application/json"`) et la consigne système persistante
(`system_instruction`) sont tous deux disponibles en 0.8.2.

Le modèle et la température restent configurables sans toucher au code, via les
variables d'environnement `LLM_MODEL` et `LLM_TEMPERATURE`.

`LLM_PROVIDER` est volontairement IGNORÉ pour le choix du fournisseur : le champ
existe encore dans `app/core/config.py` mais Gemini est le seul moteur supporté.
Si la variable désigne autre chose, un avertissement est journalisé une fois — on
ne bascule jamais silencieusement sur un autre fournisseur.

`LLMProvider` (Protocol) est conservé : il ne sert plus à changer de fournisseur
mais à permettre l'injection d'un double en test, sans clé API ni réseau.

------------------------------------------------------------------------------
SECRETS
------------------------------------------------------------------------------
Aucune clé n'est écrite dans le code. `GEMINI_API_KEY` est résolue à l'exécution,
dans cet ordre : `Settings` (backend/.env) -> variables d'environnement du
processus -> `app/agent/.env` chargé par python-dotenv. Ce dernier niveau existe
parce que `Settings` ne lit que le `.env` du répertoire courant : une clé placée
dans `app/agent/.env` serait autrement ignorée.

------------------------------------------------------------------------------
FONCTIONNEMENT AVEC UNE BASE VIDE
------------------------------------------------------------------------------
Le prompt ne transmet que les champs RÉELLEMENT disponibles ; tous les autres
sont listés explicitement comme « NON DISPONIBLE ». Le prompt système interdit
formellement d'inventer une position, une criticité, un incident ou une
localisation. Et si le LLM est injoignable (clé absente, panne, JSON invalide),
le module bascule en MODE DÉGRADÉ : la décision des règles est conservée et la
justification est construite à partir de la seule trace des règles.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from dotenv import load_dotenv

from app.agent.state import AgentState, is_available
from app.agent.rules import Decision, RiskLevel, RuleEvaluation
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chargement des variables d'environnement locales au module agent.
# `override=False` : ne remplace jamais une variable déjà définie par
# l'environnement réel ni par backend/.env. Appelé une seule fois à l'import.
# ---------------------------------------------------------------------------
_AGENT_ENV_PATH = Path(__file__).resolve().parent / ".env"
if _AGENT_ENV_PATH.exists():
    load_dotenv(_AGENT_ENV_PATH, override=False)


#: Seul fournisseur supporté. Constante explicite plutôt que chaîne littérale
#: dispersée dans le code : elle sert au nom de la clé, aux messages d'erreur et
#: à l'avertissement de configuration.
PROVIDER_NAME = "gemini"

#: Variable d'environnement portant la clé API Gemini.
API_KEY_ENV = "GEMINI_API_KEY"

#: Modèle par défaut, surchargeable sans toucher au code via LLM_MODEL.
#: `gemini-1.5-flash` est une alternative plus rapide et moins coûteuse, utile
#: pour une démonstration en direct.
DEFAULT_MODEL = "gemini-1.5-pro"

#: Température basse : on veut une justification stable et reproductible, pas de
#: créativité. Deux exécutions sur le même incident doivent se ressembler.
DEFAULT_TEMPERATURE: float = 0.2

#: Marqueur utilisé dans les prompts pour une donnée absente de PostgreSQL.
UNAVAILABLE = "NON DISPONIBLE"


# ===========================================================================
# 1. ABSTRACTION FOURNISSEUR
# ===========================================================================


class LLMUnavailable(RuntimeError):
    """
    Le LLM n'a pas pu être sollicité ou sa réponse est inexploitable.

    Volontairement NON fatale : elle est interceptée par `analyze`, qui bascule
    en mode dégradé. L'agent doit continuer à décider sans LLM.
    """


class LLMProvider(Protocol):
    """
    Interface minimale attendue d'un fournisseur LLM.

    Une seule implémentation réelle existe (`GeminiProvider`). Ce Protocol est
    conservé pour une raison précise : permettre à `analyze` de recevoir un double
    en test, sans clé API ni appel réseau. Il ne sert PAS à brancher un autre
    fournisseur — Gemini est le seul moteur supporté par le projet.
    """

    name: str

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Retourne la réponse du modèle désérialisée. Lève `LLMUnavailable` sinon."""
        ...


def _parse_json_response(raw: Optional[str]) -> dict[str, Any]:
    """
    Désérialise la réponse du modèle en tolérant les emballages courants.

    Gemini encadre parfois le JSON par des balises Markdown malgré la consigne et
    malgré `response_mime_type`. On les retire avant de parser plutôt que
    d'échouer, mais on ne tente aucune réparation plus agressive : un JSON
    réellement cassé doit faire basculer en mode dégradé, pas être deviné.
    """
    if not raw or not raw.strip():
        raise LLMUnavailable(f"{PROVIDER_NAME}: réponse vide")

    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"{PROVIDER_NAME}: JSON invalide ({exc.msg})") from exc

    if not isinstance(payload, dict):
        raise LLMUnavailable(
            f"{PROVIDER_NAME}: objet JSON attendu, reçu {type(payload).__name__}"
        )
    return payload


class GeminiProvider:
    """
    Fournisseur Google Gemini via le SDK natif `google-generativeai`.

    Seule implémentation réelle de `LLMProvider` dans ce projet.

    Utilise `system_instruction` (consigne persistante, distincte du message
    utilisateur) et `response_mime_type="application/json"`, tous deux disponibles
    en 0.8.2. Le mode JSON natif évite d'avoir à extraire le JSON d'une prose.
    """

    name = PROVIDER_NAME

    def __init__(self, api_key: str, model: str, temperature: float) -> None:
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover - dépendance déclarée
            raise LLMUnavailable("google-generativeai n'est pas installé") from exc

        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_name = model
        self._temperature = temperature

    @property
    def model_name(self) -> str:
        """Modèle réellement utilisé — exposé pour un endpoint de diagnostic ADMIN."""
        return self._model_name

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            model = self._genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=system_prompt,
                generation_config={
                    "temperature": self._temperature,
                    "response_mime_type": "application/json",
                },
            )
            response = model.generate_content(user_prompt)
        except Exception as exc:  # SDK réseau/quota/modèle : toujours récupérable
            raise LLMUnavailable(f"{PROVIDER_NAME}: {exc}") from exc
        return _parse_json_response(getattr(response, "text", None))


def _resolve_api_key() -> Optional[str]:
    """
    Résout `GEMINI_API_KEY` sans jamais l'écrire dans le code ni dans les logs.

    Ordre de priorité : `Settings` (donc backend/.env) puis l'environnement du
    processus, complété par `app/agent/.env` chargé plus haut par python-dotenv.
    Retourne None si aucune clé n'est trouvée — cas normal en développement, qui
    fait basculer l'agent en mode dégradé au lieu de le faire planter.
    """
    settings = get_settings()
    key = (getattr(settings, API_KEY_ENV, "") or "").strip()
    if not key:
        key = (os.getenv(API_KEY_ENV) or "").strip()
    return key or None


def _warn_if_other_provider_configured() -> None:
    """
    Avertit UNE SEULE FOIS si `LLM_PROVIDER` désigne autre chose que Gemini.

    Le champ existe encore dans `app/core/config.py` (non modifié). On ne bascule
    jamais silencieusement : soit Gemini, soit un avertissement explicite dans les
    logs pour que la configuration soit corrigée.
    """
    global _provider_warning_emitted
    if _provider_warning_emitted:
        return
    configured = (get_settings().LLM_PROVIDER or "").strip().lower()
    if configured and configured != PROVIDER_NAME:
        logger.warning(
            "LLM_PROVIDER='%s' est ignoré : ce projet n'utilise que Gemini. "
            "Corrigez backend/.env avec LLM_PROVIDER=%s pour lever cette ambiguïté.",
            configured,
            PROVIDER_NAME,
        )
    _provider_warning_emitted = True


#: Cache de l'instance : évite de reconfigurer le SDK à chaque incident.
_provider_cache: dict[str, LLMProvider] = {}

#: Évite de répéter l'avertissement de configuration à chaque cycle d'analyse.
_provider_warning_emitted = False


def get_llm_provider() -> GeminiProvider:
    """
    Fabrique le fournisseur Gemini configuré.

    Lit `LLM_MODEL` et `LLM_TEMPERATURE` dans l'environnement, avec des valeurs
    par défaut documentées — ce qui évite de modifier `app/core/config.py`.

    L'initialisation est PARESSEUSE et jamais faite à l'import : importer
    `reasoning` reste possible sans aucune clé API, ce qui est indispensable pour
    les tests et pour le démarrage de FastAPI.

    Lève `LLMUnavailable` si la clé est absente — jamais une exception fatale.
    """
    _warn_if_other_provider_configured()

    api_key = _resolve_api_key()
    if not api_key:
        raise LLMUnavailable(
            f"{API_KEY_ENV} absente : renseignez-la dans backend/.env "
            f"ou dans app/agent/.env (jamais dans le code)."
        )

    model = (os.getenv("LLM_MODEL") or DEFAULT_MODEL).strip()
    try:
        temperature = float(os.getenv("LLM_TEMPERATURE") or DEFAULT_TEMPERATURE)
    except ValueError:
        temperature = DEFAULT_TEMPERATURE

    cache_key = f"{model}:{temperature}"
    if cache_key not in _provider_cache:
        _provider_cache[cache_key] = GeminiProvider(api_key, model, temperature)
    return _provider_cache[cache_key]  # type: ignore[return-value]


# ===========================================================================
# 2. PROMPT SYSTÈME SENTRY
# ===========================================================================
# Rédigé en français : la justification est lue par des managers et des
# chauffeurs francophones dans le dashboard, et alimente directement
# `agent_decisions.reasoning_summary` et `alerts.message`.

SENTRY_SYSTEM_PROMPT = f"""\
Tu es SENTRY, l'agent d'analyse de résilience logistique de la plateforme Raased.
Tu surveilles des corridors de fret critiques dans la région MENA.

## TA MISSION
Expliquer une situation logistique déjà évaluée par un moteur de règles
déterministe, en langage clair et actionnable, à destination d'un responsable
logistique (manager) et, indirectement, d'un chauffeur.

## CE QUE TU NE DOIS JAMAIS FAIRE — RÈGLE ABSOLUE
Tu ne dois JAMAIS inventer, estimer, deviner, extrapoler ni compléter :
- une position, une latitude, une longitude, une ville ou une localisation ;
- un niveau de criticité de cargaison ;
- un incident, un embouteillage, un accident, un blocage ou un retard ;
- une heure, une durée, une échéance ou un temps restant ;
- une identité de chauffeur, de véhicule, de tracker ou de client ;
- un nom de corridor, de zone ou d'organisation.

Toute donnée marquée « {UNAVAILABLE} » est réellement absente de la base. Tu dois
alors écrire explicitement que l'information est indisponible et l'ajouter à
`missing_information`. Ne remplace JAMAIS une donnée absente par une valeur
plausible, par une moyenne, par un exemple ou par « probablement ».

## AUTORITÉ DES RÈGLES
La décision, le score et le niveau de risque te sont FOURNIS par le moteur de
règles déterministe. Tu ne les recalcules pas et tu ne les contredis pas.
Tu dois reprendre à l'identique la décision et le niveau de risque transmis.
Seule liberté qui t'est accordée : tu peux demander une validation humaine
(`requires_human_approval` à true) même si les règles ne l'exigeaient pas, si le
contexte te paraît trop incertain. Tu ne peux JAMAIS faire l'inverse, c'est-à-dire
retirer une validation humaine exigée par les règles.

## DÉCISIONS POSSIBLES (vocabulaire fermé)
- MONITOR : surveillance passive, aucune action.
- NOTIFY_MANAGER : informer le responsable, sans agir sur le terrain.
- RECOMMEND_ALTERNATIVE_ROUTE : proposer un itinéraire de contournement.
- REQUEST_QOD : sécuriser temporairement la qualité du lien réseau d'un tracker.
- REQUEST_NETWORK_SLICE : réserver une tranche réseau dédiée (opération critique).
- HUMAN_APPROVAL : ne pas trancher et remonter le cas au manager.
- REQUEST_MORE_INFORMATION : données insuffisantes pour conclure.

## NIVEAUX DE RISQUE (vocabulaire fermé)
LOW, MEDIUM, HIGH, CRITICAL.

## STYLE
- Français, factuel, sobre, sans emphase ni superlatif.
- `reasoning` : 3 à 6 phrases, analyse du contexte et articulation des facteurs.
- `justification` : 1 à 3 phrases maximum, directement affichables au manager.
- Cite uniquement des valeurs présentes dans les données fournies.
- Si tu ne peux rien conclure, dis-le.

## FORMAT DE SORTIE — JSON STRICT, AUCUN TEXTE AUTOUR
{{
  "risk_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "risk_factors": ["facteur aggravant réellement observé", "..."],
  "decision": "une des 7 décisions ci-dessus",
  "reasoning": "analyse contextuelle en français",
  "justification": "justification courte en français",
  "requires_human_approval": true,
  "missing_information": ["information nécessaire mais absente", "..."]
}}
Si une liste est vide, renvoie [].
"""


# ===========================================================================
# 3. CONSTRUCTION DU PROMPT UTILISATEUR
# ===========================================================================


def _fmt(value: Any) -> str:
    """Rend une valeur, ou le marqueur d'indisponibilité si elle est absente."""
    if value is None or value == "" or value == [] or value == {}:
        return UNAVAILABLE
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _fmt_location(location: Optional[dict[str, Any]]) -> str:
    """
    Formate la position sans jamais compléter une coordonnée manquante.

    Une latitude sans longitude reste une position inutilisable : on le dit.
    """
    if not location:
        return UNAVAILABLE
    lat, lon = location.get("latitude"), location.get("longitude")
    if lat is None or lon is None:
        return f"{UNAVAILABLE} (coordonnées incomplètes en base)"
    parts = [f"lat {lat}, lon {lon}"]
    if location.get("accuracy_meters") is not None:
        parts.append(f"précision {location['accuracy_meters']} m")
    if location.get("observed_at"):
        parts.append(f"relevé à {location['observed_at']}")
    if location.get("age_seconds") is not None:
        parts.append(f"ancienneté {location['age_seconds']:.0f} s")
    if location.get("source"):
        parts.append(f"source {location['source']}")
    return " ; ".join(parts)


def build_user_prompt(state: AgentState, evaluation: RuleEvaluation) -> str:
    """
    Sérialise l'état et l'évaluation des règles en un message utilisateur.

    Deux principes :
      1. tout champ absent est explicitement marqué « {UNAVAILABLE} » — le
         modèle voit donc la lacune au lieu de la deviner ;
      2. la décision des règles est transmise comme un FAIT à expliquer, pas
         comme une suggestion à évaluer.
    """
    corridor = state.get("corridor") or {}
    zone = state.get("risk_zone") or {}
    network = state.get("network_condition") or {}
    known = state.get("known_context") or {}
    incident = state.get("incident") or {}

    # Facteurs disponibles / indisponibles, extraits du calcul réel des règles.
    available_factors = [
        f"- {name} : valeur {_fmt(detail.get('value'))}, poids {_fmt(detail.get('weight'))}, "
        f"contribution {_fmt(detail.get('contribution'))}"
        for name, detail in (evaluation.risk_factors or {}).items()
        if detail.get("available")
    ]
    unavailable_factors = [
        f"- {name} : {detail.get('reason', UNAVAILABLE)}"
        for name, detail in (evaluation.risk_factors or {}).items()
        if not detail.get("available")
    ]

    sections = [
        "# CARGAISON",
        f"Référence : {_fmt(state.get('cargo_reference'))}",
        f"Type : {_fmt(state.get('cargo_type'))}",
        f"Criticité : {_fmt(state.get('criticality'))}",
        f"Statut : {_fmt(state.get('cargo_status'))}",
        f"Origine : {_fmt(state.get('origin'))}",
        f"Destination : {_fmt(state.get('destination'))}",
        f"Échéance : {_fmt(state.get('deadline'))}",
        f"Temps restant (heures) : {_fmt(state.get('remaining_time_hours'))}",
        "",
        "# POSITION ET GÉOGRAPHIE",
        f"Dernière position connue : {_fmt_location(state.get('current_location'))}",
        f"Corridor : {_fmt(corridor.get('name'))} "
        f"({_fmt(corridor.get('origin'))} -> {_fmt(corridor.get('destination'))}), "
        f"risque structurel {_fmt(corridor.get('risk_level'))}",
        f"Zone à risque : {_fmt(zone.get('name'))}, type {_fmt(zone.get('type'))}, "
        f"niveau {_fmt(zone.get('risk_level'))}, "
        f"position contenue dans la zone : {_fmt(zone.get('contains_current_position'))}",
        "",
        "# INCIDENT",
        f"Incident détecté en base : {_fmt(state.get('incident_detected'))}",
        f"Type qualifié par les règles : {_fmt(evaluation.incident_type)}",
        f"Sévérité qualifiée par les règles : {_fmt(evaluation.incident_severity)}",
        f"Source de l'événement : {_fmt(incident.get('source'))}",
        f"Observé à : {_fmt(incident.get('observed_at'))}",
        "",
        "# RÉSEAU",
        f"Niveau de congestion mesuré : {_fmt(network.get('congestion_level'))}",
        f"Confiance de la mesure : {_fmt(network.get('confidence_level'))}",
        f"Niveau habituel du corridor (baseline) : {_fmt(network.get('baseline_level'))}",
        f"Écart par rapport à la baseline : {_fmt(network.get('deviates_from_baseline'))}",
        f"Session QoD déjà active : {_fmt(network.get('active_qod_status'))}",
        f"Tranche réseau déjà active : {_fmt(network.get('active_slice_status'))}",
        "",
        "# CONTEXTE CONNU (événement planifié pouvant expliquer la situation)",
        f"Type : {_fmt(known.get('event_type'))}",
        f"Description : {_fmt(known.get('description'))}",
        f"Actif actuellement : {_fmt(known.get('is_active_now'))}",
        "",
        "# SÉCURITÉ / CHAÎNE DE CONFIANCE",
        f"Statut agrégé : {_fmt(state.get('security_check_status'))}",
        f"Détail des contrôles : {_fmt(state.get('security_checks'))}",
        "",
        "# ÉVALUATION DÉTERMINISTE (FAITS À EXPLIQUER, NON NÉGOCIABLES)",
        f"Décision retenue : {evaluation.decision}",
        f"Niveau de risque : {_fmt(evaluation.risk_level)}",
        f"Score de risque (0 à 1) : {_fmt(evaluation.risk_score)}",
        f"Couverture des données : {_fmt(evaluation.risk_data_coverage)}",
        f"Validation humaine exigée par les règles : {_fmt(evaluation.requires_human_approval)}",
        f"QoD recommandé : {_fmt(evaluation.qod_required)}",
        f"Tranche réseau recommandée : {_fmt(evaluation.network_slice_required)}",
        f"Règles appliquées : {', '.join(evaluation.rule_trace) if evaluation.rule_trace else UNAVAILABLE}",
        "",
        "# FACTEURS DE RISQUE DISPONIBLES",
        *(available_factors or [f"- aucun ({UNAVAILABLE})"]),
        "",
        "# FACTEURS DE RISQUE INDISPONIBLES (ne pas les estimer)",
        *(unavailable_factors or ["- aucun"]),
        "",
        "# INFORMATIONS DÉJÀ IDENTIFIÉES COMME MANQUANTES",
        *(
            [f"- {item}" for item in evaluation.missing_information]
            or ["- aucune"]
        ),
        "",
        "Produis maintenant l'objet JSON demandé, en français, sans inventer "
        "aucune donnée absente.",
    ]
    return "\n".join(sections)


# ===========================================================================
# 4. RÉSULTAT DU RAISONNEMENT
# ===========================================================================


@dataclass
class ReasoningResult:
    """
    Sortie de la couche de raisonnement, déjà réalignée sur les règles.

    `risk_factors_narrative` contient la liste textuelle produite par le LLM ;
    elle ne remplace PAS `state["risk_factors"]`, qui reste le détail numérique
    calculé par les règles et destiné à `risk_assessments.factors`.
    """

    decision: str
    risk_level: Optional[str]
    reasoning: Optional[str]
    justification: str
    requires_human_approval: bool
    missing_information: list[str] = field(default_factory=list)
    risk_factors_narrative: list[str] = field(default_factory=list)
    llm_available: bool = False
    overrides: list[str] = field(default_factory=list)

    def as_state_update(self) -> dict[str, Any]:
        """Projette le résultat en mise à jour partielle d'`AgentState`."""
        return {
            "decision": self.decision,
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
            "justification": self.justification,
            "requires_human_approval": self.requires_human_approval,
            "missing_information": self.missing_information,
            "llm_available": self.llm_available,
            "rule_trace": self.overrides,
        }


# ===========================================================================
# 5. GARDE-FOU : LES RÈGLES L'EMPORTENT
# ===========================================================================


def _as_str_list(value: Any) -> list[str]:
    """Normalise en liste de chaînes ce que le LLM a pu renvoyer sous d'autres formes."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [f"{k}: {v}" for k, v in value.items()]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _enforce_rule_authority(
    payload: dict[str, Any], evaluation: RuleEvaluation
) -> ReasoningResult:
    """
    Réaligne la sortie LLM sur l'évaluation déterministe.

    Trois contrôles :

      1. DÉCISION — toute valeur différente de celle des règles (ou hors du
         vocabulaire fermé) est écrasée, et l'écart est journalisé dans
         `overrides` pour être visible dans l'audit.
      2. NIVEAU DE RISQUE — dérivé du score par les règles : la valeur des
         règles prime toujours.
      3. VALIDATION HUMAINE — asymétrie volontaire : le LLM peut EXIGER une
         validation que les règles n'exigeaient pas (escalade autorisée), mais ne
         peut jamais en retirer une (désescalade refusée).

    Les lacunes signalées par le LLM sont FUSIONNÉES avec celles des règles :
    le modèle peut légitimement repérer une information manquante que les règles
    n'avaient pas énumérée.
    """
    overrides: list[str] = []

    llm_decision = str(payload.get("decision") or "").strip().upper()
    if llm_decision != evaluation.decision:
        if llm_decision:
            overrides.append(
                f"R-GUARD:decision_llm={llm_decision}:remplacee_par={evaluation.decision}"
            )
        decision = evaluation.decision
    else:
        decision = evaluation.decision

    llm_risk = str(payload.get("risk_level") or "").strip().upper()
    if llm_risk and llm_risk in RiskLevel.ALL and llm_risk != evaluation.risk_level:
        overrides.append(
            f"R-GUARD:risk_level_llm={llm_risk}:remplace_par={evaluation.risk_level}"
        )
    risk_level = evaluation.risk_level

    llm_approval = payload.get("requires_human_approval")
    approval = evaluation.requires_human_approval
    if llm_approval is True and not approval:
        approval = True  # escalade autorisée
        overrides.append("R-GUARD:escalade_humaine_demandee_par_le_llm")
    elif llm_approval is False and approval:
        overrides.append("R-GUARD:desescalade_llm_refusee")  # désescalade interdite

    missing = list(evaluation.missing_information)
    for item in _as_str_list(payload.get("missing_information")):
        if item not in missing:
            missing.append(item)

    justification = str(payload.get("justification") or "").strip()
    if not justification:
        justification = _degraded_justification(evaluation, reason="justification LLM vide")
        overrides.append("R-GUARD:justification_llm_vide:repli_sur_les_regles")

    return ReasoningResult(
        decision=decision,
        risk_level=risk_level,
        reasoning=str(payload.get("reasoning") or "").strip() or None,
        justification=justification,
        requires_human_approval=approval,
        missing_information=missing,
        risk_factors_narrative=_as_str_list(payload.get("risk_factors")),
        llm_available=True,
        overrides=overrides,
    )


# ===========================================================================
# 6. MODE DÉGRADÉ (SANS LLM)
# ===========================================================================

#: Formulations neutres par décision. Elles n'affirment aucun fait de terrain :
#: elles décrivent uniquement ce que l'agent a fait et pourquoi.
_DEGRADED_TEMPLATES: dict[str, str] = {
    Decision.MONITOR: "Aucune action requise : les règles déterministes ne relèvent pas de situation nécessitant une intervention.",
    Decision.NOTIFY_MANAGER: "Le responsable logistique est notifié pour information ; aucune action n'est engagée sur le terrain.",
    Decision.RECOMMEND_ALTERNATIVE_ROUTE: "Un itinéraire alternatif est recommandé afin de contourner un incident localisé sur le corridor.",
    Decision.REQUEST_QOD: "Une session Quality on Demand est demandée pour sécuriser temporairement le lien de suivi du tracker.",
    Decision.REQUEST_NETWORK_SLICE: "Une tranche réseau dédiée est demandée pour garantir la connectivité de cette opération critique.",
    Decision.HUMAN_APPROVAL: "Le cas est remonté au responsable logistique : l'agent ne dispose pas des éléments pour trancher seul.",
    Decision.REQUEST_MORE_INFORMATION: "Les informations nécessaires ne sont pas disponibles dans la base : aucune conclusion ne peut être formulée.",
}


def _degraded_justification(evaluation: RuleEvaluation, reason: str) -> str:
    """
    Construit une justification à partir des SEULES données réelles.

    Aucune phrase ne décrit un fait de terrain non vérifié. On mentionne la
    décision, le niveau de risque s'il existe, la couverture des données, les
    lacunes, et le fait que l'analyse contextuelle n'a pas pu être produite.
    """
    parts = [_DEGRADED_TEMPLATES.get(evaluation.decision, f"Décision retenue : {evaluation.decision}.")]

    if evaluation.risk_level is not None and evaluation.risk_score is not None:
        parts.append(
            f"Niveau de risque évalué : {evaluation.risk_level} "
            f"(score {evaluation.risk_score:.2f} sur 1, "
            f"couverture des données {evaluation.risk_data_coverage:.0%})."
        )
    else:
        parts.append(
            "Aucun score de risque n'a pu être calculé : les facteurs de risque "
            "ne sont pas disponibles dans la base."
        )

    if evaluation.missing_information:
        parts.append(
            "Informations indisponibles : " + " ; ".join(evaluation.missing_information) + "."
        )

    parts.append(f"Analyse contextuelle non disponible ({reason}).")
    return " ".join(parts)


def _degraded_result(evaluation: RuleEvaluation, reason: str) -> ReasoningResult:
    """
    Résultat de repli lorsque le LLM est injoignable.

    La décision reste INTÉGRALEMENT celle des règles : l'indisponibilité du LLM
    ne doit jamais empêcher l'agent de protéger une cargaison.
    """
    logger.warning("SENTRY: raisonnement LLM indisponible, mode dégradé actif (%s)", reason)
    return ReasoningResult(
        decision=evaluation.decision,
        risk_level=evaluation.risk_level,
        reasoning=None,
        justification=_degraded_justification(evaluation, reason),
        requires_human_approval=evaluation.requires_human_approval,
        missing_information=list(evaluation.missing_information),
        risk_factors_narrative=[
            name for name, detail in (evaluation.risk_factors or {}).items() if detail.get("available")
        ],
        llm_available=False,
        overrides=[f"R-GUARD:mode_degrade:{reason}"],
    )


# ===========================================================================
# 7. POINT D'ENTRÉE
# ===========================================================================


def analyze(
    state: AgentState,
    evaluation: RuleEvaluation,
    *,
    provider: Optional[LLMProvider] = None,
) -> ReasoningResult:
    """
    Produit l'analyse contextuelle et la justification de la décision.

    `evaluation` est le résultat de `rules.evaluate(state)` : le raisonnement
    vient TOUJOURS après les règles, jamais avant.

    Ne lève jamais d'exception : toute défaillance du LLM (clé absente, réseau,
    quota, JSON invalide, réponse vide) est convertie en mode dégradé. L'appelant
    (un noeud LangGraph) n'a donc aucune gestion d'erreur à écrire.

    `provider` permet d'injecter un double en test, sans clé API ni réseau.
    """
    try:
        llm = provider or get_llm_provider()
    except LLMUnavailable as exc:
        return _degraded_result(evaluation, str(exc))

    user_prompt = build_user_prompt(state, evaluation)

    try:
        payload = llm.generate_json(SENTRY_SYSTEM_PROMPT, user_prompt)
    except LLMUnavailable as exc:
        return _degraded_result(evaluation, str(exc))
    except Exception as exc:  # filet de sécurité : un incident ne doit rien casser
        return _degraded_result(evaluation, f"erreur inattendue du fournisseur : {exc}")

    return _enforce_rule_authority(payload, evaluation)


async def aanalyze(
    state: AgentState,
    evaluation: RuleEvaluation,
    *,
    provider: Optional[LLMProvider] = None,
) -> ReasoningResult:
    """
    Variante asynchrone de `analyze`.

    Le SDK Gemini utilisé ici est bloquant. Comme la couche base de données du
    projet est asynchrone (`create_async_engine`, `AsyncSession`), les noeuds
    LangGraph seront très probablement `async def` : on déporte donc l'appel
    bloquant dans un thread pour ne pas figer la boucle d'événements de FastAPI.
    """
    import asyncio

    return await asyncio.to_thread(analyze, state, evaluation, provider=provider)


def is_llm_configured() -> bool:
    """
    Indique si Gemini est utilisable, sans effectuer d'appel facturé.

    Utile pour un endpoint de diagnostic destiné à l'ADMIN (« le raisonnement
    contextuel est-il actif ? ») et pour les tests de démarrage.
    """
    try:
        get_llm_provider()
    except LLMUnavailable:
        return False
    return True


def llm_status() -> dict[str, Any]:
    """
    Détail de la configuration LLM pour un endpoint de diagnostic ADMIN.

    Ne renvoie JAMAIS la clé API, seulement sa présence. Aucun appel facturé.
    """
    try:
        provider = get_llm_provider()
    except LLMUnavailable as exc:
        return {
            "provider": PROVIDER_NAME,
            "configured": False,
            "model": None,
            "reason": str(exc),
        }
    return {
        "provider": provider.name,
        "configured": True,
        "model": provider.model_name,
        "reason": None,
    }


__all__ = [
    "API_KEY_ENV",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "PROVIDER_NAME",
    "SENTRY_SYSTEM_PROMPT",
    "UNAVAILABLE",
    "GeminiProvider",
    "LLMProvider",
    "LLMUnavailable",
    "ReasoningResult",
    "aanalyze",
    "analyze",
    "build_user_prompt",
    "get_llm_provider",
    "is_llm_configured",
    "llm_status",
]
