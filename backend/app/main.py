from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.agent.graph import get_agent
from app.config import get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    CompareRequest,
    EvalRequest,
    HealthResponse,
    IngestResponse,
    IngestTextRequest,
    TicketPatch,
)
from app.rag.embeddings import EmbeddingService
from app.rag.eval_suite import load_cases, run_agent_eval, run_full_metrics, run_retrieval_eval
from app.rag.hybrid_retriever import HybridGraphRetriever
from app.rag.ingest import KnowledgeIngestor
from app.rag.neo4j_client import get_neo4j
from app.security import require_admin

settings = get_settings()
app = FastAPI(
    title="知识库客服",
    description="RAG / GraphRAG 知识库问答",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SPA_DIR = REPO_ROOT / "frontend" / "dist"
LEGACY_STATIC = Path(__file__).resolve().parent.parent / "static"
# Prefer Vite build (frontend/dist) when present; otherwise legacy HTML.
STATIC_DIR = SPA_DIR if (SPA_DIR / "index.html").exists() else LEGACY_STATIC
ASSETS_DIR = STATIC_DIR / "assets" if STATIC_DIR == SPA_DIR else STATIC_DIR
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


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
    categories = neo4j.category_stats() if ok else []
    return HealthResponse(
        status="ok" if ok else "degraded",
        neo4j="up" if ok else "down",
        llm="configured" if settings.llm_ready else "missing_key",
        embedding=emb.mode,
        stats=stats,
        categories=categories,
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接，请先 docker compose up -d")
    return get_agent().chat(req.message, session_id=req.session_id)


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接，请先 docker compose up -d")

    def event_gen():
        for event in get_agent().iter_events(req.message, session_id=req.session_id):
            payload = json.dumps(event, ensure_ascii=False)
            yield f"event: {event.get('type', 'message')}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/retrieve/compare")
def compare_retrieval(req: CompareRequest) -> dict:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    return HybridGraphRetriever().compare(req.query, top_k=req.top_k)


@app.get("/api/knowledge/categories")
def knowledge_categories() -> list[dict]:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    return neo4j.category_stats()


@app.get("/api/knowledge/documents")
def knowledge_documents(category: str | None = None, limit: int = 50) -> list[dict]:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    return neo4j.list_documents(category=category, limit=limit)


@app.post("/api/knowledge/ingest", response_model=IngestResponse)
def ingest_text(
    req: IngestTextRequest,
    _: None = Depends(require_admin),
) -> IngestResponse:
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
    _: None = Depends(require_admin),
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
    return {
        **neo4j.stats(),
        "categories": neo4j.category_stats(),
    }


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


@app.get("/api/graph/subgraph")
def graph_subgraph(limit: int = 36) -> dict:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    return neo4j.subgraph(limit=limit)


@app.get("/api/tickets")
def list_tickets(status: str | None = None, limit: int = 30) -> list[dict]:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    return neo4j.list_tickets(status=status, limit=limit)


@app.patch("/api/tickets/{ticket_id}")
def patch_ticket(ticket_id: str, req: TicketPatch, _: None = Depends(require_admin)) -> dict:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    row = neo4j.update_ticket(ticket_id, req.status)
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    return row


@app.get("/api/eval/cases")
def eval_cases() -> list[dict]:
    return load_cases()


@app.post("/api/eval/run")
def eval_run(
    req: EvalRequest,
    _: None = Depends(require_admin),
) -> dict:
    neo4j = get_neo4j()
    if not neo4j.verify():
        raise HTTPException(status_code=503, detail="Neo4j 未连接")
    mode = (req.mode or "agent").lower()
    out: dict = {"mode": mode}
    if mode in {"metrics", "full"}:
        return run_full_metrics()
    if mode in {"agent", "both"}:
        out["agent"] = run_agent_eval(get_agent())
    if mode in {"retrieval", "both"}:
        out["retrieval"] = run_retrieval_eval()
    return out


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="前端未构建")
    return FileResponse(index_path)
