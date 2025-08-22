"""
Utility functions for public API tests.

Contains helper functions for logging, health checks, environment setup, and common operations.
"""

import subprocess
import time
import os
import requests
from typing import Optional
from pathlib import Path
import json


def show_backend_logs(lines: int = 50) -> None:
    """Show recent backend logs for debugging."""
    try:
        print(f"📋 Showing last {lines} lines of backend logs:")
        print("=" * 80)

        # First check what containers are running
        ps_result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=5
        )

        if ps_result.returncode == 0:
            containers = ps_result.stdout.strip().split("\n")
            backend_container = None

            # Look for backend container (might have different names)
            for container in containers:
                if "backend" in container.lower() and "airweave" in container.lower():
                    backend_container = container
                    break

            if not backend_container:
                # Fallback to default name
                backend_container = "airweave-backend"
                print(
                    f"⚠️  Backend container not found in running containers, trying default name: {backend_container}"
                )
                print(
                    f"   Running containers: {', '.join(containers) if containers[0] else 'none'}"
                )
        else:
            backend_container = "airweave-backend"
            print("⚠️  Could not list containers, using default name")

        # Get logs from the backend container
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), backend_container],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            has_output = False
            if result.stdout:
                print("STDOUT:")
                print(result.stdout)
                has_output = True
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
                has_output = True

            if not has_output:
                print("(No log output available)")
        else:
            print(f"Failed to get logs from {backend_container}: {result.stderr}")

            # Check container status specifically
            print(f"\n🔍 Checking status of {backend_container}:")
            inspect_result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    backend_container,
                    "--format",
                    "{{.State.Status}} - Exit Code: {{.State.ExitCode}} - Error: {{.State.Error}}",
                ],
                capture_output=True,
                text=True,
            )
            if inspect_result.returncode == 0:
                print(f"Container state: {inspect_result.stdout.strip()}")

            # Try to get logs anyway, even if container is in error state
            print(f"\n📋 Attempting to force get logs from {backend_container}:")
            force_logs = subprocess.run(
                ["docker", "logs", backend_container], capture_output=True, text=True, timeout=10
            )
            if force_logs.stdout or force_logs.stderr:
                if force_logs.stdout:
                    print("STDOUT:")
                    print(force_logs.stdout)
                if force_logs.stderr:
                    print("STDERR:")
                    print(force_logs.stderr)
            else:
                print("(No logs available from container)")

            # Check all containers
            print("\n🔍 All container statuses:")
            all_ps = subprocess.run(
                ["docker", "ps", "-a", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}"],
                capture_output=True,
                text=True,
            )
            if all_ps.returncode == 0:
                print(all_ps.stdout)

    except subprocess.TimeoutExpired:
        print("⚠️  Timeout getting backend logs")
    except Exception as e:
        print(f"⚠️  Error getting backend logs: {e}")
    finally:
        print("=" * 80)


def wait_for_health(url: str, timeout: int = 300, show_logs_interval: int = 30) -> bool:
    """Wait for service to be healthy.

    Args:
        url: The URL to check health
        timeout: Maximum time to wait in seconds
        show_logs_interval: Show backend logs every N seconds while waiting
    """
    print(f"Waiting for {url} to be healthy (timeout: {timeout}s)...")
    start_time = time.time()
    last_error = None
    error_count = 0
    last_log_time = 0

    # Check if we're in CI environment
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"
    if is_ci:
        print("🔍 Running in CI environment - will show logs more frequently")
        show_logs_interval = 15  # Show logs more frequently in CI

    while time.time() - start_time < timeout:
        elapsed = time.time() - start_time

        # Show logs periodically while waiting
        if elapsed - last_log_time >= show_logs_interval:
            print(f"\n📋 Health check still waiting after {elapsed:.0f}s - checking backend logs:")
            show_backend_logs(lines=20)
            last_log_time = elapsed
            print(f"Continuing health check...")

        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                print("\n✓ Service is healthy")
                return True
            else:
                last_error = f"HTTP {response.status_code}: {response.text}"
                error_count += 1
                # Log HTTP errors more frequently in CI
                if is_ci and error_count % 5 == 1:
                    print(f"\n⚠️  Health check HTTP error (#{error_count}): {last_error}")
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            error_count += 1
            # Only log errors occasionally to avoid spam
            if error_count % 10 == 1:  # Log every 10th error
                print(f"\n⚠️  Health check error (#{error_count}): {e}")

        time.sleep(2)
        print(".", end="", flush=True)

    elapsed = time.time() - start_time
    print(f"\n✗ Service health check timed out after {elapsed:.1f}s")
    if last_error:
        print(f"  Last error: {last_error}")

    # Show final logs on timeout
    print("\n📋 Final backend logs after timeout:")
    show_backend_logs(lines=50)

    return False


