import React, { useState, useEffect } from 'react';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { ArrowLeft, Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { getAppIconUrl } from '@/lib/utils/icons';

interface Source {
  short_name: string;
  name: string;
  description: string;
  auth_type: string;
  icon_url?: string;
  labels?: string[];
}

interface SourceSelectViewProps {
  humanReadableId: string;
  isAddingToExisting?: boolean;
}

export const SourceSelectView: React.FC<SourceSelectViewProps> = ({ humanReadableId, isAddingToExisting = false }) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const {
    selectedSource,
    selectSource,
    setStep,
    closeModal
  } = useCollectionCreationStore();

  const [sources, setSources] = useState<Source[]>([]);
  const [filteredSources, setFilteredSources] = useState<Source[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadSources();
  }, []);

  useEffect(() => {
    filterSources();
  }, [searchQuery, sources]);

  const loadSources = async () => {
    try {
      // Use the correct endpoint path without /api/v1 prefix
      const response = await apiClient.get('/sources/list');
      if (response.ok) {
        const data = await response.json();
        setSources(data);
        // Don't set filtered sources here, let the effect handle it
      }
    } catch (error) {
      console.error('Error loading sources:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filterSources = () => {
    let filtered = [...sources];

    // Filter by search query (case-insensitive)
    if (searchQuery) {
      filtered = filtered.filter(s =>
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.short_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.description?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredSources(filtered);
  };

  const handleSelectSource = (source: Source) => {
    selectSource(source.short_name, source.name);

    // Determine auth mode based on auth_type
    const store = useCollectionCreationStore.getState();
    if (source.auth_type?.startsWith('oauth2')) {
      store.setAuthMode('oauth2');
    } else if (source.auth_type === 'api_key' || source.auth_type === 'basic') {
      store.setAuthMode('direct_auth');
    }

    setStep('source-config');
  };

  return (
    <div className="h-full flex">
      {/* Left side - Header and Filter */}
      <div className={cn(
        "w-80 border-r flex flex-col",
        isDark ? "border-gray-800 bg-gray-900/50" : "border-gray-200 bg-gray-50"
      )}>
        {/* Header */}
        <div className="px-6 py-6">
          <div className="flex items-center gap-3 mb-6">
            {!isAddingToExisting && (
              <button
                onClick={() => setStep('collection-form')}
                className={cn(
                  "p-1.5 rounded-lg transition-colors",
                  isDark
                    ? "hover:bg-gray-800 text-gray-400"
                    : "hover:bg-gray-100 text-gray-500"
                )}
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            )}
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Select a source
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Choose where to sync data from
              </p>
            </div>
          </div>

          {/* Search input */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
              Filter
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Type to search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
                className={cn(
                  "w-full pl-9 pr-8 py-2 rounded-lg text-sm",
                  "border transition-colors",
                  "focus:outline-none focus:ring-1 focus:ring-blue-500",
                  isDark
                    ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                    : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                )}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                  title="Clear search"
                >
                  <X className="w-3 h-3 text-gray-400" />
                </button>
              )}
            </div>
          </div>

          {/* Results count */}
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {filteredSources.length} {filteredSources.length === 1 ? 'source' : 'sources'} available
          </div>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Cancel button at bottom */}
        <div className="px-6 pb-6">
          <button
            onClick={() => closeModal()}
            className={cn(
              "w-full px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              isDark
                ? "text-gray-400 hover:text-gray-200"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            Cancel
          </button>
        </div>
      </div>

      {/* Right side - Source grid */}
      <div className="flex-1 overflow-auto px-6 pt-16 pb-6">
        {/* Source Grid */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-gray-300 dark:border-gray-700 border-t-blue-600 dark:border-t-blue-400 rounded-full animate-spin" />
          </div>
        ) : filteredSources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="text-gray-400 mb-4">
              {searchQuery ? 'No sources found' : 'No sources available'}
            </div>
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Clear search
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-3">
            {filteredSources.map((source) => (
              <button
                key={source.short_name}
                onClick={() => handleSelectSource(source)}
                className={cn(
                  "group relative p-3 rounded-lg border transition-all duration-200",
                  "flex flex-col items-center gap-2",
                  isDark
                    ? "bg-gray-900/50 border-gray-800 hover:border-gray-700 hover:bg-gray-900"
                    : "bg-white border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                )}
                title={source.description || source.name}
              >
                {/* Source icon */}
                <div className="w-10 h-10 rounded-md overflow-hidden flex items-center justify-center relative">
                  <img
                    src={getAppIconUrl(source.short_name, resolvedTheme)}
                    alt={source.name}
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      // Hide the image and show fallback
                      const target = e.target as HTMLImageElement;
                      target.style.display = 'none';
                    }}
                  />
                  {/* Fallback - always rendered but hidden by default */}
                  <div
                    className={cn(
                      "absolute inset-0 flex items-center justify-center text-lg font-semibold rounded-md",
                      isDark ? "bg-gray-700 text-gray-300" : "bg-gray-100 text-gray-600"
                    )}
                    style={{
                      display: 'none',
                      // Show if image is hidden
                      ...(sources.find(s => s.short_name === source.short_name) && {})
                    }}
                  >
                    {source.name.charAt(0).toUpperCase()}
                  </div>
                </div>

                {/* Source name */}
                <span className="text-xs font-medium text-gray-900 dark:text-white text-center line-clamp-1">
                  {source.name}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
