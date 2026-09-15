from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.eval_suite import run_full_metrics


def main() -> None:
    report = run_full_metrics()
    r = report["retrieval"]
    lat = report["latency"]
    ag = report["agent"]
    print(f"Hit@3 vector={r['vector_hit_rate@3']} hybrid={r['hybrid_hit_rate@3']} lift={r['hit_rate@3_lift']}")
    print(f"Retrieve p50={lat['retrieve_ms']['p50']}ms p95={lat['retrieve_ms']['p95']}ms")
    print(f"E2E chat p50={lat['e2e_chat_ms']['p50']}ms p95={lat['e2e_chat_ms']['p95']}ms")
    print(f"Agent pass_rate={ag['pass_rate']} ({ag['passed']}/{ag['total']})")
    print("report ->", ROOT / "eval" / "metrics.json")


if __name__ == "__main__":
    main()
