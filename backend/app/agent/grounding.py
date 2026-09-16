from __future__ import annotations

from app.config import get_settings
from app.rag.embeddings import lexical_score
from app.rag.hybrid_retriever import RetrievedChunk


def evidence_confidence(question: str, hits: list[RetrievedChunk]) -> tuple[float, bool]:
    """
    Cheap, explainable gate for CS:
    - lexical overlap with top chunks
    - how many fused hits we actually got
    Not a model judge. Interview: 这是规则门控，不是 NLI。
    """
    settings = get_settings()
    if not hits:
        return 0.0, False
    lex = max(lexical_score(question, f"{h.title}\n{h.text}") for h in hits)
    coverage = min(len(hits) / 4.0, 1.0)
    graph_bonus = 0.08 if any("graph" in (h.channel or "") for h in hits) else 0.0
    confidence = round(min(1.0, 0.62 * lex + 0.30 * coverage + graph_bonus), 4)
    grounded = confidence >= settings.confidence_threshold or (lex >= 0.18 and len(hits) >= 2)
    return confidence, grounded


def should_escalate(intent: str, grounded: bool, question: str) -> bool:
    if intent == "escalate":
        return True
    if intent == "chitchat":
        return False
    if intent == "policy" and not grounded:
        return True
    q = question or ""
    if any(k in q for k in ("投诉", "律师", "法务")):
        return True
    return False
