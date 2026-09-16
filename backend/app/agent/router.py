from __future__ import annotations

import json
import re

from app.config import get_settings

INTENTS = ("escalate", "policy", "entity", "faq", "chitchat")

_ESCALATE = re.compile(r"转人工|人工客服|投诉|律师|法务|举报|工单跟进|催单")
_POLICY = re.compile(r"退款|退订|发票|计费|账单|套餐|价格|SLA|sla|保留|试用")
_ENTITY = re.compile(r"NovaDesk|NovaBot|NovaFlow|NovaInsight|核心模块|是什么")
_CHITCHAT = re.compile(r"^(你好|您好|在吗|哈喽|谢谢|感谢|哈哈+|早+|晚安)[\s!！。.~]*$")


def rule_intent(question: str) -> str:
    q = (question or "").strip()
    if not q:
        return "chitchat"
    if _CHITCHAT.search(q):
        return "chitchat"
    if _ESCALATE.search(q):
        return "escalate"
    if _POLICY.search(q):
        return "policy"
    if _ENTITY.search(q):
        return "entity"
    return "faq"


def llm_intent(question: str) -> str | None:
    settings = get_settings()
    if not settings.llm_ready or not settings.use_llm_router:
        return None
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            timeout=20,
        )
        msg = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "你是客服意图分类器。只输出 JSON："
                        '{"intent":"escalate|policy|entity|faq|chitchat","reason":"..."}。'
                        "escalate=要人工/投诉；policy=退款计费SLA；"
                        "entity=产品模块；faq=排障；chitchat=寒暄。"
                    )
                ),
                HumanMessage(content=question),
            ]
        )
        text = msg.content if isinstance(msg.content, str) else str(msg.content)
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        data = json.loads(match.group(0))
        intent = str(data.get("intent") or "").strip().lower()
        return intent if intent in INTENTS else None
    except Exception:
        return None


def classify_intent(question: str) -> tuple[str, str]:
    """Rule first for stable SOP; LLM only when the rule lands on generic faq."""
    ruled = rule_intent(question)
    if ruled != "faq":
        return ruled, "rule"
    guessed = llm_intent(question)
    if guessed:
        return guessed, "llm"
    return ruled, "rule"
