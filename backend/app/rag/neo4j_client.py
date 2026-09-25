from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from neo4j import GraphDatabase, Driver

from app.config import Settings, get_settings


class Neo4jClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._driver: Driver | None = None

    def connect(self) -> None:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self.connect()
        assert self._driver is not None
        return self._driver

    def verify(self) -> bool:
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    @contextmanager
    def session(self) -> Iterator[Any]:
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()

    def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        with self.session() as session:
            result = session.run(query, **params)
            return [record.data() for record in result]

    def init_schema(self, embedding_dim: int) -> None:
        statements = [
            "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT ticket_id IF NOT EXISTS FOR (t:Ticket) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX chunk_source IF NOT EXISTS FOR (c:Chunk) ON (c.source)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX ticket_status IF NOT EXISTS FOR (t:Ticket) ON (t.status)",
        ]
        for stmt in statements:
            self.run(stmt)

        # Vector index (Neo4j 5.x). Drop/recreate if dim mismatch is too risky; create if missing.
        existing = self.run(
            """
            SHOW INDEXES YIELD name, type
            WHERE name = 'chunk_embedding_index'
            RETURN name, type
            """
        )
        if not existing:
            self.run(
                f"""
                CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {{
                  indexConfig: {{
                    `vector.dimensions`: {int(embedding_dim)},
                    `vector.similarity_function`: 'cosine'
                  }}
                }}
                """
            )

    def stats(self) -> dict[str, int]:
        rows = self.run(
            """
            OPTIONAL MATCH (d:Document) WITH count(d) AS documents
            OPTIONAL MATCH (c:Chunk) WITH documents, count(c) AS chunks
            OPTIONAL MATCH (e:Entity) WITH documents, chunks, count(e) AS entities
            OPTIONAL MATCH ()-[r]->() WITH documents, chunks, entities, count(r) AS relations
            RETURN documents, chunks, entities, relations
            """
        )
        if not rows:
            return {"documents": 0, "chunks": 0, "entities": 0, "relations": 0}
        return {k: int(v or 0) for k, v in rows[0].items()}

    def category_stats(self) -> list[dict]:
        return self.run(
            """
            MATCH (d:Document)
            RETURN coalesce(d.category, 'general') AS category,
                   count(d) AS documents
            ORDER BY documents DESC
            """
        )

    def list_documents(self, category: str | None = None, limit: int = 50) -> list[dict]:
        if category:
            return self.run(
                """
                MATCH (d:Document)
                WHERE coalesce(d.category, 'general') = $category
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                RETURN d.id AS id, d.title AS title, d.source AS source,
                       coalesce(d.category, 'general') AS category,
                       count(c) AS chunks
                ORDER BY d.title
                LIMIT $limit
                """,
                category=category,
                limit=limit,
            )
        return self.run(
            """
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            RETURN d.id AS id, d.title AS title, d.source AS source,
                   coalesce(d.category, 'general') AS category,
                   count(c) AS chunks
            ORDER BY category, d.title
            LIMIT $limit
            """,
            limit=limit,
        )

    def delete_document(self, document_id: str) -> bool:
        """Remove a Document, its Chunks, and Entity nodes that nothing else mentions."""
        existed = self.run(
            """
            MATCH (d:Document {id: $id})
            RETURN d.id AS id
            """,
            id=document_id,
        )
        if not existed:
            return False
        self.run(
            """
            MATCH (d:Document {id: $id})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)
            WITH d, collect(DISTINCT c) AS chunks, collect(DISTINCT e) AS ents
            FOREACH (c IN chunks | DETACH DELETE c)
            DETACH DELETE d
            WITH ents
            UNWIND ents AS e
            WITH e
            WHERE e IS NOT NULL AND NOT (e)<-[:MENTIONS]-()
            DETACH DELETE e
            """,
            id=document_id,
        )
        return True

    def list_sessions(self, limit: int = 50) -> list[dict]:
        return self.run(
            """
            MATCH (s:Session)
            OPTIONAL MATCH (s)-[:HAS_TURN]->(t:Turn)
            RETURN s.id AS session_id,
                   toString(s.created_at) AS created_at,
                   toString(s.updated_at) AS updated_at,
                   count(t) AS turn_count
            ORDER BY s.updated_at DESC
            LIMIT $limit
            """,
            limit=limit,
        )

    def get_session(self, session_id: str) -> dict | None:
        heads = self.run(
            """
            MATCH (s:Session {id: $sid})
            RETURN s.id AS session_id,
                   toString(s.created_at) AS created_at,
                   toString(s.updated_at) AS updated_at
            """,
            sid=session_id,
        )
        if not heads:
            return None
        turns = self.run(
            """
            MATCH (s:Session {id: $sid})-[:HAS_TURN]->(t:Turn)
            RETURN t.role AS role,
                   t.content AS content,
                   coalesce(t.intent, '') AS intent,
                   coalesce(t.confidence, 0.0) AS confidence,
                   toString(t.created_at) AS created_at
            ORDER BY t.created_at ASC
            """,
            sid=session_id,
        )
        return {**heads[0], "turns": turns}

    def list_tickets(self, status: str | None = None, limit: int = 30) -> list[dict]:
        if status:
            return self.run(
                """
                MATCH (t:Ticket)
                WHERE t.status = $status
                RETURN t.id AS id, t.subject AS subject, t.detail AS detail,
                       t.priority AS priority, t.status AS status,
                       coalesce(t.session_id, '') AS session_id,
                       toString(t.created_at) AS created_at
                ORDER BY t.created_at DESC
                LIMIT $limit
                """,
                status=status,
                limit=limit,
            )
        return self.run(
            """
            MATCH (t:Ticket)
            RETURN t.id AS id, t.subject AS subject, t.detail AS detail,
                   t.priority AS priority, t.status AS status,
                   coalesce(t.session_id, '') AS session_id,
                   toString(t.created_at) AS created_at
            ORDER BY t.created_at DESC
            LIMIT $limit
            """,
            limit=limit,
        )

    def update_ticket(self, ticket_id: str, status: str) -> dict | None:
        rows = self.run(
            """
            MATCH (t:Ticket {id: $id})
            SET t.status = $status, t.updated_at = datetime()
            RETURN t.id AS id, t.subject AS subject, t.status AS status,
                   t.priority AS priority, t.detail AS detail,
                   toString(t.created_at) AS created_at
            """,
            id=ticket_id,
            status=status,
        )
        return rows[0] if rows else None

    def subgraph(self, limit: int = 40) -> dict:
        nodes = self.run(
            """
            MATCH (e:Entity)
            OPTIONAL MATCH (e)-[:RELATED_TO]-(other:Entity)
            RETURN e.id AS id, e.name AS name, e.type AS type,
                   count(DISTINCT other) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            """,
            limit=limit,
        )
        ids = [n["id"] for n in nodes]
        edges = []
        if ids:
            edges = self.run(
                """
                MATCH (a:Entity)-[r:RELATED_TO]-(b:Entity)
                WHERE a.id IN $ids AND b.id IN $ids AND a.id < b.id
                RETURN a.id AS source, b.id AS target,
                       sum(coalesce(r.weight, 1)) AS weight
                """,
                ids=ids,
            )
        return {"nodes": nodes, "edges": edges}


_neo4j: Neo4jClient | None = None


def get_neo4j() -> Neo4jClient:
    global _neo4j
    if _neo4j is None:
        _neo4j = Neo4jClient()
        _neo4j.connect()
    return _neo4j
