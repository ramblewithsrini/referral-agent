"""The policy layer: enforced in code, outside the model.

The agent proposes an outcome; this module decides what actually happens. It
gathers its own facts from the data (it never trusts what the agent says it
saw), applies the hard rules HR1-HR6 from data/policy.json, checks the message
to the merchant, and applies the confidence threshold.
"""

import json
import re
from pathlib import Path

from tools import DATA, World, ToolFailure, sanctions_score

POLICY = json.loads((DATA / "policy.json").read_text(encoding="utf-8"))
LIMITS = POLICY["limits"]
FX_TO_GBP = {"GBP": 1.0, "EUR": 0.86, "CAD": 0.54}
HIGH_VALUE_GBP = 5000
SANCTIONS_MATCH = 0.85

COMPLAINT = re.compile(r"\b(regulator|ombudsman|legal action|solicitor|lawyer|formal complaint|sue)\b", re.I)
INJECTION = re.compile(r"(ignore (all |your )?(previous |prior )?(rules|instructions)|instruction for the ai|^\s*system\s*:)", re.I | re.M)
CARD_NUMBER = re.compile(r"\b\d(?:[ -]?\d){11,18}\b")

QUEUE_OF = {"HR1": "financial_crime", "HR2": "fraud", "HR3": "approvals", "HR4": "merchant_risk", "HR5": "complaints"}
# What the merchant is told when a hard rule fires: never the reason (no tipping-off).
TEMPLATE = {
    "HR1": "Thank you. Your referral is under review and a member of our team will be in touch.",
    "HR2": "Please do not retry this card. Follow the retained-card procedure in your merchant guide; our team will contact you.",
    "HR3": "This payment needs a colleague's approval because of its value. We'll update you shortly.",
    "HR4": "Your account is being reviewed by our merchant team. We'll be in touch shortly.",
    "HR5": "We're sorry for the trouble. Your concern has been passed to our complaints team, who will contact you.",
    "HR6": "Thank you. A colleague is looking into this and will update you shortly.",
}


def facts(case: dict) -> dict:
    """The policy layer's own look-ups. A simulated outage hits these too."""
    world = World(case)
    out = {"lookup_failed": [], "injection": bool(INJECTION.search(case["message"])),
           "complaint": bool(COMPLAINT.search(case["message"]))}
    try:
        m = world.get_merchant(case["merchant"])
    except ToolFailure:
        out["lookup_failed"].append("get_merchant")
        m = None
    t = None
    if case.get("transaction"):
        try:
            t = world.get_transaction(case["transaction"])
        except ToolFailure:
            out["lookup_failed"].append("get_transaction")
    if m:
        out["sanctions_score"] = max(sanctions_score(m["name"], world.sanctions)["score"],
                                     sanctions_score(m["owner"], world.sanctions)["score"])
        out["new_with_spike"] = m["days_trading"] < 30 and m["recent_daily"] > 3 * m["expected_daily"]
    if t:
        out["lost_or_stolen"] = world.cards[t["card_token"]]["status"] == "lost_or_stolen"
        out["amount_gbp"] = round(t["amount"] * FX_TO_GBP[t["currency"]], 2)
    return out


def hard_rule(f: dict) -> str | None:
    """The first hard rule that applies, in priority order."""
    if f["lookup_failed"]:
        return "HR6"
    if f.get("sanctions_score", 0) >= SANCTIONS_MATCH:
        return "HR1"
    if f.get("lost_or_stolen"):
        return "HR2"
    if f.get("amount_gbp", 0) > HIGH_VALUE_GBP:
        return "HR3"
    if f.get("new_with_spike"):
        return "HR4"
    if f["complaint"]:
        return "HR5"
    return None


def decide(case: dict, proposal: dict | None, agent_failures: list[str], threshold: float | None = None) -> dict:
    """Turn the agent's proposal into the outcome that actually happens."""
    threshold = LIMITS["auto_resolve_confidence"] if threshold is None else threshold
    f = facts(case)
    guardrails = []
    if f["injection"]:
        guardrails.append("Instruction found in the merchant's text: treated as data, not followed.")
    if agent_failures:
        f["lookup_failed"] = sorted(set(f["lookup_failed"]) | set(agent_failures))

    proposed = proposal["decision"] if proposal else None
    rule = hard_rule(f)
    if proposal is None:
        guardrails.append("The agent made no decision within its step limit.")
        return _out("human_review", None, rule or "no_decision", proposal, f, guardrails, overridden=True, message=TEMPLATE["HR6"])

    if rule:
        decision = "human_review" if rule == "HR6" else "escalate"
        queue = QUEUE_OF.get(rule)
        overridden = not (proposed == decision and proposal.get("queue") == queue)
        if overridden:
            guardrails.append(f"Hard rule {rule} applied: the agent proposed '{proposed}{' to ' + proposal['queue'] if proposal.get('queue') else ''}'.")
        return _out(decision, queue, rule, proposal, f, guardrails, overridden, TEMPLATE[rule])

    msg = proposal.get("message_to_merchant", "")
    if CARD_NUMBER.search(msg):
        guardrails.append("Message blocked: it contained what looks like a card number.")
        return _out("human_review", None, "data_protection", proposal, f, guardrails, True, TEMPLATE["HR6"])

    if proposed in ("resolve", "close_as_duplicate") and proposal["confidence"] < threshold:
        guardrails.append(f"Confidence {proposal['confidence']:.2f} is below the {threshold:.2f} threshold: sent to a person.")
        return _out("human_review", None, "confidence", proposal, f, guardrails, True, TEMPLATE["HR6"])

    if proposed == "human_review" and not msg:
        msg = TEMPLATE["HR6"]
    return _out(proposed, proposal.get("queue"), None, proposal, f, guardrails, False, msg)


def _out(decision, queue, rule, proposal, f, guardrails, overridden, message):
    return {"decision": decision, "queue": queue, "rule": rule, "overridden": overridden,
            "message_to_merchant": message, "guardrails": guardrails, "facts": f}
