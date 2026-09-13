from __future__ import annotations

import json
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.prompts import ANSWER_PROMPT, SYSTEM_PROMPT
from app.agent.tools import AgentTools
from app.config import get_settings
from app.models.schemas import Citation, ChatResponse


class AgentState(TypedDict, total=False):
    messages: list
    question: str
    session_id: str


class CustomerServiceAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.tools_impl = AgentTools()
        self._graph = None
        self._build_graph()

    def _build_graph(self) -> None:
        tools_impl = self.tools_impl

        @tool
        def hybrid_search(query: str) -> str:
            """在 Neo4j GraphRAG 知识库中做向量+关键词+图谱扩展的混合检索。"""
            return tools_impl.hybrid_search(query)

        @tool
        def entity_lookup(name: str) -> str:
            """在 Neo4j 知识图谱中查找实体及其关联关系/政策片段。"""
            return tools_impl.entity_lookup(name)

        @tool
        def create_ticket(subject: str, detail: str, priority: str = "normal") -> str:
            """当无法解答或用户要求人工时，创建客服工单。"""
            return tools_impl.create_ticket(subject, detail, priority)

        self._lc_tools = [hybrid_search, entity_lookup, create_ticket]
        self._tool_node = ToolNode(self._lc_tools)

        def call_model(state: AgentState) -> dict:
            llm = self._make_llm().bind_tools(self._lc_tools)
            response = llm.invoke(state["messages"])
            return {"messages": state["messages"] + [response]}

        def should_continue(state: AgentState) -> str:
            last = state["messages"][-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                return "tools"
            return END

        def run_tools(state: AgentState) -> dict:
            result = self._tool_node.invoke({"messages": state["messages"]})
            # ToolNode returns updated messages list
            return {"messages": result["messages"]}

        graph = StateGraph(AgentState)
        graph.add_node("agent", call_model)
        graph.add_node("tools", run_tools)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")
        self._graph = graph.compile()

    def _make_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            temperature=0.2,
        )

    def chat(self, message: str, session_id: str = "default") -> ChatResponse:
        self.tools_impl.reset()
        if not self.settings.llm_ready:
            return self._offline_rag_answer(message, session_id)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=message),
        ]
        state: AgentState = {
            "messages": messages,
            "question": message,
            "session_id": session_id,
        }
        assert self._graph is not None
        out = self._graph.invoke(state)
        final_messages = out["messages"]
        answer = ""
        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                answer = msg.content if isinstance(msg.content, str) else str(msg.content)
                break
        if not answer:
            answer = "暂时无法生成回答，请稍后重试或转人工。"

        citations = [Citation(**c) for c in self.tools_impl.last_citations]
        return ChatResponse(
            answer=answer,
            citations=citations,
            tool_trace=list(self.tools_impl.trace),
            session_id=session_id,
            mode="langgraph-agent",
        )

    def _offline_rag_answer(self, message: str, session_id: str) -> ChatResponse:
        """No LLM key: still demonstrate GraphRAG retrieval + template answer."""
        context = self.tools_impl.hybrid_search(message, top_k=4)
        citations = [Citation(**c) for c in self.tools_impl.last_citations]
        if not citations:
            answer = (
                "当前未配置 LLM_API_KEY，且知识库未命中相关内容。"
                "请先启动 Neo4j 并执行 seed，或在 .env 中配置大模型密钥。"
            )
        else:
            bullets = []
            for i, c in enumerate(citations, start=1):
                bullets.append(f"[{i}] {c.snippet}")
            answer = (
                "【离线 GraphRAG 演示模式】未检测到可用 LLM_API_KEY，"
                "以下基于 Neo4j 混合检索结果整理：\n\n"
                + "\n".join(bullets)
                + "\n\n配置 LLM 后将启用 LangGraph Agent 多工具推理。"
            )
        return ChatResponse(
            answer=answer,
            citations=citations,
            tool_trace=list(self.tools_impl.trace),
            session_id=session_id,
            mode="offline-rag",
        )


_agent: CustomerServiceAgent | None = None


def get_agent() -> CustomerServiceAgent:
    global _agent
    if _agent is None:
        _agent = CustomerServiceAgent()
    return _agent
