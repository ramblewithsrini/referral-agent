"""Re-run the policy layer over saved traces (no model calls), after a policy change."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
from policy import decide  # noqa: E402

cases = {c["id"]: c for c in json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))}
for p in sorted((ROOT / "traces").glob("R*.json")):
    t = json.loads(p.read_text(encoding="utf-8"))
    failed = [s["tool"] for s in t["steps"] if s["type"] == "lookup" and "error" in s]
    t["outcome"] = decide(cases[t["case"]], t["proposal"], failed)
    p.write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
    print(t["case"], t["outcome"]["decision"], "|", t["outcome"]["message_to_merchant"][:60])
