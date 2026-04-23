from typing import Literal

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    conversation_id: str | None = None


class ConversationTurn(BaseModel):
    question: str
    answer: str


class ChunkRequest(BaseModel):
    entity_name: str
    attribute_detail: Literal["full", "minimal"] = "full"


class ChunkResponse(BaseModel):
    entity_name: str
    attribute_detail: Literal["full", "minimal"]
    chunk: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]
    retrieval_path: str
    used_kg: bool = False
    conversation_id: str | None = None
    history: list[ConversationTurn] = []


class CompareResponse(BaseModel):
    question: str
    vector_answer: str
    hybrid_answer: str
    vector_sources: list[str]
    hybrid_sources: list[str]
    retrieval_path: str  # "graph_traversal" | "fallback_vector"
    used_kg: bool = False
    conversation_id: str | None = None
    history: list[ConversationTurn] = []


class AttributeInfo(BaseModel):
    name: str
    type: str
    display_name: str
    description: str
    enum_values: list[str] = []
    is_relationship: bool = False
    referenced_entity: str = ""


class EntitySummary(BaseModel):
    name: str
    description: str
    attribute_count: int


class EntityDetail(BaseModel):
    name: str
    description: str
    extends_entity: str
    attributes: list[dict]
    relations: list[dict]
    neighbors: list[str]
