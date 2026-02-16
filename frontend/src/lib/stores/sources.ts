import { create } from 'zustand';
import { apiClient } from '@/lib/api';

// Interface for Source
export interface Source {
  name: string;
  description?: string | null;
  short_name: string;
  labels?: string[];
}

// Interface for Source Details (extended source info)
export interface SourceDetail {
  name: string;
  short_name: string;
  auth_type?: string;
  auth_fields?: {
    fields: any[];
  };
  [key: string]: any; // For any additional fields
}

interface SourcesState {
  sources: Source[];
  isLoading: boolean;
  error: string | null;
  sourceDetails: Record<string, SourceDetail>; // Cache for source details
  sourceDetailsLoading: Record<string, boolean>;
  sourceDetailsError: Record<string, string | null>;

  fetchSources: (forceRefresh?: boolean) => Promise<Source[]>;
  getSourceDetails: (shortName: string) => Promise<SourceDetail | null>;
  clearSourceDetails: (shortName: string) => void;
  clearAllSourceDetails: () => void;
}

export const useSourcesStore = create<SourcesState>((set, get) => ({
  sources: [],
  isLoading: false,
  error: null,
  sourceDetails: {},
  sourceDetailsLoading: {},
  sourceDetailsError: {},

  fetchSources: async (forceRefresh = false) => {
    // If sources are already loaded and no force refresh requested, return existing data
    const { sources, isLoading } = get();
    if (sources.length > 0 && !forceRefresh) {
      console.log("🔍 [SourcesStore] Using cached sources list, skipping API call");
      return sources;
    }

    // If we're already loading, don't start another request
    if (isLoading && !forceRefresh) {
      console.log("🔍 [SourcesStore] Sources already loading, skipping duplicate request");
      return sources;
    }

    console.log("🔍 [SourcesStore] Fetching sources from API");
    set({ isLoading: true, error: null });

    try {
      const response = await apiClient.get('/sources/');

      if (response.ok) {
        const data = await response.json();
        set({ sources: data, isLoading: false });
        return data;
      } else {
        const errorText = await response.text();
        const errorMessage = `Failed to load sources: ${errorText}`;
        set({ error: errorMessage, isLoading: false });
        console.error("❌ [SourcesStore]", errorMessage);
        return get().sources;
      }
    } catch (err) {
      const errorMessage = `An error occurred: ${err instanceof Error ? err.message : String(err)}`;
      set({ error: errorMessage, isLoading: false });
      console.error("❌ [SourcesStore]", errorMessage);
      return get().sources;
    }
  },

  getSourceDetails: async (shortName: string) => {
    // Return cached details if available
    if (get().sourceDetails[shortName]) {
      console.log(`🔍 [SourcesStore] Using cached details for ${shortName}`);
      return get().sourceDetails[shortName];
    }

    // Check if already loading this source
    if (get().sourceDetailsLoading[shortName]) {
      console.log(`🔍 [SourcesStore] Details for ${shortName} already loading, waiting for completion`);
      // Wait for the existing request to complete
      let attempts = 0;
      while (get().sourceDetailsLoading[shortName] && attempts < 20) {
        await new Promise(resolve => setTimeout(resolve, 100)); // Wait 100ms
        attempts++;
      }
      // If successful, return the cached result
      if (get().sourceDetails[shortName]) {
        return get().sourceDetails[shortName];
      }
    }

    // Set loading state for this specific source
    console.log(`🔍 [SourcesStore] Fetching details for ${shortName}`);
    set(state => ({
      sourceDetailsLoading: { ...state.sourceDetailsLoading, [shortName]: true },
      sourceDetailsError: { ...state.sourceDetailsError, [shortName]: null }
    }));

    try {
      const response = await apiClient.get(`/sources/${shortName}`);

      if (response.ok) {
        const data = await response.json();

        // Update the cache with new details
        set(state => ({
          sourceDetails: { ...state.sourceDetails, [shortName]: data },
          sourceDetailsLoading: { ...state.sourceDetailsLoading, [shortName]: false }
        }));

        return data;
      } else {
        const errorText = await response.text();
        const errorMessage = `Failed to fetch source details: ${errorText}`;

        set(state => ({
          sourceDetailsError: { ...state.sourceDetailsError, [shortName]: errorMessage },
          sourceDetailsLoading: { ...state.sourceDetailsLoading, [shortName]: false }
        }));

        return null;
      }
    } catch (err) {
      const errorMessage = `An error occurred: ${err instanceof Error ? err.message : String(err)}`;

      set(state => ({
        sourceDetailsError: { ...state.sourceDetailsError, [shortName]: errorMessage },
        sourceDetailsLoading: { ...state.sourceDetailsLoading, [shortName]: false }
      }));

      return null;
    }
  },

  clearSourceDetails: (shortName: string) => {
    set(state => {
      const { [shortName]: _, ...restDetails } = state.sourceDetails;
      const { [shortName]: __, ...restLoading } = state.sourceDetailsLoading;
      const { [shortName]: ___, ...restError } = state.sourceDetailsError;

      return {
        sourceDetails: restDetails,
        sourceDetailsLoading: restLoading,
        sourceDetailsError: restError
      };
    });
  },

  clearAllSourceDetails: () => {
    set({
      sourceDetails: {},
      sourceDetailsLoading: {},
      sourceDetailsError: {}
    });
  }
}));
