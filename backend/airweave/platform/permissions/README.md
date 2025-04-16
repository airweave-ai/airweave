# Permission-Aware Vector Search

This module implements a permission-aware vector search system for Airweave, allowing source-specific permission models to be applied at query time when searching vector databases.

## Architecture

The system consists of three main components:

1. **Source-Specific Permission Classes**: Each source has dedicated Pydantic models in `permissions/{source}.py` to represent:
   - `{Source}UserPermission`: A user's identity and permissions in that system
   - `{Source}PermissionMetadata`: Permission data stored with each entity

2. **Permission Filters**: Source-specific filter builders that generate Qdrant filters based on user permissions.

3. **Source Integration**: Source connectors add permission metadata to entities during ingestion and implement `get_user_permissions()`.

## How It Works

### During Ingestion

1. Source connectors attach permission metadata to each entity as Pydantic models:
   ```python
   permission_metadata = AsanaPermissionMetadata(workspace_gid=workspace_id, ...)
   entity.sync_metadata["permissions"] = permission_metadata.model_dump()
   ```

2. This standardized permission metadata is included in the vector database when entities are indexed.

### During Search

1. When a user performs a search, the search service identifies the source type.
2. It calls the appropriate permission filter builder for that source.
3. The filter builder fetches the user's permissions using the UserPermission model.
4. The filter builder constructs Qdrant filters to restrict results based on the user's permissions.
5. These filters are applied to the vector search query, ensuring users only see results they have permission to access.

## Implementation: Asana

The Asana implementation demonstrates this pattern:

### Permission Models (`platform/permissions/asana.py`)

```python
class AsanaUserPermission(BaseModel):
    """Represents a user's permissions in Asana."""
    user_email: str
    user_gid: str
    workspaces: List[Dict[str, str]]
    teams: List[Dict[str, str]]

    @classmethod
    async def from_email(cls, email: str) -> "AsanaUserPermission":
        # Fetch user's Asana permissions

class AsanaPermissionMetadata(BaseModel):
    """Asana-specific permission metadata for entities."""
    source_name: str = "asana"
    workspace_gid: Optional[str] = None
    is_public: bool = False
    # Other permission fields...

class AsanaPermissionFilters:
    """Builds Qdrant filters for Asana permissions."""

    @staticmethod
    async def build_filters(user_email: str) -> Dict[str, Any]:
        # Build Qdrant filters based on user's Asana permissions
```

### Source Integration (`platform/sources/asana.py`)

```python
class AsanaSource(BaseSource):
    # Base URL for Asana API
    BASE_URL = "https://app.asana.com/api/1.0"

    @classmethod
    async def get_user_permissions(cls, email: str) -> AsanaUserPermission:
        """Get permissions for a user in Asana."""
        return await AsanaUserPermission.from_email(email)

    # During entity generation
    async def _generate_entities(self):
        # Create entity
        entity = AsanaEntityType(...)

        # Add permission metadata
        permission_metadata = AsanaPermissionMetadata(
            workspace_gid=workspace_id,
            is_public=is_public,
            # Other permission attributes
        )
        entity.sync_metadata["permissions"] = permission_metadata.model_dump()
```

### Search Service Integration

```python
if source_type == "asana":
    from airweave.platform.permissions.asana import AsanaPermissionFilters
    permission_filters = await AsanaPermissionFilters.build_filters(user_email=current_user.email)
```

## Adding New Source Permissions

To add permission-aware search for a new source:

1. Create Pydantic models in a new file `permissions/new_source.py`:
   - `NewSourceUserPermission` with a `from_email()` class method
   - `NewSourcePermissionMetadata` defining the permission schema

2. Implement `get_user_permissions()` in the source connector

3. Add permission metadata to entities during ingestion

4. Create a filter builder class with `build_filters()` method

5. Add the source type handling in `search_service.py`

This architecture keeps permissions clearly separated between sources while maintaining type safety with Pydantic schemas.
