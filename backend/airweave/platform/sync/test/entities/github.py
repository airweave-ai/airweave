"""Real GitHub entities captured from actual sync for testing."""

from datetime import datetime, timezone

from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.github import (
    GitHubCodeFileEntity,
    GitHubDirectoryEntity,
    GitHubRepositoryEntity,
)

# Repository entity
repository = GitHubRepositoryEntity(
    entity_id="907754163",
    breadcrumbs=[],
    name="airweave",
    created_at=datetime(2024, 11, 21, 16, 36, 49, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 19, 13, 45, 44, tzinfo=timezone.utc),
    full_name="airweave-ai/airweave",
    description="Open-source agentic search across apps and databases",
    default_branch="main",
    language="Python",
    fork=False,
    size=95234,
    stars_count=2734,
    watchers_count=2734,
    forks_count=156,
    open_issues_count=42,
)

# Directory entity
directory = GitHubDirectoryEntity(
    entity_id="airweave-ai/airweave/backend/airweave/core",
    breadcrumbs=[
        Breadcrumb(entity_id="907754163"),
        Breadcrumb(entity_id="airweave-ai/airweave/backend"),
        Breadcrumb(entity_id="airweave-ai/airweave/backend/airweave"),
    ],
    name="core",
    created_at=None,
    updated_at=None,
    path="backend/airweave/core",
    repo_name="airweave",
    repo_owner="airweave-ai",
)


# Code File 1: THE LARGEST - source_connection_service.py (75,804 bytes)
code_file_largest = GitHubCodeFileEntity(
    entity_id="airweave-ai/airweave/backend/airweave/core/source_connection_service.py",
    breadcrumbs=[
        Breadcrumb(entity_id="907754163"),
        Breadcrumb(entity_id="airweave-ai/airweave/backend"),
        Breadcrumb(entity_id="airweave-ai/airweave/backend/airweave"),
        Breadcrumb(entity_id="airweave-ai/airweave/backend/airweave/core"),
    ],
    name="source_connection_service.py",
    created_at=None,
    updated_at=None,
    url=(
        "https://github.com/airweave-ai/airweave/blob/main/backend/airweave/core/"
        "source_connection_service.py"
    ),
    size=75804,
    file_type="text",
    mime_type="text/x-python",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "source_connection_service.py"
    ),
    repo_name="airweave",
    path_in_repo="backend/airweave/core/source_connection_service.py",
    repo_owner="airweave-ai",
    language="Python",
    commit_id="9efa9960b1a956e71e924b1de787cd76c3d28f90",
    sha="9efa9960b1a956e71e924b1de787cd76c3d28f90",
    line_count=1869,
    is_binary=False,
)

# Code File 2: source_connection_service_helpers.py (65,063 bytes)
code_file_large = GitHubCodeFileEntity(
    entity_id="airweave-ai/airweave/backend/airweave/core/source_connection_service_helpers.py",
    breadcrumbs=[
        Breadcrumb(entity_id="907754163"),
        Breadcrumb(entity_id="airweave-ai/airweave/backend"),
        Breadcrumb(entity_id="airweave-ai/airweave/backend/airweave"),
        Breadcrumb(entity_id="airweave-ai/airweave/backend/airweave/core"),
    ],
    name="source_connection_service_helpers.py",
    created_at=None,
    updated_at=None,
    url=(
        "https://github.com/airweave-ai/airweave/blob/main/backend/airweave/core/"
        "source_connection_service_helpers.py"
    ),
    size=65063,
    file_type="text",
    mime_type="text/x-python",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "source_connection_service_helpers.py"
    ),
    repo_name="airweave",
    path_in_repo="backend/airweave/core/source_connection_service_helpers.py",
    repo_owner="airweave-ai",
    language="Python",
    commit_id="2824b8d6f78244f977b9efc834b8d79f10cefd4c",
    sha="2824b8d6f78244f977b9efc834b8d79f10cefd4c",
    line_count=1625,
    is_binary=False,
)

# Code File 3: Text file (should be SKIPPED - unsupported language)
text_file = GitHubCodeFileEntity(
    entity_id=(
        "airweave-ai/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Dec Feedback Eline.txt"
    ),
    breadcrumbs=[
        Breadcrumb(entity_id="907754163"),
        Breadcrumb(
            entity_id="airweave-ai/airweave/backend/airweave/platform/sync/test/entities/tmp"
        ),
    ],
    name="Dec Feedback Eline.txt",
    created_at=None,
    updated_at=None,
    url=(
        "https://github.com/airweave-ai/airweave/blob/main/backend/airweave/platform/sync/"
        "test/entities/tmp/Dec Feedback Eline.txt"
    ),
    size=2500,
    file_type="text",
    mime_type="text/plain",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Dec Feedback Eline.txt"
    ),
    repo_name="airweave",
    path_in_repo="backend/airweave/platform/sync/test/entities/tmp/Dec Feedback Eline.txt",
    repo_owner="airweave-ai",
    language="Text",
    commit_id="abc123def456",
    sha="abc123def456",
    line_count=27,
    is_binary=False,
)

# All entities in one list
github_examples = [
    repository,
    directory,
    code_file_largest,
    code_file_large,
    text_file,  # This should be filtered out as unsupported
]
