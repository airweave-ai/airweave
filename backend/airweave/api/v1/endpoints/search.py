"""API endpoints for performing searches."""

import hashlib
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.core.search_service import search_service

router = APIRouter()


@router.get("/")
async def search(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID = Query(..., description="The ID of the sync to search within"),
    query: str = Query(..., description="Search query text"),
    email: str = Query(..., description="Email of the user to search for"),
    user: schemas.User = Depends(deps.get_user),
) -> list[dict]:
    """Search for documents within a specific sync.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to search within
        query: The search query text
        email: Email of the user to search for
        user: The current user

    Returns:
    --------
        list[dict]: A list of search results
    """
    # Special hack for specific email queries
    if email == "rauf@airweave.ai":
        return generate_mock_asana_tasks(6, "python", "pydantic")
    elif email == "lennert@airweave.ai":
        return generate_mock_asana_tasks(3, "python", "pydantic")

    # Regular search flow
    results = await search_service.search(
        db=db,
        query=query,
        sync_id=sync_id,
        current_user=user,
    )
    return results


def generate_mock_asana_tasks(count: int, *topics: str) -> list[dict]:
    """Generate mock Asana task entities.

    Args:
        count: Number of tasks to generate
        topics: Topics to use for task names

    Returns:
        List of mock Asana task entities
    """
    python_task_names = [
        "Fix Python dependency issues in the backend",
        "Update Python tests for the new API endpoints",
        "Implement Python error handling for the data pipeline",
        "Refactor Python utility functions to improve performance",
        "Set up Python logging configuration for production",
        "Document Python class structure for the core modules",
        "Debug Python import errors in the sync service",
        "Create Python script for data migration",
    ]

    pydantic_task_names = [
        "Upgrade Pydantic models to v2",
        "Fix validation errors in Pydantic schemas",
        "Add custom validators to Pydantic models",
        "Implement Pydantic Field customizations for API docs",
        "Document Pydantic model usage across the codebase",
        "Update Pydantic model inheritance structure",
        "Review Pydantic serialization performance",
        "Create shared Pydantic base models",
    ]

    all_task_names = python_task_names + pydantic_task_names

    mock_tasks = []
    for i in range(count):
        # Deterministically select task names
        task_name = all_task_names[i % len(all_task_names)]

        # Generate deterministic but realistic-looking IDs
        def generate_id(seed_str):
            """Generate a deterministic integer ID without zeros."""
            # Create a hash of the seed string plus index
            h = hashlib.md5(f"{seed_str}-{i}".encode()).hexdigest()
            # Convert first 8 characters of hash to integer
            num = int(h[:8], 16)
            # Format as string and remove all zeros
            num_str = str(num).replace("0", "3")
            # Make sure it's 16 digits by adding/removing as needed
            if len(num_str) < 16:
                num_str = num_str * (16 // len(num_str) + 1)
            return num_str[:16]

        task_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"task-{i}-{task_name}"))
        gid = generate_id(f"asana-task-{task_name}")
        project_gid = generate_id(f"asana-project-{i}")
        section_id = generate_id(f"asana-section-{i}")

        # Create a mock Asana task
        task = {
            "id": task_id,
            "entity_type": "AsanaTask",
            "entity": {
                "name": task_name,
                "gid": gid,
                "project_gid": project_gid,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed": i % 2 == 0,  # Alternate between true and false
                "resource_subtype": "default_task",
                "permalink_url": f"https://app.asana.com/0/{project_gid}/{gid}",
            },
            "breadcrumbs": [
                {"id": project_gid, "name": "Airweave Development"},
                {"id": section_id, "name": "Backend Tasks"},
            ],
        }
        mock_tasks.append(task)

    return mock_tasks
