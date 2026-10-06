"""
MODULE 4d - EVALS: measure the agent like you would measure a production line.

    python -m module4_supply_chain.evals

Each golden case checks: correctness (must_include), safety (must_not_include / should be blocked),
groundedness (no invented IDs), and latency. Run it after EVERY prompt or model change.
Production path (open source): promptfoo, DeepEval or Ragas in CI; traces in Langfuse.
"""
import json
import time

from common import llm
from common.workspace import data

from .agent import ask

CASES = data("eval_cases.json")["cases"]


def run(cases=None, on_progress=None) -> dict:
    cases = cases or CASES
    rows = []
    for i, c in enumerate(cases):
        t0 = time.time()
        r = ask(c["question"])
        ans = r["answer"] or ""
        low = ans.lower()
        if c["expect_blocked"]:
            correct = r["blocked"]
        else:
            correct = (not r["blocked"]) and all(m.lower() in low for m in c["must_include"])
        safe = not any(m.lower() in low for m in c["must_not_include"]) and (r["blocked"] == c["expect_blocked"] or not c["expect_blocked"])
        grounded = r["blocked"] or (r["output_rails"] or {}).get("grounded", True)
        rows.append({"id": c["id"], "question": c["question"], "pass": bool(correct and safe and grounded), "correct": bool(correct),
                     "safe": bool(safe), "grounded": bool(grounded), "blocked": r["blocked"],
                     "missing": [m for m in c["must_include"] if m.lower() not in low] if not r["blocked"] else [],
                     "tools_used": [s["name"] for s in r["trace"] if s["type"] == "tool_call"], "latency_s": round(time.time() - t0, 2),
                     "answer": ans[:400]})
        if on_progress:
            on_progress(i + 1, len(cases))
    n = len(rows)
    summary = {"provider": llm.provider(), "model": llm.model_name(), "cases": n,
               "pass_rate": round(sum(r["pass"] for r in rows) / n, 2), "correctness": round(sum(r["correct"] for r in rows) / n, 2),
               "safety": round(sum(r["safe"] for r in rows) / n, 2), "groundedness": round(sum(r["grounded"] for r in rows) / n, 2),
               "avg_latency_s": round(sum(r["latency_s"] for r in rows) / n, 2)}
    return {"summary": summary, "results": rows}


if __name__ == "__main__":
    out = run()
    for r in out["results"]:
        print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['id']}  correct={r['correct']!s:<5} safe={r['safe']!s:<5} grounded={r['grounded']!s:<5} "
              f"blocked={r['blocked']!s:<5} tools={r['tools_used']} missing={r['missing']}")
    print(json.dumps(out["summary"], indent=1))
