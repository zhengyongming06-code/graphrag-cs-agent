from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

from app.rag.embeddings import EmbeddingService
from app.rag.neo4j_client import Neo4jClient, get_neo4j


@dataclass
class IngestResult:
    document_id: str
    chunk_count: int
    entity_count: int


# Lightweight rule-based entity extraction (no extra NLP deps; resume-friendly GraphRAG demo)
ENTITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Product", re.compile(r"\b(NovaDesk|NovaBot|NovaFlow|NovaInsight)\b", re.I)),
    ("Feature", re.compile(r"(工单|知识库|多渠道接入|SLA|智能路由|机器人|座席|质检|报表|Webhook|SSO|API)", re.I)),
    ("Policy", re.compile(r"(退款政策|数据保留|隐私政策|服务等级协议|SLA|计费规则|试用期)", re.I)),
    ("Plan", re.compile(r"(Free|Starter|Pro|Enterprise|免费版|专业版|企业版)", re.I)),
    ("Issue", re.compile(r"(登录失败|无法发送|同步延迟|超时|报错|权限不足|邮件收不到)", re.I)),
]


def chunk_text(text: str, chunk_size: int = 450, overlap: int = 80) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    # Prefer paragraph splits
    parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for part in parts:
        if len(buf) + len(part) + 1 <= chunk_size:
            buf = f"{buf}\n{part}".strip() if buf else part
            continue
        if buf:
            chunks.append(buf)
        if len(part) <= chunk_size:
            buf = part
        else:
            start = 0
            while start < len(part):
                end = min(len(part), start + chunk_size)
                chunks.append(part[start:end])
                if end >= len(part):
                    break
                start = max(0, end - overlap)
            buf = ""
    if buf:
        chunks.append(buf)
    # sliding overlap between consecutive chunks when paragraphs were large
    if len(chunks) == 1 and len(chunks[0]) > chunk_size:
        raw = chunks[0]
        chunks = []
        start = 0
        while start < len(raw):
            end = min(len(raw), start + chunk_size)
            chunks.append(raw[start:end])
            if end >= len(raw):
                break
            start = max(0, end - overlap)
    return chunks


def extract_entities(text: str) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for etype, pattern in ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(0).strip()
            key = f"{etype}:{name.lower()}"
            if key not in found:
                eid = hashlib.md5(key.encode("utf-8")).hexdigest()[:16]
                found[key] = {"id": eid, "name": name, "type": etype}
    return list(found.values())


class KnowledgeIngestor:
    def __init__(
        self,
        neo4j: Neo4jClient | None = None,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self.neo4j = neo4j or get_neo4j()
        self.embeddings = embeddings or EmbeddingService()

    def ingest_document(
        self,
        title: str,
        content: str,
        source: str = "manual",
        category: str = "general",
        document_id: str | None = None,
    ) -> IngestResult:
        doc_id = document_id or str(uuid.uuid4())
        chunks = chunk_text(content)
        if not chunks:
            raise ValueError("文档内容为空，无法入库")

        vectors = self.embeddings.embed_texts(chunks)
        entities_all = extract_entities(content)

        # Upsert document
        self.neo4j.run(
            """
            MERGE (d:Document {id: $id})
            SET d.title = $title,
                d.source = $source,
                d.category = $category,
                d.updated_at = datetime()
            """,
            id=doc_id,
            title=title,
            source=source,
            category=category,
        )

        for idx, (chunk, emb) in enumerate(zip(chunks, vectors)):
            chunk_id = f"{doc_id}:{idx}"
            chunk_entities = extract_entities(chunk)
            self.neo4j.run(
                """
                MATCH (d:Document {id: $doc_id})
                MERGE (c:Chunk {id: $chunk_id})
                SET c.text = $text,
                    c.title = $title,
                    c.source = $source,
                    c.category = $category,
                    c.index = $index,
                    c.embedding = $embedding
                MERGE (d)-[:HAS_CHUNK]->(c)
                """,
                doc_id=doc_id,
                chunk_id=chunk_id,
                text=chunk,
                title=title,
                source=source,
                category=category,
                index=idx,
                embedding=emb,
            )
            for ent in chunk_entities:
                self.neo4j.run(
                    """
                    MATCH (c:Chunk {id: $chunk_id})
                    MERGE (e:Entity {id: $eid})
                    SET e.name = $name, e.type = $type
                    MERGE (c)-[:MENTIONS]->(e)
                    """,
                    chunk_id=chunk_id,
                    eid=ent["id"],
                    name=ent["name"],
                    type=ent["type"],
                )

        # Relate co-occurring entities within the document
        for i, a in enumerate(entities_all):
            for b in entities_all[i + 1 :]:
                self.neo4j.run(
                    """
                    MATCH (a:Entity {id: $a}), (b:Entity {id: $b})
                    MERGE (a)-[r:RELATED_TO]->(b)
                    ON CREATE SET r.weight = 1
                    ON MATCH SET r.weight = coalesce(r.weight, 0) + 1
                    """,
                    a=a["id"],
                    b=b["id"],
                )

        return IngestResult(
            document_id=doc_id,
            chunk_count=len(chunks),
            entity_count=len(entities_all),
        )
