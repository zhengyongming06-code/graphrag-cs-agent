from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agent.graph import CustomerServiceAgent
from app.rag.hybrid_retriever import HybridGraphRetriever

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "eval"
CASES_PATH = EVAL_DIR / "cases.json"
REPORT_PATH = EVAL_DIR / "last_report.json"
METRICS_PATH = EVAL_DIR / "metrics.json"

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


def _cover(hits: list[dict], case: dict[str, Any], k: int | None = None) -> bool:
    subset = hits[:k] if k else hits
    expect = case.get("expect_any") or []
    gold_title = (case.get("gold_title") or "").lower()
    text = " ".join(f"{h.get('title','')} {h.get('snippet','')}" for h in subset)
    if any(x in text for x in expect):
        return True
    if gold_title and any(gold_title in (h.get("title") or "").lower() for h in subset):
        return True
    return False


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 4)


def run_retrieval_eval(top_k: int = 5) -> dict[str, Any]:
    retriever = HybridGraphRetriever()
    cases = load_cases()
    rows = []
    hybrid_wins = 0
    vec_hit3 = 0
    hyb_hit3 = 0
    retrieve_ms: list[float] = []
    for case in cases:
        t0 = time.perf_counter()
        cmp = retriever.compare(case["q"], top_k=top_k)
        retrieve_ms.append((time.perf_counter() - t0) * 1000)
        v_ok = _cover(cmp["vector_only"], case, k=3)
        h_ok = _cover(cmp["hybrid_graphrag"], case, k=3)
        vec_hit3 += int(v_ok)
        hyb_hit3 += int(h_ok)
        if h_ok and not v_ok:
            hybrid_wins += 1
        rows.append(
            {
                "id": case.get("id"),
                "q": case["q"],
                "vector_hit@3": v_ok,
                "hybrid_hit@3": h_ok,
                "vector_cover": v_ok,
                "hybrid_cover": h_ok,
                "only_in_hybrid": len(cmp["only_in_hybrid"]),
                "overlap": cmp["overlap"],
            }
        )
    n = max(len(cases), 1)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "keyword/gold-title Hit@3 on 自建评测集（非 Ragas）",
        "fusion": "RRF(k=60)",
        "graph_hops": 1,
        "hybrid_unique_wins": hybrid_wins,
        "vector_hit_rate@3": round(vec_hit3 / n, 4),
        "hybrid_hit_rate@3": round(hyb_hit3 / n, 4),
        "hit_rate@3_lift": round((hyb_hit3 - vec_hit3) / n, 4),
        "compare_latency_ms": {
            "p50": _pct(retrieve_ms, 50),
            "p95": _pct(retrieve_ms, 95),
            "mean": round(statistics.fmean(retrieve_ms), 2) if retrieve_ms else 0,
        },
        "total": len(cases),
        "cases": rows,
    }


def run_latency_eval(repeats: int = 3) -> dict[str, Any]:
    retriever = HybridGraphRetriever()
    cases = load_cases()
    retrieve_ms: list[float] = []
    for case in cases:
        retriever.retrieve(case["q"], top_k=5)  # warmup
        for _ in range(repeats):
            t0 = time.perf_counter()
            retriever.retrieve(case["q"], top_k=5)
            retrieve_ms.append((time.perf_counter() - t0) * 1000)
    chat_ms: list[float] = []
    agent = CustomerServiceAgent()
    for case in cases:
        t0 = time.perf_counter()
        agent.chat(case["q"], session_id="latency")
        chat_ms.append((time.perf_counter() - t0) * 1000)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "retrieve_ms": {
            "n": len(retrieve_ms),
            "p50": _pct(retrieve_ms, 50),
            "p95": _pct(retrieve_ms, 95),
            "mean": round(statistics.fmean(retrieve_ms), 2) if retrieve_ms else 0,
        },
        "e2e_chat_ms": {
            "n": len(chat_ms),
            "p50": _pct(chat_ms, 50),
            "p95": _pct(chat_ms, 95),
            "mean": round(statistics.fmean(chat_ms), 2) if chat_ms else 0,
        },
    }
    return payload


def run_full_metrics() -> dict[str, Any]:
    retrieval = run_retrieval_eval(top_k=5)
    latency = run_latency_eval(repeats=3)
    agent = run_agent_eval()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "自建评测集 keyword Hit@3 + 实测延迟；未接入 Ragas/TruLens，面试勿称为 Ragas 分数。",
        "retrieval": retrieval,
        "latency": latency,
        "agent": {
            "passed": agent["passed"],
            "total": agent["total"],
            "pass_rate": agent["pass_rate"],
        },
    }
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

