"""Behavioral tests for policy boundaries and the outcome ledger."""

import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "evidence-backed-recovery" / "scripts" / "recovery.py"
SPEC = importlib.util.spec_from_file_location("recovery", SCRIPT)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def fixture():
    case = {
        "case_id": "CASE-1042", "severity": "high", "failure": "Scheduled export failed.",
        "evidence": [
            {"id": "E1", "source": "incident-482", "observation": "Export failed three times."},
            {"id": "E2", "source": "ticket-1042", "observation": "Customer reported a launch delay."},
        ],
        "claim_evidence_ids": ["E1", "E2"],
        "emotion_signal": {"label": "frustration", "evidence_id": "E2"},
        "proposal": {"remedy": "service_credit", "amount": "75.00", "currency": "USD",
                     "owner": "support-lead", "follow_up_due": "2026-10-01"},
    }
    policy = {"version": "2026-Q3", "currency": "USD", "allowed_remedies": ["repair", "service_credit"],
              "agent_limit": "25.00", "manager_limit": "100.00"}
    outcome = {"resolution": "resolved", "retained": "unknown", "repeat_complaint": False,
               "actual_amount": "75.00",
               "approval_ref": "approval-317", "recorded_at": "2026-10-02"}
    return case, policy, outcome


class RecoveryTests(unittest.TestCase):
    def test_manager_boundary_and_amount_precision(self):
        case, policy, _ = fixture()
        self.assertEqual(recovery.assess(case, policy)["status"], "manager_review")
        case["proposal"]["amount"] = "25.00"
        self.assertEqual(recovery.assess(case, policy)["status"], "agent_review")
        case["proposal"]["amount"] = "100.01"
        packet = recovery.assess(case, policy)
        self.assertEqual(packet["status"], "policy_exception")
        self.assertIn("EXCEEDS_MANAGER_LIMIT", packet["reason_codes"])

    def test_missing_evidence_blocks_case(self):
        case, policy, _ = fixture()
        case["claim_evidence_ids"].append("E404")
        packet = recovery.assess(case, policy)
        self.assertEqual(packet["status"], "needs_evidence")
        self.assertEqual(packet["missing_evidence_ids"], ["E404"])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(recovery.InputError):
                recovery.record(str(Path(directory) / "ledger.db"), packet, fixture()[2])

    def test_critical_and_unlisted_remedy_escalate(self):
        case, policy, _ = fixture()
        case["severity"] = "critical"
        case["proposal"]["remedy"] = "cash_refund"
        packet = recovery.assess(case, policy)
        self.assertEqual(packet["status"], "policy_exception")
        self.assertEqual(set(packet["reason_codes"]), {"CRITICAL_FAILURE", "REMEDY_OUTSIDE_POLICY"})

    def test_rejects_invalid_money_currency_and_duplicate_evidence(self):
        case, policy, _ = fixture()
        for amount in ("-1", "1.001", "NaN", 1.0):
            changed = deepcopy(case)
            changed["proposal"]["amount"] = amount
            with self.subTest(amount=amount), self.assertRaises(recovery.InputError):
                recovery.assess(changed, policy)
        case["proposal"]["currency"] = "EUR"
        with self.assertRaises(recovery.InputError):
            recovery.assess(case, policy)
        case["proposal"]["currency"] = "USD"
        case["evidence"].append(deepcopy(case["evidence"][0]))
        with self.assertRaises(recovery.InputError):
            recovery.assess(case, policy)

    def test_record_requires_actual_approval_reference(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        outcome["approval_ref"] = ""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(recovery.InputError):
                recovery.record(str(Path(directory) / "ledger.db"), packet, outcome)

    def test_actual_cost_cannot_exceed_proposal(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        outcome["actual_amount"] = "75.01"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(recovery.InputError):
                recovery.record(str(Path(directory) / "ledger.db"), packet, outcome)

    def test_exception_requires_exception_approval(self):
        case, policy, outcome = fixture()
        case["severity"] = "critical"
        packet = recovery.assess(case, policy)
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            with self.assertRaises(recovery.InputError):
                recovery.record(db, packet, outcome)
            outcome["exception_approval_ref"] = "exception-42"
            recovery.record(db, packet, outcome)
            self.assertEqual(recovery.report(db)["total_cases"], 1)

    def test_record_is_unique_and_report_uses_known_retention_denominator(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            recovery.record(db, packet, outcome)
            with self.assertRaises(recovery.InputError):
                recovery.record(db, packet, outcome)
            second = deepcopy(packet)
            second["case_id"] = "CASE-1043"
            second["action"]["amount"] = "25.00"
            other_outcome = deepcopy(outcome)
            other_outcome.update({"resolution": "unresolved", "retained": "no", "repeat_complaint": True,
                                  "actual_amount": "20.00"})
            recovery.record(db, second, other_outcome)
            report = recovery.report(db)
            stats = report["by_currency"]["USD"]
            self.assertEqual(stats["cases"], 2)
            self.assertEqual(stats["resolved"], 1)
            self.assertEqual(stats["repeat_complaints"], 1)
            self.assertEqual(stats["known_retention_denominator"], 1)
            self.assertEqual(stats["concession_total"], "95.00")

    def test_cli_round_trip(self):
        case, policy, outcome = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in (("case", case), ("policy", policy), ("outcome", outcome)):
                (root / f"{name}.json").write_text(json.dumps(content), encoding="utf-8")
            packet = root / "packet.json"
            db = root / "ledger.db"
            self.assertEqual(recovery.main(["assess", "--case", str(root / "case.json"),
                                            "--policy", str(root / "policy.json"), "--output", str(packet)]), 0)
            self.assertEqual(recovery.main(["record", "--packet", str(packet),
                                            "--outcome", str(root / "outcome.json"), "--db", str(db)]), 0)
            self.assertEqual(recovery.main(["report", "--db", str(db)]), 0)


if __name__ == "__main__":
    unittest.main()
