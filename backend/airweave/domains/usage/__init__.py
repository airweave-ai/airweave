"""Usage domain — limit checking, ledger, and billing event handling.

Use Inject(UsageLimitCheckerProtocol) in FastAPI endpoints for the singleton checker.
Use Inject(UsageLedgerProtocol) for the singleton ledger.
Billing events are handled automatically by UsageBillingListener via the EventBus.
"""
