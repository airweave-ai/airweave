"""Docker container management utilities for integration and E2E tests.

This module provides utilities to manage Docker Compose environments for testing.
"""

import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Tuple

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

# Use a static project name for all test runs to enable container reuse
DEFAULT_PROJECT_NAME = "airweave-test-env"


class DockerComposeManager:
    """A manager for Docker Compose environments in tests.

    This class provides methods to start and stop Docker Compose environments
    for integration and E2E tests.
    """

    def __init__(
        self,
        compose_file: str = "docker/docker-compose.test.yml",
        env_vars: Optional[Dict[str, str]] = None,
        minimal_services: Optional[bool] = False,
    ):
        """Initialize a Docker Compose manager.

        Args:
            compose_file: Path to the docker-compose file, relative to tests directory
            env_vars: Optional environment variables to pass to docker-compose
            minimal_services: If True, only start essential services like databases
        """
        # Get the tests directory
        self.tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Full path to the compose file
        self.compose_file = os.path.join(self.tests_dir, compose_file)

        # Make sure file exists
        if not os.path.exists(self.compose_file):
            raise FileNotFoundError(f"Compose file not found: {self.compose_file}")

        # Store current working directory
        self.cwd = os.getcwd()

        self.env_vars = env_vars or {}
        self.minimal_services = minimal_services
        self.is_running = False
        self.managed_services = []

        # Determine which Docker Compose command to use
        self.compose_cmd, self.compose_version = self._get_docker_compose_command()

        logger.info(
            f"Initialized Docker Compose manager with file: {self.compose_file} "
            f"(project: {DEFAULT_PROJECT_NAME}, using {self.compose_cmd} v{self.compose_version})"
        )

    def _get_docker_compose_command(self) -> Tuple[List[str], str]:
        """Determine which Docker Compose command to use.

        Returns:
            A tuple containing the command as a list and the version string
        """
        # Try docker compose (v2) first
        try:
            result = subprocess.run(
                ["docker", "compose", "version"], check=True, capture_output=True, text=True
            )
            version = result.stdout.strip()
            return ["docker", "compose"], version
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Try docker-compose (v1) next
            try:
                result = subprocess.run(
                    ["docker-compose", "--version"], check=True, capture_output=True, text=True
                )
                version = result.stdout.strip()
                return ["docker-compose"], version
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise RuntimeError(f"Docker Compose not available: {e}") from e

    def _are_services_running(self, services: Optional[List[str]] = None) -> bool:
        """Check if the specified services are already running.

        Args:
            services: List of services to check, or None to check all services

        Returns:
            True if all services are running, False otherwise
        """
        os.chdir(self.tests_dir)
        try:
            # Get list of running containers for this project
            cmd = [
                *self.compose_cmd,
                "-f",
                self.compose_file,
                "-p",
                DEFAULT_PROJECT_NAME,
                "ps",
                "-q",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            container_ids = [cid for cid in result.stdout.strip().split("\n") if cid]

            if not container_ids:
                return False

            # If no specific services were requested, just check if any containers are running
            if not services:
                return len(container_ids) > 0

            # Check if the specific services are running
            running_services = []
            for container_id in container_ids:
                inspect_cmd = [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.Config.Labels.com.docker.compose.service}}",
                    container_id,
                ]
                service_result = subprocess.run(
                    inspect_cmd, capture_output=True, text=True, check=True
                )
                service_name = service_result.stdout.strip()
                running_services.append(service_name)

            # Check if all requested services are running
            return all(service in running_services for service in services)
        except Exception as e:
            logger.debug(f"Error checking if services are running: {e}")
            return False
        finally:
            os.chdir(self.cwd)

    def start(
        self,
        services: Optional[List[str]] = None,
        wait_for_services: bool = True,
        force_rebuild: bool = False,
    ) -> None:
        """Start Docker Compose services."""
        if self.is_running:
            logger.info("Services are already running")
            return

        try:
            env = os.environ.copy()
            env["COMPOSE_PROJECT_NAME"] = DEFAULT_PROJECT_NAME

            if force_rebuild:
                # Build the backend container with no cache
                logger.info("Force rebuilding backend container...")
                build_cmd = [
                    *self.compose_cmd,
                    "-f",
                    self.compose_file,
                    "-p",
                    DEFAULT_PROJECT_NAME,
                    "build",
                    "--no-cache",
                    "backend",
                ]
                subprocess.run(build_cmd, check=True, env=env)

                # Stop and remove any existing backend container
                logger.info("Removing any existing backend container...")
                rm_cmd = [
                    *self.compose_cmd,
                    "-f",
                    self.compose_file,
                    "-p",
                    DEFAULT_PROJECT_NAME,
                    "rm",
                    "-f",
                    "backend",
                ]
                subprocess.run(rm_cmd, check=True, env=env)

            # Start services
            logger.info(f"Starting {'all' if not services else 'specified'} services...")
            start_cmd = [
                *self.compose_cmd,
                "-f",
                self.compose_file,
                "-p",
                DEFAULT_PROJECT_NAME,
                "up",
                "-d",
            ]
            if services:
                start_cmd.extend(services)

            subprocess.run(start_cmd, check=True, env=env)
            self.is_running = True

            # Wait for services to be ready if requested
            if wait_for_services:
                self.wait_for_services()

            logger.info("Services started successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"Docker command failed: {e}")
            raise
        finally:
            # Change back to original directory
            os.chdir(self.cwd)

    def stop(self, remove_volumes: bool = True) -> None:
        """Stop services using docker-compose.

        Args:
            remove_volumes: Whether to remove volumes when stopping
        """
        if not self.is_running:
            logger.info("Services are not running, nothing to stop")
            return

        # Change to tests directory
        os.chdir(self.tests_dir)

        try:
            # Only stop the backend service by default, keeping other services cached
            if "backend" in self.managed_services or not self.managed_services:
                logger.info("Stopping backend service...")
                stop_cmd = [
                    *self.compose_cmd,
                    "-f",
                    self.compose_file,
                    "-p",
                    DEFAULT_PROJECT_NAME,
                    "stop",
                    "backend",
                ]
                subprocess.run(stop_cmd, check=True)

                # Remove the backend container
                rm_cmd = [
                    *self.compose_cmd,
                    "-f",
                    self.compose_file,
                    "-p",
                    DEFAULT_PROJECT_NAME,
                    "rm",
                    "-f",
                    "backend",
                ]
                subprocess.run(rm_cmd, check=True)
                logger.info("Backend service has been stopped")

            # If explicitly asked to remove volumes, then stop all services
            if remove_volumes:
                logger.info("Removing volumes requested, stopping all services completely")
                cmd = [
                    *self.compose_cmd,
                    "-f",
                    self.compose_file,
                    "-p",
                    DEFAULT_PROJECT_NAME,
                    "down",
                    "-v",
                ]
                subprocess.run(cmd, check=True)
                logger.info("All services have been stopped and volumes removed")
            else:
                logger.info("Cached services are kept running for future test runs")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error stopping Docker Compose: {e}")
            raise
        finally:
            # Change back to original working directory
            os.chdir(self.cwd)
            # Mark services as not running for this instance
            self.is_running = False

    def _check_service_health(self, service):
        """Check if a single service is healthy.

        Args:
            service: Service health check configuration

        Returns:
            bool: True if service is healthy, False otherwise
        """
        service_name = service["name"]
        service_url = service["url"]
        expected_status = service["expected_status"]

        try:
            response = requests.get(service_url, timeout=2)
            if response.status_code != expected_status:
                logger.debug(
                    f"Service {service_name} not ready: "
                    + f"status code {response.status_code} "
                    + f"(expected {expected_status})"
                )
                return False
            return True
        except RequestException as e:
            logger.debug(f"Service {service_name} not ready: connection failed")
            logger.debug(f"Error: {e}")
            return False

    def _collect_container_logs(self):
        """Collect logs from all containers for debugging.

        Returns:
            Dict mapping container IDs to their logs
        """
        os.chdir(self.tests_dir)
        try:
            # Get list of running containers for this project
            cmd = [
                *self.compose_cmd,
                "-f",
                self.compose_file,
                "-p",
                DEFAULT_PROJECT_NAME,
                "ps",
                "-q",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            container_ids = [cid for cid in result.stdout.strip().split("\n") if cid]

            if not container_ids:
                return {}

            # Collect logs for each container
            logs = {}
            for cid in container_ids:
                if not cid:
                    continue
                try:
                    log_cmd = ["docker", "logs", cid]
                    log_result = subprocess.run(log_cmd, capture_output=True, text=True, check=True)
                    logs[cid] = log_result.stdout
                except subprocess.CalledProcessError:
                    logs[cid] = "Failed to collect logs"

            return logs
        except Exception as e:
            logger.error(f"Error collecting container logs: {e}")
            return {}
        finally:
            os.chdir(self.cwd)

    def wait_for_services(self, timeout: int = 120) -> None:
        """Wait for all services to be ready.

        Args:
            timeout: Maximum time to wait in seconds

        Raises:
            TimeoutError: If services don't become ready within timeout
        """
        logger.info(f"Waiting for services to be ready (timeout: {timeout}s)")

        # Define service health check endpoints
        health_checks = [
            {
                "name": "backend",
                "url": "http://localhost:9001/health",
                "expected_status": 200,
            }
        ]

        # Wait for all services to be ready
        start_time = time.time()
        services_ready = False

        while time.time() - start_time < timeout and not services_ready:
            pending_services = []

            for service in health_checks:
                if not self._check_service_health(service):
                    pending_services.append(service["name"])

            if not pending_services:
                services_ready = True
                logger.info("All services are ready")
                break

            logger.debug(f"Waiting for services: {', '.join(pending_services)}")
            time.sleep(2)

        if not services_ready:
            # Get logs to help diagnose issues
            logs = self._collect_container_logs()

            pending_services_str = ", ".join(
                [s["name"] for s in health_checks if s["name"] in pending_services]
            )
            error_msg = f"Services not ready within timeout: {pending_services_str}"
            if logs:
                error_msg += "\nContainer logs:\n"
                for container_id, container_logs in logs.items():
                    error_msg += f"\n--- Container {container_id} ---\n{container_logs}\n"

            raise TimeoutError(error_msg)
