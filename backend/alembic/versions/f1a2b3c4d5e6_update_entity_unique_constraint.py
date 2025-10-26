"""update entity unique constraint to include entity_definition_id

Revision ID: f1a2b3c4d5e6
Revises: e3a7e8db826c
Create Date: 2025-10-21 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e3a7e8db826c"
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade the entity table unique constraint to include entity_definition_id.
    
    This migration safely handles existing production data by:
    1. Cleaning up any NULL entity_definition_id values (shouldn't exist per CRUD logic)
    2. Dropping the old (sync_id, entity_id) unique constraint
    3. Creating new (sync_id, entity_id, entity_definition_id) unique constraint
    
    This allows different entity types (e.g., GoogleCalendarList and GoogleCalendarCalendar)
    to share the same entity_id without conflicts.
    """
    conn = op.get_bind()
    
    # Step 1: Check for and handle NULL entity_definition_id values
    # These shouldn't exist per the CRUD layer's hard guarantee, but check anyway
    result = conn.execute(text("""
        SELECT COUNT(*) 
        FROM entity 
        WHERE entity_definition_id IS NULL
    """))
    null_count = result.scalar()
    
    if null_count > 0:
        # Log the issue
        print(f"\n⚠️  Found {null_count} entities with NULL entity_definition_id")
        print("   These violate the CRUD layer's hard guarantee and will be deleted.")
        
        # Show sample for logging
        sample = conn.execute(text("""
            SELECT id, sync_id, entity_id, organization_id, created_at
            FROM entity 
            WHERE entity_definition_id IS NULL 
            LIMIT 5
        """))
        print("\n   Sample entities being deleted:")
        for row in sample:
            print(f"     - entity_id={row.entity_id}, sync_id={row.sync_id}, created_at={row.created_at}")
        
        # Delete entities with NULL entity_definition_id
        # These are invalid per the system's constraints and cannot exist under the new schema
        conn.execute(text("""
            DELETE FROM entity 
            WHERE entity_definition_id IS NULL
        """))
        print(f"\n✅ Deleted {null_count} invalid entities")
    else:
        print("\n✅ No NULL entity_definition_id values found - data is clean")
    
    # Step 2: Check for potential duplicates that would violate the new constraint
    # (Different entity types with same sync_id + entity_id)
    result = conn.execute(text("""
        SELECT 
            sync_id, 
            entity_id, 
            COUNT(DISTINCT entity_definition_id) as type_count,
            COUNT(*) as total_count
        FROM entity
        GROUP BY sync_id, entity_id
        HAVING COUNT(DISTINCT entity_definition_id) > 1
    """))
    
    multi_type_entities = list(result)
    if multi_type_entities:
        print(f"\n✅ Found {len(multi_type_entities)} entity_ids with multiple types")
        print("   This is expected behavior (e.g., Google Calendar shared IDs)")
        print("   The new constraint will preserve all of them correctly.")
        if len(multi_type_entities) <= 10:
            for sync_id, entity_id, type_count, total_count in multi_type_entities:
                print(f"     - entity_id={entity_id[:40]}...: {type_count} types, {total_count} total rows")
    else:
        print("\n✅ No multi-type entities found")
    
    # Step 3: Drop the old unique constraint
    print("\n🔧 Dropping old unique constraint (sync_id, entity_id)...")
    op.drop_constraint("uq_sync_id_entity_id", "entity", type_="unique")
    
    # Step 4: Create the new unique constraint with entity_definition_id
    print("🔧 Creating new unique constraint (sync_id, entity_id, entity_definition_id)...")
    op.create_unique_constraint(
        "uq_sync_id_entity_id_entity_definition_id",
        "entity",
        ["sync_id", "entity_id", "entity_definition_id"],
    )
    
    print("\n✅ Successfully updated entity unique constraint!")
    print("   Entities with same entity_id but different types can now coexist.")


def downgrade():
    """Revert the constraint changes.
    
    WARNING: This may fail if multi-type entities exist in the database.
    Rolling back this migration in production is not recommended.
    """
    print("\n⚠️  WARNING: Downgrading entity unique constraint")
    print("   This will fail if entities with same (sync_id, entity_id) but different types exist.")
    
    # Drop the new constraint
    op.drop_constraint("uq_sync_id_entity_id_entity_definition_id", "entity", type_="unique")
    
    # Recreate the old constraint
    op.create_unique_constraint(
        "uq_sync_id_entity_id",
        "entity",
        ["sync_id", "entity_id"],
    )
    
    print("✅ Reverted to old constraint (not recommended for production)")

