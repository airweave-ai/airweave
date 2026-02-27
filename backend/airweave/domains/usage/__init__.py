"""Usage domain — enforcement, tracking, and limit management.

Use Inject(UsageServiceFactoryProtocol) in FastAPI endpoints to get the
container-managed factory, then call factory.create(organization_id, logger)
to obtain a per-organization UsageGuardrailProtocol instance.
"""
