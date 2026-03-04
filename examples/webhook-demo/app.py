"""Airweave Webhook Demo Receiver.

A minimal FastAPI app that receives Airweave webhook events and streams them
to a browser UI in real time via WebSocket. Optionally verifies Svix signatures.

Usage:
    uvicorn app:app --port 8000
"""

import base64
import hashlib
import hmac
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Airweave Webhook Receiver")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# ---------------------------------------------------------------------------
# Ngrok tunnel detection
# ---------------------------------------------------------------------------

NGROK_API = "http://127.0.0.1:4040/api/tunnels"
ngrok_public_url: str | None = None


async def detect_ngrok_url() -> str | None:
    """Try to discover the ngrok public URL from its local API."""
    global ngrok_public_url
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(NGROK_API, timeout=2.0)
            tunnels = resp.json().get("tunnels", [])
            for t in tunnels:
                if t.get("proto") == "https":
                    ngrok_public_url = t["public_url"]
                    return ngrok_public_url
            if tunnels:
                ngrok_public_url = tunnels[0].get("public_url")
                return ngrok_public_url
    except Exception:
        pass
    return None


@app.on_event("startup")
async def startup_detect_ngrok() -> None:
    await detect_ngrok_url()


# ---------------------------------------------------------------------------
# Signing secret & verification
# ---------------------------------------------------------------------------

signing_secret: str | None = None


def verify_signature(secret: str, payload_bytes: bytes, headers: dict[str, str]) -> bool:
    """Verify Svix webhook signature.

    Svix signs with: HMAC-SHA256(base64decode(secret), "{msg_id}.{timestamp}.{body}")
    The secret has a 'whsec_' prefix that must be stripped before base64-decoding.
    """
    msg_id = headers.get("webhook-id", "")
    timestamp = headers.get("webhook-timestamp", "")
    signatures = headers.get("webhook-signature", "")

    print(f"[verify] msg_id={msg_id!r}")
    print(f"[verify] timestamp={timestamp!r}")
    print(f"[verify] signature_count={len(signatures.split())}")
    print(f"[verify] secret_length={len(secret)}")
    print(f"[verify] body_length={len(payload_bytes)}")

    if not msg_id or not timestamp or not signatures:
        print("[verify] FAIL: missing header fields")
        return False

    try:
        raw_secret = secret
        if raw_secret.startswith("whsec_"):
            raw_secret = raw_secret[6:]
        secret_bytes = base64.b64decode(raw_secret)
        print(f"[verify] decoded secret bytes length={len(secret_bytes)}")
    except Exception as e:
        print(f"[verify] FAIL: could not decode secret: {e}")
        return False

    # Construct the signed content
    body_str = payload_bytes.decode("utf-8")
    signed_content = f"{msg_id}.{timestamp}.{body_str}"
    expected = hmac.new(secret_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
    expected_b64 = base64.b64encode(expected).decode("utf-8")

    print(f"[verify] expected sig computed (length={len(expected_b64)})")

    # Svix sends space-separated signatures like "v1,<base64>"
    for sig in signatures.split(" "):
        parts = sig.split(",", 1)
        if len(parts) == 2 and parts[0] == "v1":
            print(f"[verify] comparing candidate signature (length={len(parts[1])})")
            if hmac.compare_digest(expected_b64, parts[1]):
                print("[verify] PASS")
                return True

    print("[verify] FAIL: no matching signature")
    return False


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections for broadcasting events."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)

    async def broadcast(self, data: dict[str, Any]) -> None:
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                self.active.remove(ws)


manager = ConnectionManager()

# Keep a rolling log so late-joining browsers get context
event_log: list[dict[str, Any]] = []

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the single-page frontend."""
    html = (Path(__file__).parent / "static" / "index.html").read_text()
    return HTMLResponse(html)


@app.get("/api/endpoint-url")
async def get_endpoint_url() -> dict[str, str]:
    """Return the best public endpoint URL (ngrok if available)."""
    if not ngrok_public_url:
        await detect_ngrok_url()
    if ngrok_public_url:
        return {"url": f"{ngrok_public_url}/webhook"}
    return {"url": "http://localhost:8000/webhook"}


@app.delete("/api/events")
async def clear_events() -> dict[str, str]:
    """Clear all stored events and notify connected browsers."""
    event_log.clear()
    await manager.broadcast({"type": "clear"})
    return {"status": "ok"}


@app.post("/api/secret")
async def set_secret(request: Request) -> dict[str, Any]:
    """Set or clear the signing secret used for verification."""
    global signing_secret
    body = await request.json()
    signing_secret = body.get("secret") or None
    await manager.broadcast({"type": "secret_updated", "has_secret": signing_secret is not None})
    return {"status": "ok", "has_secret": signing_secret is not None}


@app.get("/api/secret")
async def get_secret_status() -> dict[str, Any]:
    """Check if a signing secret is currently set."""
    return {"has_secret": signing_secret is not None}


@app.head("/webhook")
@app.head("/events")
@app.get("/webhook")
@app.get("/events")
async def webhook_health_check() -> dict[str, str]:
    """Respond to Svix health-check probes (HEAD/GET)."""
    return {"status": "ok"}


@app.post("/webhook")
@app.post("/events")
async def receive_webhook(request: Request) -> dict[str, str]:
    """Receive an Airweave webhook event and broadcast it."""
    body_bytes = await request.body()
    body = await request.json()

    # Signature verification — Svix sends both svix-* and webhook-* headers
    verified: bool | None = None  # None = no secret configured
    if signing_secret:
        hdrs = {
            "webhook-id": request.headers.get("webhook-id") or request.headers.get("svix-id", ""),
            "webhook-timestamp": request.headers.get("webhook-timestamp") or request.headers.get("svix-timestamp", ""),
            "webhook-signature": request.headers.get("webhook-signature") or request.headers.get("svix-signature", ""),
        }
        verified = verify_signature(signing_secret, body_bytes, hdrs)

    envelope = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "verified": verified,
        "headers": {
            "content-type": request.headers.get("content-type", ""),
            "user-agent": request.headers.get("user-agent", ""),
            "webhook-id": request.headers.get("webhook-id") or request.headers.get("svix-id", ""),
            "webhook-timestamp": request.headers.get("webhook-timestamp") or request.headers.get("svix-timestamp", ""),
        },
        "payload": body,
    }

    event_log.append(envelope)
    if len(event_log) > 200:
        event_log.pop(0)

    await manager.broadcast(envelope)
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Stream events to the browser in real time."""
    await manager.connect(ws)

    try:
        await ws.send_json({"type": "history", "events": event_log})
    except Exception:
        manager.disconnect(ws)
        return

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
