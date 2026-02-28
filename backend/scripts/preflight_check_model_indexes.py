"""Pre-flight check: validates that the database is safe for the model index migration.

Run BEFORE applying the Alembic migration to catch issues that would cause it to fail.

Usage:
    cd backend
    python scripts/preflight_check_model_indexes.py

Checks:
    1. Duplicate rows that would violate new unique constraints
    2. Confirms the migration is safe to apply
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from airweave.core.config import settings

CHECKS = [
    {
        "name": "sync_connection duplicates (sync_id, connection_id)",
        "constraint": "uq_sync_connection",
        "query": """
            SELECT sync_id, connection_id, COUNT(*) as cnt
            FROM sync_connection
            GROUP BY sync_id, connection_id
            HAVING COUNT(*) > 1
        """,
    },
    {
        "name": "entity_relation duplicates (from, to, name, organization_id)",
        "constraint": "uq_entity_relation",
        "query": """
            SELECT from_entity_definition_id, to_entity_definition_id, name,
                   organization_id, COUNT(*) as cnt
            FROM entity_relation
            GROUP BY from_entity_definition_id, to_entity_definition_id, name, organization_id
            HAVING COUNT(*) > 1
        """,
    },
    {
        "name": "user_organization duplicates (user_id, organization_id)",
        "constraint": "uq_user_organization",
        "query": """
            SELECT user_id, organization_id, COUNT(*) as cnt
            FROM user_organization
            GROUP BY user_id, organization_id
            HAVING COUNT(*) > 1
        """,
    },
]


async def run_checks() -> bool:
    """Run all pre-flight checks. Returns True if safe to migrate."""
    engine = create_async_engine(str(settings.SQLALCHEMY_ASYNC_DATABASE_URI))
    all_ok = True

    async with engine.connect() as conn:
        for check in CHECKS:
            result = await conn.execute(text(check["query"]))
            rows = result.fetchall()
            if rows:
                all_ok = False
                print(f"\n  FAIL: {check['name']}")
                print(f"         Constraint: {check['constraint']}")
                print(f"         Found {len(rows)} duplicate group(s):")
                for row in rows[:10]:
                    print(f"           {dict(row._mapping)}")
                if len(rows) > 10:
                    print(f"           ... and {len(rows) - 10} more")
            else:
                print(f"  OK:   {check['name']}")

    await engine.dispose()
    return all_ok


def main() -> None:
    """Run all pre-flight checks and print results."""
    print("=" * 60)
    print("Pre-flight check: model index migration")
    print("=" * 60)
    print()

    ok = asyncio.run(run_checks())

    print()
    if ok:
        print("All checks passed. Safe to run the migration.")
        print()
        print("  cd backend")
        print("  alembic revision --autogenerate -m 'add_missing_indexes_and_constraints'")
        print("  alembic upgrade head")
        sys.exit(0)
    else:
        print("BLOCKED: Duplicate data found. Clean up before migrating.")
        print()
        print("To deduplicate, keep the newest row per group:")
        print()
        print("  DELETE FROM <table> WHERE id NOT IN (")
        print("    SELECT DISTINCT ON (<unique_cols>) id")
        print("    FROM <table>")
        print("    ORDER BY <unique_cols>, modified_at DESC")
        print("  );")
        sys.exit(1)


if __name__ == "__main__":
    main()
