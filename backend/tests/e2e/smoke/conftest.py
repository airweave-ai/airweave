"""Smoke-test fixtures.

Provides a publicly reachable webhook endpoint (via postb.in) so that:

1. The Airweave backend can verify the URL on subscription creation.
2. The Svix container can actually deliver webhooks to it.

postb.in is a free HTTP request bin that accepts any POST and returns
200.  It is reachable from both the test host *and* from inside Docker
containers, which sidesteps all the host.docker.internal / ngrok /
firewall headaches.
"""

import httpx
import pytest


POSTBIN_API = "https://www.postb.in/api/bin"


@pytest.fixture(scope="function")
def webhook_receiver():
    """Create a postb.in bin for the duration of a single test.

    Each test gets its own bin to avoid cross-contamination when tests
    run concurrently (pytest-xdist).  postb.in's ``/req/shift`` pops
    requests, so a shared bin would let concurrent tests steal each
    other's deliveries.

    Yields a dict with:
        url   – a publicly reachable URL that accepts POST and returns 200.
        bin_id – the postbin identifier (for manual inspection if needed).
    """
    try:
        resp = httpx.post(POSTBIN_API, timeout=15.0)
        resp.raise_for_status()
        bin_data = resp.json()
        bin_id = bin_data["binId"]
    except Exception as exc:
        pytest.fail(f"Failed to create postbin: {exc}")

    url = f"https://www.postb.in/{bin_id}"

    # Warm-up: first request to a fresh bin can be slow.
    try:
        httpx.post(url, json={"warmup": True}, timeout=10.0)
    except Exception:
        pass

    yield {"url": url, "bin_id": bin_id}
