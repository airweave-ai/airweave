import React, { useEffect, useState } from 'react';
import { useAuthProvidersStore } from '@/lib/stores/authProviders';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Check, ExternalLink } from 'lucide-react';
import { getAuthProviderIconUrl } from '@/lib/utils/icons';
import { ValidatedInput } from '@/components/ui/validated-input';
import { authConfigIdValidation, accountIdValidation, projectIdValidation, environmentValidation, externalUserIdValidation } from '@/lib/validation/rules';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface AuthProviderSelectorProps {
  selectedProvider?: string;
  onProviderSelect: (providerId: string) => void;
  onConfigChange: (config: Record<string, any>) => void;
  supportedAuthProviders?: string[]; // List of provider short names that support this source
}

export const AuthProviderSelector: React.FC<AuthProviderSelectorProps> = ({
  selectedProvider,
  onProviderSelect,
  onConfigChange,
  supportedAuthProviders,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const {
    authProviderConnections,
    isLoadingConnections,
    fetchAuthProviderConnections,
  } = useAuthProvidersStore();

  // Filter connections to only show providers that are supported by this source
  const filteredAuthProviderConnections = authProviderConnections.filter(
    (conn) => !supportedAuthProviders || supportedAuthProviders.includes(conn.short_name)
  );

  const [providerConfig, setProviderConfig] = useState<Record<string, any>>({});

  useEffect(() => {
    fetchAuthProviderConnections();
  }, [fetchAuthProviderConnections]);

  // Reset config when provider changes
  useEffect(() => {
    setProviderConfig({});
    onConfigChange({});
  }, [selectedProvider]);

  const handleConfigFieldChange = (fieldName: string, value: string) => {
    const newConfig = { ...providerConfig, [fieldName]: value };
    setProviderConfig(newConfig);
    onConfigChange(newConfig);
  };

  // Provider-specific config fields
  const getProviderConfigFields = (providerShortName: string) => {
    switch (providerShortName) {
      case 'composio':
        return [
          { name: 'auth_config_id', label: 'Auth Config ID', placeholder: 'config_xyz789', required: true, validation: authConfigIdValidation },
          { name: 'account_id', label: 'Account ID', placeholder: 'account_abc123', required: true, validation: accountIdValidation },
        ];
      case 'pipedream':
        return [
          { name: 'project_id', label: 'Project ID', placeholder: 'proj_JPsD74a', required: true, validation: projectIdValidation },
          { name: 'account_id', label: 'Account ID', placeholder: 'apn_gyha5Ky', required: true, validation: accountIdValidation },
          { name: 'external_user_id', label: 'External User ID', placeholder: 'user_123', required: true, validation: externalUserIdValidation },
          { name: 'environment', label: 'Environment', placeholder: 'production', required: false, validation: environmentValidation },
        ];
      default:
        return [];
    }
  };

  if (isLoadingConnections) {
    return (
      <div className="flex justify-center py-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900 dark:border-gray-100" />
      </div>
    );
  }

  if (filteredAuthProviderConnections.length === 0) {
    const hasConnections = authProviderConnections.length > 0;
    const message = hasConnections 
      ? "This source is not supported by your connected auth providers."
      : "No auth providers connected.";
    
    return (
      <div className={cn(
        "p-3 rounded-lg border text-center",
        isDark ? "border-gray-800 bg-gray-900/30" : "border-gray-200 bg-gray-50"
      )}>
        <p className={cn(
          "text-xs",
          isDark ? "text-gray-500" : "text-gray-500"
        )}>
          {message}
          {!hasConnections && (
            <a
              href="/organization/settings"
              target="_blank"
              className={cn(
                "ml-1 hover:underline",
                isDark ? "text-blue-400" : "text-blue-600"
              )}
            >
              Connect one →
            </a>
          )}
        </p>
      </div>
    );
  }

  const selectedProviderConnection = filteredAuthProviderConnections.find(
    p => p.readable_id === selectedProvider
  );

  return (
    <div className="space-y-3">
      {/* Provider Selection */}
      <div className="space-y-2">
        <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          Select Provider
        </label>
        <div className="space-y-2">
          {filteredAuthProviderConnections.map((provider) => (
            <button
              key={provider.readable_id}
              onClick={() => onProviderSelect(provider.readable_id)}
              className={cn(
                "w-full flex items-center gap-3 p-2.5 rounded-lg border transition-all text-left",
                selectedProvider === provider.readable_id
                  ? isDark
                    ? "border-blue-500/50 bg-blue-500/10"
                    : "border-blue-500/50 bg-blue-50/50"
                  : isDark
                    ? "border-gray-800 hover:border-gray-700 bg-gray-900/30"
                    : "border-gray-200 hover:border-gray-300 bg-white"
              )}
            >
              <div className={cn(
                "w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0",
                selectedProvider === provider.readable_id
                  ? "border-blue-500 bg-blue-500"
                  : isDark
                    ? "border-gray-600"
                    : "border-gray-400"
              )}>
                {selectedProvider === provider.readable_id && (
                  <Check className="h-3 w-3 text-white" />
                )}
              </div>
              <img
                src={getAuthProviderIconUrl(provider.short_name, resolvedTheme)}
                alt={provider.short_name}
                className="w-5 h-5 object-contain flex-shrink-0"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
              <div className={cn(
                "text-sm flex-1 min-w-0",
                isDark ? "text-gray-200" : "text-gray-700"
              )}>
                {provider.readable_id}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Provider Configuration */}
      {selectedProviderConnection && (
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Provider Configuration
            </label>

            {/* Platform Buttons for Auth Providers */}
            {(selectedProviderConnection.short_name === 'composio' || selectedProviderConnection.short_name === 'pipedream') && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => {
                        const url = selectedProviderConnection.short_name === 'composio'
                          ? 'https://platform.composio.dev/'
                          : 'https://pipedream.com/';
                        window.open(url, '_blank');
                      }}
                      className={cn(
                        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                        "border",
                        isDark
                          ? "bg-gray-800/50 border-gray-700 text-gray-300 hover:bg-gray-700 hover:text-white"
                          : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                      )}
                    >
                      <img
                        src={getAuthProviderIconUrl(selectedProviderConnection.short_name, resolvedTheme)}
                        alt={selectedProviderConnection.short_name}
                        className="w-3 h-3 object-contain"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none';
                        }}
                      />
                      Get from {selectedProviderConnection.short_name === 'composio' ? 'Composio' : 'Pipedream'}
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>
                      {selectedProviderConnection.short_name === 'composio'
                        ? 'Opens Composio platform to retrieve your auth config ID and account ID'
                        : 'Opens Pipedream platform to retrieve your project ID, account ID, and other credentials'
                      }
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>

          {getProviderConfigFields(selectedProviderConnection.short_name).map((field) => (
            <div key={field.name}>
              <label className={cn(
                "block text-sm mb-1",
                isDark ? "text-gray-300" : "text-gray-600"
              )}>
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>
              <ValidatedInput
                type="text"
                placeholder={field.placeholder}
                value={providerConfig[field.name] || ''}
                onChange={(value) => handleConfigFieldChange(field.name, value)}
                validation={field.validation}
                className={cn(
                  "focus:border-gray-400 dark:focus:border-gray-600",
                  isDark
                    ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                    : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                )}
              />
            </div>
          ))}

          <p className={cn(
            "text-xs mt-1",
            isDark ? "text-gray-500" : "text-gray-500"
          )}>
            Find these values in your {selectedProviderConnection.short_name.charAt(0).toUpperCase() + selectedProviderConnection.short_name.slice(1)} dashboard
          </p>
        </div>
      )}
    </div>
  );
};
