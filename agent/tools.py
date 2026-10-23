"""The agent's tools over the fictional Srini Pay data.

Look-up tools return data; action tools only *propose* an outcome, which the
policy layer (policy.py) checks before anything is sent. Card data is minimised:
the agent only ever sees a token and the last four digits.
"""

import json
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
TODAY = date(2026, 10, 20)


def _load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


class ToolFailure(Exception):
    """A look-up that failed (used to simulate timeouts)."""


class World:
    """All look-ups for one case, with any simulated failures for that case."""

    def __init__(self, case: dict):
        self.case = case
        self.simulate = case.get("simulate") or {}
        self.merchants = {m["id"]: m for m in _load("merchants")}
        self.transactions = {t["id"]: t for t in _load("transactions")}
        self.cards = {c["token"]: c for c in _load("cards")}
        self.sanctions = _load("sanctions")
        self.history = _load("history")
        self.failures: list[str] = []  # every failed call, in order

    def _maybe_fail(self, tool: str):
        if self.simulate.get(tool) == "timeout":
            self.failures.append(tool)
            raise ToolFailure(f"{tool} timed out")

    # ---- look-ups ----
    def get_merchant(self, merchant_id: str) -> dict:
        self._maybe_fail("get_merchant")
        m = self.merchants.get(merchant_id)
        if m is None:
            return {"error": f"no merchant {merchant_id}"}
        days = (TODAY - date.fromisoformat(m["onboarded"])).days
        return {**m, "days_trading": days}

    def get_transaction(self, transaction_id: str) -> dict:
        self._maybe_fail("get_transaction")
        t = self.transactions.get(transaction_id)
        if t is None:
            return {"error": f"no transaction {transaction_id}"}
        card = self.cards[t["card"]]
        return {
            "id": t["id"], "merchant_id": t["merchant"], "card_token": t["card"],
            "card_last4": card["last4"], "amount": t["amount"], "currency": t["currency"],
            "terminal_currency": t["terminal_currency"], "decline_reason": t["decline_reason"], "at": t["at"],
        }

    def get_card_status(self, card_token: str) -> dict:
        self._maybe_fail("get_card_status")
        c = self.cards.get(card_token)
        if c is None:
            return {"error": f"no card {card_token}"}
        return {"card_token": c["token"], "last4": c["last4"], "status": c["status"], "expiry": c["expiry"]}

    def screen_sanctions(self, name: str) -> dict:
        self._maybe_fail("screen_sanctions")
        return sanctions_score(name, self.sanctions)

    def get_referral_history(self, merchant_id: str) -> dict:
        self._maybe_fail("get_referral_history")
        return {"merchant_id": merchant_id, "referrals": [h for h in self.history if h["merchant"] == merchant_id]}


def sanctions_score(name: str, entries: list[dict]) -> dict:
    """Best fuzzy match of a name against the (fictional) list, 0 to 1."""
    query = " ".join(name.lower().split())
    best, best_score = None, 0.0
    for e in entries:
        score = round(SequenceMatcher(None, query, e["name"].lower()).ratio(), 2)
        if score > best_score:
            best, best_score = e, score
    return {"query": name, "score": best_score, "closest_entry": best["name"] if best else None}


# ---- tool definitions sent to Claude ----
def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


CONFIDENCE = {"type": "number", "description": "0 to 1: how sure you are that this outcome and message are right."}
MESSAGE = {"type": "string", "description": "What the merchant will be told. Plain, polite, no card or personal data."}

LOOKUP_TOOLS = [
    {"name": "get_merchant", "description": "Look up a merchant: owner, country, onboarding date, days trading, KYB status, expected and recent daily volume.",
     "input_schema": _schema({"merchant_id": {"type": "string"}}, ["merchant_id"])},
    {"name": "get_transaction", "description": "Look up a declined transaction: amount, currency, terminal currency, decline reason, card token and last four digits.",
     "input_schema": _schema({"transaction_id": {"type": "string"}}, ["transaction_id"])},
    {"name": "get_card_status", "description": "Status of a card by token: active, expired or lost_or_stolen.",
     "input_schema": _schema({"card_token": {"type": "string"}}, ["card_token"])},
    {"name": "screen_sanctions", "description": "Screen a person or company name against the sanctions list. Returns the closest entry and a 0-1 match score.",
     "input_schema": _schema({"name": {"type": "string"}}, ["name"])},
    {"name": "get_referral_history", "description": "Earlier referrals for a merchant, with the transaction each one was about.",
     "input_schema": _schema({"merchant_id": {"type": "string"}}, ["merchant_id"])},
]

ACTION_TOOLS = [
    {"name": "resolve_with_guidance", "description": "Resolve the referral: send the merchant guidance and close it.",
     "input_schema": _schema({"message_to_merchant": MESSAGE, "reason": {"type": "string"}, "confidence": CONFIDENCE},
                             ["message_to_merchant", "reason", "confidence"])},
    {"name": "request_information", "description": "Ask the merchant for a missing detail; the case waits.",
     "input_schema": _schema({"missing": {"type": "string"}, "message_to_merchant": MESSAGE, "confidence": CONFIDENCE},
                             ["missing", "message_to_merchant", "confidence"])},
    {"name": "close_as_duplicate", "description": "Close as a duplicate of an earlier referral about the same transaction.",
     "input_schema": _schema({"earlier_case": {"type": "string"}, "message_to_merchant": MESSAGE, "confidence": CONFIDENCE},
                             ["earlier_case", "message_to_merchant", "confidence"])},
    {"name": "escalate", "description": "Hand the case to a specialist queue.",
     "input_schema": _schema({"queue": {"type": "string", "enum": ["financial_crime", "fraud", "approvals", "merchant_risk", "complaints"]},
                              "reason": {"type": "string"}, "message_to_merchant": MESSAGE, "confidence": CONFIDENCE},
                             ["queue", "reason", "message_to_merchant", "confidence"])},
    {"name": "send_to_human_review", "description": "Hand the case to a person when you are not sure, or a look-up failed.",
     "input_schema": _schema({"reason": {"type": "string"}, "confidence": CONFIDENCE}, ["reason", "confidence"])},
]

ACTION_NAMES = {t["name"] for t in ACTION_TOOLS}
DECISION_OF = {
    "resolve_with_guidance": "resolve", "request_information": "request_information",
    "close_as_duplicate": "close_as_duplicate", "escalate": "escalate", "send_to_human_review": "human_review",
}


def run_lookup(world: World, name: str, args: dict) -> dict:
    return getattr(world, name)(**args)
