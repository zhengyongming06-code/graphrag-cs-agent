from __future__ import annotations

from dataclasses import dataclass, field

from app.rag.embeddings import EmbeddingService, lexical_score
from app.rag.neo4j_client import Neo4jClient, get_neo4j


@dataclass
class RetrievedChunk:
    chunk_id: str
    title: str
    text: str
    source: str
    score: float
    channel: str
    entities: list[dict] = field(default_factory=list)


class HybridGraphRetriever:
    """
    GraphRAG hybrid retrieval:
    1) Neo4j vector similarity on Chunk embeddings
    2) Lexical / keyword fallback over chunk text
    3) Graph expansion via MENTIONS / RELATED_TO neighbors
    """

    def __init__(
        self,
        neo4j: Neo4jClient | None = None,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self.neo4j = neo4j or get_neo4j()
        self.embeddings = embeddings or EmbeddingService()

    def retrieve(self, query: str, top_k: int = 6) -> list[RetrievedChunk]:
        vec_hits = self._vector_search(query, k=top_k)
        lex_hits = self._lexical_search(query, k=top_k)
        merged = self._merge(vec_hits + lex_hits)
        expanded = self._graph_expand(merged, query=query, limit=top_k)
        return expanded[:top_k]

    def entity_lookup(self, name: str, limit: int = 8) -> list[dict]:
        rows = self.neo4j.run(
            """
            MATCH (e:Entity)
            WHERE toLower(e.name) CONTAINS toLower($name)
            OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e)
            OPTIONAL MATCH (e)-[:RELATED_TO]-(other:Entity)
            RETURN e.id AS id, e.name AS name, e.type AS type,
                   collect(DISTINCT c.id)[0..5] AS chunk_ids,
                   collect(DISTINCT {name: other.name, type: other.type})[0..8] AS related
            LIMIT $limit
            """,
            name=name,
            limit=limit,
        )
        return rows

    def policy_paths(self, topic: str, limit: int = 5) -> list[dict]:
        rows = self.neo4j.run(
            """
            MATCH (e:Entity)
            WHERE toLower(e.name) CONTAINS toLower($topic)
               OR toLower(e.type) CONTAINS 'policy'
            MATCH (c:Chunk)-[:MENTIONS]->(e)
            RETURN e.name AS entity, e.type AS type, c.id AS chunk_id,
                   c.title AS title, c.text AS text, c.source AS source
            LIMIT $limit
            """,
            topic=topic,
            limit=limit,
        )
        return rows

    def _vector_search(self, query: str, k: int) -> list[RetrievedChunk]:
        emb = self.embeddings.embed_query(query)
        try:
            rows = self.neo4j.run(
                """
                CALL db.index.vector.queryNodes('chunk_embedding_index', $k, $embedding)
                YIELD node, score
                OPTIONAL MATCH (node)-[:MENTIONS]->(e:Entity)
                RETURN node.id AS chunk_id, node.title AS title, node.text AS text,
                       node.source AS source, score AS score,
                       collect({name: e.name, type: e.type}) AS entities
                """,
                k=k,
                embedding=emb,
            )
        except Exception:
            # Fallback: brute-force cosine in Cypher-less Python if vector index unavailable
            return self._bruteforce_vector(query, emb, k)

        hits: list[RetrievedChunk] = []
        for row in rows:
            hits.append(
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    title=row.get("title") or "",
                    text=row.get("text") or "",
                    source=row.get("source") or "",
                    score=float(row.get("score") or 0.0),
                    channel="vector",
                    entities=[e for e in (row.get("entities") or []) if e.get("name")],
                )
            )
        return hits

    def _bruteforce_vector(self, query: str, emb: list[float], k: int) -> list[RetrievedChunk]:
        rows = self.neo4j.run(
            """
            MATCH (c:Chunk)
            WHERE c.embedding IS NOT NULL
            RETURN c.id AS chunk_id, c.title AS title, c.text AS text,
                   c.source AS source, c.embedding AS embedding
            LIMIT 500
            """
        )
        scored: list[RetrievedChunk] = []
        import numpy as np

        q = np.array(emb, dtype=np.float64)
        qn = np.linalg.norm(q) or 1.0
        for row in rows:
            v = np.array(row["embedding"], dtype=np.float64)
            vn = np.linalg.norm(v) or 1.0
            score = float(np.dot(q, v) / (qn * vn))
            scored.append(
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    title=row.get("title") or "",
                    text=row.get("text") or "",
                    source=row.get("source") or "",
                    score=score,
                    channel="vector-bf",
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:k]

    def _lexical_search(self, query: str, k: int) -> list[RetrievedChunk]:
        rows = self.neo4j.run(
            """
            MATCH (c:Chunk)
            RETURN c.id AS chunk_id, c.title AS title, c.text AS text, c.source AS source
            LIMIT 400
            """
        )
        scored: list[RetrievedChunk] = []
        for row in rows:
            text = f"{row.get('title') or ''}\n{row.get('text') or ''}"
            score = lexical_score(query, text)
            if score <= 0:
                continue
            scored.append(
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    title=row.get("title") or "",
                    text=row.get("text") or "",
                    source=row.get("source") or "",
                    score=score,
                    channel="lexical",
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:k]

    def _merge(self, hits: list[RetrievedChunk]) -> list[RetrievedChunk]:
        bucket: dict[str, RetrievedChunk] = {}
        for hit in hits:
            if hit.chunk_id not in bucket:
                bucket[hit.chunk_id] = hit
                continue
            cur = bucket[hit.chunk_id]
            # Weighted fusion
            fused = 0.65 * max(cur.score, hit.score) + 0.35 * min(cur.score, hit.score)
            channel = f"{cur.channel}+{hit.channel}"
            entities = cur.entities or hit.entities
            bucket[hit.chunk_id] = RetrievedChunk(
                chunk_id=cur.chunk_id,
                title=cur.title,
                text=cur.text,
                source=cur.source,
                score=fused,
                channel=channel,
                entities=entities,
            )
        return sorted(bucket.values(), key=lambda x: x.score, reverse=True)

    def _graph_expand(
        self, seeds: list[RetrievedChunk], query: str, limit: int
    ) -> list[RetrievedChunk]:
        if not seeds:
            return []
        seed_ids = [s.chunk_id for s in seeds[:4]]
        rows = self.neo4j.run(
            """
            MATCH (seed:Chunk)-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(nbr:Chunk)
            WHERE seed.id IN $seed_ids AND NOT nbr.id IN $seed_ids
            WITH nbr, count(*) AS shared
            OPTIONAL MATCH (nbr)-[:MENTIONS]->(ent:Entity)
            RETURN nbr.id AS chunk_id, nbr.title AS title, nbr.text AS text,
                   nbr.source AS source, shared,
                   collect({name: ent.name, type: ent.type}) AS entities
            ORDER BY shared DESC
            LIMIT 8
            """,
            seed_ids=seed_ids,
        )
        expanded = list(seeds)
        seen = {s.chunk_id for s in seeds}
        for row in rows:
            cid = row["chunk_id"]
            if cid in seen:
                continue
            text = row.get("text") or ""
            score = 0.25 * float(row.get("shared") or 1) + 0.4 * lexical_score(query, text)
            expanded.append(
                RetrievedChunk(
                    chunk_id=cid,
                    title=row.get("title") or "",
                    text=text,
                    source=row.get("source") or "",
                    score=score,
                    channel="graph",
                    entities=[e for e in (row.get("entities") or []) if e.get("name")],
                )
            )
            seen.add(cid)
        expanded.sort(key=lambda x: x.score, reverse=True)
        return expanded[:limit]
