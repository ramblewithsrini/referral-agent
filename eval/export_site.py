"""Export the recorded runs for the website's replay page.

    python eval/export_site.py ../my-portfolio/src/data/referral-runs.json

Writes both runs (governed Opus 4.6, and the Haiku stress test without rules in
its prompt) in a compact form: everything the page shows, nothing it doesn't.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
merchants = {m["id"]: m for m in json.loads((ROOT / "data" / "merchants.json").read_text(encoding="utf-8"))}
cases = {c["id"]: c for c in json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))}
policy = json.loads((ROOT / "data" / "policy.json").read_text(encoding="utf-8"))

KEEP = {  # the fields worth showing from each look-up
    "get_merchant": ["name", "owner", "country", "days_trading", "kyb_status", "expected_daily", "recent_daily"],
    "get_transaction": ["amount", "currency", "terminal_currency", "decline_reason", "card_last4"],
    "get_card_status": ["last4", "status"],
    "screen_sanctions": ["query", "closest_entry", "score"],
    "get_referral_history": ["referrals"],
}


def step(s):
    if s["type"] == "lookup":
        out = {"kind": "lookup", "tool": s["tool"], "input": s["input"]}
        if "error" in s:
            out["error"] = s["error"]
        else:
            r = s["result"]
            if s["tool"] == "get_referral_history":
                out["result"] = {"earlier": [f"{h['case']} on {h['transaction']} ({h['outcome']})" for h in r["referrals"]]}
            else:
                out["result"] = {k: r[k] for k in KEEP[s["tool"]] if k in r}
        return out
    if s["type"] == "action":
        return {"kind": "action", "tool": s["tool"]}
    return None


def run(folder: Path, label: str, model: str, rules: bool):
    out = []
    for p in sorted(folder.glob("R*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        c = cases[t["case"]]
        prop = t["proposal"] or {}
        o = t["outcome"]
        out.append({
            "id": c["id"], "title": c["title"], "showcase": c["showcase"],
            "merchant": merchants[c["merchant"]]["name"], "message": c["message"],
            "transaction": c.get("transaction"),
            "steps": [x for x in (step(s) for s in t["steps"]) if x],
            "proposal": {"decision": prop.get("decision"), "queue": prop.get("queue"),
                         "confidence": prop.get("confidence"),
                         "reason": prop.get("reason"), "message": prop.get("message_to_merchant")} if prop else None,
            "outcome": {"decision": o["decision"], "queue": o["queue"], "rule": o["rule"],
                        "overridden": o["overridden"], "guardrails": o["guardrails"], "message": o["message_to_merchant"]},
            "expected": {"decision": c["expected"]["decision"], "queue": c["expected"].get("queue"), "rule": c["expected"].get("rule")},
            "toolCalls": t["tool_calls"], "seconds": t["seconds"],
        })
    return {"label": label, "model": model, "rulesInPrompt": rules, "cases": out}


def main():
    target = Path(sys.argv[1])
    data = {
        "network": policy["network"],
        "hardRules": [{"id": r["id"], "name": r["name"], "when": r["when"], "then": r["then"]} for r in policy["hard_rules"]],
        "limits": policy["limits"],
        "dataProtection": policy["data_protection"],
        "approvedTools": policy["approved_tools"],
        "runs": {
            "governed": run(ROOT / "traces", "Claude Opus 4.6, rules in its prompt", "Claude Opus 4.6 on Amazon Bedrock", True),
            "stress": run(ROOT / "traces" / "stress", "Stress test: Claude Haiku 4.5, no rules in its prompt", "Claude Haiku 4.5 on Amazon Bedrock", False),
        },
    }
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {target} ({target.stat().st_size // 1024} KB): "
          f"{len(data['runs']['governed']['cases'])} governed, {len(data['runs']['stress']['cases'])} stress cases")


if __name__ == "__main__":
    main()
