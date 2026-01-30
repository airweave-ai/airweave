"""OAuth client loader from YAML configuration.

Loads OAuth client definitions from oauth_clients.yaml and syncs them to the database.
Similar to how integrations are loaded.
"""

import yaml
from pathlib import Path
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.exceptions import NotFoundException


async def load_oauth_clients(db: AsyncSession) -> None:
    """Load OAuth clients from YAML and sync to database.
    
    This function:
    1. Reads oauth_clients.yaml from the same directory
    2. Creates or updates OAuth clients in the database
    3. Uses client_id as the unique identifier (upsert logic)
    
    Args:
        db: Database session
    """
    yaml_path = Path(__file__).parent / "oauth_clients.yaml"
    
    if not yaml_path.exists():
        print(f"⚠️  OAuth clients YAML not found at {yaml_path}")
        return
    
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if not config or 'oauth_clients' not in config:
        print("⚠️  No oauth_clients found in YAML")
        return
    
    clients_data = config['oauth_clients']
    created_count = 0
    updated_count = 0
    
    for client_id, client_config in clients_data.items():
        try:
            # Check if client already exists
            existing_client = await crud.oauth_client.get_by_client_id(db, client_id=client_id)
            
            # Update existing client
            update_data = schemas.OAuthClientUpdate(
                name=client_config.get('name'),
                redirect_uris=client_config.get('redirect_uris'),
                grant_types=client_config.get('grant_types'),
            )
            await crud.oauth_client.update(
                db,
                db_obj=existing_client,
                obj_in=update_data,
            )
            updated_count += 1
            print(f"✓ Updated OAuth client: {client_id}")
            
        except NotFoundException:
            # Create new client
            create_data = schemas.OAuthClientCreate(
                client_id=client_id,
                name=client_config['name'],
                redirect_uris=client_config['redirect_uris'],
                grant_types=client_config['grant_types'],
                client_type=client_config.get('client_type', 'public'),
            )
            await crud.oauth_client.create(db, obj_in=create_data)
            created_count += 1
            print(f"✓ Created OAuth client: {client_id}")
    
    print(f"📝 OAuth clients loaded: {created_count} created, {updated_count} updated")
