"""Policy gate and minimal outcome ledger for evidence-backed service recovery."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path


CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
SEVERITIES = {"low", "medium", "high", "critical"}
RESOLUTIONS = {"resolved", "unresolved"}
RETENTION = {"yes", "no", "unknown"}
EVIDENCE_KINDS = {"independent_record", "customer_statement"}


class InputError(ValueError):
    """A case, policy, packet, or outcome violates its public contract."""


def require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{label} must be a non-empty string")
    return value.strip()


def money(value: object, label: str) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
        raise InputError(f"{label} must be a non-negative decimal string with at most two places")
    result = Decimal(value)
    if result > Decimal("999999999.99"):
        raise InputError(f"{label} exceeds the supported amount")
    return result


def require_date(value: object, label: str) -> str:
    text = require_text(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise InputError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != text:
        raise InputError(f"{label} must be an ISO date")
    return text


def read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            obj = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise InputError(f"{path} must contain a JSON object")
    return obj


def assess(case: dict, policy: dict) -> dict:
    """Return a deterministic decision packet without changing business state."""
    case_id = require_text(case.get("case_id"), "case_id")
    if not CASE_ID.fullmatch(case_id):
        raise InputError("case_id must be 3-64 pseudonymous letters, digits, underscores, or hyphens")
    severity = case.get("severity")
    if severity not in SEVERITIES:
        raise InputError("severity must be low, medium, high, or critical")
    require_text(case.get("failure"), "failure")
    evidence = case.get("evidence")
    if not isinstance(evidence, list):
        raise InputError("evidence must be a list")
    evidence_ids: set[str] = set()
    evidence_kinds: dict[str, str] = {}
    for item in evidence:
        if not isinstance(item, dict):
            raise InputError("each evidence item must be an object")
        identifier = require_text(item.get("id"), "evidence.id")
        if identifier in evidence_ids:
            raise InputError(f"duplicate evidence ID: {identifier}")
        evidence_ids.add(identifier)
        kind = item.get("kind")
        if kind not in EVIDENCE_KINDS:
            raise InputError("evidence.kind must be independent_record or customer_statement")
        evidence_kinds[identifier] = kind
        require_text(item.get("source"), "evidence.source")
        require_text(item.get("observation"), "evidence.observation")
    claim_ids = case.get("claim_evidence_ids")
    if not isinstance(claim_ids, list) or not all(isinstance(x, str) for x in claim_ids):
        raise InputError("claim_evidence_ids must be a list of strings")
    missing_ids = sorted(set(claim_ids) - evidence_ids)
    if not claim_ids:
        missing_ids.append("claim_evidence_ids")
    if not any(evidence_kinds.get(identifier) == "independent_record" for identifier in claim_ids):
        missing_ids.append("independent_record")
    signal = case.get("emotion_signal")
    if signal is not None:
        if not isinstance(signal, dict):
            raise InputError("emotion_signal must be an object")
        require_text(signal.get("label"), "emotion_signal.label")
        signal_id = require_text(signal.get("evidence_id"), "emotion_signal.evidence_id")
        if signal_id not in evidence_ids:
            missing_ids.append(signal_id)
        elif evidence_kinds[signal_id] != "customer_statement":
            raise InputError("emotion_signal must reference a customer_statement")

    proposal = case.get("proposal")
    if not isinstance(proposal, dict):
        raise InputError("proposal must be an object")
    remedy = require_text(proposal.get("remedy"), "proposal.remedy")
    amount = money(proposal.get("amount"), "proposal.amount")
    currency = require_text(proposal.get("currency"), "proposal.currency")
    owner = require_text(proposal.get("owner"), "proposal.owner")
    due = require_date(proposal.get("follow_up_due"), "proposal.follow_up_due")

    version = require_text(policy.get("version"), "policy.version")
    policy_currency = require_text(policy.get("currency"), "policy.currency")
    remedies = policy.get("allowed_remedies")
    if not isinstance(remedies, list) or not remedies or not all(isinstance(x, str) and x for x in remedies):
        raise InputError("allowed_remedies must be a non-empty list of strings")
    agent_limit = money(policy.get("agent_limit"), "policy.agent_limit")
    manager_limit = money(policy.get("manager_limit"), "policy.manager_limit")
    if agent_limit > manager_limit:
        raise InputError("agent_limit cannot exceed manager_limit")
    if currency != policy_currency:
        raise InputError("proposal and policy currency must match")

    reasons: list[str] = []
    if missing_ids:
        reasons.append("MISSING_EVIDENCE")
    if remedy not in remedies:
        reasons.append("REMEDY_OUTSIDE_POLICY")
    if amount > manager_limit:
        reasons.append("EXCEEDS_MANAGER_LIMIT")
    if severity == "critical":
        reasons.append("CRITICAL_FAILURE")
    if "MISSING_EVIDENCE" in reasons:
        status = "needs_evidence"
    elif reasons:
        status = "policy_exception"
    elif amount > agent_limit:
        status = "manager_review"
    else:
        status = "agent_review"

    return {
        "schema_version": 1,
        "case_id": case_id,
        "policy_version": version,
        "status": status,
        "reason_codes": reasons,
        "missing_evidence_ids": sorted(set(missing_ids)),
        "severity": severity,
        "evidence_ids": sorted(evidence_ids),
        "action": {
            "remedy": remedy,
            "amount": f"{amount:.2f}",
            "currency": currency,
            "owner": owner,
            "follow_up_due": due,
        },
    }


def record(db_path: str, packet: dict, outcome: dict) -> None:
    """Insert one observed outcome; never overwrite an earlier audit record."""
    if packet.get("schema_version") != 1 or packet.get("status") not in {"agent_review", "manager_review", "policy_exception"}:
        raise InputError("only a current packet with sufficient evidence can be recorded")
    case_id = require_text(packet.get("case_id"), "packet.case_id")
    if not CASE_ID.fullmatch(case_id):
        raise InputError("packet.case_id is invalid")
    policy_version = require_text(packet.get("policy_version"), "packet.policy_version")
    action = packet.get("action")
    if not isinstance(action, dict):
        raise InputError("packet.action must be an object")
    remedy = require_text(action.get("remedy"), "packet.action.remedy")
    amount = money(action.get("amount"), "packet.action.amount")
    actual_amount = money(outcome.get("actual_amount"), "outcome.actual_amount")
    if actual_amount > amount:
        raise InputError("actual_amount exceeds the assessed proposal; reassess the case")
    currency = require_text(action.get("currency"), "packet.action.currency")
    resolution = outcome.get("resolution")
    retained = outcome.get("retained")
    repeat = outcome.get("repeat_complaint")
    if resolution not in RESOLUTIONS or retained not in RETENTION or not isinstance(repeat, bool):
        raise InputError("outcome resolution, retained, or repeat_complaint is invalid")
    approval_ref = outcome.get("approval_ref", "")
    if actual_amount > 0:
        approval_ref = require_text(approval_ref, "outcome.approval_ref")
    elif not isinstance(approval_ref, str):
        raise InputError("outcome.approval_ref must be a string")
    exception_ref = outcome.get("exception_approval_ref", "")
    if packet["status"] == "policy_exception":
        exception_ref = require_text(exception_ref, "outcome.exception_approval_ref")
    elif not isinstance(exception_ref, str):
        raise InputError("outcome.exception_approval_ref must be a string")
    recorded_at = require_date(outcome.get("recorded_at"), "outcome.recorded_at")
    amount_cents = int(actual_amount * 100)

    # The ledger intentionally omits complaint text and evidence observations.
    with closing(sqlite3.connect(db_path, timeout=10)) as connection:
      with connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS outcomes (
            case_id TEXT PRIMARY KEY, policy_version TEXT NOT NULL,
            review_status TEXT NOT NULL, remedy TEXT NOT NULL,
            amount_cents INTEGER NOT NULL, currency TEXT NOT NULL,
            resolution TEXT NOT NULL, retained TEXT NOT NULL,
            repeat_complaint INTEGER NOT NULL, approval_ref TEXT NOT NULL,
            exception_approval_ref TEXT NOT NULL,
            recorded_at TEXT NOT NULL)""")
        try:
            connection.execute("INSERT INTO outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (case_id, policy_version, packet["status"], remedy,
                                amount_cents, currency, resolution, retained,
                                int(repeat), approval_ref, exception_ref, recorded_at))
        except sqlite3.IntegrityError as exc:
            raise InputError(f"case {case_id} is already recorded") from exc


