/**
 * Constants for native connections.
 * These MUST match the UUIDs defined in backend/airweave/core/constants/native_connections.py
 */

// Native connection UUIDs
export const NATIVE_QDRANT_UUID = "11111111-1111-1111-1111-111111111111";
export const NATIVE_NEO4J_UUID = "22222222-2222-2222-2222-222222222222";
export const NATIVE_TEXT2VEC_UUID = "33333333-3333-3333-3333-333333333333";

// Map of connection short names to their UUIDs
export const NATIVE_CONNECTION_UUIDS = {
  qdrant_native: NATIVE_QDRANT_UUID,
  neo4j_native: NATIVE_NEO4J_UUID,
  local_text2vec: NATIVE_TEXT2VEC_UUID,
};
