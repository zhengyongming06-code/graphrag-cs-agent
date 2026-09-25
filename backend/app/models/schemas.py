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
    document_id: str | None = Field(default=None, max_length=64)


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


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    detail: str = Field(default="", max_length=4000)
    priority: str = Field(default="normal", max_length=16)
    session_id: str = Field(default="", max_length=64)
    ticket_id: str | None = Field(default=None, max_length=64)


class TicketPatch(BaseModel):
    status: Literal["open", "pending", "resolved", "closed"] = "open"


class SessionSummary(BaseModel):
    session_id: str
    created_at: str | None = None
    updated_at: str | None = None
    turn_count: int = 0


class SessionTurn(BaseModel):
    role: str
    content: str
    intent: str = ""
    confidence: float = 0.0
    created_at: str | None = None


class SessionDetail(BaseModel):
    session_id: str
    created_at: str | None = None
    updated_at: str | None = None
    turns: list[SessionTurn] = []
