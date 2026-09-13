"""Tests techniques isolés du pipeline LangGraph SENTRY.

Ces tests ne créent ni donnée PostgreSQL ni mémoire ChromaDB : les nœuds
testés quittent le flux avant tout accès externe, ou sont remplacés par mocks.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.agent.graph as graph_module
from app.agent.graph import _after_persistence, build_graph
import app.agent.nodes as nodes_module
from app.agent.nodes import camara_perception_node, network_action_node, trust_checks_node


def test_graph_compiles() -> None:
    assert build_graph() is not None


@pytest.mark.asyncio
async def test_graph_runs_minimal_state_with_isolated_nodes(monkeypatch) -> None:
    async def noop_node(state):
        return {}

    for name in (
        "load_context_node", "camara_perception_node", "trust_checks_node",
        "rules_node", "reasoning_node", "persist_assessment_node",
        "network_action_node", "memory_node",
    ):
        monkeypatch.setattr(graph_module, name, noop_node)

    result = await graph_module.build_graph().ainvoke({"missing_information": [], "rule_trace": [], "errors": []})
    assert result["missing_information"] == []


def test_network_action_branch_requires_the_matching_decision() -> None:
    assert _after_persistence({"qod_required": True, "decision": "REQUEST_MORE_INFORMATION"}) == "memory"
    assert _after_persistence({
        "qod_required": True,
        "decision": "REQUEST_QOD",
        "risk_assessment_id": "persisted-assessment",
    }) == "network_action"


def test_network_action_branch_waits_for_human_approval() -> None:
    assert _after_persistence({
        "network_slice_required": True,
        "decision": "REQUEST_NETWORK_SLICE",
        "requires_human_approval": True,
        "human_approved": None,
    }) == "memory"


@pytest.mark.asyncio
async def test_perception_skips_camara_without_explicit_plan(monkeypatch) -> None:
    async def must_not_run(*args, **kwargs):
        raise AssertionError("CAMARA ne doit pas être appelé sans plan explicite")

    monkeypatch.setattr("app.agent.nodes.get_congestion_risk", must_not_run)
    assert await camara_perception_node({"tracker_id": "not-used"}) == {}


@pytest.mark.asyncio
async def test_perception_does_not_call_camara_without_tracker_id(monkeypatch) -> None:
    async def must_not_run(*args, **kwargs):
        raise AssertionError("CAMARA ne doit pas être appelé sans tracker_id")

    monkeypatch.setattr("app.agent.nodes.get_congestion_risk", must_not_run)
    result = await camara_perception_node({"camara_requests": {"congestion": True}})
    assert "tracker_id indisponible" in result["missing_information"][0]


class _FakeSession:
    def __init__(self, tracker):
        self.tracker = tracker

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, model, identifier):
        return self.tracker


@pytest.mark.asyncio
async def test_congestion_skips_camara_without_corridor(monkeypatch) -> None:
    tracker_id = str(uuid4())
    monkeypatch.setattr(nodes_module, "AsyncSessionLocal", lambda: _FakeSession(SimpleNamespace(msisdn="+212600000000")))

    async def must_not_run(*args, **kwargs):
        raise AssertionError("Congestion Insights ne doit pas être appelé sans corridor")

    monkeypatch.setattr(nodes_module, "get_congestion_risk", must_not_run)
    result = await camara_perception_node({
        "tracker_id": tracker_id,
        "camara_requests": {"congestion": True},
    })
    assert "corridor_id indisponible" in result["missing_information"][0]


@pytest.mark.asyncio
async def test_trust_checks_skip_camara_without_explicit_check_plan(monkeypatch) -> None:
    async def must_not_run(*args, **kwargs):
        raise AssertionError("Les contrôles de confiance ne sont pas systématiques")

    monkeypatch.setattr("app.agent.nodes.verify_number", must_not_run)
    assert await trust_checks_node({"tracker_id": "not-used", "camara_requests": {"congestion": True}}) == {}


@pytest.mark.asyncio
async def test_qod_skips_camara_without_real_network_parameters(monkeypatch) -> None:
    tracker_id, assessment_id = str(uuid4()), str(uuid4())
    monkeypatch.setattr(nodes_module, "AsyncSessionLocal", lambda: _FakeSession(SimpleNamespace(msisdn="+212600000000")))

    async def must_not_run(*args, **kwargs):
        raise AssertionError("QoD ne doit pas être appelé avec des paramètres réseau absents")

    monkeypatch.setattr(nodes_module, "request_priority_for_tracker", must_not_run)
    result = await network_action_node({
        "tracker_id": tracker_id,
        "risk_assessment_id": assessment_id,
        "decision": "REQUEST_QOD",
        "qod_required": True,
        "qod_parameters": {},
    })
    assert "paramètres QoD réels indisponibles" in result["missing_information"][0]
