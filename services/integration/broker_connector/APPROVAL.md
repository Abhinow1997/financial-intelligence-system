# Approval Policy - Broker Connector

This is a **state-changing, potentially irreversible** integration.

- All order actions route through the `policy_engine` approval gate.
- Read-only endpoints (positions, balances) may run without approval.
- Every action is idempotent (client order id) and audited.
