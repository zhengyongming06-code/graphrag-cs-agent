from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent.graph import get_agent
from app.config import get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IngestResponse,
    IngestTextRequest,
)
from app.rag.embeddings import EmbeddingService
from app.rag.ingest import KnowledgeIngestor
from app.rag.neo4j_client import get_neo4j

settings = get_settings()
app = FastAPI(
    title="NovaDesk GraphRAG CS Agent",
    description="Neo4j GraphRAG + LangGraph 智能客服 Agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.on_event("startup")
def on_startup() -> None:
    neo4j = get_neo4j()
    emb = EmbeddingService()
    if neo4j.verify():
        neo4j.init_schema(emb.dim)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    neo4j = get_neo4j()
    emb = EmbeddingService()
    ok = neo4j.verify()
    stats = neo4j.stats() if ok else {}
    return HealthResponse(
        status="ok" if ok else "degraded",
        neo4j="up" if ok else "down",
        llm="configured" if settings.llm_ready else "missing_key",
        embedding=emb.mode,
        stats=stats,
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接，请先 docker compose up -d")
    return get_agent().chat(req.message, session_id=req.session_id)


@app.post("/api/knowledge/ingest", response_model=IngestResponse)
def ingest_text(req: IngestTextRequest) -> IngestResponse:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    try:
        result = KnowledgeIngestor().ingest_document(
            title=req.title,
            content=req.content,
            source=req.source,
            category=req.category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IngestResponse(
        document_id=result.document_id,
        chunk_count=result.chunk_count,
        entity_count=result.entity_count,
        message="入库成功：已写入 Document/Chunk/Entity 并建立 MENTIONS/RELATED_TO 关系",
    )


@app.post("/api/knowledge/upload", response_model=IngestResponse)
async def ingest_upload(
    file: UploadFile = File(...),
    category: str = "upload",
) -> IngestResponse:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    raw = await file.read()
    name = file.filename or "upload.txt"
    if name.lower().endswith(".pdf"):
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw))
        content = "\n".join((page.extract_text() or "") for page in reader.pages)
    else:
        content = raw.decode("utf-8", errors="ignore")
    title = Path(name).stem
    result = KnowledgeIngestor().ingest_document(
        title=title,
        content=content,
        source=name,
        category=category,
    )
    return IngestResponse(
        document_id=result.document_id,
        chunk_count=result.chunk_count,
        entity_count=result.entity_count,
        message=f"文件 {name} 入库成功",
    )


@app.get("/api/knowledge/stats")
def knowledge_stats() -> dict:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    return neo4j.stats()


@app.get("/api/graph/entities")
def list_entities(limit: int = 50) -> list[dict]:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    return neo4j.run(
        """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[r:RELATED_TO]-(other:Entity)
        RETURN e.id AS id, e.name AS name, e.type AS type,
               count(DISTINCT other) AS degree
        ORDER BY degree DESC
        LIMIT $limit
        """,
        limit=limit,
    )


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="前端未构建")
    return FileResponse(index_path)
