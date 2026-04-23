"""
Unit tests for retrieval logic — ChromaDB and Neo4j are fully mocked.
Tests verify routing logic, context building, and state transitions.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.retrieval.pipeline import (
    CDMQueryState,
    initial_state,
    node_check_sufficiency,
    node_generate,
    node_graph_traversal,
    node_vector_search,
    route_score_gate,
    route_sufficiency,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _state(**overrides) -> CDMQueryState:
    base = initial_state("What attributes does Bank have?")
    base.update(overrides)
    return base


# ── node_vector_search ────────────────────────────────────────────────────────

@patch("app.retrieval.pipeline.similarity_search")
# checks that vector search fills the state with retrieved entry nodes
def test_vector_search_populates_entry_nodes(mock_search):
    mock_search.return_value = [
        {"entity_name": "Bank", "document": "Entity: Bank\nAttributes: ...", "score": 0.91},
        {"entity_name": "Branch", "document": "Entity: Branch\nAttributes: ...", "score": 0.72},
    ]
    state = _state(query_vector=[0.1] * 10)
    result = node_vector_search(state)

    assert len(result["entry_nodes"]) == 2
    assert result["entry_nodes"][0]["entity_name"] == "Bank"
    assert "Bank" in result["sources"]
    assert "Entity: Bank" in result["context_text"]


@patch("app.retrieval.pipeline.similarity_search")
# checks that multiple retrieved docs are merged into one retrieval context
def test_vector_search_context_joins_documents(mock_search):
    mock_search.return_value = [
        {"entity_name": "Bank",   "document": "Doc A", "score": 0.9},
        {"entity_name": "Branch", "document": "Doc B", "score": 0.8},
    ]
    state = _state(query_vector=[0.0] * 10)
    result = node_vector_search(state)
    assert "Doc A" in result["context_text"]
    assert "Doc B" in result["context_text"]


# ── route_score_gate ──────────────────────────────────────────────────────────

# checks that a strong similarity hit moves the pipeline into the KG path
def test_score_gate_routes_to_graph_when_above_threshold():
    state = _state(entry_nodes=[{"entity_name": "Bank", "score": 0.90}])
    with patch("app.retrieval.pipeline.settings.graph_threshold", 0.75):
        assert route_score_gate(state) == "graph_traversal"


# checks that compare can force the KG path even below the normal threshold
def test_score_gate_routes_to_graph_when_force_kg_is_true():
    state = _state(
        entry_nodes=[{"entity_name": "Bank", "score": 0.10}],
        force_kg=True,
    )
    assert route_score_gate(state) == "graph_traversal"


# checks that weaker similarity stays on the pure vector path
def test_score_gate_routes_to_generate_when_below_threshold():
    state = _state(entry_nodes=[{"entity_name": "Bank", "score": 0.50}])
    with patch("app.retrieval.pipeline.settings.graph_threshold", 0.75):
        assert route_score_gate(state) == "generate"


# checks that no hits means no graph traversal
def test_score_gate_routes_to_generate_when_no_nodes():
    state = _state(entry_nodes=[])
    assert route_score_gate(state) == "generate"


# ── node_graph_traversal ──────────────────────────────────────────────────────

@patch("app.retrieval.pipeline.get_entity_subgraph")
# checks that KG traversal really enriches the context with graph data
def test_graph_traversal_enriches_context(mock_subgraph):
    mock_subgraph.return_value = {
        "entities": [
            {
                "name": "Bank",
                "description": "A bank entity.",
                "parents": [],
                "attributes": [
                    {"name": "routingNumber", "type": "string",
                     "display_name": "Routing Number", "description": ""}
                ],
            }
        ],
        "relations": [{"from_entity": "Bank", "to_entity": "Branch"}],
    }
    state = _state(
        entry_nodes=[{"entity_name": "Bank", "score": 0.92}],
        context_text="Entity: Bank\nAttributes: ...",
        hop_depth=1,
    )
    result = node_graph_traversal(state)

    assert "Bank" in result["context_text"]
    assert "Routing Number" in result["context_text"]
    assert result["retrieval_path"] == "graph_traversal"
    assert "Bank" in result["sources"]


@patch("app.retrieval.pipeline.get_entity_subgraph")
# checks that KG traversal falls back cleanly if there is no entry node
def test_graph_traversal_fallback_when_no_entry_nodes(mock_subgraph):
    state = _state(entry_nodes=[])
    result = node_graph_traversal(state)
    mock_subgraph.assert_not_called()
    assert result["retrieval_path"] == "fallback_vector"


# ── node_check_sufficiency ────────────────────────────────────────────────────

# checks the current heuristic: long enough context means stop expanding
def test_sufficiency_true_when_context_long():
    state = _state(context_text="x" * 900, hop_depth=1)
    result = node_check_sufficiency(state)
    assert result["context_sufficient"] is True


# checks the hard stop after 2 hops even if the context is still short
def test_sufficiency_true_when_max_hops_reached():
    state = _state(context_text="short", hop_depth=2)
    result = node_check_sufficiency(state)
    assert result["context_sufficient"] is True


# checks that short context at low hop depth keeps the expansion loop going
def test_sufficiency_false_when_short_context_and_low_hops():
    state = _state(context_text="short", hop_depth=1)
    result = node_check_sufficiency(state)
    assert result["context_sufficient"] is False


# ── route_sufficiency ─────────────────────────────────────────────────────────

# checks that a sufficient context goes straight to answer generation
def test_route_sufficiency_generates_when_sufficient():
    state = _state(context_sufficient=True)
    assert route_sufficiency(state) == "generate"


# checks that an insufficient context triggers one more graph expansion step
def test_route_sufficiency_expands_when_not_sufficient():
    state = _state(context_sufficient=False)
    assert route_sufficiency(state) == "expand_hops"


# ── vector_pipeline end-to-end (mocked) ──────────────────────────────────────

@patch("app.retrieval.pipeline.similarity_search")
@patch("app.retrieval.pipeline.embed_query")
@patch("app.retrieval.pipeline.OpenAI")
# checks the full vector pipeline flow from query to final answer
def test_vector_pipeline_returns_answer(mock_openai, mock_embed, mock_search):
    mock_embed.return_value = [0.1] * 10
    mock_search.return_value = [
        {"entity_name": "Bank", "document": "Entity: Bank", "score": 0.88}
    ]
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value.choices[0].message.content = (
        "Bank has routing number and address attributes."
    )

    from app.retrieval.pipeline import vector_pipeline
    result = vector_pipeline.invoke(initial_state("What fields does Bank have?"))

    assert result["answer"] == "Bank has routing number and address attributes."
    assert "Bank" in result["sources"]
    assert result["retrieval_path"] == "vector"


@patch("app.retrieval.pipeline.OpenAI")
@patch("app.retrieval.pipeline.get_history")
# checks that conversation history is added separately in the prompt, not inside the question
def test_generate_includes_history_separately_from_question(mock_history, mock_openai):
    mock_history.return_value = [
        {"question": "What is Bank?", "answer": "Bank is an entity."}
    ]
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value.choices[0].message.content = (
        "bankId is the unique identifier."
    )

    state = _state(
        query="What is bankId?",
        conversation_id="demo-1",
        context_text="Entity: Bank\nAttributes: bankId ...",
    )
    result = node_generate(state)

    assert result["answer"] == "bankId is the unique identifier."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Conversation history:\nUser: What is Bank?\nAssistant: Bank is an entity." in prompt
    assert "Question: What is bankId?" in prompt
