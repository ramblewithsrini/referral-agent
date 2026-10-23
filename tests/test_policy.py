"""Policy layer tests: no model calls. The hard rules must hold whatever the agent proposes."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

import policy  # noqa: E402

CASES = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))


def perfect(case):
    e = case["expected"]
    return {"decision": e["decision"], "queue": e.get("queue"), "confidence": 0.95, "message_to_merchant": "ok"}


def careless(_case):
    return {"decision": "resolve", "queue": None, "confidence": 0.95, "message_to_merchant": "Please retry."}


def test_perfect_agent_passes_every_case():
    for c in CASES:
        out = policy.decide(c, perfect(c), [])
        e = c["expected"]
        assert out["decision"] == e["decision"], c["id"]
        assert out["queue"] == e.get("queue"), c["id"]
        assert not out["overridden"], c["id"]


def test_hard_rules_hold_against_a_careless_agent():
    for c in CASES:
        rule = c["expected"].get("rule")
        if rule:
            out = policy.decide(c, careless(c), [])
            assert out["rule"] == rule, c["id"]
            assert out["overridden"], c["id"]
            assert out["decision"] == c["expected"]["decision"], c["id"]


def test_no_false_rules_on_clean_cases():
    for c in CASES:
        if not c["expected"].get("rule"):
            assert policy.hard_rule(policy.facts(c)) is None, c["id"]


def test_low_confidence_goes_to_a_person():
    c = next(x for x in CASES if x["id"] == "R1007")
    low = {**careless(c), "confidence": 0.55}
    assert policy.decide(c, low, [])["decision"] == "human_review"
    assert policy.decide(c, low, [], threshold=0.5)["decision"] == "resolve"


def test_card_number_in_message_is_blocked():
    c = next(x for x in CASES if x["id"] == "R1014")
    leak = {**careless(c), "message_to_merchant": "The card was 4111 1111 1111 1111"}
    out = policy.decide(c, leak, [])
    assert out["decision"] == "human_review" and out["rule"] == "data_protection"


def test_tipping_off_is_impossible():
    c = next(x for x in CASES if x["id"] == "R1008")
    chatty = {**careless(c), "decision": "escalate", "queue": "financial_crime",
              "message_to_merchant": "Your owner matched a sanctions list."}
    out = policy.decide(c, chatty, [])
    assert "sanction" not in out["message_to_merchant"].lower()


def test_injection_is_flagged():
    c = next(x for x in CASES if x["id"] == "R1013")
    assert any("treated as data" in g for g in policy.decide(c, careless(c), [])["guardrails"])
