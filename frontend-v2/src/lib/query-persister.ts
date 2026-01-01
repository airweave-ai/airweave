import type { PersistedClient, Persister } from "@tanstack/react-query-persist-client";
import { del, get, set } from "idb-keyval";

const IDB_KEY = "airweave-query-cache";

/**
 * Creates an IndexedDB persister for TanStack Query.
 * This allows query cache to persist across page reloads for instant loading.
 */
export function createIDBPersister(): Persister {
  return {
    persistClient: async (client: PersistedClient) => {
      try {
        await set(IDB_KEY, client);
      } catch (error) {
        console.debug("Failed to persist query cache:", error);
      }
    },
    restoreClient: async () => {
      try {
        return await get<PersistedClient>(IDB_KEY);
      } catch (error) {
        console.debug("Failed to restore query cache:", error);
        return undefined;
      }
    },
    removeClient: async () => {
      try {
        await del(IDB_KEY);
      } catch (error) {
        console.debug("Failed to remove query cache:", error);
      }
    },
  };
}

/**
 * Cache duration: 1 hour in milliseconds.
 * Data older than this will be considered stale and refetched.
 */
export const CACHE_MAX_AGE = 1000 * 60 * 60; // 1 hour

