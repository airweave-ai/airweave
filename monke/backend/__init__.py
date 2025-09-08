"""Monke backend package.

FastAPI app lives in `monke.backend.app`. WebSockets are used for live logs.
In-process queues are used for log and run-state fan-out; no external Pub/Sub.
"""
