"""Constants for native connections."""

import uuid

# Native connection UUIDs - these must match the ones in init_db_native.py
NATIVE_NEO4J_UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")
NATIVE_VESPA_UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")

# String versions for use in frontend code or string contexts
NATIVE_NEO4J_UUID_STR = str(NATIVE_NEO4J_UUID)
NATIVE_VESPA_UUID_STR = str(NATIVE_VESPA_UUID)
