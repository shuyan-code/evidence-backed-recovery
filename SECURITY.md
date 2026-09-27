# Security and privacy

Please report a security issue privately through the repository's GitHub Security advisory feature if available. Otherwise open an issue without exploit details or customer data and request a private contact route.

The CLI runs locally and makes no network requests. It compares a decision packet with a fresh assessment of the supplied case and policy; this detects a stale or edited packet but does not authenticate the files, evidence references, or approval references. It does not authorize compensation, send messages, or operate a payment system. Integrations that perform actions must independently verify policy version, reviewer authority, approval references, and the current case state at execution time.

Use pseudonymous case IDs. Do not place names, contact details, secrets, full transcripts, or payment data in inputs or the SQLite ledger. Protect and delete local case files under your organization's data handling rules. SQLite is not encrypted by this project.
