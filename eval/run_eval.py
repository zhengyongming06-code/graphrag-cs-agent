from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import CustomerServiceAgent


CASES = [
    {"q": "NovaDesk 有哪些核心模块？", "expect_any": ["NovaBot", "NovaFlow", "NovaInsight"]},
    {"q": "登录失败怎么处理？", "expect_any": ["激活", "SSO", "锁定"]},
    {"q": "退款政策是什么？", "expect_any": ["7 日", "7日", "退款"]},
    {"q": "Enterprise 的 SLA 首响多久？", "expect_any": ["5 分钟", "5分钟"]},
]


def main() -> None:
    agent = CustomerServiceAgent()
    report = []
    passed = 0
    for case in CASES:
        resp = agent.chat(case["q"], session_id="eval")
        hit = any(x in resp.answer for x in case["expect_any"]) or any(
            x in (c.snippet + c.title) for c in resp.citations for x in case["expect_any"]
        )
        passed += int(hit)
        report.append(
            {
                "q": case["q"],
                "pass": hit,
                "mode": resp.mode,
                "citations": len(resp.citations),
                "answer_preview": resp.answer[:180],
            }
        )
        print(("PASS" if hit else "FAIL"), case["q"], f"citations={len(resp.citations)}")

    out = ROOT / "eval" / "last_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(CASES)} passed · report -> {out}")


if __name__ == "__main__":
    main()
