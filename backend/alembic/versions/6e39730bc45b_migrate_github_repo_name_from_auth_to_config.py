"""migrate_github_repo_name_from_auth_to_config

Revision ID: 6e39730bc45b
Revises: c60291fb2129
Create Date: 2025-09-28 22:12:53.758477

This migration moves the GitHub repository name from encrypted credentials
to plaintext config_fields on the source_connection table. This change was
made to improve the user experience by making repo_name visible and editable
in the UI without requiring credential re-authentication.

IMPORTANT: This migration requires the ENCRYPTION_KEY environment variable
to be set, as it needs to decrypt and re-encrypt credentials.

To run a dry-run first:
  DRY_RUN=true alembic upgrade head

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import json
import os
import logging
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet, InvalidToken

# revision identifiers, used by Alembic.
revision = '6e39730bc45b'
down_revision = 'c60291fb2129'
branch_labels = None
depends_on = None

# Set up logging
logger = logging.getLogger(__name__)

# Check for dry-run mode
DRY_RUN = os.environ.get('DRY_RUN', '').lower() in ('true', '1', 'yes')


def get_encryption_key() -> bytes:
    """Get encryption key from environment variable.
    
    Returns:
        bytes: The encryption key encoded as bytes.
        
    Raises:
        ValueError: If ENCRYPTION_KEY is not set in environment.
    """
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable is not set")
    return key.encode()


def encrypt_data(data: Dict[str, Any]) -> str:
    """Encrypt dictionary data using Fernet encryption.
    
    Args:
        data: Dictionary to encrypt.
        
    Returns:
        str: Base64-encoded encrypted string.
        
    Raises:
        Exception: If encryption fails.
    """
    try:
        f = Fernet(get_encryption_key())
        json_str = json.dumps(data, sort_keys=True)  # sort_keys for consistency
        encrypted_data = f.encrypt(json_str.encode())
        return encrypted_data.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_data(encrypted_str: str) -> Optional[Dict[str, Any]]:
    """Decrypt data using Fernet encryption.
    
    Args:
        encrypted_str: Encrypted string to decrypt.
        
    Returns:
        Optional[Dict]: Decrypted dictionary or None if decryption fails.
    """
    if not encrypted_str:
        return None
        
    try:
        f = Fernet(get_encryption_key())
        decrypted_bytes = f.decrypt(encrypted_str.encode())
        return json.loads(decrypted_bytes.decode())
    except InvalidToken:
        logger.error("Invalid encryption token - data may be corrupted or key mismatch")
        return None
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return None


def upgrade():
    """Migrate GitHub repo_name from encrypted credentials to config_fields.
    
    Production-ready migration that safely moves repo_name from encrypted 
    GitHubAuthConfig to plaintext config_fields on source_connection.
    
    This migration:
    1. Finds GitHub source connections missing repo_name in config_fields
    2. Decrypts their integration credentials
    3. Extracts repo_name from credentials (if it exists)
    4. Adds repo_name to source_connection.config_fields
    5. Removes repo_name from encrypted credentials
    6. Re-encrypts and saves credentials
    """
    # Get database connection
    conn = op.get_bind()
    
    # Check if we have encryption key available
    try:
        encryption_key = get_encryption_key()
    except ValueError as e:
        logger.error(f"Cannot proceed with migration: {e}")
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable must be set to run this migration. "
            "This is required to decrypt and re-encrypt credentials."
        )
    
    # Start transaction
    if DRY_RUN:
        logger.info("Starting GitHub repo_name migration (DRY RUN MODE - no changes will be made)...")
    else:
        logger.info("Starting GitHub repo_name migration...")
    
    # Find GitHub connections that need migration
    # Using explicit column selection and proper NULL handling
    result = conn.execute(text("""
        SELECT 
            sc.id as source_connection_id,
            sc.name,
            sc.config_fields,
            ic.id as credential_id,
            ic.encrypted_credentials,
            o.name as organization_name
        FROM source_connection sc
        JOIN connection c ON sc.connection_id = c.id
        JOIN integration_credential ic ON c.integration_credential_id = ic.id
        JOIN organization o ON sc.organization_id = o.id
        WHERE sc.short_name = 'github'
        AND (
            sc.config_fields IS NULL 
            OR NOT (sc.config_fields::jsonb ? 'repo_name')
        )
        ORDER BY sc.created_at DESC
    """))
    
    connections_to_migrate = result.fetchall()
    total_connections = len(connections_to_migrate)
    
    logger.info(f"Found {total_connections} GitHub connections to migrate")
    
    # Track migration statistics
    migrated_count = 0
    skipped_count = 0
    failed_count = 0
    
    for idx, row in enumerate(connections_to_migrate, 1):
        source_connection_id = row.source_connection_id
        name = row.name
        config_fields = row.config_fields or {}
        credential_id = row.credential_id
        encrypted_credentials = row.encrypted_credentials
        organization_name = row.organization_name
        
        logger.info(
            f"[{idx}/{total_connections}] Processing connection '{name}' "
            f"(ID: {source_connection_id}) for organization '{organization_name}'"
        )
        
        # Skip if no encrypted credentials
        if not encrypted_credentials:
            logger.warning(f"  No encrypted credentials found, skipping")
            skipped_count += 1
            continue
            
        try:
            # Decrypt credentials
            decrypted_credentials = decrypt_data(encrypted_credentials)
            
            if not decrypted_credentials:
                logger.error(f"  Failed to decrypt credentials, skipping")
                failed_count += 1
                continue
            
            # Check if repo_name exists in credentials
            if 'repo_name' not in decrypted_credentials:
                logger.info(f"  No repo_name in credentials, nothing to migrate")
                skipped_count += 1
                continue
                
            # Extract repo_name
            repo_name = decrypted_credentials['repo_name']
            
            # Validate repo_name format (owner/repo)
            if not repo_name or '/' not in repo_name:
                logger.warning(
                    f"  Invalid repo_name format: '{repo_name}', "
                    f"expected 'owner/repo' format, skipping"
                )
                skipped_count += 1
                continue
            
            logger.info(f"  Found repo_name: {repo_name}")
            
            # Prepare updated config_fields
            if isinstance(config_fields, str):
                # Handle case where config_fields might be stored as string
                try:
                    config_fields = json.loads(config_fields)
                except json.JSONDecodeError:
                    config_fields = {}
                    
            config_fields['repo_name'] = repo_name
            
            # Remove repo_name from credentials
            del decrypted_credentials['repo_name']
            
            # Re-encrypt credentials
            new_encrypted_credentials = encrypt_data(decrypted_credentials)
            
            if DRY_RUN:
                logger.info(f"  [DRY RUN] Would update config_fields and remove repo_name from credentials")
                logger.info(f"  [DRY RUN] New config_fields would be: {json.dumps(config_fields, indent=2)}")
                logger.info(f"  [DRY RUN] Credentials would have keys: {list(decrypted_credentials.keys())}")
            else:
                # Update database in a transaction
                # First update source_connection
                conn.execute(text("""
                    UPDATE source_connection 
                    SET config_fields = :config_fields::jsonb,
                        modified_at = CURRENT_TIMESTAMP
                    WHERE id = :source_connection_id
                """), {
                    'config_fields': json.dumps(config_fields),
                    'source_connection_id': source_connection_id
                })
                
                # Then update integration_credential
                conn.execute(text("""
                    UPDATE integration_credential 
                    SET encrypted_credentials = :encrypted_credentials,
                        modified_at = CURRENT_TIMESTAMP
                    WHERE id = :credential_id
                """), {
                    'encrypted_credentials': new_encrypted_credentials,
                    'credential_id': credential_id
                })
                
                logger.info(f"  ✅ Successfully migrated repo_name to config_fields")
            
            migrated_count += 1
            
        except Exception as e:
            logger.error(f"  Failed to migrate connection: {str(e)}", exc_info=True)
            failed_count += 1
            # Continue with other connections - don't fail the entire migration
    
    # Log final statistics
    if DRY_RUN:
        logger.info(
            f"\nDRY RUN completed (no changes made):\n"
            f"  - Total connections that would be processed: {total_connections}\n"
            f"  - Would migrate: {migrated_count}\n"
            f"  - Would skip (no repo_name): {skipped_count}\n"
            f"  - Would fail: {failed_count}"
        )
    else:
        logger.info(
            f"\nMigration completed:\n"
            f"  - Total connections: {total_connections}\n"
            f"  - Successfully migrated: {migrated_count}\n"
            f"  - Skipped (no repo_name): {skipped_count}\n"
            f"  - Failed: {failed_count}"
        )
        
        if failed_count > 0:
            logger.warning(
                f"{failed_count} connections failed to migrate. "
                f"Manual intervention may be required for these connections."
            )


def downgrade():
    """Reverse the migration by moving repo_name back to encrypted credentials.
    
    Production-ready downgrade that safely moves repo_name from config_fields
    back to encrypted credentials.
    
    This will:
    1. Find GitHub connections with repo_name in config_fields
    2. Extract repo_name from config_fields
    3. Decrypt existing credentials
    4. Add repo_name back to credentials
    5. Re-encrypt credentials
    6. Remove repo_name from config_fields
    """
    # Get database connection
    conn = op.get_bind()
    
    # Check if we have encryption key available
    try:
        encryption_key = get_encryption_key()
    except ValueError as e:
        logger.error(f"Cannot proceed with downgrade: {e}")
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable must be set to run this downgrade. "
            "This is required to decrypt and re-encrypt credentials."
        )
    
    if DRY_RUN:
        logger.info("Starting GitHub repo_name downgrade (DRY RUN MODE - no changes will be made)...")
    else:
        logger.info("Starting GitHub repo_name downgrade...")
    
    # Find GitHub connections that have repo_name in config_fields
    # Using proper JSONB operators for safety
    result = conn.execute(text("""
        SELECT 
            sc.id as source_connection_id,
            sc.name,
            sc.config_fields,
            ic.id as credential_id,
            ic.encrypted_credentials,
            o.name as organization_name
        FROM source_connection sc
        JOIN connection c ON sc.connection_id = c.id
        JOIN integration_credential ic ON c.integration_credential_id = ic.id
        JOIN organization o ON sc.organization_id = o.id
        WHERE sc.short_name = 'github'
        AND sc.config_fields IS NOT NULL 
        AND (sc.config_fields::jsonb ? 'repo_name')
        ORDER BY sc.created_at DESC
    """))
    
    connections_to_revert = result.fetchall()
    total_connections = len(connections_to_revert)
    
    logger.info(f"Found {total_connections} GitHub connections to revert")
    
    # Track downgrade statistics
    reverted_count = 0
    skipped_count = 0
    failed_count = 0
    
    for idx, row in enumerate(connections_to_revert, 1):
        source_connection_id = row.source_connection_id
        name = row.name
        config_fields = row.config_fields or {}
        credential_id = row.credential_id
        encrypted_credentials = row.encrypted_credentials
        organization_name = row.organization_name
        
        logger.info(
            f"[{idx}/{total_connections}] Reverting connection '{name}' "
            f"(ID: {source_connection_id}) for organization '{organization_name}'"
        )
        
        try:
            # Handle config_fields as string if needed
            if isinstance(config_fields, str):
                try:
                    config_fields = json.loads(config_fields)
                except json.JSONDecodeError:
                    logger.error(f"  Invalid JSON in config_fields, skipping")
                    failed_count += 1
                    continue
            
            # Check if repo_name exists in config_fields
            if 'repo_name' not in config_fields:
                logger.info(f"  No repo_name in config_fields, nothing to revert")
                skipped_count += 1
                continue
                
            repo_name = config_fields['repo_name']
            
            # Validate repo_name before adding back
            if not repo_name or not isinstance(repo_name, str):
                logger.warning(f"  Invalid repo_name value: {repo_name}, skipping")
                skipped_count += 1
                continue
                
            logger.info(f"  Found repo_name to revert: {repo_name}")
            
            # Decrypt existing credentials or start with empty dict
            if encrypted_credentials:
                decrypted_credentials = decrypt_data(encrypted_credentials)
                if not decrypted_credentials:
                    logger.error(f"  Failed to decrypt existing credentials")
                    failed_count += 1
                    continue
            else:
                # No existing credentials, create new
                decrypted_credentials = {}
                logger.info(f"  No existing credentials, creating new")
            
            # Check if repo_name already exists in credentials (shouldn't happen)
            if 'repo_name' in decrypted_credentials:
                logger.warning(
                    f"  repo_name already exists in credentials with value: "
                    f"'{decrypted_credentials['repo_name']}', will overwrite"
                )
            
            # Add repo_name back to credentials
            decrypted_credentials['repo_name'] = repo_name
            
            # Re-encrypt credentials with repo_name
            new_encrypted_credentials = encrypt_data(decrypted_credentials)
            
            # Remove repo_name from config_fields
            del config_fields['repo_name']
            
            if DRY_RUN:
                logger.info(f"  [DRY RUN] Would move repo_name back to credentials")
                logger.info(f"  [DRY RUN] Remaining config_fields would be: {json.dumps(config_fields, indent=2) if config_fields else 'NULL'}")
                logger.info(f"  [DRY RUN] Credentials would have keys: {list(decrypted_credentials.keys())}")
            else:
                # Update database in a transaction
                # First update source_connection
                if config_fields:
                    # Still has other config, update with remaining fields
                    conn.execute(text("""
                        UPDATE source_connection 
                        SET config_fields = :config_fields::jsonb,
                            modified_at = CURRENT_TIMESTAMP
                        WHERE id = :source_connection_id
                    """), {
                        'config_fields': json.dumps(config_fields),
                        'source_connection_id': source_connection_id
                    })
                else:
                    # No more config fields, set to NULL
                    conn.execute(text("""
                        UPDATE source_connection 
                        SET config_fields = NULL,
                            modified_at = CURRENT_TIMESTAMP
                        WHERE id = :source_connection_id
                    """), {
                        'source_connection_id': source_connection_id
                    })
                
                # Then update integration_credential
                conn.execute(text("""
                    UPDATE integration_credential 
                    SET encrypted_credentials = :encrypted_credentials,
                        modified_at = CURRENT_TIMESTAMP
                    WHERE id = :credential_id
                """), {
                    'encrypted_credentials': new_encrypted_credentials,
                    'credential_id': credential_id
                })
                
                logger.info(f"  ✅ Successfully reverted repo_name to credentials")
            
            reverted_count += 1
            
        except Exception as e:
            logger.error(f"  Failed to revert connection: {str(e)}", exc_info=True)
            failed_count += 1
            # Continue with other connections - don't fail the entire downgrade
    
    # Log final statistics
    if DRY_RUN:
        logger.info(
            f"\nDRY RUN downgrade completed (no changes made):\n"
            f"  - Total connections that would be processed: {total_connections}\n"
            f"  - Would revert: {reverted_count}\n"
            f"  - Would skip (no repo_name): {skipped_count}\n"
            f"  - Would fail: {failed_count}"
        )
    else:
        logger.info(
            f"\nDowngrade completed:\n"
            f"  - Total connections: {total_connections}\n"
            f"  - Successfully reverted: {reverted_count}\n"
            f"  - Skipped (no repo_name): {skipped_count}\n"
            f"  - Failed: {failed_count}"
        )
        
        if failed_count > 0:
            logger.warning(
                f"{failed_count} connections failed to revert. "
                f"Manual intervention may be required for these connections."
            )