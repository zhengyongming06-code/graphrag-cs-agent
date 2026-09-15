from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.eval_suite import run_agent_eval, run_retrieval_eval


def main() -> None:
    agent_report = run_agent_eval()
    retrieval_report = run_retrieval_eval()
    print(
        f"Agent {agent_report['passed']}/{agent_report['total']} "
        f"pass_rate={agent_report['pass_rate']}"
    )
    print(
        f"Retrieval hybrid_unique_wins="
        f"{retrieval_report['hybrid_unique_wins']}/{retrieval_report['total']}"
    )
    for row in agent_report["cases"]:
        print(("PASS" if row["pass"] else "FAIL"), row["q"])
    out = ROOT / "eval" / "last_report.json"
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
