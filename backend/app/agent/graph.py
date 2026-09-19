from __future__ import annotations

from typing import Any, Iterator, TypedDict

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.agent.grounding import evidence_confidence, should_escalate
from app.agent.memory import SessionMemory
from app.agent.prompts import ANSWER_PROMPT, SYSTEM_PROMPT
from app.agent.router import classify_intent
from app.agent.tools import AgentTools
from app.config import get_settings
from app.models.schemas import ChatResponse, Citation, PipelineStep
from app.rag.hybrid_retriever import RetrievedChunk


class CSState(TypedDict, total=False):
    question: str
    session_id: str
    history: str
    intent: str
    intent_source: str
    evidence: str
    confidence: float
    grounded: bool
    should_escalate: bool
    citations: list[dict[str, Any]]
    tool_trace: list[str]
    pipeline: list[dict[str, Any]]
    answer: str
    ticket_id: str
    mode: str


class CustomerServiceAgent:
    """客服 SOP 状态机：memory → route → retrieve → ground → act → persist。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.tools_impl = AgentTools()
        self.memory = SessionMemory()
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(CSState)
        graph.add_node("memory", self._node_memory)
        graph.add_node("route", self._node_route)
        graph.add_node("retrieve", self._node_retrieve)
        graph.add_node("ground", self._node_ground)
        graph.add_node("act", self._node_act)
        graph.add_node("persist", self._node_persist)
        graph.add_edge(START, "memory")
        graph.add_edge("memory", "route")
        graph.add_conditional_edges(
            "route",
            lambda s: "act" if s.get("intent") == "chitchat" else "retrieve",
            {"act": "act", "retrieve": "retrieve"},
        )
        graph.add_edge("retrieve", "ground")
        graph.add_edge("ground", "act")
        graph.add_edge("act", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _node_memory(self, state: CSState) -> dict:
        history = self.memory.load_text(state["session_id"])
        return {
            "history": history,
            "pipeline": [
                {
                    "step": "memory",
                    "detail": "载入多轮会话" if history else "新会话",
                    "ok": True,
                }
            ],
            "tool_trace": [],
            "citations": [],
        }

    def _node_route(self, state: CSState) -> dict:
        intent, source = classify_intent(state["question"])
        pipeline = list(state.get("pipeline") or [])
        pipeline.append({"step": "route", "detail": f"intent={intent} source={source}", "ok": True})
        return {
            "intent": intent,
            "intent_source": source,
            "pipeline": pipeline,
            "tool_trace": list(state.get("tool_trace") or []) + [f"route({intent}/{source})"],
        }

    def _node_retrieve(self, state: CSState) -> dict:
        self.tools_impl.reset()
        question = state["question"]
        intent = state.get("intent") or "faq"
        parts: list[str] = [self.tools_impl.hybrid_search(question, top_k=5)]
        if intent == "entity":
            parts.append(self.tools_impl.entity_lookup(self._entity_query(question)))
        pipeline = list(state.get("pipeline") or [])
        pipeline.append(
            {
                "step": "retrieve",
                "detail": f"GraphRAG hits={len(self.tools_impl.last_citations)}",
                "ok": bool(self.tools_impl.last_citations),
            }
        )
        return {
            "evidence": "\n\n".join(p for p in parts if p),
            "citations": list(self.tools_impl.last_citations),
            "tool_trace": list(state.get("tool_trace") or []) + list(self.tools_impl.trace),
            "pipeline": pipeline,
        }

    def _node_ground(self, state: CSState) -> dict:
        hits = self.tools_impl.last_hits or [
            RetrievedChunk(
                chunk_id=c.get("chunk_id") or "",
                title=c.get("title") or "",
                text=c.get("snippet") or "",
                source=c.get("source") or "",
                score=float(c.get("score") or 0),
                channel="fused",
            )
            for c in (state.get("citations") or [])
        ]
        confidence, grounded = evidence_confidence(state["question"], hits)
        escalate = should_escalate(state.get("intent") or "faq", grounded, state["question"])
        pipeline = list(state.get("pipeline") or [])
        pipeline.append(
            {
                "step": "ground",
                "detail": f"confidence={confidence:.2f} grounded={grounded} escalate={escalate}",
                "ok": grounded or escalate,
            }
        )
        return {
            "confidence": confidence,
            "grounded": grounded,
            "should_escalate": escalate,
            "pipeline": pipeline,
            "tool_trace": list(state.get("tool_trace") or [])
            + [f"ground(conf={confidence:.2f}, grounded={grounded})"],
        }

    def _node_act(self, state: CSState) -> dict:
        intent = state.get("intent") or "faq"
        ticket_id = ""
        if state.get("should_escalate") or intent == "escalate":
            ticket = self.tools_impl.create_ticket(
                subject=state["question"][:80],
                detail=state["question"],
                priority="high" if intent == "escalate" else "normal",
            )
            ticket_id = self.tools_impl.last_ticket_id
            answer = self._compose_escalation(state, ticket)
            mode = "escalate"
        elif intent == "chitchat":
            answer = "在。问产品、登录、退款、SLA 都可以。搞不定就说转人工。"
            mode = "chitchat"
        else:
            answer, mode = self._generate_answer(state)
        pipeline = list(state.get("pipeline") or [])
        pipeline.append({"step": "act", "detail": mode, "ok": bool(answer)})
        return {
            "answer": answer,
            "ticket_id": ticket_id,
            "mode": mode,
            "pipeline": pipeline,
            "tool_trace": list(state.get("tool_trace") or []) + list(self.tools_impl.trace),
            "citations": list(self.tools_impl.last_citations or state.get("citations") or []),
        }

    def _node_persist(self, state: CSState) -> dict:
        sid = state["session_id"]
        extra = {"intent": state.get("intent") or "", "confidence": state.get("confidence") or 0.0}
        self.memory.append(sid, "user", state["question"], extra)
        self.memory.append(sid, "assistant", state.get("answer") or "", extra)
        pipeline = list(state.get("pipeline") or [])
        pipeline.append({"step": "persist", "detail": f"session={sid}", "ok": True})
        return {"pipeline": pipeline}

    def _generate_answer(self, state: CSState) -> tuple[str, str]:
        if not self.settings.llm_ready:
            return self._offline_answer(state), "offline-rag"
        user = ANSWER_PROMPT.format(
            history=state.get("history") or "（无）",
            intent=state.get("intent") or "faq",
            confidence=f"{float(state.get('confidence') or 0):.2f}",
            grounded="是" if state.get("grounded") else "否",
            question=state["question"],
            evidence=(state.get("evidence") or "（无检索命中）")[:6000],
        )
        try:
            llm = ChatOpenAI(
                model=self.settings.llm_model,
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
                temperature=0.2,
                timeout=25,
                http_client=httpx.Client(trust_env=False, timeout=25.0),
            )
            msg = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user)])
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            return (text.strip() or self._offline_answer(state)), "langgraph-cs"
        except Exception:
            return self._offline_answer(state), "offline-rag"

    def _offline_answer(self, state: CSState) -> str:
        cites = state.get("citations") or []
        if not cites:
            return "知识库没搜到。换个问法，或者说转人工。"
        lines = []
        for i, c in enumerate(cites[:4], start=1):
            title = (c.get("title") or "").strip()
            snippet = (c.get("snippet") or "").strip().replace("\n", " ")
            lines.append(f"[{i}] {title} {snippet[:180]}")
        low = "" if state.get("grounded") else "\n（检索把握偏低，仅供参考。）"
        return "根据知识库：\n\n" + "\n".join(lines) + low

    def _compose_escalation(self, state: CSState, ticket_text: str) -> str:
        conf = float(state.get("confidence") or 0.0)
        extra = "\n材料里有一点相关内容，一并留在工单里。" if state.get("citations") else ""
        return (
            f"这个我先记工单，不在这儿硬答。{ticket_text}{extra}\n"
            f"（检索把握 {conf:.2f}）把注册邮箱留一下就行，工作时间有人看。"
        )

    @staticmethod
    def _entity_query(question: str) -> str:
        for name in ("NovaInsight", "NovaFlow", "NovaBot", "NovaDesk", "SSO"):
            if name.lower() in question.lower() or name in question:
                return name
        return question[:24]

    def _to_response(self, out: CSState, session_id: str) -> ChatResponse:
        citations = [Citation(**c) for c in (out.get("citations") or []) if c.get("chunk_id")]
        steps = [PipelineStep(**s) for s in (out.get("pipeline") or []) if s.get("step")]
        return ChatResponse(
            answer=out.get("answer") or "暂时无法生成回答。",
            citations=citations,
            tool_trace=list(out.get("tool_trace") or []),
            session_id=session_id,
            mode=out.get("mode") or "langgraph-cs",
            intent=out.get("intent") or "",
            confidence=float(out.get("confidence") or 0.0),
            grounded=bool(out.get("grounded")),
            ticket_id=out.get("ticket_id") or "",
            pipeline=steps,
        )

    def chat(self, message: str, session_id: str = "default") -> ChatResponse:
        self.tools_impl.reset()
        try:
            out = self._graph.invoke({"question": message, "session_id": session_id or "default"})
        except Exception:
            out = {"question": message, "session_id": session_id, "answer": "知识库在，回答链路中断了。换个问法或说转人工。", "mode": "offline-rag"}
        return self._to_response(out, session_id)

    def iter_events(self, message: str, session_id: str = "default") -> Iterator[dict[str, Any]]:
        self.tools_impl.reset()
        init: CSState = {"question": message, "session_id": session_id or "default"}
        merged: CSState = dict(init)
        try:
            for event in self._graph.stream(init, stream_mode="updates"):
                for node, payload in event.items():
                    merged.update(payload)
                    last = (payload.get("pipeline") or [{"step": node, "detail": node, "ok": True}])[-1]
                    yield {"type": node, **last}
            resp = self._to_response(merged, session_id)
            yield {"type": "final", "response": resp.model_dump()}
        except Exception:
            merged["answer"] = merged.get("answer") or self._offline_answer(merged)
            merged["mode"] = merged.get("mode") or "offline-rag"
            yield {"type": "final", "response": self._to_response(merged, session_id).model_dump()}


_agent: CustomerServiceAgent | None = None


def get_agent() -> CustomerServiceAgent:
    global _agent
    if _agent is None:
        _agent = CustomerServiceAgent()
    return _agent
