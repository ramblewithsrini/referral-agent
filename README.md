# A governed AI agent: Srini Pay referral triage

A demo of how I would build a governed AI agent for a regulated payments workflow.

Srini Pay is a fictional card network. Merchants raise a **referral** when a card payment
doesn't go through. The agent (Claude, with tools) works each referral like an analyst:
it looks up the merchant, the transaction and the card, screens names against a
sanctions list, checks earlier referrals, and then **proposes** an outcome. A **policy
layer**, enforced in code outside the model, decides what actually happens.

Live, interactive replay: **https://srinivankeepuram.co.uk/lab/referral-agent**

All data is invented: merchants, people, cards, transactions and the sanctions list.
This is not any employer's system.

## Results

30 labelled cases, including traps: near-misses on value and sanctions, prompt
injection, requests for card data, and simulated outages.

| | Claude Opus 4.6, rules in its prompt | Stress test: Claude Haiku 4.5, no rules in its prompt |
|---|---|---|
| Correct by the agent alone | 30/30 | 24/30 |
| Correct after the policy layer | 30/30 | 29/30 |
| Mistakes caught by the policy layer | 0 | 5 |
| Wrong auto-resolutions | 0 | 0 |

The stress test is the point: a smaller model that was never told the rules tried to
resolve two lost or stolen cards and two high-value sales as ordinary declines, and sent
a regulator threat to the wrong team. The policy layer caught all five. The one miss
(an unclear decline sent to fraud rather than to a person) shows the limit of this
design: the policy layer blocks risky automation, not over-caution.

## How it works

- `agent/tools.py`: look-up tools over the fictional data, and action tools that only
  *propose* an outcome. The agent sees card tokens and last four digits only.
- `agent/policy.py`: the policy layer. It gathers its own facts (never trusting the
  agent's account), applies hard rules HR1–HR6, blocks card numbers in messages,
  replaces the merchant message when a rule fires (no tipping-off), and applies a
  confidence threshold to automatic resolutions.
- `agent/agent.py`: a manual tool-use loop, so every proposal stops at the policy layer
  and every step is recorded.
- `data/policy.json`: the governance written down: approved tools, data protection,
  limits and hard rules.
- `data/cases.json`: 30 labelled cases; `data/generate.py` rebuilds the data and checks
  every label against it.
- `eval/score.py`: scores the recorded runs, with a confidence-threshold sweep.
- `traces/`: every recorded run, step by step (`traces/stress/` for the stress test).

## Run it

Needs Python 3.11+ and an AWS account with Claude enabled in Amazon Bedrock (eu-west-1).

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # or .venv/bin/pip on macOS/Linux
python data/generate.py                          # rebuild and check the data
python -m pytest tests                           # policy layer tests, no model calls
aws login --profile <your-profile>
python agent/run.py showcase                     # 15 showcase cases
python agent/run.py all --stress                 # the stress test
python eval/score.py                             # or: python eval/score.py --stress
```

Settings go in a `.env` file (`AWS_PROFILE`, `AWS_REGION`, optional `AGENT_MODEL_ID`).

`anthropic[bedrock]` is pinned below 2.0: version 2 sends an API version that Bedrock
rejects for Claude 4.6 and earlier models.
