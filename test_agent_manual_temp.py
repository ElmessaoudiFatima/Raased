#!/usr/bin/env python3
"""
Script de test manuel de l'agent SENTRY avec les modules :
- state.py
- rules.py
- reasoning.py
- memory.py

Il simule un AgentState, passe successivement par :
1. rules.evaluate() -> decision deterministe
2. reasoning.analyze() -> justification en langage naturel
3. memory.store_memory() + memory.search_similar() -> stockage & recherche sémantique

Ce script ne nécessite aucune base de données ni clé API Gemini (le mode dégradé sera utilisé).
"""

import asyncio
from app.agent.state import AgentState, create_initial_state
from app.agent.rules import evaluate
from app.agent.reasoning import analyze
from app.agent.memory import get_agent_memory, build_situation_text


def main() -> None:
    print("=== TEST MANUEL DE L'AGENT SENTRY ===\n")

    # 1. Créer un état initial avec quelques données factices (simulées)
    state: AgentState = create_initial_state()
    state["trip_id"] = "TRIP-002"
    state["cargo_id"] = "CARGO-002"
    state["cargo_type"] = "marchandise dangereuse"
    state["criticality"] = "HIGH"
    state["incident_detected"] = True
    state["incident_type"] = "temperature_breach"
    state["incident_severity"] = "HIGH"
    # Les champs suivants seront remplis par rules.py
    # state["risk_score"] = None
    # state["risk_level"] = None
    # state["decision"] = None

    print("État initial (simulé) :")
    print(f"  trip_id: {state.get('trip_id')}")
    print(f"  cargo_type: {state.get('cargo_type')}")
    print(f"  criticality: {state.get('criticality')}")
    print(f"  incident_detected: {state.get('incident_detected')}")
    print(f"  incident_type: {state.get('incident_type')}")
    print(f"  incident_severity: {state.get('incident_severity')}")
    print()

    # 2. Test rules.py
    print("--- 1. RULES.EVALUATE ---")
    try:
        evaluation = evaluate(state)  # RuleEvaluation
        print(f"Décision : {evaluation.decision}")
        print(f"Niveau de risque : {evaluation.risk_level}")
        print(f"Score de risque : {evaluation.risk_score}")
        print(f"Confiance : {evaluation.confidence}")
        print(f"Requiert QoD : {evaluation.qod_required}")
        print(f"Requiert slice réseau : {evaluation.network_slice_required}")
        print(f"Requiert validation humaine : {evaluation.requires_human_approval}")
        print(f"Trace des règles : {evaluation.rule_trace}")
        print(f"Informations manquantes : {evaluation.missing_information}")
        print()
    except Exception as e:
        print(f"Erreur dans rules.evaluate : {e}")
        return

    # 3. Test reasoning.py
    print("--- 2. REASONING.ANALYZE ---")
    try:
        # analyze est synchrone et prend l'état + l'évaluation
        result = analyze(state, evaluation)  # ReasoningResult
        print(f"Justification : {result.justification}")
        print(f"Raisonnement : {result.reasoning}")
        print(f"LLM disponible : {result.llm_available}")
        print()
    except Exception as e:
        print(f"Erreur dans reasoning.analyze : {e}")
        return

    # 4. Test memory.py
    print("--- 3. MEMORY ---")
    try:
        memory = get_agent_memory()

        # Construire le texte situationnel à partir de l'état réel
        situation_text = build_situation_text(state)
        print(f"Texte situationnel : {situation_text}")

        # ID déterministe basé sur trip_id, incident_type et timestamp simple
        # Dans la vraie implémentation, on utiliserait evaluated_at depuis l'état
        memory_id = f"{state['trip_id']}__{state.get('incident_type', 'unknown')}__2026-09-07T12:00:00Z"

        # Métadonnées plates (ChromaDB accepte uniquement str/int/float/bool)
        metadata = {
            "trip_id": state.get("trip_id", ""),
            "cargo_id": state.get("cargo_id", ""),
            "cargo_type": state.get("cargo_type", ""),
            "criticality": state.get("criticality", ""),
            "incident_type": state.get("incident_type", ""),
            "incident_severity": state.get("incident_severity", ""),
            "risk_level": evaluation.risk_level or "",
            "decision": str(evaluation.decision),
            "action_result": "simulated",  # champ factice pour le test
            "created_at": "2026-09-07T12:00:00Z",
        }

        print(f"Stockage de la mémoire avec ID : {memory_id}")
        memory.store_memory(memory_id, situation_text, metadata)
        print("Mémoire stockée avec succès.")

        # Recherche similaire
        print("\nRecherche de situations similaires...")
        similar = memory.search_similar(situation_text, n_results=3)
        print(f"Résultats trouvés : {len(similar)}")
        for i, mem in enumerate(similar, 1):
            print(f"  {i}. ID: {mem['id']}")
            print(f"     Document: {mem['document'][:80]}...")
            print(f"     Distance: {mem['distance']:.4f}")
            print()
    except Exception as e:
        print(f"Erreur dans memory : {e}")
        import traceback
        traceback.print_exc()
        return

    print("=== TEST TERMINÉ AVEC SUCCÈS ===")


if __name__ == "__main__":
    main()