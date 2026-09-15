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


RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]],
    rrf_k: int = RRF_K,
) -> list[RetrievedChunk]:
    """RRF: score = Σ 1 / (k + rank). Rank is 1-indexed. Score-scale independent."""
    bucket: dict[str, RetrievedChunk] = {}
    scores: dict[str, float] = {}
    channels: dict[str, set[str]] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            channels.setdefault(hit.chunk_id, set()).add(hit.channel.split("+")[0])
            if hit.chunk_id not in bucket:
                bucket[hit.chunk_id] = hit
            elif hit.entities and not bucket[hit.chunk_id].entities:
                bucket[hit.chunk_id].entities = hit.entities
    fused: list[RetrievedChunk] = []
    for cid, base in bucket.items():
        fused.append(
            RetrievedChunk(
                chunk_id=base.chunk_id,
                title=base.title,
                text=base.text,
                source=base.source,
                score=scores[cid],
                channel="+".join(sorted(channels[cid])),
                entities=base.entities,
            )
        )
    fused.sort(key=lambda x: x.score, reverse=True)
    return fused


class HybridGraphRetriever:
    """
    GraphRAG hybrid retrieval:
    1) Neo4j vector similarity on Chunk embeddings
    2) Lexical / keyword fallback over chunk text
    3) 1-hop graph expansion via shared MENTIONS entities
    Fusion: Reciprocal Rank Fusion (RRF, k=60)
    """

    def __init__(
        self,
        neo4j: Neo4jClient | None = None,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self.neo4j = neo4j or get_neo4j()
        self.embeddings = embeddings or EmbeddingService()

    def retrieve(self, query: str, top_k: int = 6) -> list[RetrievedChunk]:
        pool = max(top_k * 2, 8)
        vec_hits = self._vector_search(query, k=pool)
        lex_hits = self._lexical_search(query, k=pool)
        seed = reciprocal_rank_fusion([vec_hits, lex_hits])[:4]
        graph_hits = self._graph_neighbors(seed, query=query, limit=pool)
        fused = reciprocal_rank_fusion([vec_hits, lex_hits, graph_hits])
        return fused[:top_k]

    def retrieve_vector_only(self, query: str, top_k: int = 6) -> list[RetrievedChunk]:
        return self._vector_search(query, k=top_k)[:top_k]

    def compare(self, query: str, top_k: int = 5) -> dict:
        """A/B compare: pure vector vs hybrid GraphRAG."""
        vector_hits = self.retrieve_vector_only(query, top_k=top_k)
        hybrid_hits = self.retrieve(query, top_k=top_k)
        vec_ids = {h.chunk_id for h in vector_hits}
        hyb_ids = {h.chunk_id for h in hybrid_hits}
        only_hybrid = sorted(hyb_ids - vec_ids)
        only_vector = sorted(vec_ids - hyb_ids)
        return {
            "query": query,
            "top_k": top_k,
            "vector_only": [self._hit_dict(h) for h in vector_hits],
            "hybrid_graphrag": [self._hit_dict(h) for h in hybrid_hits],
            "overlap": len(vec_ids & hyb_ids),
            "only_in_hybrid": only_hybrid,
            "only_in_vector": only_vector,
            "fusion": "RRF(k=60)",
            "graph_hops": 1,
            "summary": (
                f"融合=RRF(k=60)，图扩展=1-hop MENTIONS；"
                f"hybrid 独有 {len(only_hybrid)} 条，重合 {len(vec_ids & hyb_ids)} 条。"
            ),
        }

    @staticmethod
    def _hit_dict(hit: RetrievedChunk) -> dict:
        return {
            "chunk_id": hit.chunk_id,
            "title": hit.title,
            "source": hit.source,
            "score": round(hit.score, 4),
            "channel": hit.channel,
            "snippet": hit.text[:220].replace("\n", " "),
            "entities": hit.entities[:6],
        }

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

    def _graph_neighbors(
        self, seeds: list[RetrievedChunk], query: str, limit: int
    ) -> list[RetrievedChunk]:
        """1-hop: seed -[:MENTIONS]-> Entity <-[:MENTIONS]- neighbor Chunk."""
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
            LIMIT $limit
            """,
            seed_ids=seed_ids,
            limit=limit,
        )
        hits: list[RetrievedChunk] = []
        for row in rows:
            text = row.get("text") or ""
            hits.append(
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    title=row.get("title") or "",
                    text=text,
                    source=row.get("source") or "",
                    score=float(row.get("shared") or 0) + lexical_score(query, text),
                    channel="graph-1hop",
                    entities=[e for e in (row.get("entities") or []) if e.get("name")],
                )
            )
        return hits
