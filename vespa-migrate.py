#!/usr/bin/env python3
"""
Vespa Migration CLI Tool

Track and manage Vespa migration progress for Airweave syncs.

Usage:
    python vespa-migrate.py list [--status pending|completed|failed|all]
    python vespa-migrate.py run <sync_id>
    python vespa-migrate.py run-pending [--limit 10]
    python vespa-migrate.py compare <collection_id> <query>

Environment:
    AIRWEAVE_API_URL - API base URL (default: http://localhost:8000)
    AIRWEAVE_API_KEY - API key with admin_sync permission
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional
from enum import Enum

try:
    import httpx
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install httpx typer rich")
    sys.exit(1)

# ============================================================================
# Configuration
# ============================================================================

API_BASE = os.environ.get("AIRWEAVE_API_URL", "http://localhost:8000")
API_KEY = os.environ.get("AIRWEAVE_API_KEY", "")

app = typer.Typer(
    help="🚀 Vespa Migration CLI - Track and manage Airweave sync migrations",
    no_args_is_help=True,
)
console = Console()


# ============================================================================
# Helpers
# ============================================================================


def get_client() -> httpx.Client:
    """Create HTTP client with auth headers."""
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return httpx.Client(
        base_url=API_BASE,
        headers=headers,
        timeout=30.0,
    )


def format_status(status: Optional[str]) -> Text:
    """Format job status with color and emoji."""
    if not status:
        return Text("—", style="dim")

    status_map = {
        "COMPLETED": ("✅", "green"),
        "RUNNING": ("🔄", "yellow"),
        "PENDING": ("⏳", "dim"),
        "FAILED": ("❌", "red"),
        "CANCELLED": ("🚫", "dim red"),
    }
    emoji, color = status_map.get(status.upper(), ("?", "white"))
    return Text(f"{emoji} {status}", style=color)


def format_time(dt: Optional[str]) -> str:
    """Format datetime as relative time."""
    if not dt:
        return "—"
    try:
        if isinstance(dt, str):
            # Handle ISO format
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt

        if diff.days > 30:
            return dt.strftime("%Y-%m-%d")
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"
    except Exception:
        return str(dt)[:10] if dt else "—"


def format_count(count: int) -> Text:
    """Format entity count with color based on size."""
    if count == 0:
        return Text("0", style="dim")
    elif count < 100:
        return Text(str(count), style="white")
    elif count < 1000:
        return Text(str(count), style="cyan")
    elif count < 10000:
        return Text(f"{count:,}", style="green")
    else:
        return Text(f"{count:,}", style="bold green")


def truncate(s: Optional[str], max_len: int = 20) -> str:
    """Truncate string with ellipsis."""
    if not s:
        return "—"
    return s[:max_len-1] + "…" if len(s) > max_len else s


class MigrationStatus(str, Enum):
    """Migration status categories."""
    COMPLETED = "completed"  # Has successful Vespa job
    FAILED = "failed"        # Last Vespa job failed
    RUNNING = "running"      # Vespa job in progress
    PENDING = "pending"      # No Vespa job yet
    ALL = "all"


def categorize_sync(sync: dict) -> MigrationStatus:
    """Categorize sync by Vespa migration status."""
    vespa_status = sync.get("last_vespa_job_status")
    if not vespa_status:
        return MigrationStatus.PENDING
    status_upper = vespa_status.upper()
    if status_upper == "COMPLETED":
        return MigrationStatus.COMPLETED
    elif status_upper in ("RUNNING", "PENDING"):
        return MigrationStatus.RUNNING
    else:
        return MigrationStatus.FAILED


# ============================================================================
# Commands
# ============================================================================


@app.command("list")
def list_syncs(
    status: MigrationStatus = typer.Option(
        MigrationStatus.ALL, "--status", "-s",
        help="Filter by migration status"
    ),
    org: Optional[str] = typer.Option(
        None, "--org", "-o",
        help="Filter by organization ID"
    ),
    limit: int = typer.Option(
        200, "--limit", "-l",
        help="Maximum syncs to fetch"
    ),
    sort: str = typer.Option(
        "entities", "--sort",
        help="Sort by: entities, name, status, time"
    ),
):
    """
    📋 List all syncs with Vespa migration status.

    Shows a table of all syncs with their current migration state.
    Use --status to filter by migration status.
    """
    with get_client() as client:
        # Fetch syncs
        params = {"limit": limit}
        if org:
            params["organization_id"] = org

        try:
            resp = client.get("/admin/syncs", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]API Error:[/] {e}")
            raise typer.Exit(1)

        syncs = resp.json()

        if not syncs:
            console.print("[dim]No syncs found[/]")
            raise typer.Exit(0)

        # Filter by status
        if status != MigrationStatus.ALL:
            syncs = [s for s in syncs if categorize_sync(s) == status]

        # Sort
        sort_keys = {
            "entities": lambda s: s.get("total_entity_count", 0),
            "name": lambda s: s.get("source_short_name") or "",
            "status": lambda s: categorize_sync(s).value,
            "time": lambda s: s.get("last_vespa_job_at") or "",
        }
        sort_fn = sort_keys.get(sort, sort_keys["entities"])
        syncs = sorted(syncs, key=sort_fn, reverse=(sort == "entities"))

        # Count by status
        counts = {
            MigrationStatus.COMPLETED: 0,
            MigrationStatus.FAILED: 0,
            MigrationStatus.RUNNING: 0,
            MigrationStatus.PENDING: 0,
        }
        total_entities = 0
        migrated_entities = 0

        for s in syncs:
            cat = categorize_sync(s)
            counts[cat] += 1
            total_entities += s.get("total_entity_count", 0)
            if cat == MigrationStatus.COMPLETED:
                migrated_entities += s.get("total_entity_count", 0)

        # Build table
        table = Table(
            title="Vespa Migration Status",
            box=box.ROUNDED,
            show_lines=False,
            header_style="bold cyan",
        )

        table.add_column("Source", style="white", max_width=25)
        table.add_column("Collection", style="dim", max_width=30)
        table.add_column("Entities", justify="right")
        table.add_column("Last Job", justify="center")
        table.add_column("Vespa Status", justify="center")
        table.add_column("Vespa Job", justify="right", style="dim")
        table.add_column("Sync ID", style="dim", max_width=36)

        for sync in syncs:
            table.add_row(
                truncate(sync.get("source_short_name"), 25),
                truncate(sync.get("readable_collection_id"), 30),
                format_count(sync.get("total_entity_count", 0)),
                format_status(sync.get("last_job_status")),
                format_status(sync.get("last_vespa_job_status")),
                format_time(sync.get("last_vespa_job_at")),
                str(sync.get("id", ""))[:8] + "…",
            )

        console.print()
        console.print(table)

        # Summary
        pct = (migrated_entities / total_entities * 100) if total_entities > 0 else 0
        summary = Text()
        summary.append("\n📊 Summary: ", style="bold")
        summary.append(f"{len(syncs)} syncs", style="white")
        summary.append(" | ", style="dim")
        summary.append(f"✅ {counts[MigrationStatus.COMPLETED]} completed", style="green")
        summary.append(" | ", style="dim")
        summary.append(f"🔄 {counts[MigrationStatus.RUNNING]} running", style="yellow")
        summary.append(" | ", style="dim")
        summary.append(f"❌ {counts[MigrationStatus.FAILED]} failed", style="red")
        summary.append(" | ", style="dim")
        summary.append(f"⏳ {counts[MigrationStatus.PENDING]} pending", style="dim")

        console.print(summary)

        entity_summary = Text()
        entity_summary.append("📦 Entities: ", style="bold")
        entity_summary.append(f"{migrated_entities:,}", style="green")
        entity_summary.append(f" / {total_entities:,}", style="white")
        entity_summary.append(f" ({pct:.1f}% migrated)", style="cyan")

        console.print(entity_summary)
        console.print()


@app.command("status")
def sync_status(
    sync_id: str = typer.Argument(..., help="Sync ID to check"),
):
    """
    🔍 Show detailed status for a specific sync.
    """
    with get_client() as client:
        try:
            resp = client.get("/admin/syncs", params={"limit": 500})
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]API Error:[/] {e}")
            raise typer.Exit(1)

        syncs = resp.json()
        sync = next((s for s in syncs if str(s.get("id", "")).startswith(sync_id)), None)

        if not sync:
            console.print(f"[red]Sync not found:[/] {sync_id}")
            raise typer.Exit(1)

        # Display detailed info
        console.print()
        console.print(Panel(
            f"[bold]{sync.get('source_short_name', 'Unknown')}[/]\n"
            f"[dim]{sync.get('id')}[/]",
            title="Sync Details",
            border_style="cyan",
        ))

        info_table = Table(box=None, show_header=False, padding=(0, 2))
        info_table.add_column("Key", style="dim")
        info_table.add_column("Value")

        info_table.add_row("Collection", sync.get("readable_collection_id") or "—")
        info_table.add_row("Organization", str(sync.get("organization_id") or "—"))
        info_table.add_row("Entities", f"{sync.get('total_entity_count', 0):,}")
        info_table.add_row("", "")
        info_table.add_row("Last Job Status", str(format_status(sync.get("last_job_status"))))
        info_table.add_row("Last Job Time", format_time(sync.get("last_job_at")))
        info_table.add_row("", "")
        info_table.add_row("Vespa Status", str(format_status(sync.get("last_vespa_job_status"))))
        info_table.add_row("Vespa Job Time", format_time(sync.get("last_vespa_job_at")))
        info_table.add_row("Vespa Job ID", str(sync.get("last_vespa_job_id") or "—")[:8] + "…" if sync.get("last_vespa_job_id") else "—")

        console.print(info_table)
        console.print()


@app.command("run")
def run_migration(
    sync_id: str = typer.Argument(..., help="Sync ID to migrate"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done"),
):
    """
    🚀 Trigger ARF → Vespa replay for a sync.

    This will replay all data from ARF storage to Vespa.
    """
    with get_client() as client:
        # First, verify sync exists
        try:
            resp = client.get("/admin/syncs", params={"limit": 500})
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]API Error:[/] {e}")
            raise typer.Exit(1)

        syncs = resp.json()
        sync = next((s for s in syncs if str(s.get("id", "")).startswith(sync_id)), None)

        if not sync:
            console.print(f"[red]Sync not found:[/] {sync_id}")
            raise typer.Exit(1)

        full_id = sync["id"]
        source = sync.get("source_short_name", "Unknown")
        entities = sync.get("total_entity_count", 0)

        console.print()
        console.print(f"[bold]Sync:[/] {source}")
        console.print(f"[dim]ID:[/] {full_id}")
        console.print(f"[dim]Entities:[/] {entities:,}")
        console.print()

        if dry_run:
            console.print("[yellow]DRY RUN:[/] Would trigger ARF → Vespa replay")
            console.print("[dim]Config: skip_qdrant=true, replay_from_arf=true[/]")
            return

        # Confirm
        if not typer.confirm(f"Trigger Vespa migration for {source}?"):
            console.print("[dim]Cancelled[/]")
            raise typer.Exit(0)

        # Trigger resync
        try:
            resp = client.post(
                f"/admin/resync/{full_id}",
                json={
                    "skip_qdrant": True,
                    "replay_from_arf": True,
                    "enable_raw_data_handler": False,
                    "enable_postgres_handler": False,
                }
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]Failed to trigger migration:[/] {e}")
            if hasattr(e, 'response') and e.response is not None:
                console.print(f"[dim]{e.response.text}[/]")
            raise typer.Exit(1)

        result = resp.json()
        console.print(f"[green]✅ Migration triggered![/]")
        console.print(f"[dim]Job ID: {result.get('id', 'unknown')}[/]")


@app.command("run-pending")
def run_pending(
    limit: int = typer.Option(10, "--limit", "-l", help="Max syncs to process"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done"),
    min_entities: int = typer.Option(0, "--min-entities", help="Min entity count to process"),
):
    """
    🚀 Trigger ARF → Vespa replay for all pending syncs.

    Processes syncs that have no Vespa job yet.
    """
    with get_client() as client:
        try:
            resp = client.get("/admin/syncs", params={"limit": 500})
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]API Error:[/] {e}")
            raise typer.Exit(1)

        syncs = resp.json()

        # Filter to pending syncs
        pending = [
            s for s in syncs
            if categorize_sync(s) == MigrationStatus.PENDING
            and s.get("total_entity_count", 0) >= min_entities
        ]

        # Sort by entity count (larger first)
        pending = sorted(pending, key=lambda s: s.get("total_entity_count", 0), reverse=True)
        pending = pending[:limit]

        if not pending:
            console.print("[dim]No pending syncs found[/]")
            raise typer.Exit(0)

        total_entities = sum(s.get("total_entity_count", 0) for s in pending)

        console.print()
        console.print(f"[bold]Found {len(pending)} pending syncs[/] ({total_entities:,} entities)")
        console.print()

        for s in pending:
            source = s.get("source_short_name", "Unknown")
            entities = s.get("total_entity_count", 0)
            console.print(f"  • {source} ({entities:,} entities)")

        console.print()

        if dry_run:
            console.print("[yellow]DRY RUN:[/] Would trigger migrations for above syncs")
            return

        if not typer.confirm(f"Trigger Vespa migration for {len(pending)} syncs?"):
            console.print("[dim]Cancelled[/]")
            raise typer.Exit(0)

        # Process each sync
        success = 0
        failed = 0

        for sync in pending:
            full_id = sync["id"]
            source = sync.get("source_short_name", "Unknown")

            try:
                resp = client.post(
                    f"/admin/resync/{full_id}",
                    json={
                        "skip_qdrant": True,
                        "replay_from_arf": True,
                        "enable_raw_data_handler": False,
                        "enable_postgres_handler": False,
                    }
                )
                resp.raise_for_status()
                console.print(f"  [green]✅[/] {source}")
                success += 1
            except httpx.HTTPError as e:
                console.print(f"  [red]❌[/] {source}: {e}")
                failed += 1

        console.print()
        console.print(f"[bold]Done:[/] {success} triggered, {failed} failed")


@app.command("sync-to-vespa")
def sync_to_vespa(
    sync_id: str = typer.Argument(..., help="Sync ID to run"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done"),
    skip_qdrant: bool = typer.Option(True, "--skip-qdrant/--include-qdrant", help="Skip Qdrant write"),
):
    """
    🔄 Sync from source to Vespa (fetches fresh data from authenticated source).

    Unlike 'run' which replays from ARF, this fetches fresh data from the source.
    """
    with get_client() as client:
        # First, verify sync exists
        try:
            resp = client.get("/admin/syncs", params={"limit": 500})
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]API Error:[/] {e}")
            raise typer.Exit(1)

        syncs = resp.json()
        sync = next((s for s in syncs if str(s.get("id", "")).startswith(sync_id)), None)

        if not sync:
            console.print(f"[red]Sync not found:[/] {sync_id}")
            raise typer.Exit(1)

        full_id = sync["id"]
        source = sync.get("source_short_name", "Unknown")
        entities = sync.get("total_entity_count", 0)

        console.print()
        console.print(f"[bold]Sync:[/] {source}")
        console.print(f"[dim]ID:[/] {full_id}")
        console.print(f"[dim]Current entities:[/] {entities:,}")
        console.print(f"[dim]Mode:[/] Fresh sync from source → Vespa" + (" only" if skip_qdrant else " + Qdrant"))
        console.print()

        if dry_run:
            console.print("[yellow]DRY RUN:[/] Would trigger fresh sync to Vespa")
            return

        # Confirm
        if not typer.confirm(f"Trigger fresh sync for {source}?"):
            console.print("[dim]Cancelled[/]")
            raise typer.Exit(0)

        # Trigger resync - fresh from source, not ARF replay
        config = {
            "skip_qdrant": skip_qdrant,
            "skip_vespa": False,
            # Don't set replay_from_arf - fetch fresh from source
        }

        try:
            resp = client.post(f"/admin/resync/{full_id}", json=config)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]Failed to trigger sync:[/] {e}")
            if hasattr(e, 'response') and e.response is not None:
                console.print(f"[dim]{e.response.text}[/]")
            raise typer.Exit(1)

        result = resp.json()
        console.print(f"[green]✅ Sync triggered![/]")
        console.print(f"[dim]Job ID: {result.get('id', 'unknown')}[/]")


@app.command("sync-batch")
def sync_batch(
    limit: int = typer.Option(5, "--limit", "-l", help="Max syncs to process"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done"),
    min_entities: int = typer.Option(0, "--min-entities", help="Min entity count to process"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Filter by source type"),
    skip_qdrant: bool = typer.Option(True, "--skip-qdrant/--include-qdrant", help="Skip Qdrant write"),
):
    """
    🔄 Batch sync from sources to Vespa (fetches fresh data).

    Processes pending syncs by fetching fresh data from their sources.
    """
    with get_client() as client:
        try:
            resp = client.get("/admin/syncs", params={"limit": 500})
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]API Error:[/] {e}")
            raise typer.Exit(1)

        syncs = resp.json()

        # Filter to pending syncs with source info
        pending = [
            s for s in syncs
            if categorize_sync(s) == MigrationStatus.PENDING
            and s.get("total_entity_count", 0) >= min_entities
            and s.get("source_short_name")  # Must have source info
        ]

        # Filter by source type if specified
        if source:
            pending = [s for s in pending if s.get("source_short_name") == source]

        # Sort by entity count (larger first)
        pending = sorted(pending, key=lambda s: s.get("total_entity_count", 0), reverse=True)
        pending = pending[:limit]

        if not pending:
            console.print("[dim]No pending syncs with source info found[/]")
            raise typer.Exit(0)

        total_entities = sum(s.get("total_entity_count", 0) for s in pending)

        console.print()
        console.print(f"[bold]Found {len(pending)} syncs to process[/] ({total_entities:,} entities)")
        console.print(f"[dim]Mode:[/] Fresh sync from source → Vespa" + (" only" if skip_qdrant else " + Qdrant"))
        console.print()

        for s in pending:
            src = s.get("source_short_name", "Unknown")
            entities = s.get("total_entity_count", 0)
            console.print(f"  • {src} ({entities:,} entities)")

        console.print()

        if dry_run:
            console.print("[yellow]DRY RUN:[/] Would trigger syncs for above")
            return

        if not typer.confirm(f"Trigger {len(pending)} syncs?"):
            console.print("[dim]Cancelled[/]")
            raise typer.Exit(0)

        # Process each sync
        success = 0
        failed = 0

        config = {
            "skip_qdrant": skip_qdrant,
            "skip_vespa": False,
        }

        for sync in pending:
            full_id = sync["id"]
            src = sync.get("source_short_name", "Unknown")

            try:
                resp = client.post(f"/admin/resync/{full_id}", json=config)
                resp.raise_for_status()
                console.print(f"  [green]✅[/] {src}")
                success += 1
            except httpx.HTTPError as e:
                console.print(f"  [red]❌[/] {src}: {e}")
                failed += 1

        console.print()
        console.print(f"[bold]Done:[/] {success} triggered, {failed} failed")


@app.command("compare")
def compare_search(
    collection_id: str = typer.Argument(..., help="Collection readable ID"),
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(5, "--limit", "-l", help="Results per destination"),
):
    """
    🔍 Compare search results between Qdrant and Vespa.

    Runs the same query against both destinations and shows side-by-side results.
    """
    with get_client() as client:
        results = {}

        for dest in ["qdrant", "vespa"]:
            try:
                resp = client.post(
                    f"/admin/collections/{collection_id}/search",
                    params={"destination": dest},
                    json={"query": query, "limit": limit},
                )
                resp.raise_for_status()
                results[dest] = resp.json()
            except httpx.HTTPError as e:
                console.print(f"[red]{dest.upper()} Error:[/] {e}")
                results[dest] = None

        console.print()
        console.print(f"[bold]Search:[/] \"{query}\"")
        console.print(f"[dim]Collection:[/] {collection_id}")
        console.print()

        # Side by side comparison
        for dest in ["qdrant", "vespa"]:
            data = results[dest]
            if not data:
                console.print(f"[bold {('cyan' if dest == 'qdrant' else 'magenta')}]{dest.upper()}[/]: [red]Error[/]")
                continue

            items = data.get("results", [])
            total = data.get("total", len(items))

            color = "cyan" if dest == "qdrant" else "magenta"
            console.print(f"[bold {color}]{dest.upper()}[/] ({total} total)")

            if not items:
                console.print("  [dim]No results[/]")
            else:
                for i, item in enumerate(items[:limit], 1):
                    # Handle nested payload structure (Vespa) vs flat structure (Qdrant)
                    payload = item.get("payload", {})
                    title = (
                        item.get("title") or item.get("name") or
                        payload.get("name") or payload.get("title") or
                        item.get("entity_id") or payload.get("entity_id") or "Unknown"
                    )
                    score = item.get("score", 0)
                    console.print(f"  {i}. {truncate(title, 60)} [dim](score: {score:.3f})[/]")

            console.print()

        # Quick comparison - handle nested payload structure
        def get_entity_id(r):
            return r.get("entity_id") or r.get("payload", {}).get("entity_id")

        qdrant_ids = set(get_entity_id(r) for r in (results.get("qdrant") or {}).get("results", []))
        vespa_ids = set(get_entity_id(r) for r in (results.get("vespa") or {}).get("results", []))

        if qdrant_ids and vespa_ids:
            overlap = len(qdrant_ids & vespa_ids)
            total = len(qdrant_ids | vespa_ids)
            pct = (overlap / total * 100) if total > 0 else 0

            console.print(f"[bold]Overlap:[/] {overlap}/{total} results ({pct:.0f}%)")

            only_qdrant = qdrant_ids - vespa_ids
            only_vespa = vespa_ids - qdrant_ids

            if only_qdrant:
                console.print(f"[cyan]Only in Qdrant:[/] {len(only_qdrant)}")
            if only_vespa:
                console.print(f"[magenta]Only in Vespa:[/] {len(only_vespa)}")


@app.command("cancel")
def cancel_job(
    job_id: str = typer.Argument(..., help="Sync job ID to cancel"),
):
    """
    🛑 Cancel a running sync job.
    """
    with get_client() as client:
        try:
            resp = client.post(f"/admin/sync-jobs/{job_id}/cancel")
            resp.raise_for_status()
        except httpx.HTTPError as e:
            console.print(f"[red]Failed to cancel job:[/] {e}")
            raise typer.Exit(1)

        console.print(f"[green]✅ Job cancelled:[/] {job_id}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    app()
