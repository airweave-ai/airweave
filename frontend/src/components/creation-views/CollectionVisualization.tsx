import React from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { getAppIconUrl } from '@/lib/utils/icons';
import { Plus } from 'lucide-react';

interface CollectionVisualizationProps {
  collectionName: string;
  humanReadableId: string;
  selectedSource?: string;
  sourceName?: string;
  sourceConnectionName?: string;
  currentStep: string;
}

export const CollectionVisualization: React.FC<CollectionVisualizationProps> = ({
  collectionName,
  humanReadableId,
  selectedSource,
  sourceName,
  sourceConnectionName,
  currentStep,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Get source icon using the proper utility function
  const getSourceIcon = () => {
    if (!selectedSource) {
      // Placeholder dashed box when no source selected
      return (
        <div className={cn(
          "w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center",
          isDark ? "border-gray-600" : "border-gray-400"
        )}>
          <Plus className={cn(
            "w-8 h-8",
            isDark ? "text-gray-600" : "text-gray-400"
          )} />
        </div>
      );
    }

    // Use the proper utility function to get the icon URL
    const iconUrl = getAppIconUrl(selectedSource, resolvedTheme);

    return (
      <img
        src={iconUrl}
        alt={sourceName || selectedSource}
        className="w-20 h-20 opacity-90"
      />
    );
  };

  return (
    <div className="h-full flex flex-col px-8 py-8">
      <div className="flex-1 flex flex-col justify-center">
        <div className="w-full max-w-lg mx-auto">
          {/* Collection title - with sketch-like appearance */}
          <div className="text-center mb-8">
            <h3 className={cn(
              "text-2xl font-light tracking-tight opacity-65",
              isDark ? "text-gray-400" : "text-gray-600"
            )}>
              {collectionName || 'Your Collection'}
            </h3>
          </div>

          {/* Sketch-like container with dashed border */}
          <div className="relative">
            {/* Header with ID and pseudo-tabs - more muted */}
            <div className={cn(
              "rounded-t-xl border-2 border-b-0 border-dashed px-5 py-3",
              isDark
                ? "bg-gray-900/35 border-gray-700"
                : "bg-gray-50 border-gray-300"
            )}>
              {/* Readable ID - more prominent */}
              <div className={cn(
                "text-xs font-mono mb-2 opacity-80",
                isDark ? "text-gray-400" : "text-gray-500"
              )}>
                {humanReadableId ? `#${humanReadableId}` : '#your-collection-id'}
              </div>

              {/* Pseudo tabs - clearly non-interactive */}
              <div className="flex gap-4">
                <div className={cn(
                  "text-xs font-medium pb-1 cursor-default",
                  "border-b-2 border-transparent opacity-45",
                  isDark ? "text-gray-500" : "text-gray-400"
                )}>
                  Search
                </div>
                <div className={cn(
                  "text-xs font-medium pb-1 cursor-default",
                  "border-b-2 opacity-65",
                  isDark
                    ? "text-gray-400 border-gray-600"
                    : "text-gray-500 border-gray-400"
                )}>
                  Source Connections
                </div>
              </div>
            </div>

            {/* Quadrant visualization - sketch-like with dashed borders */}
            <div className={cn(
              "rounded-b-xl border-2 border-t border-dashed p-5",
              isDark
                ? "bg-gray-900/35 border-gray-700"
                : "bg-gray-50 border-gray-300"
            )}>
              <div className={cn(
                "grid grid-cols-2 gap-1 rounded-lg overflow-hidden",
                isDark ? "bg-gray-800/25" : "bg-gray-100/60"
              )}>
                {/* Top left - Selected source icon or placeholder */}
                <div className={cn(
                  "aspect-square p-4",
                  isDark ? "bg-gray-900/50" : "bg-white/70"
                )}>
                  <div className="w-full h-full flex flex-col items-center justify-center">
                    {selectedSource ? (
                      <>
                        {getSourceIcon()}
                        <div className={cn(
                          "text-[10px] font-mono mt-2",
                          selectedSource ? "opacity-50" : "opacity-35",
                          isDark ? "text-gray-500" : "text-gray-400"
                        )}>
                          {sourceConnectionName || sourceName || selectedSource}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className={cn(
                          "w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center",
                          isDark ? "border-gray-700" : "border-gray-350"
                        )}>
                          <Plus className={cn(
                            "w-8 h-8 opacity-35",
                            isDark ? "text-gray-700" : "text-gray-350"
                          )} />
                        </div>
                        <div className={cn(
                          "text-[10px] font-mono opacity-35 mt-2",
                          isDark ? "text-gray-600" : "text-gray-400"
                        )}>
                          future source
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Top right - Placeholder for future source */}
                <div className={cn(
                  "aspect-square p-4",
                  isDark ? "bg-gray-900/50" : "bg-white/70"
                )}>
                  <div className="w-full h-full flex flex-col items-center justify-center">
                    <div className={cn(
                      "w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center",
                      isDark ? "border-gray-700" : "border-gray-350"
                    )}>
                      <Plus className={cn(
                        "w-8 h-8 opacity-35",
                        isDark ? "text-gray-700" : "text-gray-350"
                      )} />
                    </div>
                    <div className={cn(
                      "text-[10px] font-mono opacity-35 mt-2",
                      isDark ? "text-gray-600" : "text-gray-400"
                    )}>
                      future source
                    </div>
                  </div>
                </div>

                {/* Bottom left - Placeholder for future source */}
                <div className={cn(
                  "aspect-square p-4",
                  isDark ? "bg-gray-900/50" : "bg-white/70"
                )}>
                  <div className="w-full h-full flex flex-col items-center justify-center">
                    <div className={cn(
                      "w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center",
                      isDark ? "border-gray-700" : "border-gray-350"
                    )}>
                      <Plus className={cn(
                        "w-8 h-8 opacity-35",
                        isDark ? "text-gray-700" : "text-gray-350"
                      )} />
                    </div>
                    <div className={cn(
                      "text-[10px] font-mono opacity-35 mt-2",
                      isDark ? "text-gray-600" : "text-gray-400"
                    )}>
                      future source
                    </div>
                  </div>
                </div>

                {/* Bottom right - Placeholder for future source */}
                <div className={cn(
                  "aspect-square p-4",
                  isDark ? "bg-gray-900/50" : "bg-white/70"
                )}>
                  <div className="w-full h-full flex flex-col items-center justify-center">
                    <div className={cn(
                      "w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center",
                      isDark ? "border-gray-700" : "border-gray-350"
                    )}>
                      <Plus className={cn(
                        "w-8 h-8 opacity-35",
                        isDark ? "text-gray-700" : "text-gray-350"
                      )} />
                    </div>
                    <div className={cn(
                      "text-[10px] font-mono opacity-35 mt-2",
                      isDark ? "text-gray-600" : "text-gray-400"
                    )}>
                      future source
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom message - more prominent to explain the sketch */}
          <div className="text-center mt-8">
            <p className={cn(
              "text-sm opacity-65 italic",
              isDark ? "text-gray-500" : "text-gray-500"
            )}>
              This is a preview of your collection structure.
            </p>
            <p className={cn(
              "text-xs opacity-55 mt-1",
              isDark ? "text-gray-600" : "text-gray-400"
            )}>
              You can add more source connections anytime after creation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
