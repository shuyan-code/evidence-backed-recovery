# Input contract

Money amounts are non-negative decimal strings in the policy currency, with at most two fractional digits. Case IDs must be pseudonymous. Evidence observations should be concise and free of personal data. Source references may be internal ticket or incident IDs; do not embed private URLs with tokens.

## Case JSON

```json
{
  "case_id": "CASE-1042",
  "severity": "high",
  "failure": "Three scheduled exports failed during onboarding.",
  "evidence": [
    {"id": "E1", "kind": "independent_record", "source": "incident-482", "observation": "Export job failed on three scheduled runs."},
    {"id": "E2", "kind": "customer_statement", "source": "ticket-1042", "observation": "Customer said the delay blocked launch."}
  ],
  "claim_evidence_ids": ["E1", "E2"],
  "emotion_signal": {"label": "frustration", "evidence_id": "E2"},
  "proposal": {
    "remedy": "service_credit", "amount": "75.00", "currency": "USD",
    "owner": "support-lead", "follow_up_due": "2026-10-01"
  }
}
```

`severity` is `low`, `medium`, `high`, or `critical`. `evidence.kind` is `independent_record` or `customer_statement`. The emotion label is descriptive, not a diagnosis, and must reference a customer statement. `claim_evidence_ids` must point to provided evidence and include at least one independent record before a recovery proposal proceeds. Omit `emotion_signal` if the customer's words do not support it. A `critical` case always escalates for human review.

## Policy JSON

```json
{
  "version": "2026-Q3", "currency": "USD",
  "allowed_remedies": ["repair", "service_credit"],
  "agent_limit": "25.00", "manager_limit": "100.00"
}
```

Limits are maximum proposed concession values, not authority to issue them. A remedy outside `allowed_remedies` or amount above `manager_limit` is a policy exception. `agent_limit` selects the review queue. For a zero-cost repair, use `"amount": "0.00"`.

## Outcome JSON

```json
{
  "resolution": "resolved", "retained": "unknown",
  "repeat_complaint": false, "actual_amount": "75.00",
  "approval_ref": "approval-317",
  "recorded_at": "2026-10-02"
}
```

`resolution` is `resolved` or `unresolved`; `retained` is `yes`, `no`, or `unknown`. `actual_amount` is the concession actually issued and cannot exceed the assessed proposal. `approval_ref` identifies real authorization for a nonzero concession. The ledger stores only case ID, policy and outcome fields, with no complaint text or evidence observations. Re-recording a case fails so a user investigates rather than silently overwrites an audit event.

For a `policy_exception` packet, add `"exception_approval_ref": "exception-42"` to the outcome after an authorized human approves the exception. A `needs_evidence` packet cannot be recorded until the evidence gap is fixed and the case is reassessed.

