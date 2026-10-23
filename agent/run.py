"""Run the agent over the cases and save one trace per case.

    python agent/run.py showcase        # the 15 showcase cases
    python agent/run.py all             # all 30
    python agent/run.py R1007 R1013     # specific cases
"""

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

import anthropic  # noqa: E402

from agent import make_client, run_case  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TRACES = ROOT / "traces"
STRESS = "--stress" in sys.argv  # Haiku 4.5, hard rules left out of the prompt
if STRESS:
    TRACES = TRACES / "stress"


def main(args: list[str]) -> None:
    args = [a for a in args if a not in ("--redo", "--stress")]
    cases = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))
    if args == ["showcase"]:
        cases = [c for c in cases if c["showcase"]]
    elif args and args != ["all"]:
        cases = [c for c in cases if c["id"] in args]
    model = "eu.anthropic.claude-haiku-4-5-20251001-v1:0" if STRESS else os.environ.get("AGENT_MODEL_ID", "eu.anthropic.claude-opus-4-6-v1")
    client = make_client()
    TRACES.mkdir(exist_ok=True)
    redo = "--redo" in sys.argv
    for c in cases:
        if (TRACES / f"{c['id']}.json").exists() and not redo:
            print(f"{c['id']}: already done (use --redo to run again)")
            continue
        for attempt in range(4):
            try:
                trace = run_case(client, c, model, with_rules=not STRESS)
                break
            except anthropic.RateLimitError:
                wait = 60 * (attempt + 1)
                print(f"{c['id']}: rate limited, waiting {wait}s")
                time.sleep(wait)
            except anthropic.APIStatusError as e:
                print(f"{c['id']}: API error {e.status_code}: {e.message}")
                trace = None
                break
        else:
            trace = None
        if trace is None:
            continue
        (TRACES / f"{c['id']}.json").write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
        o, e = trace["outcome"], c["expected"]
        ok = o["decision"] == e["decision"] and o["queue"] == e.get("queue")
        p = trace["proposal"] or {}
        print(f"{c['id']} {'PASS' if ok else 'FAIL'}  agent={p.get('decision')}/{p.get('queue')} "
              f"conf={p.get('confidence')}  final={o['decision']}/{o['queue']}  rule={o['rule']}  "
              f"calls={trace['tool_calls']}  {trace['seconds']}s")
        time.sleep(15)  # stay under the account's request quota


if __name__ == "__main__":
    main(sys.argv[1:])
