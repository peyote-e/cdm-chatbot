from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ChunkRequest,
    ChunkResponse,
    CompareResponse,
    EntityDetail,
    EntitySummary,
    QueryRequest,
    QueryResponse,
)
from app.conversation.memory import get_history, store_turn
from app.ingestion.chunker import build_chunk
from app.ingestion.fetcher import load_entity
from app.ingestion.parser import parse_entity_file
from app.retrieval.graph import get_entity_detail, list_all_entities
from app.retrieval.pipeline import hybrid_pipeline, initial_state, vector_pipeline

router = APIRouter()


def _used_kg(result: dict) -> bool:
    return result.get("retrieval_path") == "graph_traversal"


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/chunk", response_model=ChunkResponse)
async def preview_chunk(request: ChunkRequest):
    import json
    import tempfile
    from pathlib import Path

    filename = f"{request.entity_name}.cdm.json"
    raw = load_entity(filename)
    if raw is None:
        raise HTTPException(
            status_code=404,
            detail=f"Entity source '{request.entity_name}' not found.",
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".cdm.json", delete=False) as f:
        json.dump(raw, f)
        tmp_path = Path(f.name)

    try:
        parsed = parse_entity_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not parsed:
        raise HTTPException(
            status_code=422,
            detail=f"Entity source '{request.entity_name}' could not be parsed.",
        )

    return ChunkResponse(
        entity_name=parsed["entity_name"],
        attribute_detail=request.attribute_detail,
        chunk=build_chunk(parsed, attribute_detail=request.attribute_detail),
    )


@router.post("/query/vector", response_model=QueryResponse)
async def query_vector(request: QueryRequest):
    result = vector_pipeline.invoke(
        initial_state(request.question, conversation_id=request.conversation_id)
    )
    store_turn(request.conversation_id, request.question, result["answer"])
    return QueryResponse(
        question=request.question,
        answer=result["answer"],
        sources=result["sources"],
        retrieval_path="vector",
        used_kg=False,
        conversation_id=request.conversation_id,
        history=get_history(request.conversation_id),
    )


@router.post("/query/hybrid", response_model=QueryResponse)
async def query_hybrid(request: QueryRequest):
    result = hybrid_pipeline.invoke(
        initial_state(request.question, conversation_id=request.conversation_id)
    )
    store_turn(request.conversation_id, request.question, result["answer"])
    return QueryResponse(
        question=request.question,
        answer=result["answer"],
        sources=result["sources"],
        retrieval_path=result.get("retrieval_path", "graph_traversal"),
        used_kg=_used_kg(result),
        conversation_id=request.conversation_id,
        history=get_history(request.conversation_id),
    )


@router.post("/query/compare", response_model=CompareResponse)
async def query_compare(request: QueryRequest):
    """Run both pipelines and return answers side-by-side."""
    v_state = initial_state(request.question, conversation_id=request.conversation_id)
    h_state = initial_state(
        request.question,
        conversation_id=request.conversation_id,
        force_kg=True,
    )

    vector_result = vector_pipeline.invoke(v_state)
    hybrid_result = hybrid_pipeline.invoke(h_state)
    store_turn(request.conversation_id, request.question, hybrid_result["answer"])

    return CompareResponse(
        question=request.question,
        vector_answer=vector_result["answer"],
        hybrid_answer=hybrid_result["answer"],
        vector_sources=vector_result["sources"],
        hybrid_sources=hybrid_result["sources"],
        retrieval_path=hybrid_result.get("retrieval_path", "graph_traversal"),
        used_kg=_used_kg(hybrid_result),
        conversation_id=request.conversation_id,
        history=get_history(request.conversation_id),
    )


@router.get("/entities", response_model=list[EntitySummary])
async def list_entities():
    rows = list_all_entities()
    return [
        EntitySummary(
            name=r["name"],
            description=r.get("description") or "",
            attribute_count=r.get("attribute_count") or 0,
        )
        for r in rows
    ]


@router.get("/entity/{name}", response_model=EntityDetail)
async def get_entity(name: str):
    detail = get_entity_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Entity '{name}' not found.")
    return EntityDetail(
        name=detail["name"],
        description=detail.get("description") or "",
        extends_entity=detail.get("extends_entity") or "",
        attributes=detail.get("attributes") or [],
        relations=detail.get("relations") or [],
        neighbors=detail.get("neighbors") or [],
    )
