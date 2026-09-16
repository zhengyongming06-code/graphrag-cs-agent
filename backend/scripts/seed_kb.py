from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.rag.embeddings import EmbeddingService
from app.rag.ingest import KnowledgeIngestor
from app.rag.neo4j_client import Neo4jClient


def main() -> None:
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    if not neo4j.verify():
        raise SystemExit(
            f"无法连接 Neo4j: {settings.neo4j_uri}\n请先运行: docker compose up -d"
        )

    emb = EmbeddingService(settings)
    neo4j.init_schema(emb.dim)
    if "--reset" in sys.argv:
        neo4j.run("MATCH (d:Document) DETACH DELETE d")
        neo4j.run("MATCH (c:Chunk) DETACH DELETE c")
        neo4j.run("MATCH (e:Entity) DETACH DELETE e")
        print("[RESET] 已清空 Document / Chunk / Entity")
    ingestor = KnowledgeIngestor(neo4j, emb)

    kb_dir = ROOT / "data" / "knowledge"
    files = sorted(kb_dir.glob("*.md"))
    if not files:
        raise SystemExit(f"未找到知识库文件: {kb_dir}")

    total_chunks = 0
    total_entities = 0
    category_map = {
        "01_product_overview": "product",
        "02_login_permissions": "support",
        "03_billing_refund": "billing",
        "04_bot_sla": "sla",
    }
    for path in files:
        text = path.read_text(encoding="utf-8")
        title = path.stem
        result = ingestor.ingest_document(
            title=title,
            content=text,
            source=path.name,
            category=category_map.get(path.stem, "general"),
            document_id=path.stem,
        )
        total_chunks += result.chunk_count
        total_entities += result.entity_count
        print(
            f"[OK] {path.name} -> doc={result.document_id} "
            f"chunks={result.chunk_count} entities={result.entity_count}"
        )

    stats = neo4j.stats()
    print("\nNeo4j 统计:", stats)
    print(f"本次写入文件数={len(files)}, chunks={total_chunks}, entities≈{total_entities}")
    print("完成。可打开 http://localhost:7475 查看图谱。")


if __name__ == "__main__":
    main()
