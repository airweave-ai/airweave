"""Pure types and logic for the users domain.

Every function here is deterministic and performs zero I/O.
Test with direct calls — no fixtures needed.
"""

from dataclasses import dataclass
from typing import Optional

from airweave import schemas

# ---------------------------------------------------------------------------
# Result type for create-or-update
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreateOrUpdateResult:
    """Outcome of the create-or-update user flow.

    ``is_new`` tells the caller whether the user was just created (True)
    or was an existing user that got synced/returned (False).
    """

    user: schemas.User
    is_new: bool


# ---------------------------------------------------------------------------
# Authorization guard
# ---------------------------------------------------------------------------


def is_email_authorized(request_email: str, auth_email: str) -> bool:
    """Check whether the requesting email matches the authenticated email."""
    return request_email == auth_email


# ---------------------------------------------------------------------------
# Auth0 ID conflict detection
# ---------------------------------------------------------------------------


def has_auth0_id_conflict(
    existing_auth0_id: Optional[str], incoming_auth0_id: Optional[str]
) -> bool:
    """Detect a conflict between existing and incoming Auth0 IDs.

    A conflict means the same email is associated with two different Auth0
    identities — typically caused by signing up with a different auth method.
    """
    return bool(existing_auth0_id and incoming_auth0_id and existing_auth0_id != incoming_auth0_id)
