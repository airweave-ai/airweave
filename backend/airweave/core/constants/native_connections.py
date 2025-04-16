"""Constants for native connections."""

import uuid

# Native connection UUIDs - these must match the ones in init_db_native.py
NATIVE_QDRANT_UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
NATIVE_NEO4J_UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")
NATIVE_TEXT2VEC_UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")

# String versions for use in frontend code or string contexts
NATIVE_QDRANT_UUID_STR = str(NATIVE_QDRANT_UUID)
NATIVE_NEO4J_UUID_STR = str(NATIVE_NEO4J_UUID)
NATIVE_TEXT2VEC_UUID_STR = str(NATIVE_TEXT2VEC_UUID)
