"""Behavioral tests for policy boundaries and the outcome ledger."""

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "evidence-backed-recovery" / "scripts" / "recovery.py"
SPEC = importlib.util.spec_from_file_location("recovery", SCRIPT)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def fixture():
    case = {
        "case_id": "CASE-1042", "severity": "high", "failure": "Scheduled export failed.",
        "repair_action": "Restore the export schedule and monitor three runs.",
        "recovery_criterion": "Three consecutive scheduled exports complete successfully.",
        "evidence": [
            {"id": "E1", "kind": "independent_record", "source": "incident-482", "observation": "Export failed three times."},
            {"id": "E2", "kind": "customer_statement", "source": "ticket-1042", "observation": "Customer reported a launch delay."},
        ],
        "claim_evidence_ids": ["E1", "E2"],
        "emotion_signal": {"label": "frustration", "evidence_id": "E2"},
        "proposal": {"remedy": "service_credit", "amount": "75.00", "currency": "USD",
                     "owner": "support-lead", "follow_up_due": "2026-09-01"},
    }
    policy = {"version": "2026-Q3", "currency": "USD", "allowed_remedies": ["repair", "service_credit"],
              "agent_limit": "25.00", "manager_limit": "100.00", "minimum_repeat_window_days": 7}
    outcome = {"resolution": "resolved", "resolution_basis": "independent_record",
               "resolution_evidence_ref": "monitoring-771", "retained": "unknown",
               "repeat_complaint": False, "repeat_window_end": "2026-09-08",
               "repeat_check_ref": "ticket-query-771", "actual_amount": "75.00",
               "follow_up_completed_at": "2026-09-01",
               "approval_ref": "approval-317", "recorded_at": "2026-09-09"}
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
                recovery.record(str(Path(directory) / "ledger.db"), packet, fixture()[2], case, policy)

    def test_customer_statement_alone_cannot_verify_failure(self):
        case, policy, _ = fixture()
        case["claim_evidence_ids"] = ["E2"]
        packet = recovery.assess(case, policy)
        self.assertEqual(packet["status"], "needs_evidence")
        self.assertIn("independent_record", packet["missing_evidence_ids"])

    def test_emotion_signal_must_reference_customer_statement(self):
        case, policy, _ = fixture()
        case["emotion_signal"]["evidence_id"] = "E1"
        with self.assertRaises(recovery.InputError):
            recovery.assess(case, policy)

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
                recovery.record(str(Path(directory) / "ledger.db"), packet, outcome, case, policy)

    def test_actual_cost_cannot_exceed_proposal(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        outcome["actual_amount"] = "75.01"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(recovery.InputError):
                recovery.record(str(Path(directory) / "ledger.db"), packet, outcome, case, policy)

    def test_exception_requires_exception_approval(self):
        case, policy, outcome = fixture()
        case["severity"] = "critical"
        packet = recovery.assess(case, policy)
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            with self.assertRaises(recovery.InputError):
                recovery.record(db, packet, outcome, case, policy)
            outcome["exception_approval_ref"] = "exception-42"
            recovery.record(db, packet, outcome, case, policy)
            self.assertEqual(recovery.report(db)["total_cases"], 1)

    def test_stale_or_edited_packet_cannot_be_recorded(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        changed_policy = deepcopy(policy)
        changed_policy["agent_limit"] = "80.00"
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            with self.assertRaises(recovery.InputError):
                recovery.record(db, packet, outcome, case, changed_policy)
            tampered = deepcopy(packet)
            tampered["action"]["amount"] = "99.00"
            with self.assertRaises(recovery.InputError):
                recovery.record(db, tampered, outcome, case, policy)
            self.assertFalse(Path(db).exists())

    def test_resolution_requires_evidence_and_mature_follow_up(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            for key, value in (("resolution_basis", "unverified"),
                               ("resolution_evidence_ref", ""),
                               ("repeat_window_end", "2026-09-07"),
                               ("repeat_window_end", "2026-09-10"),
                               ("follow_up_completed_at", "2026-09-10")):
                bad = deepcopy(outcome)
                bad[key] = value
                with self.subTest(key=key), self.assertRaises(recovery.InputError):
                    recovery.record(db, packet, bad, case, policy)

    def test_repeat_window_policy_rejects_invalid_values(self):
        case, policy, _ = fixture()
        for value in (0, 366, True, "7"):
            changed = deepcopy(policy)
            changed["minimum_repeat_window_days"] = value
            with self.subTest(value=value), self.assertRaises(recovery.InputError):
                recovery.assess(case, changed)

    def test_future_outcome_cannot_be_recorded(self):
        case, policy, outcome = fixture()
        outcome["recorded_at"] = (date.today() + timedelta(days=1)).isoformat()
        packet = recovery.assess(case, policy)
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            with self.assertRaisesRegex(recovery.InputError, "cannot be in the future"):
                recovery.record(db, packet, outcome, case, policy)
            self.assertFalse(Path(db).exists())

    def test_known_retention_requires_later_observation(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        outcome["retained"] = "yes"
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            with self.assertRaises(recovery.InputError):
                recovery.record(db, packet, outcome, case, policy)
            outcome["retention_observed_at"] = "2026-09-08"
            outcome["retention_evidence_ref"] = "renewal-482"
            recovery.record(db, packet, outcome, case, policy)
            self.assertEqual(recovery.report(db)["by_currency"]["USD"]["retained_yes"], 1)

    def test_existing_v1_ledger_migrates_without_promoting_legacy_evidence(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            with closing(sqlite3.connect(db)) as connection:
              with connection:
                connection.execute("""CREATE TABLE outcomes (
                    case_id TEXT PRIMARY KEY, policy_version TEXT, review_status TEXT,
                    remedy TEXT, amount_cents INTEGER, currency TEXT, resolution TEXT,
                    retained TEXT, repeat_complaint INTEGER, approval_ref TEXT,
                    exception_approval_ref TEXT, recorded_at TEXT)""")
                connection.execute("INSERT INTO outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   ("CASE-OLD", "2026-Q2", "agent_review", "service_credit",
                                    500, "USD", "resolved", "yes", 0, "approval-old", "", "2026-09-01"))
            recovery.record(db, packet, outcome, case, policy)
            stats = recovery.report(db)["by_currency"]["USD"]
            self.assertEqual(stats["cases"], 2)
            self.assertEqual(stats["verified_cases"], 1)
            self.assertEqual(stats["legacy_unverified_cases"], 1)
            self.assertEqual(stats["resolved"], 1)
            self.assertEqual(stats["concession_total"], "80.00")
            self.assertEqual(stats["verified_concession_total"], "75.00")
            self.assertEqual(stats["rates"]["evidence_coverage"],
                             {"numerator": 1, "denominator": 2, "percent": 50.0})

    def test_record_is_unique_and_report_uses_known_retention_denominator(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            recovery.record(db, packet, outcome, case, policy)
            with self.assertRaises(recovery.InputError):
                recovery.record(db, packet, outcome, case, policy)
            second_case = deepcopy(case)
            second_case["case_id"] = "CASE-1043"
            second_case["proposal"]["amount"] = "25.00"
            second = recovery.assess(second_case, policy)
            other_outcome = deepcopy(outcome)
            other_outcome.update({"resolution": "unresolved", "retained": "no", "repeat_complaint": True,
                                  "actual_amount": "20.00", "retention_observed_at": "2026-09-08",
                                  "retention_evidence_ref": "renewal-483"})
            other_outcome["resolution_basis"] = "unverified"
            other_outcome["resolution_evidence_ref"] = ""
            recovery.record(db, second, other_outcome, second_case, policy)
            report = recovery.report(db)
            stats = report["by_currency"]["USD"]
            self.assertEqual(stats["cases"], 2)
            self.assertEqual(stats["resolved"], 1)
            self.assertEqual(stats["repeat_complaints"], 1)
            self.assertEqual(stats["known_retention_denominator"], 1)
            self.assertEqual(stats["concession_total"], "95.00")
            self.assertEqual(stats["verified_concession_total"], "95.00")
            self.assertEqual(stats["follow_up_on_time"], 2)
            self.assertEqual(stats["rates"]["verified_resolution"]["percent"], 50.0)
            self.assertEqual(stats["rates"]["repeat_complaint"]["percent"], 50.0)
            self.assertEqual(stats["rates"]["on_time_follow_up"],
                             {"numerator": 2, "denominator": 2, "percent": 100.0})
            self.assertEqual(stats["rates"]["retention_observation_coverage"]["percent"], 50.0)
            self.assertEqual(stats["rates"]["retained_among_known"]["percent"], 0.0)

    def test_report_excludes_records_missing_required_outcome_evidence(self):
        case, policy, outcome = fixture()
        packet = recovery.assess(case, policy)
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "ledger.db")
            recovery.record(db, packet, outcome, case, policy)
            with closing(sqlite3.connect(db)) as connection:
                with connection:
                    connection.execute("UPDATE outcomes SET repeat_check_ref = NULL")
            stats = recovery.report(db)["by_currency"]["USD"]
            self.assertEqual(stats["verified_cases"], 0)
            self.assertEqual(stats["incomplete_unverified_cases"], 1)
            self.assertIsNone(stats["rates"]["verified_resolution"]["percent"])

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
                                            "--case", str(root / "case.json"),
                                            "--policy", str(root / "policy.json"),
                                            "--outcome", str(root / "outcome.json"), "--db", str(db)]), 0)
            self.assertEqual(recovery.main(["report", "--db", str(db)]), 0)


if __name__ == "__main__":
    unittest.main()
