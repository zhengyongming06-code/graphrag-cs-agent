from __future__ import annotations

import uuid
from typing import Any

from app.rag.hybrid_retriever import HybridGraphRetriever, RetrievedChunk
from app.rag.neo4j_client import get_neo4j


class AgentTools:
    def __init__(self, retriever: HybridGraphRetriever | None = None) -> None:
        self.retriever = retriever or HybridGraphRetriever()
        self.last_citations: list[dict[str, Any]] = []
        self.last_hits: list[RetrievedChunk] = []
        self.last_ticket_id: str = ""
        self.trace: list[str] = []

    def reset(self) -> None:
        self.last_citations = []
        self.last_hits = []
        self.last_ticket_id = ""
        self.trace = []

    def hybrid_search(self, query: str, top_k: int = 5) -> str:
        hits = self.retriever.retrieve(query, top_k=top_k)
        self.last_hits = hits
        self.trace.append(f"hybrid_search(q={query!r}, k={top_k}) -> {len(hits)} hits")
        if not hits:
            return "未检索到相关知识片段。"
        blocks: list[str] = []
        citations: list[dict[str, Any]] = []
        for i, hit in enumerate(hits, start=1):
            snippet = hit.text[:280].replace("\n", " ")
            blocks.append(
                f"[{i}] title={hit.title} source={hit.source} "
                f"channel={hit.channel} score={hit.score:.3f}\n{hit.text}"
            )
            citations.append(
                {
                    "chunk_id": hit.chunk_id,
                    "title": hit.title,
                    "score": round(hit.score, 4),
                    "snippet": snippet,
                    "source": hit.source,
                }
            )
        self.last_citations = citations
        return "\n\n".join(blocks)

    def entity_lookup(self, name: str) -> str:
        rows = self.retriever.entity_lookup(name)
        self.trace.append(f"entity_lookup(name={name!r}) -> {len(rows)} entities")
        if not rows:
            return f"知识图谱中未找到与「{name}」相关的实体。"
        lines = []
        for row in rows:
            related = ", ".join(
                f"{r.get('name')}({r.get('type')})"
                for r in (row.get("related") or [])
                if r.get("name")
            )
            lines.append(
                f"- {row.get('name')} [{row.get('type')}] related: {related or '无'}"
            )
        policies = self.retriever.policy_paths(name, limit=3)
        if policies:
            lines.append("关联片段：")
            for i, p in enumerate(policies, start=1):
                lines.append(f"  ({i}) {p.get('title')}: {(p.get('text') or '')[:180]}")
                self.last_citations.append(
                    {
                        "chunk_id": p.get("chunk_id") or f"policy-{i}",
                        "title": p.get("title") or "",
                        "score": 0.5,
                        "snippet": (p.get("text") or "")[:200],
                        "source": p.get("source") or "graph",
                    }
                )
        return "\n".join(lines)

    def create_ticket(
        self,
        subject: str,
        detail: str,
        priority: str = "normal",
        session_id: str = "",
        ticket_id: str | None = None,
    ) -> str:
        ticket_id = ticket_id or f"TKT-{uuid.uuid4().hex[:8].upper()}"
        self.last_ticket_id = ticket_id
        neo4j = get_neo4j()
        neo4j.run(
            """
            MERGE (t:Ticket {id: $id})
            SET t.subject = $subject,
                t.detail = $detail,
                t.priority = $priority,
                t.status = 'open',
                t.session_id = $session_id,
                t.created_at = datetime()
            """,
            id=ticket_id,
            subject=subject,
            detail=detail,
            priority=priority,
            session_id=session_id or "",
        )
        if session_id:
            neo4j.run(
                """
                MERGE (s:Session {id: $sid})
                ON CREATE SET s.created_at = datetime()
                SET s.updated_at = datetime()
                MERGE (t:Ticket {id: $id})
                MERGE (s)-[:HAS_TICKET]->(t)
                """,
                sid=session_id,
                id=ticket_id,
            )
        self.trace.append(f"create_ticket(id={ticket_id}, priority={priority})")
        return (
            f"已建工单 {ticket_id}（{priority}）。主题：{subject}。工作时间有人看。"
        )
