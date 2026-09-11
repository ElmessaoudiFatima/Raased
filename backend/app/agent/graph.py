"""Assemblage du graphe LangGraph SENTRY.

Workflow logique : COLLECT (load) -> CHECK CAMARA (perception/trust, si demandé)
-> CHECK_WEATHER (conditionnel, fallback) -> FUSE_CONTEXT -> CALCULATE_RISK
(rules) -> SEARCH_SIMILAR (mémoire réutilisée) -> LLM_REASONING -> DECIDE
(dans rules) -> NOTIFY/RECORD (persist) -> HUMAN_GATE -> EXECUTE (network)
-> MEMORY. Les noms historiques sont conservés, pas de réécriture.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    camara_perception_node, fuse_context_node, load_context_node, memory_node,
    network_action_node, persist_assessment_node, reasoning_node, rules_node,
    similar_cases_node, trust_checks_node, weather_node,
)
from app.agent.state import AgentState


def _after_context(state: AgentState) -> str:
    """Évite même d'entrer dans le nœud CAMARA sans demande explicite."""
    plan = state.get("camara_requests") or {}
    if plan.get("congestion") or plan.get("location"):
        return "camara_perception"
    return "trust_checks" if _needs_trust_check(state) else "rules"


def _needs_trust_check(state: AgentState) -> bool:
    plan = state.get("camara_requests") or {}
    return any(plan.get(name) for name in ("number_verification", "sim_swap", "device_swap"))


def _after_perception(state: AgentState) -> str:
    return "trust_checks" if _needs_trust_check(state) else "rules"


def _after_persistence(state: AgentState) -> str:
    """N'autorise une action réseau qu'après approbation humaine si nécessaire."""
    decision = state.get("decision")
    if decision not in {"REQUEST_QOD", "IMPROVE_CONNECTIVITY", "REQUEST_NETWORK_SLICE"}:
        return "memory"
    if decision in {"REQUEST_QOD", "IMPROVE_CONNECTIVITY"} and state.get("qod_required") is not True:
        return "memory"
    if decision == "REQUEST_NETWORK_SLICE" and state.get("network_slice_required") is not True:
        return "memory"
    if not state.get("risk_assessment_id"):
        return "memory"
    if state.get("requires_human_approval") and state.get("human_approved") is not True:
        return "memory"
    return "network_action"


def _after_trust(state: AgentState) -> str:
    """Après les contrôles : toujours météo puis fusion avant le risque."""
    return "weather"


def build_graph():
    """Construit un graphe compilé sans singleton, adapté aux tests."""
    graph = StateGraph(AgentState)
    graph.add_node("load_context", load_context_node)
    graph.add_node("camara_perception", camara_perception_node)
    graph.add_node("trust_checks", trust_checks_node)
    graph.add_node("check_weather", weather_node)
    graph.add_node("fuse_context", fuse_context_node)
    graph.add_node("rules", rules_node)
    graph.add_node("search_similar", similar_cases_node)
    graph.add_node("llm_reasoning", reasoning_node)
    graph.add_node("persist_assessment", persist_assessment_node)
    graph.add_node("network_action", network_action_node)
    graph.add_node("memory", memory_node)
    graph.add_edge(START, "load_context")
    graph.add_conditional_edges("load_context", _after_context, {
        "camara_perception": "camara_perception",
        "trust_checks": "trust_checks",
        "rules": "rules",
    })
    graph.add_conditional_edges("camara_perception", _after_perception, {
        "trust_checks": "trust_checks",
        "rules": "rules",
    })
    graph.add_edge("trust_checks", "check_weather")
    graph.add_edge("check_weather", "fuse_context")
    graph.add_edge("fuse_context", "rules")
    graph.add_edge("rules", "search_similar")
    graph.add_edge("search_similar", "llm_reasoning")
    graph.add_edge("llm_reasoning", "persist_assessment")
    graph.add_conditional_edges("persist_assessment", _after_persistence,
        {"network_action": "network_action", "memory": "memory"})
    graph.add_edge("network_action", "memory")
    graph.add_edge("memory", END)
    return graph.compile()


__all__ = ["build_graph"]
