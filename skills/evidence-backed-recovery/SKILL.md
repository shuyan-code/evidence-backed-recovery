---
name: evidence-backed-recovery
description: Turn emotionally charged B2B customer complaints into evidence-linked service recovery proposals, policy-gated concessions, and measurable follow-up. Use for support or customer-success recovery decisions; not for generic sentiment tagging or personal emotional support.
---

# Evidence-backed recovery

Use this skill when a support or customer-success team must respond to a service failure and later verify whether the recovery worked. Customer emotion signals urgency and communication needs; it does not prove the failure or predict churn.

## Workflow

1. Obtain the complaint, operational records, current concession policy, an owner, and a follow-up date. Minimize customer data. Use a pseudonymous case ID and short evidence observations. Do not put names, contact details, full transcripts, payment data, or secrets in case files or the ledger.
2. Separate observed facts from customer claims and unknowns. Give each material claim an evidence ID with a source reference. Record expressed emotion only when supported by a quoted or referenced statement. Never infer a diagnosis, personality, or churn probability.
3. Prepare case and policy JSON using [the input contract](references/schema.md). Run `python scripts/recovery.py assess --case case.json --policy policy.json --output packet.json` from this skill folder. Inspect reason codes and resolve missing evidence before proposing a concession.
4. Draft a response that acknowledges the specific impact, states only verified facts, gives one owned next step and a date, and avoids promising approval, refunds, service credits, or resolution before authorization. Route policy exceptions and critical failures to an authorized human.
5. Obtain the organization's actual approval in its normal system before executing a concession or sending a binding offer. This skill and script never issue money, change an account, send a message, or assert approval. Do not invent an approval reference.
6. After the customer interaction and follow-up, create outcome JSON and run `python scripts/recovery.py record --packet packet.json --outcome outcome.json --db recovery.sqlite3`. Use `report --db recovery.sqlite3` for observed resolution, repeat contact, concession cost, and known retention rates. These are descriptive metrics, not causal ROI or proven churn prevention.

The CLI uses only the Python standard library. Its policy gate is deterministic; human judgment remains responsible for the proposed remedy, message, and actual business action. For executable examples and command details, read [the input contract](references/schema.md).
