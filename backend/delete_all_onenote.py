#!/usr/bin/env python3
"""
Nuclear option: Delete EVERYTHING from OneNote.

This script uses Composio authentication to connect to OneNote
and systematically deletes all notebooks, sections, and pages.

⚠️  WARNING: This is DESTRUCTIVE and IRREVERSIBLE! ⚠️

Usage:
    python delete_all_onenote.py [--dry-run]

Environment variables required:
    MONKE_COMPOSIO_API_KEY: Your Composio API key

You can optionally specify:
    ONENOTE_AUTH_CONFIG_ID: Specific auth config ID
    ONENOTE_ACCOUNT_ID: Specific account ID
"""

import asyncio
import os
import sys
import time
from typing import Dict, Optional

import httpx


GRAPH = "https://graph.microsoft.com/v1.0"
COMPOSIO_BASE = "https://backend.composio.dev/api/v3"


class OneNoteDestroyer:
    """Systematically destroys all OneNote content."""

    def __init__(self, access_token: str, dry_run: bool = False):
        self.access_token = access_token
        self.dry_run = dry_run
        self.rate_limit_delay = 2.0  # 2 seconds between requests to avoid rate limiting
        self._last_req = 0.0

        self.stats = {
            "notebooks_found": 0,
            "notebooks_deleted": 0,
            "sections_found": 0,
            "sections_deleted": 0,
            "pages_found": 0,
            "pages_deleted": 0,
            "errors": 0,
        }

    def _hdrs(self) -> Dict[str, str]:
        """Get standard headers for Graph API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _pace(self):
        """Rate limiting helper."""
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()

    async def destroy_all(self):
        """Delete everything from OneNote."""
        print("=" * 80)
        if self.dry_run:
            print("🔍 DRY RUN MODE - No actual deletions will be performed")
        else:
            print("💣 DESTRUCTION MODE - All content will be permanently deleted!")
        print("=" * 80)
        print()

        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            # Get all notebooks
            await self._pace()
            print("📚 Fetching all notebooks...")

            try:
                r = await client.get("/me/onenote/notebooks", headers=self._hdrs())
                r.raise_for_status()
                notebooks = r.json().get("value", [])
                self.stats["notebooks_found"] = len(notebooks)

                print(f"Found {len(notebooks)} notebooks")
                print()

                if not notebooks:
                    print("✅ No notebooks found. OneNote is already empty!")
                    return

                # Process each notebook
                for i, notebook in enumerate(notebooks, 1):
                    nb_id = notebook["id"]
                    nb_name = notebook.get("displayName", "Unknown")

                    print(f"[{i}/{len(notebooks)}] Processing notebook: '{nb_name}'")
                    print(f"  ID: {nb_id}")

                    # Get all sections in this notebook
                    await self._delete_notebook_sections(client, nb_id)

                    # Delete the notebook itself
                    await self._delete_notebook(client, nb_id, nb_name)
                    print()

                # Summary
                print("=" * 80)
                print("📊 DESTRUCTION SUMMARY")
                print("=" * 80)
                print(f"Notebooks found:   {self.stats['notebooks_found']}")
                print(f"Notebooks deleted: {self.stats['notebooks_deleted']}")
                print(f"Sections found:    {self.stats['sections_found']}")
                print(f"Sections deleted:  {self.stats['sections_deleted']}")
                print(f"Pages found:       {self.stats['pages_found']}")
                print(f"Pages deleted:     {self.stats['pages_deleted']}")
                print(f"Errors:            {self.stats['errors']}")
                print("=" * 80)

                if self.dry_run:
                    print("\n✅ Dry run completed - no actual changes were made")
                else:
                    print("\n💥 Destruction completed!")

            except Exception as e:
                print(f"❌ Fatal error: {e}")
                self.stats["errors"] += 1
                raise

    async def _delete_notebook_sections(
        self, client: httpx.AsyncClient, notebook_id: str
    ):
        """Delete all sections in a notebook."""
        try:
            await self._pace()
            r = await client.get(
                f"/me/onenote/notebooks/{notebook_id}/sections", headers=self._hdrs()
            )
            r.raise_for_status()
            sections = r.json().get("value", [])
            self.stats["sections_found"] += len(sections)

            if sections:
                print(f"  Found {len(sections)} sections")

                for section in sections:
                    section_id = section["id"]
                    section_name = section.get("displayName", "Unknown")

                    # Get pages in this section
                    await self._delete_section_pages(client, section_id, section_name)

                    # Delete the section
                    await self._delete_section(client, section_id, section_name)

        except Exception as e:
            print(f"  ⚠️ Error fetching sections: {e}")
            self.stats["errors"] += 1

    async def _delete_section_pages(
        self, client: httpx.AsyncClient, section_id: str, section_name: str
    ):
        """Delete all pages in a section."""
        try:
            await self._pace()
            r = await client.get(
                f"/me/onenote/sections/{section_id}/pages", headers=self._hdrs()
            )
            r.raise_for_status()
            pages = r.json().get("value", [])
            self.stats["pages_found"] += len(pages)

            if pages:
                print(f"    Section '{section_name}': {len(pages)} pages")

                for page in pages:
                    page_id = page["id"]
                    page_title = page.get("title", "Untitled")

                    await self._delete_page(client, page_id, page_title)

        except Exception as e:
            print(f"    ⚠️ Error fetching pages in section '{section_name}': {e}")
            self.stats["errors"] += 1

    async def _delete_page(self, client: httpx.AsyncClient, page_id: str, title: str):
        """Delete a single page."""
        try:
            if self.dry_run:
                print(f"      [DRY RUN] Would delete page: {title[:50]}")
                self.stats["pages_deleted"] += 1
                return

            await self._pace()
            r = await client.delete(
                f"/me/onenote/pages/{page_id}", headers=self._hdrs()
            )

            if r.status_code == 204:
                self.stats["pages_deleted"] += 1
                print(f"      ✓ Deleted page: {title[:50]}")
            else:
                self.stats["errors"] += 1
                print(f"      ✗ Failed to delete page '{title[:50]}': {r.status_code}")

        except Exception as e:
            self.stats["errors"] += 1
            print(f"      ✗ Error deleting page '{title[:50]}': {e}")

    async def _delete_section(
        self, client: httpx.AsyncClient, section_id: str, name: str
    ):
        """Delete a single section."""
        try:
            if self.dry_run:
                print(f"    [DRY RUN] Would delete section: {name}")
                self.stats["sections_deleted"] += 1
                return

            await self._pace()
            r = await client.delete(
                f"/me/onenote/sections/{section_id}", headers=self._hdrs()
            )

            if r.status_code == 204:
                self.stats["sections_deleted"] += 1
                print(f"    ✓ Deleted section: {name}")
            elif r.status_code == 404:
                # Section already deleted or doesn't exist
                self.stats["sections_deleted"] += 1
                print(f"    ✓ Section already deleted: {name}")
            elif r.status_code in (503, 429):
                # Service unavailable or rate limited - retry after delay
                delay = 5 if r.status_code == 429 else 2
                print(
                    f"    ⚠️ {'Rate limited' if r.status_code == 429 else 'Service unavailable'} for section '{name}', retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                await self._pace()
                r2 = await client.delete(
                    f"/me/onenote/sections/{section_id}", headers=self._hdrs()
                )
                if r2.status_code in (204, 404):
                    self.stats["sections_deleted"] += 1
                    print(f"    ✓ Deleted section (retry): {name}")
                else:
                    self.stats["errors"] += 1
                    print(
                        f"    ✗ Failed to delete section '{name}' (retry): {r2.status_code}"
                    )
            else:
                self.stats["errors"] += 1
                print(f"    ✗ Failed to delete section '{name}': {r.status_code}")

        except Exception as e:
            self.stats["errors"] += 1
            print(f"    ✗ Error deleting section '{name}': {e}")

    async def _delete_notebook(
        self, client: httpx.AsyncClient, notebook_id: str, name: str
    ):
        """Delete a single notebook."""
        try:
            if self.dry_run:
                print(f"  [DRY RUN] Would delete notebook: {name}")
                self.stats["notebooks_deleted"] += 1
                return

            await self._pace()
            r = await client.delete(
                f"/me/onenote/notebooks/{notebook_id}", headers=self._hdrs()
            )

            if r.status_code == 204:
                self.stats["notebooks_deleted"] += 1
                print(f"  ✓ Deleted notebook: {name}")
            elif r.status_code == 404:
                # Notebook already deleted or doesn't exist
                self.stats["notebooks_deleted"] += 1
                print(f"  ✓ Notebook already deleted: {name}")
            elif r.status_code in (503, 429):
                # Service unavailable or rate limited - retry after delay
                delay = 8 if r.status_code == 429 else 3
                print(
                    f"  ⚠️ {'Rate limited' if r.status_code == 429 else 'Service unavailable'} for notebook '{name}', retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                await self._pace()
                r2 = await client.delete(
                    f"/me/onenote/notebooks/{notebook_id}", headers=self._hdrs()
                )
                if r2.status_code in (204, 404):
                    self.stats["notebooks_deleted"] += 1
                    print(f"  ✓ Deleted notebook (retry): {name}")
                else:
                    self.stats["errors"] += 1
                    print(
                        f"  ✗ Failed to delete notebook '{name}' (retry): {r2.status_code}"
                    )
            else:
                self.stats["errors"] += 1
                print(f"  ✗ Failed to delete notebook '{name}': {r.status_code}")

        except Exception as e:
            self.stats["errors"] += 1
            print(f"  ✗ Error deleting notebook '{name}': {e}")


async def get_composio_credentials(
    api_key: str, auth_config_id: Optional[str] = None, account_id: Optional[str] = None
) -> str:
    """Fetch OneNote access token from Composio.

    Args:
        api_key: Composio API key
        auth_config_id: Optional specific auth config ID
        account_id: Optional specific account ID

    Returns:
        Access token for Microsoft Graph API
    """
    print("🔑 Fetching credentials from Composio...")

    async with httpx.AsyncClient() as client:
        # Get all connected accounts
        r = await client.get(
            f"{COMPOSIO_BASE}/connected_accounts",
            headers={"x-api-key": api_key},
            params={"limit": 100},
            timeout=30.0,
        )
        r.raise_for_status()

        accounts = r.json().get("items", [])

        # Filter for OneDrive accounts (OneNote uses OneDrive integration)
        onenote_accounts = [
            a for a in accounts if a.get("toolkit", {}).get("slug") == "one_drive"
        ]

        if not onenote_accounts:
            raise RuntimeError("No OneNote/OneDrive accounts found in Composio")

        # Select account
        selected = None
        if auth_config_id and account_id:
            for a in onenote_accounts:
                if (
                    a.get("auth_config", {}).get("id") == auth_config_id
                    and a.get("id") == account_id
                ):
                    selected = a
                    break

            if not selected:
                raise RuntimeError(
                    f"No account found with auth_config_id={auth_config_id} "
                    f"and account_id={account_id}"
                )
        else:
            selected = onenote_accounts[0]

        # Extract access token
        credentials = selected.get("state", {}).get("val", {})
        access_token = credentials.get("access_token")

        if not access_token:
            raise RuntimeError("No access_token found in Composio credentials")

        print(f"✅ Authenticated as: {selected.get('email', 'Unknown')}")
        print(f"   Account ID: {selected['id']}")
        print(
            f"   Auth Config ID: {selected.get('auth_config', {}).get('id', 'Unknown')}"
        )
        print()

        return access_token


async def main():
    """Main entry point."""
    # Parse arguments
    dry_run = "--dry-run" in sys.argv

    # Get environment variables
    api_key = os.getenv("MONKE_COMPOSIO_API_KEY")
    if not api_key:
        print("❌ Error: MONKE_COMPOSIO_API_KEY environment variable not set")
        sys.exit(1)

    auth_config_id = os.getenv("ONENOTE_AUTH_CONFIG_ID")
    account_id = os.getenv("ONENOTE_ACCOUNT_ID")

    if not dry_run:
        print()
        print("⚠️  " + "=" * 74 + "  ⚠️")
        print("⚠️  WARNING: This will DELETE ALL content from your OneNote account!  ⚠️")
        print("⚠️  " + "=" * 74 + "  ⚠️")
        print()
        print("This action is IRREVERSIBLE. All notebooks, sections, and pages will be")
        print("permanently deleted.")
        print()
        print("To preview what would be deleted, run with --dry-run flag:")
        print(f"  {sys.argv[0]} --dry-run")
        print()
        print("🚀 Proceeding with deletion (interactive mode disabled)...")
        print()

    try:
        # Get credentials
        access_token = await get_composio_credentials(
            api_key=api_key, auth_config_id=auth_config_id, account_id=account_id
        )

        # Execute destruction
        destroyer = OneNoteDestroyer(access_token, dry_run=dry_run)
        await destroyer.destroy_all()

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
