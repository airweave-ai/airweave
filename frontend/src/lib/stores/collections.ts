import { create } from 'zustand';
import { apiClient } from '@/lib/api';
import { onCollectionEvent, COLLECTION_DELETED, COLLECTION_CREATED, COLLECTION_UPDATED } from "@/lib/events";

// Interface for Collection type
export interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
}

// Interface for SourceConnection type
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
  // Cache for source connections by collection ID
  sourceConnections: Record<string, SourceConnection[]>;
  sourceConnectionsLoading: Record<string, boolean>;

  // Request deduplication
  inflightCollectionsRequest: Promise<Collection[]> | null;
  inflightSourceRequests: Record<string, Promise<SourceConnection[]>>;
  lastCollectionsFetch: number;
  lastSourceFetch: Record<string, number>;

  fetchCollections: (forceRefresh?: boolean) => Promise<Collection[]>;
  fetchCollectionsCount: (searchQuery?: string) => Promise<number>;
  fetchCollectionsPaginated: (skip: number, limit: number, searchQuery?: string) => Promise<Collection[]>;
  fetchSourceConnections: (collectionId: string, forceRefresh?: boolean) => Promise<SourceConnection[]>;
  subscribeToEvents: () => () => void;
  clearCollections: () => void;
}

export const useCollectionsStore = create<CollectionsState>((set, get) => ({
  collections: [],
  totalCount: null,
  isLoading: false,
  error: null,
  sourceConnections: {},
  sourceConnectionsLoading: {},
  inflightCollectionsRequest: null,
  inflightSourceRequests: {},
  lastCollectionsFetch: 0,
  lastSourceFetch: {},

  fetchCollections: async (forceRefresh = false) => {
    // Check if we have a recent fetch (within 5 seconds) unless force refresh
    const now = Date.now();
    const { lastCollectionsFetch, collections, inflightCollectionsRequest } = get();

    if (!forceRefresh && lastCollectionsFetch && (now - lastCollectionsFetch) < 5000 && collections.length > 0) {
      console.log('Using cached collections (fetched', Math.round((now - lastCollectionsFetch) / 1000), 'seconds ago)');
      return collections;
    }

    // If there's already a request in flight and no force refresh, return it
    if (!forceRefresh && inflightCollectionsRequest) {
      console.log('Returning existing collections request');
      return inflightCollectionsRequest;
    }

    // Create new request
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

  fetchSourceConnections: async (collectionId: string, forceRefresh = false) => {
    // Check if we have a recent fetch (within 5 seconds) unless force refresh
    const now = Date.now();
    const { lastSourceFetch, sourceConnections, inflightSourceRequests } = get();
    const lastFetch = lastSourceFetch[collectionId];

    if (!forceRefresh && lastFetch && (now - lastFetch) < 5000 && sourceConnections[collectionId]) {
      console.log(`Using cached source connections for ${collectionId} (fetched`, Math.round((now - lastFetch) / 1000), 'seconds ago)');
      return sourceConnections[collectionId];
    }

    // If there's already a request in flight and no force refresh, return it
    if (!forceRefresh && inflightSourceRequests[collectionId]) {
      console.log(`Returning existing source connections request for ${collectionId}`);
      return inflightSourceRequests[collectionId];
    }

    // Create new request
    const request = (async () => {
      // Mark as loading
      set(state => ({
        sourceConnectionsLoading: {
          ...state.sourceConnectionsLoading,
          [collectionId]: true
        }
      }));

      try {
        const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);

        if (response.ok) {
          const data = await response.json();
          set(state => ({
            sourceConnections: {
              ...state.sourceConnections,
              [collectionId]: data
            },
            sourceConnectionsLoading: {
              ...state.sourceConnectionsLoading,
              [collectionId]: false
            },
            inflightSourceRequests: {
              ...state.inflightSourceRequests,
              [collectionId]: undefined
            },
            lastSourceFetch: {
              ...state.lastSourceFetch,
              [collectionId]: Date.now()
            }
          }));
          return data;
        } else {
          console.error(`Failed to load source connections for ${collectionId}:`, await response.text());
          set(state => ({
            sourceConnections: {
              ...state.sourceConnections,
              [collectionId]: []
            },
            sourceConnectionsLoading: {
              ...state.sourceConnectionsLoading,
              [collectionId]: false
            },
            inflightSourceRequests: {
              ...state.inflightSourceRequests,
              [collectionId]: undefined
            }
          }));
          return [];
        }
      } catch (err) {
        console.error(`Error fetching source connections for ${collectionId}:`, err);
        set(state => ({
          sourceConnections: {
            ...state.sourceConnections,
            [collectionId]: []
          },
          sourceConnectionsLoading: {
            ...state.sourceConnectionsLoading,
            [collectionId]: false
          },
          inflightSourceRequests: {
            ...state.inflightSourceRequests,
            [collectionId]: undefined
          }
        }));
        return [];
      }
    })();

    // Store the inflight request
    set(state => ({
      inflightSourceRequests: {
        ...state.inflightSourceRequests,
        [collectionId]: request
      }
    }));

    return request;
  },

  subscribeToEvents: () => {
    // Subscribe to collection events

    const unsubscribeDeleted = onCollectionEvent(COLLECTION_DELETED, () => {
      get().fetchCollections(true); // Force refresh on delete
    });

    const unsubscribeCreated = onCollectionEvent(COLLECTION_CREATED, () => {
      get().fetchCollections(true); // Force refresh on create
    });

    const unsubscribeUpdated = onCollectionEvent(COLLECTION_UPDATED, () => {
      get().fetchCollections(true); // Force refresh on update
    });

    // Return function to unsubscribe from all events
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
      sourceConnections: {},
      sourceConnectionsLoading: {}
    });
  }
}));
