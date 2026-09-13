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


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    tool_trace: list[str] = []
    session_id: str
    mode: str = "agent"


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
