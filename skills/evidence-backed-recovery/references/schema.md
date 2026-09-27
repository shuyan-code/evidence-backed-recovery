# Input contract

Money amounts are non-negative decimal strings in the policy currency, with at most two fractional digits. Case IDs must be pseudonymous. Evidence observations should be concise and free of personal data. Source references may be internal ticket or incident IDs; do not embed private URLs with tokens.

## Case JSON

```json
{
  "case_id": "CASE-1042",
  "severity": "high",
  "failure": "Three scheduled exports failed during onboarding.",
  "repair_action": "Restore the export schedule and monitor three runs.",
  "recovery_criterion": "Three consecutive scheduled exports complete successfully.",
  "evidence": [
    {"id": "E1", "kind": "independent_record", "source": "incident-482", "observation": "Export job failed on three scheduled runs."},
    {"id": "E2", "kind": "customer_statement", "source": "ticket-1042", "observation": "Customer said the delay blocked launch."}
  ],
  "claim_evidence_ids": ["E1", "E2"],
  "emotion_signal": {"label": "frustration", "evidence_id": "E2"},
  "proposal": {
    "remedy": "service_credit", "amount": "75.00", "currency": "USD",
    "owner": "support-lead", "follow_up_due": "2026-09-01"
  }
}
```

`severity` is `low`, `medium`, `high`, or `critical`. `evidence.kind` is `independent_record` or `customer_statement`. The emotion label is descriptive, not a diagnosis, and must reference a customer statement. `claim_evidence_ids` must point to provided evidence and include at least one independent record before a recovery proposal proceeds. `repair_action` describes the operational fix even when the remedy is a credit; `recovery_criterion` states the observable completion condition. Omit `emotion_signal` if the customer's words do not support it. A `critical` case always escalates for human review.

## Policy JSON

```json
{
  "version": "2026-Q3", "currency": "USD",
  "allowed_remedies": ["repair", "service_credit"],
  "agent_limit": "25.00", "manager_limit": "100.00",
  "minimum_repeat_window_days": 7
}
```

Limits are maximum proposed concession values, not authority to issue them. A remedy outside `allowed_remedies` or amount above `manager_limit` is a policy exception. `agent_limit` selects the review queue. `minimum_repeat_window_days` is an integer from 1 to 365 and defines the minimum period after follow-up before the absence of a repeat complaint can be counted. For a zero-cost repair, use `"amount": "0.00"`.

## Outcome JSON

```json
{
  "resolution": "resolved", "resolution_basis": "independent_record",
  "resolution_evidence_ref": "monitoring-771", "retained": "unknown",
  "repeat_complaint": false, "repeat_window_end": "2026-09-08",
  "repeat_check_ref": "ticket-query-771", "actual_amount": "75.00",
  "follow_up_completed_at": "2026-09-01",
  "approval_ref": "approval-317",
  "recorded_at": "2026-09-09"
}
```

`resolution` is `resolved` or `unresolved`. `resolution_basis` is `customer_confirmed`, `independent_record`, or `unverified`. A resolved outcome requires a non-unverified basis and `resolution_evidence_ref`. An unresolved outcome may use `unverified`; if it uses another basis, a reference is required. The reference should identify the actual customer confirmation or operational check, not a model judgment.

`repeat_window_end` must be at least `minimum_repeat_window_days` after `follow_up_completed_at`, and no later than `recorded_at`. `repeat_check_ref` identifies the ticket-system query or other source used to check for another complaint. `retained` is `yes`, `no`, or `unknown`; only `yes` or `no` require `retention_observed_at` and `retention_evidence_ref`, based on an actual renewal or cancellation event. All observation dates must be no later than `recorded_at`, which itself cannot be later than the current system date. The host clock must therefore be reliable.

`actual_amount` is the concession actually issued and cannot exceed the assessed proposal. `approval_ref` identifies real authorization for a nonzero concession. The ledger stores only case ID, policy and outcome fields, with no complaint text or evidence observations. Re-recording a case fails so a user investigates rather than silently overwrites an audit event.

For a `policy_exception` packet, add `"exception_approval_ref": "exception-42"` to the outcome after an authorized human approves the exception. A `needs_evidence` packet cannot be recorded until the evidence gap is fixed and the case is reassessed.

## Version 2 recording and legacy data

Run `record` with `--case`, `--policy`, `--packet`, `--outcome`, and `--db`. The packet must exactly match a fresh assessment of the supplied case and policy. This prevents a stale or edited packet from being accepted by the local CLI; it does not authenticate the input files or external approval references. Existing version 1 SQLite rows are retained when the database schema is extended. Reports mark them `legacy_unverified_cases` and exclude them from evidence-qualified outcome counts while retaining their recorded concession cost.
