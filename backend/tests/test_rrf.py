from app.rag.hybrid_retriever import RetrievedChunk, reciprocal_rank_fusion


def _hit(chunk_id: str, channel: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        title=chunk_id,
        text=chunk_id,
        source="test",
        score=1.0,
        channel=channel,
    )


def test_rrf_promotes_overlap_across_channels():
    vector = [_hit("a", "vector"), _hit("b", "vector")]
    lexical = [_hit("a", "lexical"), _hit("c", "lexical")]
    fused = reciprocal_rank_fusion([vector, lexical])
    assert fused[0].chunk_id == "a"
    assert {h.chunk_id for h in fused} == {"a", "b", "c"}


def test_rrf_is_rank_based_not_raw_score():
    high = RetrievedChunk(
        chunk_id="only-vector",
        title="t",
        text="t",
        source="s",
        score=99.0,
        channel="vector",
    )
    both_v = RetrievedChunk(
        chunk_id="both",
        title="t",
        text="t",
        source="s",
        score=0.1,
        channel="vector",
    )
    both_l = RetrievedChunk(
        chunk_id="both",
        title="t",
        text="t",
        source="s",
        score=0.1,
        channel="lexical",
    )
    fused = reciprocal_rank_fusion([[both_v, high], [both_l]])
    assert fused[0].chunk_id == "both"
