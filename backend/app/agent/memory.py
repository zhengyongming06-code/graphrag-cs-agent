from __future__ import annotations

from app.config import get_settings
from app.rag.neo4j_client import Neo4jClient, get_neo4j


class SessionMemory:
    """Persist CS turns on the same Neo4j graph — no extra Redis for the demo."""

    def __init__(self, neo4j: Neo4jClient | None = None) -> None:
        self.neo4j = neo4j or get_neo4j()
        self.max_turns = get_settings().max_history_turns

    def load_text(self, session_id: str) -> str:
        rows = self.neo4j.run(
            """
            MATCH (s:Session {id: $sid})-[:HAS_TURN]->(t:Turn)
            RETURN t.role AS role, t.content AS content, t.created_at AS ts
            ORDER BY t.created_at DESC
            LIMIT $limit
            """,
            sid=session_id,
            limit=self.max_turns * 2,
        )
        if not rows:
            return ""
        lines = []
        for row in reversed(rows):
            role = "用户" if row.get("role") == "user" else "客服"
            content = (row.get("content") or "").replace("\n", " ")
            lines.append(f"{role}：{content[:400]}")
        return "\n".join(lines)

    def append(self, session_id: str, role: str, content: str, extra: dict | None = None) -> None:
        extra = extra or {}
        self.neo4j.run(
            """
            MERGE (s:Session {id: $sid})
            ON CREATE SET s.created_at = datetime()
            SET s.updated_at = datetime()
            CREATE (t:Turn {
                id: randomUUID(),
                role: $role,
                content: $content,
                intent: $intent,
                confidence: $confidence,
                created_at: datetime()
            })
            MERGE (s)-[:HAS_TURN]->(t)
            """,
            sid=session_id,
            role=role,
            content=content[:4000],
            intent=extra.get("intent") or "",
            confidence=float(extra.get("confidence") or 0.0),
        )