def start_local_services(openai_api_key: Optional[str] = None) -> bool:
    """Start local services using start.sh script."""
    print("Starting local services...")

    # Find the repository root (where start.sh is located)
    current_dir = Path(__file__).resolve()
    repo_root = (
        current_dir.parent.parent.parent.parent.parent.parent
    )  # Go up from backend/tests/e2e/smoke/public_api_tests/utils.py
    start_script = repo_root / "start.sh"

    if not start_script.exists():
        print(f"✗ start.sh not found at {start_script}")
        return False

    # Prepare automated responses for the interactive prompts
    if openai_api_key:
        # If we have an API key, answer 'y' and provide the key, then 'n' for Mistral
        automated_input = f"y\n{openai_api_key}\nn\ny\n"
    else:
        # If no API key, answer 'n' to both API key prompts, 'y' to remove containers
        automated_input = "n\nn\ny\n"

    # Set environment variables to suppress Azure credential warnings
    env = os.environ.copy()
    env.update(
        {
            "AZURE_CLIENT_ID": "",
            "AZURE_CLIENT_SECRET": "",
            "AZURE_TENANT_ID": "",
            "AZURE_USERNAME": "",
            "AZURE_PASSWORD": "",
            "MSI_ENDPOINT": "",  # Disable managed identity
            "IMDS_ENDPOINT": "",  # Disable IMDS
        }
    )

    try:
        # Run start.sh script with automated input
        process = subprocess.Popen(
            ["bash", str(start_script)],
            cwd=str(repo_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,  # Pass environment variables to suppress Azure warnings
        )

        # Send automated responses
        process.stdin.write(automated_input)
        process.stdin.flush()
        process.stdin.close()  # Close stdin to prevent hanging

        # Monitor output
        services_started = False
        is_ci = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"

        # In CI, show more detailed output
        if is_ci:
            print("📋 Detailed startup output (CI mode):")

        for line in process.stdout:
            # Always print the line
            print(f"  {line.strip()}")

            # Check for success
            if "All services started successfully!" in line:
                services_started = True
                break

            # Check for various error indicators
            if any(
                err in line.lower()
                for err in ["error:", "failed", "exception", "cannot", "unable", "unhealthy"]
            ):
                print(f"⚠️  Potential error detected: {line.strip()}")

                # If backend container failed, immediately try to get its logs
                if "airweave-backend" in line and any(
                    err in line.lower() for err in ["error", "unhealthy", "failed"]
                ):
                    print("\n🚨 Backend container error detected - getting logs immediately:")
                    show_backend_logs(lines=100)

                    # Also check container inspect for more details
                    print("\n🔍 Backend container detailed status:")
                    try:
                        inspect_result = subprocess.run(
                            ["docker", "inspect", "airweave-backend"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if inspect_result.returncode == 0:
                            import json

                            container_data = json.loads(inspect_result.stdout)[0]
                            state = container_data.get("State", {})
                            print(f"  Status: {state.get('Status', 'unknown')}")
                            print(f"  Running: {state.get('Running', False)}")
                            print(f"  Exit Code: {state.get('ExitCode', 'N/A')}")
                            print(f"  Error: {state.get('Error', 'None')}")
                            print(
                                f"  Health Status: {state.get('Health', {}).get('Status', 'N/A')}"
                            )

                            # Show last health check log if available
                            health_log = state.get("Health", {}).get("Log", [])
                            if health_log:
                                print(f"  Last health check: {health_log[-1].get('Output', 'N/A')}")
                    except Exception as e:
                        print(f"  Could not inspect container: {e}")

            # In CI, also check Docker status periodically
            if is_ci and "Starting" in line:
                try:
                    # Show docker ps to see container status
                    docker_ps = subprocess.run(
                        ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if docker_ps.returncode == 0:
                        print("\n📊 Current container status:")
                        print(docker_ps.stdout)
                except Exception as e:
                    print(f"Could not check docker status: {e}")

        # Wait for process to complete (but with longer timeout since Docker health checks take time)
        return_code = process.wait(timeout=180)  # 3 minutes for Docker to pull images and start

        if return_code != 0:
            print(f"✗ start.sh exited with code {return_code}")

            # Try to get backend logs before failing
            print("\n📋 Attempting to get backend logs after startup failure:")
            show_backend_logs(lines=50)

            # Also show all container statuses
            print("\n📊 Container statuses after failure:")
            try:
                ps_result = subprocess.run(
                    ["docker", "ps", "-a", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if ps_result.returncode == 0:
                    print(ps_result.stdout)
            except Exception as e:
                print(f"Could not check container status: {e}")

            return False

        if not services_started:
            print("✗ Services did not start successfully")

            # Try to get backend logs
            print("\n📋 Attempting to get backend logs after incomplete startup:")
            show_backend_logs(lines=50)

            return False

        print("✓ Services started and should be healthy")
        return True

    except subprocess.TimeoutExpired:
        print("✗ start.sh script timed out (Docker may be slow)")
        process.kill()

        # Try to get logs on timeout too
        print("\n📋 Attempting to get backend logs after timeout:")
        show_backend_logs(lines=50)

        return False
    except Exception as e:
        print(f"✗ Failed to start local services: {e}")

        # Try to get logs on any error
        print("\n📋 Attempting to get backend logs after error:")
        show_backend_logs(lines=50)

        return False


def get_api_url(env: str) -> str:
    """Get API URL based on environment."""
    urls = {
        "local": "http://localhost:8001",
        "dev": "https://api.dev-airweave.com",
        "prod": "https://api.airweave.ai",
    }
    return urls[env]


def setup_environment(env: str, openai_api_key: Optional[str] = None) -> Optional[str]:
    """Setup environment and return API URL if successful."""
    api_url = get_api_url(env)

    # Debug info for CI
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"
    if is_ci:
        print("\n🔍 CI Environment Debug Info:")
        print(f"  - Running in GitHub Actions: {os.environ.get('GITHUB_ACTIONS', 'false')}")
        print(f"  - CI flag: {os.environ.get('CI', 'false')}")
        print(f"  - Current directory: {os.getcwd()}")
        print(f"  - Docker version check:")
        try:
            docker_version = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            print(f"    {docker_version.stdout.strip()}")
            docker_compose_version = subprocess.run(
                ["docker", "compose", "version"], capture_output=True, text=True
            )
            print(f"    {docker_compose_version.stdout.strip()}")
        except Exception as e:
            print(f"    Error checking Docker: {e}")

    if env == "local":
        # Start local services (they should be healthy when this completes)
        if not start_local_services(openai_api_key):
            return None

        # Health check to verify backend is accessible (longer timeout for full initialization)
        print("Verifying backend is accessible...")
        if not wait_for_health(api_url, timeout=120):  # Increased from 30 to 120 seconds
            print("✗ Backend is not responding after 2 minutes")
            print("📋 Checking backend logs for debugging...")
            show_backend_logs()
            return None

    else:
        # For dev/prod, just check if API is reachable
        print(f"Checking {env} API availability...")
        if not wait_for_health(api_url, timeout=30):
            print(f"✗ {env.upper()} API is not reachable")
            return None

    print(f"✓ Using API URL: {api_url}")
    return api_url
