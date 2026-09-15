from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
)
from app.rag.embeddings import EmbeddingService
from app.rag.eval_suite import load_cases, run_agent_eval, run_full_metrics, run_retrieval_eval
from app.rag.hybrid_retriever import HybridGraphRetriever
from app.rag.ingest import KnowledgeIngestor
from app.rag.neo4j_client import get_neo4j
from app.security import require_admin

settings = get_settings()
app = FastAPI(
    title="NovaDesk GraphRAG CS Agent",
    description="Neo4j GraphRAG + LangGraph 智能客服 Agent 中台",
    version="1.1.0",
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
