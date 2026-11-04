"""One-command health check for the GenAI layer against the REAL warehouse.

    uv run python -m genai.smoke_check                 # DB + tools + RAG + config (no LLM call)
    uv run python -m genai.smoke_check --llm           # also asks the real Groq agent 2 questions
    uv run python -m genai.smoke_check --city Aswan

Exit code 1 if any check FAILS (warnings do not fail).
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from genai import db, rag, tools  
from genai.data_to_text import build_alert_payload 

OK, WARN, FAIL = "PASS", "WARN", "FAIL"


def run_checks(city: str = "Hurghada", with_llm: bool = False, check_env: bool = True) -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []

    def add(status, name, detail=""):
        results.append((status, name, detail))

    # 1) environment
    if check_env:
        missing = [k for k in ("SQLSERVER_HOST", "SQLSERVER_DATABASE", "SQLSERVER_USER", "SQLSERVER_PASSWORD")
                   if not os.getenv(k)]
        add(FAIL if missing else OK, "SQL Server env vars", f"missing: {', '.join(missing)}" if missing else "")
        if missing:
            return results
    add(OK if os.getenv("GROQ_API_KEY") else WARN, "GROQ_API_KEY",
        "" if os.getenv("GROQ_API_KEY") else "not set -> /chatbot/ask returns 503 and alerts use the template")

    # 2) connection + tables
    try:
        db.run_query("SELECT 1 AS ok")
        add(OK, "connect to SQL Server")
    except Exception as exc:
        add(FAIL, "connect to SQL Server", f"{type(exc).__name__}: {str(exc)[:160]}")
        return results
    counts = {}
    for table in ("gold.fact_hourly_risk", "gold.dim_location", "gold.predictions"):
        try:
            counts[table] = db.run_query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]
        except Exception as exc:
            counts[table] = None
            add(FAIL, f"table {table}", f"{type(exc).__name__}: {str(exc)[:120]}")
    if counts.get("gold.fact_hourly_risk") is not None:
        n = counts["gold.fact_hourly_risk"]
        add(OK if n > 0 else FAIL, "gold.fact_hourly_risk rows", f"{n} rows" + ("" if n else " -> run the DAGs first"))
    if counts.get("gold.dim_location") is not None:
        n = counts["gold.dim_location"]
        add(OK if n == 15 else WARN, "gold.dim_location rows", f"{n} (expected 15)")
    if counts.get("gold.predictions") is not None:
        n = counts["gold.predictions"]
        add(OK if n > 0 else WARN, "gold.predictions rows",
            f"{n}" + ("" if n else " -> empty until ml/inference_job.py runs; outlook will say 'no data'"))
    if not counts.get("gold.fact_hourly_risk"):
        return results

    # 3) every SQL tool
    for label, fn in [
        ("get_current_risk", lambda: tools.current_risk(city)),
        ("get_top_risky_regions", lambda: tools.top_risky_regions(3)),
        ("get_risk_history", lambda: tools.risk_history(city, 24)),
        ("get_weather_outlook", lambda: tools.weather_outlook(city)),
        ("get_past_events", lambda: tools.past_events(None, "Watch", 365)),
    ]:
        try:
            r = fn()
        except Exception as exc:
            add(FAIL, f"tool {label}", f"{type(exc).__name__}: {str(exc)[:140]}")
            continue
        if r["status"] == "ok":
            extra = f"as of {r['data_as_of']} UTC" + (" (STALE)" if r.get("stale") else "")
            add(WARN if r.get("stale") else OK, f"tool {label}", f"{len(r['rows'])} rows, {extra}")
        elif r["status"] == "no_data":
            add(WARN, f"tool {label}", r.get("reason", "no data"))
        else:
            add(FAIL, f"tool {label}", r.get("reason", "error"))

    # 4) RAG
    r = rag.search_documents("what to do during a flash flood")
    if r["status"] == "ok":
        add(OK, "RAG search", f"{len(r['rows'])} passages, top: {r['rows'][0]['source']}")
    elif r["status"] == "no_data":
        add(WARN, "RAG search", r["reason"] + " (run: python -m genai.vector_store_setup, or raise RAG_MAX_DISTANCE)")
    else:
        add(FAIL, "RAG search", r["reason"])

    # 5) alert payload
    p = build_alert_payload(city)
    add(OK if p["status"] == "ok" else FAIL, "alert payload",
        f"{p.get('risk_level')} (peak {p['peak']['risk_level']})" if p["status"] == "ok" else str(p.get("reason")))

    # 6) real LLM (optional)
    if with_llm:
        from genai.chatbot_chain import FloodAgent
        agent = FloodAgent()
        for q, expect in [(f"What is the current flood risk in {city}?", "get_current_risk"),
                          ("What should I do if my car is surrounded by floodwater?", "search_knowledge_base")]:
            try:
                a = agent.ask(q)
            except Exception as exc:
                add(FAIL, f"LLM: {q[:35]}...", f"{type(exc).__name__}: {str(exc)[:120]}")
                continue
            good = a.status == "ok" and a.grounded and expect in a.tools_used
            add(OK if good else WARN, f"LLM: {q[:35]}...",
                f"status={a.status} grounded={a.grounded} tools={a.tools_used}")
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="Hurghada")
    ap.add_argument("--llm", action="store_true", help="also call the real Groq model")
    args = ap.parse_args(argv)
    icons = {OK: "✅", WARN: "⚠️ ", FAIL: "❌"}
    results = run_checks(args.city, args.llm)
    for status, name, detail in results:
        print(f"{icons[status]} {status}  {name}" + (f"  - {detail}" if detail else ""))
    failed = sum(1 for s, _, _ in results if s == FAIL)
    print(f"\n{len(results)} checks, {failed} failed, {sum(1 for s,_,_ in results if s == WARN)} warnings")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
