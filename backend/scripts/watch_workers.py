#!/usr/bin/env python3
"""Real-time dashboard for monitoring Temporal workers.

Usage:
    python scripts/watch_workers.py [--namespace airweave] [--interval 2]
    
Example:
    # Watch workers in default namespace
    python scripts/watch_workers.py
    
    # Watch workers in custom namespace
    python scripts/watch_workers.py --namespace my-namespace
    
    # Change refresh interval
    python scripts/watch_workers.py --interval 5
"""

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
except ImportError:
    print("Error: 'rich' library not found. Install it with:")
    print("  pip install rich")
    sys.exit(1)

try:
    import aiohttp
except ImportError:
    print("Error: 'aiohttp' library not found. Install it with:")
    print("  pip install aiohttp")
    sys.exit(1)


console = Console()


def get_worker_pods(namespace: str = "airweave") -> List[Dict[str, str]]:
    """Get all worker pods using kubectl.
    
    Returns:
        List of dicts with pod_name and status
    """
    try:
        cmd = [
            "kubectl", "get", "pods",
            "-n", namespace,
            "-l", "app.kubernetes.io/component=sync-worker",
            "-o", "json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        pods = []
        for item in data.get("items", []):
            pod_name = item["metadata"]["name"]
            status = item["status"]["phase"]
            
            # Get container status
            container_statuses = item["status"].get("containerStatuses", [])
            ready = False
            if container_statuses:
                ready = container_statuses[0].get("ready", False)
            
            pods.append({
                "name": pod_name,
                "status": status,
                "ready": ready,
            })
        
        return pods
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error getting pods: {e.stderr}[/red]")
        return []
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return []


async def fetch_pod_metrics(pod_name: str, namespace: str = "airweave", local_port: int = 18888) -> Optional[Dict[str, Any]]:
    """Fetch metrics from a single pod by creating a temporary port-forward.
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        local_port: Local port to use for port-forward (must be unique per call)
        
    Returns:
        Metrics dict or None if failed
    """
    # Start port-forward process
    cmd = [
        "kubectl", "port-forward",
        "-n", namespace,
        f"pod/{pod_name}",
        f"{local_port}:8888"
    ]
    
    proc = None
    try:
        # Start port-forward in background
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Wait a moment for port-forward to establish
        await asyncio.sleep(0.5)
        
        # Fetch metrics
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
            async with session.get(f"http://localhost:{local_port}/metrics") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
                    
    except Exception:
        return None
    finally:
        # Kill port-forward process
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_bytes(bytes_val: int) -> str:
    """Format bytes in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f}TB"


def create_dashboard(pods_data: List[Dict[str, Any]], last_update: datetime) -> Layout:
    """Create a rich dashboard layout.
    
    Args:
        pods_data: List of pod data with metrics
        last_update: Timestamp of last update
        
    Returns:
        Rich Layout object
    """
    layout = Layout()
    
    # Summary stats
    total_pods = len(pods_data)
    ready_pods = sum(1 for p in pods_data if p and p.get("ready", False))
    total_syncs = sum(
        p.get("metrics", {}).get("active_activities_count", 0) 
        for p in pods_data 
        if p and p.get("metrics")
    )
    
    # Create summary panel
    summary_text = Text()
    summary_text.append("Workers: ", style="bold")
    summary_text.append(f"{ready_pods}/{total_pods} ready", style="green" if ready_pods == total_pods else "yellow")
    summary_text.append("  |  ", style="dim")
    summary_text.append("Active Syncs: ", style="bold")
    summary_text.append(str(total_syncs), style="cyan")
    summary_text.append("  |  ", style="dim")
    summary_text.append("Last Update: ", style="bold")
    summary_text.append(last_update.strftime("%H:%M:%S"), style="dim")
    
    summary_panel = Panel(summary_text, title="📊 Temporal Workers Dashboard", border_style="blue")
    
    # Create workers table
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Pod", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Active Syncs", justify="center")
    table.add_column("Uptime", justify="right")
    table.add_column("Current Jobs", style="dim")
    
    for pod_data in pods_data:
        if not pod_data:
            continue
            
        pod_name = pod_data.get("name", "unknown")
        ready = pod_data.get("ready", False)
        metrics = pod_data.get("metrics")
        
        # Status indicator
        if ready and metrics:
            status_emoji = "🟢"
            status_text = metrics.get("status", "unknown")
        elif ready:
            status_emoji = "🟡"
            status_text = "no metrics"
        else:
            status_emoji = "🔴"
            status_text = "not ready"
        
        status = f"{status_emoji} {status_text}"
        
        if metrics:
            active_count = metrics.get("active_activities_count", 0)
            uptime = format_duration(metrics.get("uptime_seconds", 0))
            
            # Format active jobs
            activities = metrics.get("active_activities", [])
            if activities:
                job_lines = []
                for activity in activities:  # Show all jobs
                    conn = activity.get("metadata", {}).get("connection_name", "Unknown")
                    coll = activity.get("metadata", {}).get("collection_name", "")
                    duration = format_duration(activity.get("duration_seconds", 0))
                    # Show connection and collection if available
                    if coll:
                        job_lines.append(f"  • {conn} → {coll} ({duration})")
                    else:
                        job_lines.append(f"  • {conn} ({duration})")
                
                jobs_text = "\n".join(job_lines)
            else:
                jobs_text = "  (idle)"
        else:
            active_count = "-"
            uptime = "-"
            jobs_text = "  (no data)"
        
        # Truncate pod name for display
        display_name = pod_name.split("-sync-worker-")[-1][:12]
        
        table.add_row(
            display_name,
            status,
            str(active_count),
            uptime,
            jobs_text
        )
    
    # Combine into layout
    layout.split(
        Layout(summary_panel, size=3),
        Layout(table)
    )
    
    return layout


async def watch_workers(namespace: str = "airweave", interval: int = 2):
    """Continuously watch and display worker metrics.
    
    Args:
        namespace: Kubernetes namespace
        interval: Refresh interval in seconds
    """
    console.print(f"\n[bold]Starting worker monitoring...[/bold]")
    console.print(f"Namespace: {namespace} | Refresh: {interval}s\n")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")
    
    with Live(console=console, refresh_per_second=1) as live:
        try:
            while True:
                # Get all worker pods
                pods = get_worker_pods(namespace)
                
                if not pods:
                    live.update("[yellow]No worker pods found. Waiting...[/yellow]")
                    await asyncio.sleep(interval)
                    continue
                
                # Fetch metrics from all pods concurrently with unique ports
                tasks = [
                    fetch_pod_metrics(pod["name"], namespace, local_port=18888 + i) 
                    for i, pod in enumerate(pods)
                ]
                metrics_results = await asyncio.gather(*tasks)
                
                # Combine pod info with metrics
                pods_data = []
                for pod, metrics in zip(pods, metrics_results):
                    pod_data = {**pod, "metrics": metrics}
                    pods_data.append(pod_data)
                
                # Create and display dashboard
                last_update = datetime.now()
                dashboard = create_dashboard(pods_data, last_update)
                live.update(dashboard)
                
                # Wait before next update
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped.[/yellow]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Real-time dashboard for Temporal workers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Watch workers in default namespace
  %(prog)s
  
  # Watch workers in custom namespace
  %(prog)s --namespace my-namespace
  
  # Change refresh interval to 5 seconds
  %(prog)s --interval 5
        """
    )
    parser.add_argument(
        "--namespace", "-n",
        default="airweave",
        help="Kubernetes namespace (default: airweave)"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=2,
        help="Refresh interval in seconds (default: 2)"
    )
    
    args = parser.parse_args()
    
    # Run async main
    try:
        asyncio.run(watch_workers(namespace=args.namespace, interval=args.interval))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

