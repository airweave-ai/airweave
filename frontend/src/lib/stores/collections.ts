import { create } from 'zustand';
import { apiClient } from '@/lib/api';
import { onCollectionEvent, COLLECTION_DELETED, COLLECTION_CREATED, COLLECTION_UPDATED } from "@/lib/events";

// Lightweight source connection info included in collection list responses
export interface SourceConnectionSummary {
  short_name: string;
  name: string;
}

// Interface for Collection type
export interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
  source_connection_summaries?: SourceConnectionSummary[];
}

// Interface for SourceConnection type (still used by CollectionDetailView)
export interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  collection: string;
  status?: string;
}

interface CollectionsState {
  collections: Collection[];
  totalCount: number | null;
  isLoading: boolean;
  error: string | null;

  // Request deduplication
  inflightCollectionsRequest: Promise<Collection[]> | null;
  lastCollectionsFetch: number;

  fetchCollections: (forceRefresh?: boolean) => Promise<Collection[]>;
  fetchCollectionsCount: (searchQuery?: string) => Promise<number>;
  fetchCollectionsPaginated: (skip: number, limit: number, searchQuery?: string) => Promise<Collection[]>;
  subscribeToEvents: () => () => void;
  clearCollections: () => void;
}

export const useCollectionsStore = create<CollectionsState>((set, get) => ({
  collections: [],
  totalCount: null,
  isLoading: false,
  error: null,
  inflightCollectionsRequest: null,
  lastCollectionsFetch: 0,

  fetchCollections: async (forceRefresh = false) => {
    const now = Date.now();
    const { lastCollectionsFetch, collections, inflightCollectionsRequest } = get();

    if (!forceRefresh && lastCollectionsFetch && (now - lastCollectionsFetch) < 5000 && collections.length > 0) {
      return collections;
    }

    if (!forceRefresh && inflightCollectionsRequest) {
      return inflightCollectionsRequest;
    }

    const request = (async () => {
      set({ isLoading: true, error: null });

      try {
        const response = await apiClient.get('/collections');

        if (response.ok) {
          const data = await response.json();
          set({
            collections: data,
            isLoading: false,
            inflightCollectionsRequest: null,
            lastCollectionsFetch: Date.now()
          });
          return data;
        } else {
          const errorText = await response.text();
          const errorMessage = `Failed to load collections: ${errorText}`;
          set({ error: errorMessage, isLoading: false, inflightCollectionsRequest: null });
          return get().collections;
        }
      } catch (err) {
        const errorMessage = `An error occurred: ${err instanceof Error ? err.message : String(err)}`;
        set({ error: errorMessage, isLoading: false, inflightCollectionsRequest: null });
        return get().collections;
      }
    })();

    set({ inflightCollectionsRequest: request });
    return request;
  },

  fetchCollectionsCount: async (searchQuery?: string) => {
    try {
      const params = new URLSearchParams();
      if (searchQuery) {
        params.set('search', searchQuery);
      }
      const url = params.toString() ? `/collections/count?${params}` : '/collections/count';
      const response = await apiClient.get(url);
      if (response.ok) {
        const count = await response.json();
        set({ totalCount: count });
        return count;
      }
    } catch (err) {
      console.error('Failed to fetch collections count:', err);
    }
    return get().totalCount || 0;
  },

  fetchCollectionsPaginated: async (skip: number, limit: number, searchQuery?: string) => {
    try {
      const params = new URLSearchParams({
        skip: skip.toString(),
        limit: limit.toString(),
      });

      if (searchQuery) {
        params.set('search', searchQuery);
      }

      const response = await apiClient.get(`/collections?${params}`);

      if (response.ok) {
        const data = await response.json();
        return data;
      } else {
        throw new Error('Failed to fetch collections');
      }
    } catch (err) {
      console.error('Failed to load paginated collections:', err);
      return [];
    }
  },

  subscribeToEvents: () => {
    const unsubscribeDeleted = onCollectionEvent(COLLECTION_DELETED, () => {
      get().fetchCollections(true);
    });

    const unsubscribeCreated = onCollectionEvent(COLLECTION_CREATED, () => {
      get().fetchCollections(true);
    });

    const unsubscribeUpdated = onCollectionEvent(COLLECTION_UPDATED, () => {
      get().fetchCollections(true);
    });

    return () => {
      unsubscribeDeleted();
      unsubscribeCreated();
      unsubscribeUpdated();
    };
  },

  clearCollections: () => {
    set({
      collections: [],
      isLoading: false,
      error: null,
    });
  }
}));
