import React, { useEffect } from 'react';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { CheckCircle, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

interface SuccessViewProps {
  onComplete: () => void;
  isAddingToExisting?: boolean;
}

export const SuccessView: React.FC<SuccessViewProps> = ({ onComplete, isAddingToExisting = false }) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const navigate = useNavigate();

  const {
    collectionId,
    collectionName,
    sourceName
  } = useCollectionCreationStore();

  useEffect(() => {
    // Emit event for collection created
    window.dispatchEvent(new CustomEvent('collection-created'));
  }, []);

  const handleGoToCollection = () => {
    if (collectionId) {
      navigate(`/collections/${collectionId}`);
    }
    onComplete();
  };

  const handleDone = () => {
    onComplete();
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="text-center space-y-6 max-w-sm">
          {/* Success icon */}
          <div className={cn(
            "w-20 h-20 rounded-full mx-auto flex items-center justify-center",
            "bg-green-100 dark:bg-green-900/30"
          )}>
            <CheckCircle className="w-10 h-10 text-green-600 dark:text-green-400" />
          </div>

          {/* Success message */}
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              {isAddingToExisting ? 'Source added' : 'Collection created'}
            </h2>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Your data is now syncing
            </p>
          </div>

          {/* Collection info */}
          <div className={cn(
            "p-4 rounded-lg border",
            isDark
              ? "bg-gray-800/50 border-gray-700"
              : "bg-gray-50 border-gray-200"
          )}>
            <div className="space-y-2 text-left">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Collection</span>
                <span className="font-medium">{collectionName}</span>
              </div>
              {sourceName && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Source</span>
                  <span className="font-medium">{sourceName}</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Status</span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <span className="font-medium text-green-600 dark:text-green-400">
                    Syncing
                  </span>
                </span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-3">
            <button
              onClick={handleGoToCollection}
              className={cn(
                "w-full py-2 px-4 rounded-lg text-sm font-medium",
                "flex items-center justify-center gap-2",
                "transition-all",
                "bg-blue-600 hover:bg-blue-700 text-white"
              )}
            >
              <span>View Collection</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            <button
              onClick={handleDone}
              className={cn(
                "w-full py-2 px-4 rounded-lg text-sm font-medium",
                "transition-colors",
                isDark
                  ? "text-gray-400 hover:text-gray-200"
                  : "text-gray-600 hover:text-gray-900"
              )}
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
