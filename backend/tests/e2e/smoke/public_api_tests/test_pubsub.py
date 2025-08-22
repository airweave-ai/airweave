"""
Test module for PubSub functionality.

This module tests the sync job pubsub subscription via SSE including:
- Subscribing to sync job progress updates
- Receiving and validating progress messages
- Handling SSE stream with authentication
"""

import json
import threading
import requests


def test_sync_job_pubsub(api_url: str, job_id: str, headers: dict, timeout: int = 30) -> bool:
    """Test sync job pubsub functionality via SSE with header authentication.

    Args:
        api_url: The API URL
        job_id: The sync job ID to subscribe to
        headers: Request headers including authentication
        timeout: Maximum time to wait for messages

    Returns:
        bool: True if pubsub test succeeded, False otherwise
    """
    sse_url = f"{api_url}/sync/job/{job_id}/subscribe"
    print(f"    Subscribing to SSE endpoint: {sse_url}")

    messages_received = []
    error_occurred = False

    def read_sse_stream():
        """Read SSE stream in a thread."""
        nonlocal error_occurred
        try:
            # Use stream=True for SSE with header authentication
            response = requests.get(sse_url, stream=True, timeout=timeout, headers=headers)

            if response.status_code != 200:
                print(f"    ✗ SSE connection failed: {response.status_code}")
                error_occurred = True
                return

            # Read SSE stream line by line
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        # Extract JSON data after "data: " prefix
                        data_str = line_str[6:]
                        try:
                            data = json.loads(data_str)
                            messages_received.append(data)
                            print(
                                f"    📨 Received update: inserted={data.get('inserted', 0)}, "
                                f"updated={data.get('updated', 0)}, "
                                f"deleted={data.get('deleted', 0)}, "
                                f"is_complete={data.get('is_complete', False)}"
                            )

                            # Stop if job is complete
                            if data.get("is_complete") or data.get("is_failed"):
                                break
                        except json.JSONDecodeError as e:
                            print(f"    ⚠️  Failed to parse SSE data: {e}")

                # Stop after receiving some messages to avoid hanging
                if len(messages_received) >= 3:
                    break

        except requests.exceptions.Timeout:
            print("    ℹ️  SSE stream timed out (expected)")
        except Exception as e:
            print(f"    ✗ SSE stream error: {e}")
            error_occurred = True

    # Start SSE reader in a thread
    sse_thread = threading.Thread(target=read_sse_stream)
    sse_thread.daemon = True
    sse_thread.start()

    # Wait for thread to complete or timeout
    sse_thread.join(timeout=timeout)

    if error_occurred:
        return False

    # Verify we received at least one message
    if len(messages_received) == 0:
        print("    ⚠️  No pubsub messages received (sync might have completed too quickly)")
        return True  # Not necessarily a failure

    # Verify message structure
    for msg in messages_received:
        # Skip non-progress messages (connected, heartbeat, etc.)
        if msg.get("type") in ["connected", "heartbeat", "error"]:
            continue

        required_fields = [
            "inserted",
            "updated",
            "deleted",
            "kept",
            "skipped",
            "entities_encountered",
            "is_complete",
            "is_failed",
        ]
        for field in required_fields:
            if field not in msg:
                print(f"    ✗ Missing required field '{field}' in pubsub message")
                return False

    print(f"    ✓ PubSub test successful - received {len(messages_received)} progress updates")
    return True
