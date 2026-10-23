"""Score the saved traces against the labelled cases.

    python eval/score.py            # every case that has a trace
    python eval/score.py showcase   # showcase cases only

Reports the agent on its own (what it proposed) and the governed system (after
the policy layer), plus a threshold sweep re-using each run's recorded proposal.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from policy import decide  # noqa: E402

AUTO = {"resolve", "close_as_duplicate"}


def match(decision, queue, expected):
    return decision == expected["decision"] and queue == expected.get("queue")


def load(only_showcase: bool):
    cases = {c["id"]: c for c in json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))}
    traces = []
    for p in sorted((ROOT / "traces").glob("R*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        if only_showcase and not t["showcase"]:
            continue
        traces.append((cases[t["case"]], t))
    return traces


def score(traces, threshold=None):
    n = len(traces)
    agent_ok = system_ok = wrong_auto = over_escalated = rescued = 0
    for case, t in traces:
        e, p = case["expected"], t["proposal"] or {}
        out = decide(case, t["proposal"], [], threshold) if threshold is not None else t["outcome"]
        a_ok = match(p.get("decision"), p.get("queue"), e)
        s_ok = match(out["decision"], out["queue"], e)
        agent_ok += a_ok
        system_ok += s_ok
        wrong_auto += out["decision"] in AUTO and not s_ok
        over_escalated += out["decision"] in ("escalate", "human_review") and e["decision"] not in ("escalate", "human_review")
        rescued += s_ok and not a_ok
    return dict(cases=n, agent_alone=agent_ok, governed=system_ok, wrong_auto_resolves=wrong_auto,
                over_escalations=over_escalated, rescued_by_policy=rescued)


def main():
    traces = load("showcase" in sys.argv)
    if not traces:
        raise SystemExit("No traces yet: run agent/run.py first.")
    s = score(traces)
    calls = sum(t["tool_calls"] for _, t in traces) / len(traces)
    toks = sum(t["usage"]["input_tokens"] + t["usage"]["output_tokens"] for _, t in traces)
    print(f"Cases: {s['cases']}")
    print(f"Agent alone correct:   {s['agent_alone']}/{s['cases']}")
    print(f"Governed correct:      {s['governed']}/{s['cases']}  (rescued by policy: {s['rescued_by_policy']})")
    print(f"Wrong auto-resolves:   {s['wrong_auto_resolves']}")
    print(f"Over-escalations:      {s['over_escalations']}")
    print(f"Avg tool calls: {calls:.1f}   Total tokens: {toks:,}")
    print("\nThreshold sweep (governed correct / wrong auto-resolves / over-escalations):")
    for th in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        r = score(traces, th)
        print(f"  {th:.2f}: {r['governed']}/{r['cases']}  {r['wrong_auto_resolves']}  {r['over_escalations']}")
    print("\nMisses:")
    for case, t in traces:
        out, e, p = t["outcome"], case["expected"], t["proposal"] or {}
        if not match(out["decision"], out["queue"], e):
            print(f"  {case['id']} {case['title']}: expected {e['decision']}/{e.get('queue')}, "
                  f"got {out['decision']}/{out['queue']} (agent {p.get('decision')}, conf {p.get('confidence')})")


if __name__ == "__main__":
    main()
