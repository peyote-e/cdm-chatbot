"""
Integration tests for FastAPI endpoints using TestClient.
All external calls (Voyage AI, OpenAI, ChromaDB, Neo4j) are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.conversation import memory
from app.main import app

client = TestClient(app)


# ── Shared mock helpers ───────────────────────────────────────────────────────

def _mock_vector_pipeline(answer="Vector answer.", sources=None):
    mock = MagicMock()
    mock.invoke.return_value = {
        "answer": answer,
        "sources": sources or ["Bank"],
        "retrieval_path": "vector",
    }
    return mock


def _mock_hybrid_pipeline(answer="Hybrid answer.", sources=None, path="graph_traversal"):
    mock = MagicMock()
    mock.invoke.return_value = {
        "answer": answer,
        "sources": sources or ["Bank", "Branch"],
        "retrieval_path": path,
    }
    return mock


# ── /health ───────────────────────────────────────────────────────────────────

# simple smoke test for the api itself
def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.fixture(autouse=True)
def clear_memory():
    memory.clear_memory()
    yield
    memory.clear_memory()


# ── /chunk ────────────────────────────────────────────────────────────────────

@patch("app.api.routes.load_entity")
@patch("app.api.routes.parse_entity_file")
# checks that the chunk preview endpoint returns the rich full chunk
def test_chunk_preview_returns_full_chunk(mock_parse, mock_load):
    mock_load.return_value = {"definitions": [{}]}
    mock_parse.return_value = {
        "entity_name": "Bank",
        "description": "A bank entity.",
        "extends_entity": "CdsStandard",
        "attributes": [
            {
                "name": "bankId",
                "type": "entityId",
                "display_name": "Bank",
                "description": "Unique identifier for entity instances",
                "enum_values": [],
                "referenced_entity": "",
                "is_relationship": False,
            }
        ],
        "relationships": [],
    }

    resp = client.post("/chunk", json={"entity_name": "Bank", "attribute_detail": "full"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_name"] == "Bank"
    assert data["attribute_detail"] == "full"
    assert '"name": "bankId"' in data["chunk"]


@patch("app.api.routes.load_entity")
@patch("app.api.routes.parse_entity_file")
# checks that the chunk preview endpoint can still return the minimal chunk
def test_chunk_preview_returns_minimal_chunk(mock_parse, mock_load):
    mock_load.return_value = {"definitions": [{}]}
    mock_parse.return_value = {
        "entity_name": "Bank",
        "description": "A bank entity.",
        "extends_entity": "CdsStandard",
        "attributes": [
            {
                "name": "bankId",
                "type": "entityId",
                "display_name": "Bank",
                "description": "Unique identifier for entity instances",
                "enum_values": [],
                "referenced_entity": "",
                "is_relationship": False,
            }
        ],
        "relationships": [],
    }

    resp = client.post("/chunk", json={"entity_name": "Bank", "attribute_detail": "minimal"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["attribute_detail"] == "minimal"
    assert "Attributes (own): Bank (entityId)" in data["chunk"]


@patch("app.api.routes.load_entity")
# checks that unknown entities return a clean 404
def test_chunk_preview_not_found(mock_load):
    mock_load.return_value = None

    resp = client.post("/chunk", json={"entity_name": "DoesNotExist"})
    assert resp.status_code == 404


# ── /query/vector ─────────────────────────────────────────────────────────────

@patch("app.api.routes.vector_pipeline", _mock_vector_pipeline())
# checks that the vector endpoint returns a normal answer payload
def test_query_vector_returns_answer():
    resp = client.post("/query/vector", json={"question": "What fields does Bank have?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Vector answer."
    assert data["retrieval_path"] == "vector"
    assert data["used_kg"] is False
    assert "Bank" in data["sources"]
    assert data["history"] == []


@patch("app.api.routes.vector_pipeline", _mock_vector_pipeline())
# checks that the original user question is echoed back in the response
def test_query_vector_echoes_question():
    resp = client.post("/query/vector", json={"question": "Test question"})
    assert resp.json()["question"] == "Test question"


# checks request validation when the question field is missing
def test_query_vector_missing_question():
    resp = client.post("/query/vector", json={})
    assert resp.status_code == 422


@patch("app.api.routes.vector_pipeline")
# checks that the api passes the conversation id into the retrieval pipeline state
def test_query_vector_passes_conversation_id_into_pipeline(mock_pipeline):
    mock_pipeline.invoke.side_effect = [
        {"answer": "Bank has id fields.", "sources": ["Bank"], "retrieval_path": "vector"},
        {"answer": "It also has status fields.", "sources": ["Bank"], "retrieval_path": "vector"},
    ]

    first = client.post(
        "/query/vector",
        json={"question": "What fields does Bank have?", "conversation_id": "demo-1"},
    )
    second = client.post(
        "/query/vector",
        json={"question": "What about its status fields?", "conversation_id": "demo-1"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_pipeline.invoke.call_count == 2
    second_state = mock_pipeline.invoke.call_args_list[1].args[0]
    assert second_state["query"] == "What about its status fields?"
    assert second_state["conversation_id"] == "demo-1"
    second_data = second.json()
    assert second_data["conversation_id"] == "demo-1"
    assert second_data["history"] == [
        {
            "question": "What fields does Bank have?",
            "answer": "Bank has id fields.",
        },
        {
            "question": "What about its status fields?",
            "answer": "It also has status fields.",
        },
    ]


@patch("app.api.routes.hybrid_pipeline")
# checks that without a conversation id the hybrid route stays stateless
def test_query_hybrid_without_conversation_id_stays_stateless(mock_pipeline):
    mock_pipeline.invoke.return_value = {
        "answer": "Hybrid answer.",
        "sources": ["Bank"],
        "retrieval_path": "graph_traversal",
    }

    resp = client.post("/query/hybrid", json={"question": "What is bankId?"})

    assert resp.status_code == 200
    state = mock_pipeline.invoke.call_args.args[0]
    assert state["query"] == "What is bankId?"
    assert resp.json()["history"] == []


# ── /query/hybrid ─────────────────────────────────────────────────────────────

@patch("app.api.routes.hybrid_pipeline", _mock_hybrid_pipeline())
# checks that the hybrid endpoint returns an answer and marks the kg path
def test_query_hybrid_returns_answer():
    resp = client.post("/query/hybrid", json={"question": "Which branch handles a loan?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Hybrid answer."
    assert data["retrieval_path"] == "graph_traversal"
    assert data["used_kg"] is True


@patch("app.api.routes.hybrid_pipeline", _mock_hybrid_pipeline(path="fallback_vector"))
# checks that the api exposes the fallback retrieval path correctly
def test_query_hybrid_fallback_path_is_returned():
    resp = client.post("/query/hybrid", json={"question": "Some question"})
    data = resp.json()
    assert data["retrieval_path"] == "fallback_vector"
    assert data["used_kg"] is False


# ── /query/compare ────────────────────────────────────────────────────────────

@patch("app.api.routes.hybrid_pipeline")
@patch("app.api.routes.vector_pipeline")
# checks that compare returns both answers side by side
def test_compare_returns_both_answers(mock_vector, mock_hybrid):
    mock_vector.invoke.return_value = {
        "answer": "Vector gives less detail.",
        "sources": ["Bank"],
        "retrieval_path": "vector",
    }
    mock_hybrid.invoke.return_value = {
        "answer": "KG gives more detail.",
        "sources": ["Bank", "Branch"],
        "retrieval_path": "graph_traversal",
    }

    resp = client.post("/query/compare", json={"question": "Which branch handles a loan?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["vector_answer"] == "Vector gives less detail."
    assert data["hybrid_answer"] == "KG gives more detail."
    assert "retrieval_path" in data
    assert data["used_kg"] is True
    assert data["history"] == []
    hybrid_state = mock_hybrid.invoke.call_args.args[0]
    assert hybrid_state["force_kg"] is True


@patch("app.api.routes.hybrid_pipeline", _mock_hybrid_pipeline())
@patch("app.api.routes.vector_pipeline", _mock_vector_pipeline())
# checks that compare keeps the vector and hybrid sources separate
def test_compare_returns_separate_sources():
    resp = client.post("/query/compare", json={"question": "Test"})
    data = resp.json()
    assert "vector_sources" in data
    assert "hybrid_sources" in data


# ── /entities ─────────────────────────────────────────────────────────────────

@patch("app.api.routes.list_all_entities")
# checks that the entity list endpoint maps graph rows into api output
def test_list_entities(mock_list):
    mock_list.return_value = [
        {"name": "Bank",   "description": "A bank.", "attribute_count": 12},
        {"name": "Branch", "description": "A branch.", "attribute_count": 8},
    ]
    resp = client.get("/entities")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "Bank"
    assert data[0]["attribute_count"] == 12


# ── /entity/{name} ────────────────────────────────────────────────────────────

@patch("app.api.routes.get_entity_detail")
# checks that entity detail returns attributes, relations and neighbors correctly
def test_get_entity_detail(mock_detail):
    mock_detail.return_value = {
        "name": "Bank",
        "description": "The physical bank location.",
        "extends_entity": "CdsStandard",
        "attributes": [{"name": "routingNumber", "type": "string",
                        "display_name": "Routing Number", "description": ""}],
        "relations": [{"to_entity": "Branch", "from_attribute": "homeBranchId"}],
        "neighbors": ["Branch"],
    }
    resp = client.get("/entity/Bank")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Bank"
    assert data["extends_entity"] == "CdsStandard"
    assert len(data["attributes"]) == 1
    assert "Branch" in data["neighbors"]


@patch("app.api.routes.get_entity_detail")
# checks the 404 case for unknown entities
def test_get_entity_not_found(mock_detail):
    mock_detail.return_value = None
    resp = client.get("/entity/NonExistentEntity")
    assert resp.status_code == 404
