# Governed referral-triage agent (Srini Pay)

A demo of a governed AI agent for a fictional card network, Srini Pay. Merchants raise
referrals when a payment doesn't go through; the agent looks things up with tools, then
resolves the case, asks for information, or hands it to a person. A policy layer outside
the model enforces hard rules the agent cannot talk its way past.

All data is invented: merchants, people, cards, the sanctions list and the cases.

## Status
- Phase 1 (done): fictional data, policy rules and 30 labelled cases (`data/`).
  Run `python data/generate.py` to rebuild the data and check every label against it.
- Phase 2: the agent and policy layer (Claude on Amazon Bedrock).
- Phase 3: evaluation against the 30 cases.
- Phase 4: recorded runs replayed on srinivankeepuram.co.uk/lab.

## Files
- `data/policy.json` — approved tools, data protection, limits and hard rules HR1–HR6.
- `data/cases.json` — 30 cases (15 showcase, 15 scoring-only) with expected outcomes.
- `data/cases-review.md` — the cases as a table for review.
