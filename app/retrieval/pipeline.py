"""
LangGraph pipelines for CDM query answering.

"""

from __future__ import annotations

import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph
from openai import OpenAI

from app.config import settings
from app.conversation.memory import get_history
from app.ingestion.embedder import embed_query
from app.retrieval.graph import get_entity_subgraph
from app.retrieval.vector import similarity_search

log = logging.getLogger("cdm.pipeline")


class CDMQueryState(TypedDict):
    query: str
    conversation_id: str | None
    force_kg: bool
    query_vector: list
    entry_nodes: list
    subgraph: dict
    context_text: str
    answer: str
    sources: list
    hop_depth: int
    context_sufficient: bool
    retrieval_path: str


def node_embed(state: CDMQueryState) -> dict:
    return {"query_vector": embed_query(state["query"])}


def node_vector_search(state: CDMQueryState) -> dict:
    hits = similarity_search(state["query_vector"], n_results=3)
    context = "\n\n".join(h["document"] for h in hits)
    log.info(
        "[VECTOR] top hits: %s",
        ", ".join(f"{h['entity_name']} (score={h['score']})" for h in hits),
    )
    return {
        "entry_nodes": hits,
        "context_text": context,
        "sources": [h["entity_name"] for h in hits],
    }


def node_generate(state: CDMQueryState) -> dict:
    client = OpenAI(api_key=settings.openai_api_key)

    history = get_history(state.get("conversation_id"))
    history_text = "None"
    if history:
        history_lines: list[str] = []
        for turn in history:
            history_lines.append(f"User: {turn['question']}")
            history_lines.append(f"Assistant: {turn['answer']}")
        history_text = "\n".join(history_lines)

    prompt = (
        "You are an expert on the Microsoft Common Data Model (CDM) Banking schema.\n"
        "Answer the question using ONLY the CDM context below. "
        "Also only answer CDM-related questions — if the question is outside the scope of CDM, say you don't know.\n"
        "If the context does not contain enough information, say so do not guess.\n\n"
        f"Conversation history:\n{history_text}\n\n"
        f"Context:\n{state['context_text']}\n\n"
        f"Question: {state['query']}\n\nAnswer:"
    )
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return {"answer": response.choices[0].message.content}


def node_graph_traversal(state: CDMQueryState) -> dict:
    entity_names = [
        n["entity_name"] for n in state["entry_nodes"] if n.get("entity_name")
    ]
    if not entity_names:
        return {"retrieval_path": "fallback_vector"}

    subgraph = get_entity_subgraph(entity_names, hop_depth=state.get("hop_depth", 1))

    parts = [state.get("context_text", "")]
    for entity in subgraph.get("entities", []):
        lines = [f"\n=== CDM Entity: {entity['name']} ==="]
        if entity.get("description"):
            lines.append(f"Description: {entity['description']}")
        if entity.get("parents"):
            lines.append(f"Inherits from: {', '.join(entity['parents'])}")
        attrs = entity.get("attributes", [])
        if attrs:
            attr_str = ", ".join(
                f"{a['display_name'] or a['name']} ({a['type']})" for a in attrs[:30]
            )
            lines.append(f"Attributes: {attr_str}")
        parts.append("\n".join(lines))

    rels = subgraph.get("relations", [])
    if rels:
        rel_lines = ["Relationships:"]
        for r in rels:
            rel_lines.append(f"  {r['from_entity']} → {r['to_entity']}")
        parts.append("\n".join(rel_lines))

    all_sources = list(
        {
            *[n["entity_name"] for n in state["entry_nodes"]],
            *[e["name"] for e in subgraph.get("entities", [])],
        }
    )

    kg_entities = [e["name"] for e in subgraph.get("entities", [])]
    kg_rels = [(r["from_entity"], r["to_entity"]) for r in subgraph.get("relations", [])]
    log.info("[KG] hop_depth=%d entities=%s", state.get("hop_depth", 1), kg_entities)
    log.info("[KG] relations=%s", [f"{f}→{t}" for f, t in kg_rels])
    log.info("[KG] context_length=%d chars", len("\n\n".join(p for p in parts if p)))

    return {
        "subgraph": subgraph,
        "context_text": "\n\n".join(p for p in parts if p),
        "sources": all_sources,
        "retrieval_path": "graph_traversal",
    }


def node_check_sufficiency(state: CDMQueryState) -> dict:
    sufficient = (
        len(state.get("context_text", "")) > 800
        or state.get("hop_depth", 1) >= 2
    )
    return {"context_sufficient": sufficient}


def node_expand_hops(state: CDMQueryState) -> dict:
    return {"hop_depth": state.get("hop_depth", 1) + 1}


def route_score_gate(state: CDMQueryState) -> str:
    if not state.get("entry_nodes"):
        log.info("[ROUTE] no entry nodes → fallback generate")
        return "generate"
    if state.get("force_kg", False):
        log.info("[ROUTE] force_kg=true → graph_traversal")
        return "graph_traversal"
    best_score = max(n["score"] for n in state["entry_nodes"])
    path = "graph_traversal" if best_score > settings.graph_threshold else "generate"
    log.info(
        "[ROUTE] best_score=%.4f threshold=%.2f → %s",
        best_score,
        settings.graph_threshold,
        path,
    )
    return path


def route_sufficiency(state: CDMQueryState) -> str:
    return "generate" if state.get("context_sufficient") else "expand_hops"


def _build_vector_pipeline():
    g = StateGraph(CDMQueryState)
    g.add_node("embed", node_embed)
    g.add_node("vector_search", node_vector_search)
    g.add_node("generate", node_generate)

    g.set_entry_point("embed")
    g.add_edge("embed", "vector_search")
    g.add_edge("vector_search", "generate")
    g.add_edge("generate", END)
    return g.compile()


def _build_hybrid_pipeline():
    g = StateGraph(CDMQueryState)
    g.add_node("embed", node_embed)
    g.add_node("vector_search", node_vector_search)
    g.add_node("graph_traversal", node_graph_traversal)
    g.add_node("check_sufficiency", node_check_sufficiency)
    g.add_node("expand_hops", node_expand_hops)
    g.add_node("generate", node_generate)

    g.set_entry_point("embed")
    g.add_edge("embed", "vector_search")
    g.add_conditional_edges(
        "vector_search",
        route_score_gate,
        {"graph_traversal": "graph_traversal", "generate": "generate"},
    )
    g.add_edge("graph_traversal", "check_sufficiency")
    g.add_conditional_edges(
        "check_sufficiency",
        route_sufficiency,
        {"generate": "generate", "expand_hops": "expand_hops"},
    )
    g.add_edge("expand_hops", "graph_traversal")
    g.add_edge("generate", END)
    return g.compile()


vector_pipeline = _build_vector_pipeline()
hybrid_pipeline = _build_hybrid_pipeline()


def initial_state(
    question: str,
    conversation_id: str | None = None,
    force_kg: bool = False,
) -> CDMQueryState:
    return CDMQueryState(
        query=question,
        conversation_id=conversation_id,
        force_kg=force_kg,
        query_vector=[],
        entry_nodes=[],
        subgraph={},
        context_text="",
        answer="",
        sources=[],
        hop_depth=1,
        context_sufficient=False,
        retrieval_path="vector",
    )
