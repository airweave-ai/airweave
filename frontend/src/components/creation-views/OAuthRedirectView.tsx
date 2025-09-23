import React, { useState } from 'react';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { ExternalLink, Copy, Check, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

export const OAuthRedirectView: React.FC = () => {
  const {
    sourceName,
    authenticationUrl,
    setStep
  } = useCollectionCreationStore();

  const [copied, setCopied] = useState(false);

  const handleConnect = () => {
    if (authenticationUrl) {
      window.location.href = authenticationUrl;
    }
  };

  const handleCopyUrl = async () => {
    if (authenticationUrl) {
      try {
        await navigator.clipboard.writeText(authenticationUrl);
        setCopied(true);
        toast.success('Authentication URL copied to clipboard');
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        toast.error('Failed to copy URL');
      }
    }
  };

  return (
    <div className="px-8 py-10">
      <div className="max-w-md mx-auto">
        <div className="space-y-8">
          {/* Header */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => setStep('source-config')}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900 transition-colors"
            >
              <ArrowLeft className="w-4 h-4 text-gray-400" />
            </button>
            <div className="flex-1">
              <h2 className="text-3xl font-light tracking-tight text-gray-900 dark:text-white">
                Authorize {sourceName}
              </h2>
              <p className="mt-1 text-base text-gray-500 dark:text-gray-400">
                Complete the connection
              </p>
            </div>
          </div>

          {/* Main content */}
          <div className="text-center space-y-6">
            <div className="w-20 h-20 mx-auto rounded-full bg-gray-100 dark:bg-gray-900 flex items-center justify-center">
              <ExternalLink className="w-10 h-10 text-gray-600 dark:text-gray-400" />
            </div>

            <div>
              <p className="text-gray-600 dark:text-gray-400">
                Click below to authorize Airweave to access your {sourceName} data
              </p>
            </div>

            <button
              onClick={handleConnect}
              className="w-full py-2 px-4 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white transition-all flex items-center justify-center gap-2"
            >
              <span>Connect with {sourceName}</span>
              <ExternalLink className="w-4 h-4" />
            </button>
          </div>

          {/* Alternative: Copy URL */}
          <div className="pt-6 border-t border-gray-200 dark:border-gray-800">
            <div className="space-y-3">
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
                Or share this link with someone who can authorize
              </p>

              <div className="flex items-center gap-2">
                <div className="flex-1 p-3 rounded-xl bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800">
                  <p className="text-xs font-mono text-gray-600 dark:text-gray-400 truncate">
                    {authenticationUrl || 'Loading...'}
                  </p>
                </div>
                <button
                  onClick={handleCopyUrl}
                  disabled={!authenticationUrl}
                  className="p-3 rounded-xl border border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {copied ? (
                    <Check className="w-4 h-4 text-green-600 dark:text-green-400" />
                  ) : (
                    <Copy className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
