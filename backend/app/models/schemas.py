from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="default", max_length=64)
    stream: bool = False


class Citation(BaseModel):
    chunk_id: str
    title: str
    score: float
    snippet: str
    source: str = ""


class PipelineStep(BaseModel):
    step: str
    detail: str = ""
    ok: bool = True


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    tool_trace: list[str] = []
    session_id: str
    mode: str = "agent"
    intent: str = ""
    confidence: float = 0.0
    grounded: bool = False
    ticket_id: str = ""
    pipeline: list[PipelineStep] = []


class IngestTextRequest(BaseModel):
    title: str
    content: str
    source: str = "manual"
    category: str = "general"


class IngestResponse(BaseModel):
    document_id: str
    chunk_count: int
    entity_count: int
    message: str


class HealthResponse(BaseModel):
    status: str
    neo4j: str
    llm: str
    embedding: str
    stats: dict = {}
    categories: list[dict] = []


class CompareRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class EvalRequest(BaseModel):
    mode: str = Field(default="agent", description="agent | retrieval | both")


class TicketPatch(BaseModel):
    status: Literal["open", "pending", "resolved", "closed"] = "open"