def report(db_path: str) -> dict:
    """Summarize observed outcomes without claiming causal business impact."""
    if not Path(db_path).is_file():
        raise InputError("ledger does not exist")
    with closing(sqlite3.connect(db_path)) as connection:
        try:
            rows = connection.execute("SELECT currency, resolution, retained, repeat_complaint, amount_cents FROM outcomes").fetchall()
        except sqlite3.OperationalError as exc:
            raise InputError("ledger schema is missing or invalid") from exc
    by_currency: dict[str, dict] = {}
    for currency, resolution, retained, repeat, cents in rows:
        stats = by_currency.setdefault(currency, {"cases": 0, "resolved": 0, "repeat_complaints": 0,
                                                 "retained_yes": 0, "retained_no": 0,
                                                 "retained_unknown": 0, "concession_cents": 0})
        stats["cases"] += 1
        stats["resolved"] += resolution == "resolved"
        stats["repeat_complaints"] += bool(repeat)
        stats[f"retained_{retained}"] += 1
        stats["concession_cents"] += cents
    for stats in by_currency.values():
        stats["concession_total"] = f"{Decimal(stats.pop('concession_cents')) / 100:.2f}"
        stats["known_retention_denominator"] = stats["retained_yes"] + stats["retained_no"]
    return {"schema_version": 1, "total_cases": len(rows), "by_currency": by_currency,
            "interpretation": "Descriptive outcomes only; no causal retention or ROI claim."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    assess_parser = commands.add_parser("assess", help="Create a policy-gated decision packet")
    assess_parser.add_argument("--case", required=True)
    assess_parser.add_argument("--policy", required=True)
    assess_parser.add_argument("--output", required=True)
    record_parser = commands.add_parser("record", help="Record an approved case outcome")
    record_parser.add_argument("--packet", required=True)
    record_parser.add_argument("--outcome", required=True)
    record_parser.add_argument("--db", required=True)
    report_parser = commands.add_parser("report", help="Summarize observed outcomes")
    report_parser.add_argument("--db", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "assess":
            packet = assess(read_json(args.case), read_json(args.policy))
            Path(args.output).write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"status": packet["status"], "output": args.output}))
        elif args.command == "record":
            record(args.db, read_json(args.packet), read_json(args.outcome))
            print(json.dumps({"recorded": True, "db": args.db}))
        else:
            print(json.dumps(report(args.db), indent=2))
    except (InputError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

