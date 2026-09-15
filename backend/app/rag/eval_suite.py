from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agent.graph import CustomerServiceAgent
from app.rag.hybrid_retriever import HybridGraphRetriever

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "eval"
CASES_PATH = EVAL_DIR / "cases.json"
REPORT_PATH = EVAL_DIR / "last_report.json"

DEFAULT_CASES = [
    {
        "id": "product_modules",
        "q": "NovaDesk 有哪些核心模块？",
        "expect_any": ["NovaBot", "NovaFlow", "NovaInsight"],
        "category": "product",
    },
    {
        "id": "login_fail",
        "q": "登录失败怎么处理？",
        "expect_any": ["激活", "SSO", "锁定"],
        "category": "support",
    },
    {
        "id": "refund_policy",
        "q": "退款政策是什么？",
        "expect_any": ["7 日", "7日", "退款"],
        "category": "billing",
    },
    {
        "id": "enterprise_sla",
        "q": "Enterprise 的 SLA 首响多久？",
        "expect_any": ["5 分钟", "5分钟"],
        "category": "sla",
    },
    {
        "id": "data_retention",
        "q": "退订后数据保留多久？",
        "expect_any": ["30 天", "30天"],
        "category": "billing",
    },
]


def load_cases() -> list[dict[str, Any]]:
    if CASES_PATH.exists():
        return json.loads(CASES_PATH.read_text(encoding="utf-8"))
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    CASES_PATH.write_text(json.dumps(DEFAULT_CASES, ensure_ascii=False, indent=2), encoding="utf-8")
    return list(DEFAULT_CASES)


def _hit(case: dict[str, Any], answer: str, citations: list) -> bool:
    expect = case.get("expect_any") or []
    if any(x in answer for x in expect):
        return True
    blob = " ".join(f"{getattr(c, 'title', '')} {getattr(c, 'snippet', '')}" for c in citations)
    return any(x in blob for x in expect)


def run_agent_eval(agent: CustomerServiceAgent | None = None) -> dict[str, Any]:
    agent = agent or CustomerServiceAgent()
    cases = load_cases()
    rows = []
    passed = 0
    for case in cases:
        resp = agent.chat(case["q"], session_id="eval-suite")
        ok = _hit(case, resp.answer, resp.citations)
        passed += int(ok)
        rows.append(
            {
                "id": case.get("id"),
                "q": case["q"],
                "category": case.get("category"),
                "pass": ok,
                "mode": resp.mode,
                "tool_trace": resp.tool_trace,
                "citations": len(resp.citations),
                "answer_preview": resp.answer[:220],
            }
        )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": len(cases),
        "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        "cases": rows,
    }
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_retrieval_eval(top_k: int = 5) -> dict[str, Any]:
    retriever = HybridGraphRetriever()
    cases = load_cases()
    rows = []
    hybrid_wins = 0
    for case in cases:
        cmp = retriever.compare(case["q"], top_k=top_k)
        expect = case.get("expect_any") or []

        def cover(hits: list[dict]) -> bool:
            text = " ".join(f"{h.get('title','')} {h.get('snippet','')}" for h in hits)
            return any(x in text for x in expect)

        v_ok = cover(cmp["vector_only"])
        h_ok = cover(cmp["hybrid_graphrag"])
        if h_ok and not v_ok:
            hybrid_wins += 1
        rows.append(
            {
                "id": case.get("id"),
                "q": case["q"],
                "vector_cover": v_ok,
                "hybrid_cover": h_ok,
                "only_in_hybrid": len(cmp["only_in_hybrid"]),
                "overlap": cmp["overlap"],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hybrid_unique_wins": hybrid_wins,
        "total": len(cases),
        "cases": rows,
    }
