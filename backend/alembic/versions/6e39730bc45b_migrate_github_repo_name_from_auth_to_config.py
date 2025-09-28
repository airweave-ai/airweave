"""migrate_github_repo_name_from_auth_to_config

Revision ID: 6e39730bc45b
Revises: c60291fb2129
Create Date: 2025-09-28 22:12:53.758477

"""
from alembic import op
import sqlalchemy as sa
import json
import os
from cryptography.fernet import Fernet

# revision identifiers, used by Alembic.
revision = '6e39730bc45b'
down_revision = 'c60291fb2129'
branch_labels = None
depends_on = None


def get_encryption_key():
    """Get encryption key from environment variable."""
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable is not set")
    return key.encode()


def encrypt_data(data):
    """Encrypt dictionary data using Fernet encryption."""
    f = Fernet(get_encryption_key())
    json_str = json.dumps(data)
    encrypted_data = f.encrypt(json_str.encode())
    return encrypted_data.decode()


def decrypt_data(encrypted_str):
    """Decrypt data using Fernet encryption."""
    if not encrypted_str:
        return None
    try:
        f = Fernet(get_encryption_key())
        decrypted_bytes = f.decrypt(encrypted_str.encode())
        return json.loads(decrypted_bytes.decode())
    except Exception:
        return None


def upgrade():
    """Migrate GitHub repo_name from encrypted credentials to config_fields."""
    
    # Check encryption key is available
    try:
        get_encryption_key()
    except ValueError:
        raise RuntimeError("ENCRYPTION_KEY environment variable must be set")
    
    conn = op.get_bind()
    
    # Find GitHub connections that need migration
    result = op.execute("""
        SELECT 
            sc.id as source_connection_id,
            sc.config_fields,
            ic.id as credential_id,
            ic.encrypted_credentials
        FROM source_connection sc
        JOIN connection c ON sc.connection_id = c.id
        JOIN integration_credential ic ON c.integration_credential_id = ic.id
        WHERE sc.short_name = 'github'
        AND (sc.config_fields IS NULL OR NOT (sc.config_fields::jsonb ? 'repo_name'))
        AND ic.encrypted_credentials IS NOT NULL
    """)
    
    migrated_count = 0
    
    for row in result:
        source_connection_id = row.source_connection_id
        config_fields = row.config_fields or {}
        credential_id = row.credential_id
        encrypted_credentials = row.encrypted_credentials
        
        # Decrypt credentials
        decrypted_credentials = decrypt_data(encrypted_credentials)
        if not decrypted_credentials or 'repo_name' not in decrypted_credentials:
            continue
            
        repo_name = decrypted_credentials['repo_name']
        if not repo_name:
            continue
            
        # Add repo_name to config_fields
        if isinstance(config_fields, str):
            config_fields = json.loads(config_fields) if config_fields else {}
        config_fields['repo_name'] = repo_name
        
        # Remove repo_name from credentials and re-encrypt
        del decrypted_credentials['repo_name']
        new_encrypted_credentials = encrypt_data(decrypted_credentials)
        
        # Update both tables
        op.execute(f"""
            UPDATE source_connection 
            SET config_fields = '{json.dumps(config_fields)}'::jsonb,
                modified_at = CURRENT_TIMESTAMP
            WHERE id = '{source_connection_id}'
        """)
        
        op.execute(f"""
            UPDATE integration_credential 
            SET encrypted_credentials = '{new_encrypted_credentials}',
                modified_at = CURRENT_TIMESTAMP
            WHERE id = '{credential_id}'
        """)
        
        migrated_count += 1
    
    print(f"Migrated {migrated_count} GitHub connections")


def downgrade():
    """Reverse the migration by moving repo_name back to encrypted credentials."""
    
    # Check encryption key is available
    try:
        get_encryption_key()
    except ValueError:
        raise RuntimeError("ENCRYPTION_KEY environment variable must be set")
    
    # Find GitHub connections that have repo_name in config_fields
    result = op.execute("""
        SELECT 
            sc.id as source_connection_id,
            sc.config_fields,
            ic.id as credential_id,
            ic.encrypted_credentials
        FROM source_connection sc
        JOIN connection c ON sc.connection_id = c.id
        JOIN integration_credential ic ON c.integration_credential_id = ic.id
        WHERE sc.short_name = 'github'
        AND sc.config_fields IS NOT NULL 
        AND (sc.config_fields::jsonb ? 'repo_name')
    """)
    
    reverted_count = 0
    
    for row in result:
        source_connection_id = row.source_connection_id
        config_fields = row.config_fields or {}
        credential_id = row.credential_id
        encrypted_credentials = row.encrypted_credentials
        
        # Parse config_fields if it's a string
        if isinstance(config_fields, str):
            config_fields = json.loads(config_fields) if config_fields else {}
        
        if 'repo_name' not in config_fields:
            continue
            
        repo_name = config_fields['repo_name']
        if not repo_name:
            continue
        
        # Decrypt existing credentials or start with empty dict
        decrypted_credentials = decrypt_data(encrypted_credentials) if encrypted_credentials else {}
        if decrypted_credentials is None:
            decrypted_credentials = {}
        
        # Add repo_name back to credentials
        decrypted_credentials['repo_name'] = repo_name
        new_encrypted_credentials = encrypt_data(decrypted_credentials)
        
        # Remove repo_name from config_fields
        del config_fields['repo_name']
        
        # Update both tables
        if config_fields:
            op.execute(f"""
                UPDATE source_connection 
                SET config_fields = '{json.dumps(config_fields)}'::jsonb,
                    modified_at = CURRENT_TIMESTAMP
                WHERE id = '{source_connection_id}'
            """)
        else:
            op.execute(f"""
                UPDATE source_connection 
                SET config_fields = NULL,
                    modified_at = CURRENT_TIMESTAMP
                WHERE id = '{source_connection_id}'
            """)
        
        op.execute(f"""
            UPDATE integration_credential 
            SET encrypted_credentials = '{new_encrypted_credentials}',
                modified_at = CURRENT_TIMESTAMP
            WHERE id = '{credential_id}'
        """)
        
        reverted_count += 1
    
    print(f"Reverted {reverted_count} GitHub connections")