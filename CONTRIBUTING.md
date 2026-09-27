# Contributing

Issues and pull requests are welcome. Describe the business case, expected behavior, and evidence for proposed policy changes. Use synthetic or fully de-identified examples; do not post customer transcripts, contact details, credentials, or internal approval records.

## Local checks

Python 3.11+ is required. From the repository root:

```bash
python -m unittest discover -s tests -v
python path/to/skill-creator/scripts/quick_validate.py skills/evidence-backed-recovery
```

The second command uses the Codex skill-creator validator when available; CI performs structural checks independently on Windows and Linux. Keep the skill's description narrow, preserve the distinction between a proposal and authorization, and add behavioral tests for policy, evidence, observation windows, and ledger migrations. Update the skill contract, examples, README, and market analysis when an interface or product claim changes.

All project code, comments, skill instructions, and documentation are in English.
