"""Backward-compatible re-exports for HERB entity classes.

The HERB entities were split into per-source files (herb_documents.py,
herb_messaging.py, etc.) for db_sync compatibility. Existing snapshots
on Azure still reference the old module path
``airweave.platform.entities.herb``, so this shim re-exports all entity
classes to keep snapshot replay working.
"""

from airweave.platform.entities.herb_code_review import *  # noqa: F401, F403
from airweave.platform.entities.herb_documents import *  # noqa: F401, F403
from airweave.platform.entities.herb_meetings import *  # noqa: F401, F403
from airweave.platform.entities.herb_messaging import *  # noqa: F401, F403
from airweave.platform.entities.herb_people import *  # noqa: F401, F403
from airweave.platform.entities.herb_resources import *  # noqa: F401, F403
