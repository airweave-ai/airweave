import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollectionCreationStore, AuthMode } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { ArrowLeft, Copy, ExternalLink, Check, User, Users, Mail, Link2, ChevronRight, Send, Info, HelpCircle, Share2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { SourceAuthenticationView } from '@/components/shared/SourceAuthenticationView';
import { AuthMethodSelector } from './AuthMethodSelector';
import { AuthProviderSelector } from './AuthProviderSelector';
import { useAuthProvidersStore } from '@/lib/stores/authProviders';
import { ValidatedInput } from '@/components/ui/validated-input';
import { TagInput } from '@/components/ui/tag-input';
import { sourceConnectionNameValidation, getAuthFieldValidation, clientIdValidation, clientSecretValidation, redirectUrlValidation } from '@/lib/validation/rules';
import ReactMarkdown from 'react-markdown';

interface SourceConfigViewProps {
  humanReadableId: string;
  isAddingToExisting?: boolean;
}

interface SourceDetails {
  short_name: string;
  name: string;
  auth_methods?: string[];  // Array of supported auth methods
  oauth_type?: string;  // OAuth token type (oauth1, access_only, with_refresh, etc.)
  requires_byoc?: boolean;  // Whether source requires user to bring their own OAuth credentials
  auth_config_class?: string;  // Optional, only for DIRECT auth sources
  supported_auth_providers?: string[];  // Array of auth provider short names that support this source
  auth_fields?: {  // Optional, only present for DIRECT auth sources
    fields: Array<{
      name: string;
      title?: string;
      description?: string;
      type?: string;
      required?: boolean;
    }>;
  };
  config_fields?: {
    fields: Array<{
      name: string;
      title?: string;
      description?: string;
      type?: string;
      required?: boolean;
    }>;
  };
}

export const SourceConfigView: React.FC<SourceConfigViewProps> = ({ humanReadableId, isAddingToExisting = false }) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const navigate = useNavigate();

  const {
    collectionId,
    collectionName,
    selectedSource,
    sourceName,
    sourceConnectionName,
    authMode,
    setAuthMode,
    selectedAuthProvider,
    setSelectedAuthProvider,
    authProviderConfig,
    setAuthProviderConfig,
    setOAuthData,
    setConnectionId,
    setStep,
    handleBackFromSourceConfig,
    setSourceConnectionName,
    existingCollectionId,
    closeModal,
    reset,
    isAddingToExistingCollection
  } = useCollectionCreationStore();

  const { authProviderConnections, fetchAuthProviderConnections } = useAuthProvidersStore();


  const [isCreating, setIsCreating] = useState(false);
  const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
  const [authFields, setAuthFields] = useState<Record<string, string>>({});
  const [configData, setConfigData] = useState<Record<string, string | string[]>>({});
  const [useOwnCredentials, setUseOwnCredentials] = useState(false);
  // Initialize connection name from store or with source default
  const [connectionName, setConnectionName] = useState(
    sourceConnectionName || (sourceName ? `${sourceName} Connection` : '')
  );
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [customRedirectUrl, setCustomRedirectUrl] = useState('');
  const [showCustomRedirect, setShowCustomRedirect] = useState(false);

  // Handle URL input with automatic https:// prefix
  const handleRedirectUrlChange = (value: string) => {
    const trimmed = value.trim();

    // If user starts typing without protocol, automatically add https://
    if (trimmed && !trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      // Check if it looks like a domain (contains dots or is localhost)
      if (trimmed.includes('.') || trimmed.includes('localhost') || trimmed.includes(':')) {
        setCustomRedirectUrl(`https://${trimmed}`);
        return;
      }
    }

    setCustomRedirectUrl(value);
  };

  // Generate default redirect URL
  const getDefaultRedirectUrl = () => {
    const origin = window.location.origin;
    // Use the current protocol (don't force HTTPS for local dev)
    return `${origin}?oauth_return=true`;
  };

  // Update store when connection name changes
  useEffect(() => {
    // Only update if the value actually changed
    if (connectionName !== sourceConnectionName) {
      setSourceConnectionName(connectionName);
    }
  }, [connectionName]); // Only depend on connectionName changes

  // Update connection name when source changes (when user goes back and selects different source)
  useEffect(() => {
    if (sourceName && !sourceConnectionName) {
      // Only set default name if no custom name is set
      const defaultName = `${sourceName} Connection`;
      setConnectionName(defaultName);
    }
  }, [sourceName, sourceConnectionName]);

  const [connectionUrl, setConnectionUrl] = useState('');

  // Check if source uses OAuth1 (vs OAuth2)
  const isOAuth1 = () => {
    return sourceDetails?.oauth_type === 'oauth1';
  };

  // Check if source requires custom OAuth credentials (BYOC - Bring Your Own Credentials)
  const requiresCustomOAuth = () => {
    // Check the requires_byoc flag on the source
    return sourceDetails?.requires_byoc === true;
  };

  // Check if this is a direct auth source (API keys, passwords, etc.)
  const isDirectAuth = () => {
    return sourceDetails?.auth_methods?.includes('direct');
  };

  // Determine available auth methods based on source
  const getAvailableAuthMethods = (): AuthMode[] => {
    if (!sourceDetails || !sourceDetails.auth_methods) return [];

    const methods: AuthMode[] = [];

    // Check for direct auth (API keys, passwords, config)
    if (sourceDetails.auth_methods.includes('direct')) {
      methods.push('direct_auth');
    }

    // Check for OAuth browser flow
    if (sourceDetails.auth_methods.includes('oauth_browser') ||
      sourceDetails.auth_methods.includes('oauth_token')) {
      methods.push('oauth2');
    }

    // Add external provider if any are connected and source supports it
    if (authProviderConnections.length > 0 &&
      sourceDetails.auth_methods.includes('auth_provider') &&
      sourceDetails.supported_auth_providers &&
      sourceDetails.supported_auth_providers.length > 0) {
      methods.push('external_provider');
    }

    return methods;
  };

  // Fetch auth provider connections on mount
  useEffect(() => {
    fetchAuthProviderConnections();
  }, [fetchAuthProviderConnections]);

  // Fetch source details to understand config requirements
  useEffect(() => {
    const fetchSourceDetails = async () => {
      if (!selectedSource) return;

      try {
        const response = await apiClient.get(`/sources/${selectedSource}`);
        if (response.ok) {
          const source = await response.json();
          setSourceDetails(source);

          // Initialize auth fields for config-based auth
          if (source.auth_fields?.fields) {
            const initialValues: Record<string, string> = {};
            source.auth_fields.fields.forEach((field: any) => {
              // Skip token fields that come from OAuth
              if (!field.name.includes('token') && !field.name.includes('client_')) {
                initialValues[field.name] = '';
              }
            });
            setAuthFields(initialValues);
          }

          // Initialize config fields
          if (source.config_fields?.fields) {
            const initialValues: Record<string, string> = {};
            source.config_fields.fields.forEach((field: any) => {
              initialValues[field.name] = '';
            });
            setConfigData(initialValues);
          }
        }
      } catch (error) {
        console.error('Error fetching source details:', error);
      }
    };

    fetchSourceDetails();
  }, [selectedSource]);

  // Set default auth mode based on available methods
  // This runs after source details and auth providers are loaded
  useEffect(() => {
    if (!sourceDetails || !sourceDetails.auth_methods || authMode) return;

    // Determine default auth mode based on available methods
    if (sourceDetails.auth_methods.includes('direct')) {
      // Prefer direct auth if available
      setAuthMode('direct_auth');
    } else if (sourceDetails.auth_methods.includes('oauth_browser')) {
      // Then OAuth
      setAuthMode('oauth2');
      // Auto-enable custom credentials for sources that require BYOC
      if (sourceDetails.requires_byoc) {
        setUseOwnCredentials(true);
      }
    } else if (authProviderConnections.length > 0 && sourceDetails.auth_methods.includes('auth_provider')) {
      // Auth provider only if providers are connected
      setAuthMode('external_provider');
    }
  }, [sourceDetails, authProviderConnections, authMode, setAuthMode]);

  // Helper function to get required config fields for a provider
  const getRequiredProviderConfigFields = (providerShortName: string) => {
    switch (providerShortName) {
      case 'composio':
        return ['auth_config_id', 'account_id'];
      case 'pipedream':
        return ['project_id', 'account_id', 'external_user_id'];  // environment is optional
      default:
        return [];
    }
  };

  // Check if form is valid for submission
  const isFormValid = () => {
    // Must have a valid connection name (4-42 characters)
    const trimmedName = connectionName.trim();
    if (!trimmedName || trimmedName.length < 4 || trimmedName.length > 42) return false;

    // Check if custom redirect URL is valid (if provided)
    if (authMode === 'oauth2' && customRedirectUrl) {
      const validation = redirectUrlValidation.validate(customRedirectUrl);
      if (!validation.isValid) return false;
    }

    // Check auth mode specific requirements
    if (authMode === 'external_provider') {
      // Must have a provider selected
      if (!selectedAuthProvider) return false;

      // Find the selected provider to check its requirements
      const selectedProviderConnection = authProviderConnections.find(
        p => p.readable_id === selectedAuthProvider
      );

      if (selectedProviderConnection) {
        // Check if all required provider config fields are filled
        const requiredFields = getRequiredProviderConfigFields(selectedProviderConnection.short_name);
        if (requiredFields.length > 0) {
          const allFilled = requiredFields.every(fieldName => authProviderConfig[fieldName]?.trim());
          if (!allFilled) return false;
        }
      }
    } else if (authMode === 'direct_auth') {
      // Check if all required auth fields are filled
      if (sourceDetails?.auth_fields?.fields) {
        const requiredFields = sourceDetails.auth_fields.fields.filter(f => f.required);
        const allFilled = requiredFields.every(field => authFields[field.name]?.trim());
        if (!allFilled) return false;
      }
    } else if (authMode === 'oauth2') {
      // Check if custom OAuth credentials are required
      if (requiresCustomOAuth() || useOwnCredentials) {
        if (!clientId.trim() || !clientSecret.trim()) return false;
      }
    }

    // Check required config fields (applies to ALL auth modes)
    if (sourceDetails?.config_fields?.fields) {
      const requiredConfigFields = sourceDetails.config_fields.fields.filter(f => f.required);
      if (requiredConfigFields.length > 0) {
        const allFilled = requiredConfigFields.every(field => {
          const value = configData[field.name];
          if (Array.isArray(value)) {
            return value.length > 0;
          }
          return typeof value === 'string' && value.trim() !== '';
        });
        if (!allFilled) return false;
      }
    }

    return true;
  };

  const handleCreate = async () => {
    setIsCreating(true);

    try {
      // Validate connection name
      if (!connectionName.trim()) {
        toast.error('Please enter a connection name');
        setIsCreating(false);
        return;
      }

      // Build nested authentication structure
      let authentication: any = {};

      // Handle different auth modes
      if (authMode === 'direct_auth') {
        // Direct auth (API key, passwords, config)
        if (Object.keys(authFields).length === 0) {
          toast.error('Please provide authentication credentials');
          setIsCreating(false);
          return;
        }
        authentication = {
          credentials: authFields
        };
      } else if (authMode === 'oauth2') {
        // OAuth flow (OAuth1 or OAuth2)
        authentication = {
          redirect_uri: customRedirectUrl.trim() || getDefaultRedirectUrl()
        };

        // Add credentials if BYOC or user chose to use own credentials
        if (requiresCustomOAuth() || useOwnCredentials) {
          if (!clientId || !clientSecret) {
            const credType = isOAuth1() ? 'consumer' : 'client';
            toast.error(`Please provide OAuth ${credType} credentials`);
            setIsCreating(false);
            return;
          }

          // OAuth1 uses consumer_key/consumer_secret, OAuth2 uses client_id/client_secret
          if (isOAuth1()) {
            authentication.consumer_key = clientId;
            authentication.consumer_secret = clientSecret;
          } else {
            authentication.client_id = clientId;
            authentication.client_secret = clientSecret;
          }
        }
      } else if (authMode === 'external_provider') {
        // External provider auth
        if (!selectedAuthProvider) {
          toast.error('Please select an auth provider');
          setIsCreating(false);
          return;
        }
        authentication = {
          provider_readable_id: selectedAuthProvider,
          provider_config: authProviderConfig && Object.keys(authProviderConfig).length > 0 ? authProviderConfig : undefined
        };
      }

      const payload: any = {
        name: connectionName.trim(),
        description: `${sourceName} connection for ${collectionName}`,
        short_name: selectedSource,
        readable_collection_id: isAddingToExisting ? existingCollectionId : collectionId,
        authentication: authentication,
        // For direct auth, sync immediately since we have credentials
        // For OAuth, don't sync until after authorization is complete
        // For external provider, sync immediately since we're using existing auth
        sync_immediately: authMode === 'direct_auth' || authMode === 'external_provider',
        // Set redirect URL for OAuth flows
        redirect_url: getDefaultRedirectUrl(),
      };

      // Add config fields if any - filter out empty values
      if (Object.keys(configData).length > 0) {
        const filteredConfig = Object.entries(configData).reduce((acc, [key, value]) => {
          // Only include non-empty values
          if (value !== '' && value !== null && value !== undefined) {
            // Also check arrays aren't empty
            if (Array.isArray(value) && value.length === 0) {
              return acc;
            }
            acc[key] = value;
          }
          return acc;
        }, {} as Record<string, any>);

        // Only add config if there are actual values
        if (Object.keys(filteredConfig).length > 0) {
          payload.config = filteredConfig;
        }
      }

      const response = await apiClient.post('/source-connections', payload);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(errorText);
        throw new Error(errorText || 'Failed to create connection');
      }

      const result = await response.json();

      // Check if OAuth flow is needed
      // The authentication_url is now inside the auth object
      const authUrl = result.auth?.authentication_url || result.auth?.auth_url;
      if (authUrl) {
        setOAuthData(
          result.id,
          payload.redirect_url || getDefaultRedirectUrl(),
          authUrl
        );

        setConnectionUrl(authUrl);
      } else {
        // Direct auth, config auth, or external provider successful
        setConnectionId(result.id);

        // For direct token sources, navigate directly to collection detail
        // instead of showing the success screen
        const targetCollectionId = isAddingToExisting ? existingCollectionId : collectionId;
        if (targetCollectionId) {
          // Close the modal
          closeModal();

          // Navigate to collection detail with success params
          navigate(`/collections/${targetCollectionId}?status=success&source_connection_id=${result.id}`);

          // Reset store state after navigation
          setTimeout(() => {
            reset();
          }, 100);
        } else {
          // Fallback to success view if no collection ID
          setStep('success');
        }
      }

    } catch (error) {
      console.error('Error creating source connection:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create connection');
    } finally {
      setIsCreating(false);
    }
  };


  return (
    <div className="h-full flex flex-col">
      <div className="px-8 py-8 flex-1 overflow-auto">
        <div className="min-h-full flex flex-col">
          <div className="space-y-6 flex-1">
            {/* Header */}
            <div>
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
                Create Source Connection
              </h2>
              <p className="my-2.5 text-sm text-gray-500 dark:text-gray-400">
                Connect your {sourceName || 'data source'} to sync and search its content
              </p>
            </div>

            {/* WARNING: Slack + Pipedream compatibility - Show at top */}
            {authMode === 'external_provider' && selectedSource === 'slack' && selectedAuthProvider && (() => {
              const selectedProviderConnection = authProviderConnections.find(
                p => p.readable_id === selectedAuthProvider
              );
              return selectedProviderConnection?.short_name === 'pipedream' && (
                <div className={cn(
                  "flex items-start gap-2 p-3 rounded-lg border",
                  isDark
                    ? "bg-amber-900/20 border-amber-800/30 text-amber-400"
                    : "bg-amber-50 border-amber-200 text-amber-700"
                )}>
                  <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <div className="text-sm space-y-1">
                    <p className="font-medium">Pipedream OAuth Limitation</p>
                    <p className={cn(
                      "text-xs leading-relaxed",
                      isDark ? "text-amber-400/80" : "text-amber-600"
                    )}>
                      Slack federated search does not work with Pipedream's official OAuth client
                      due to missing scopes. Please use:
                    </p>
                    <ul className={cn(
                      "text-xs list-disc pl-4 space-y-0.5",
                      isDark ? "text-amber-400/80" : "text-amber-600"
                    )}>
                      <li>Custom Pipedream OAuth client (with search:read scope)</li>
                      <li>Composio auth provider</li>
                      <li>Direct OAuth flow (without auth provider)</li>
                    </ul>
                  </div>
                </div>
              );
            })()}

            {/* Connection created state - Use shared component */}
            {connectionUrl ? (
              <SourceAuthenticationView
                sourceName={sourceName}
                sourceShortName={selectedSource}
                authenticationUrl={connectionUrl}
                showBorder={false}
              />
            ) : (
              <>
                {/* Form fields - Clean minimal design */}
                <div className="space-y-5">
                  <div>
                    <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">
                      Name
                    </label>
                    <ValidatedInput
                      type="text"
                      value={connectionName}
                      onChange={(value) => {
                        setConnectionName(value);
                        setSourceConnectionName(value);
                      }}
                      placeholder="Enter connection name"
                      validation={sourceConnectionNameValidation}
                      className={cn(
                        "focus:border-gray-400 dark:focus:border-gray-600",
                        isDark
                          ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                          : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                      )}
                    />
                  </div>

                  {/* Auth Method Selection */}
                  {sourceDetails && (
                    <AuthMethodSelector
                      selectedMethod={authMode}
                      onMethodChange={setAuthMode}
                      availableAuthMethods={getAvailableAuthMethods()}
                    />
                  )}

                  {/* Auth Provider Selection */}
                  {authMode === 'external_provider' && (
                    <AuthProviderSelector
                      selectedProvider={selectedAuthProvider}
                      onProviderSelect={setSelectedAuthProvider}
                      onConfigChange={setAuthProviderConfig}
                      supportedAuthProviders={sourceDetails?.supported_auth_providers}
                    />
                  )}

                  {/* Direct auth fields (API keys, passwords, config) */}
                  {authMode === 'direct_auth' && sourceDetails?.auth_fields?.fields && (
                    <div className="space-y-3">
                      <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Direct Credentials Configuration
                      </label>
                      {sourceDetails.auth_fields.fields.map((field) => (
                        <div key={field.name}>
                          <label className="block text-sm font-medium mb-1">
                            {field.title || field.name}
                            {field.required && <span className="text-red-500 ml-1">*</span>}
                          </label>
                          {field.description && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1.5">
                              <ReactMarkdown
                                components={{
                                  p: ({ children }) => <span>{children}</span>,
                                  a: ({ href, children }) => (
                                    <a
                                      href={href}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-blue-600 dark:text-blue-400 hover:underline"
                                    >
                                      {children}
                                    </a>
                                  ),
                                  ul: ({ children }) => (
                                    <ul className="list-disc pl-4 my-2 space-y-0.5">
                                      {children}
                                    </ul>
                                  ),
                                  li: ({ children }) => (
                                    <li className="text-xs text-gray-500 dark:text-gray-400">
                                      {children}
                                    </li>
                                  ),
                                }}
                              >
                                {field.description}
                              </ReactMarkdown>
                            </div>
                          )}
                          <ValidatedInput
                            type={field.name.includes('password') || field.name.includes('token') ? 'password' : 'text'}
                            placeholder=""
                            value={authFields[field.name] || ''}
                            onChange={(value) => setAuthFields({ ...authFields, [field.name]: value })}
                            validation={getAuthFieldValidation(field.name, sourceDetails?.short_name)}
                            className={cn(
                              "focus:border-gray-400 dark:focus:border-gray-600",
                              isDark
                                ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                            )}
                          />
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Config fields (additional configuration) */}
                  {sourceDetails?.config_fields?.fields && sourceDetails.config_fields.fields.length > 0 && (
                    <div className="space-y-3">
                      <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        {(() => {
                          const hasRequiredFields = sourceDetails.config_fields.fields.some((field: any) => field.required);
                          return hasRequiredFields ? "Additional Configuration" : "Additional Configuration (optional)";
                        })()}
                      </label>
                      {sourceDetails.config_fields.fields.map((field) => (
                        <div key={field.name}>
                          <label className="block text-sm font-medium mb-1">
                            {field.title || field.name}
                            {field.required && <span className="text-red-500 ml-1">*</span>}
                          </label>
                          {field.description && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1.5">
                              <ReactMarkdown
                                components={{
                                  p: ({ children }) => <span>{children}</span>,
                                  a: ({ href, children }) => (
                                    <a
                                      href={href}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-blue-600 dark:text-blue-400 hover:underline"
                                    >
                                      {children}
                                    </a>
                                  ),
                                  ul: ({ children }) => (
                                    <ul className="list-disc pl-4 my-2 space-y-0.5">
                                      {children}
                                    </ul>
                                  ),
                                  li: ({ children }) => (
                                    <li className="text-xs text-gray-500 dark:text-gray-400">
                                      {children}
                                    </li>
                                  ),
                                }}
                              >
                                {field.description}
                              </ReactMarkdown>
                            </div>
                          )}
                          {field.type === 'array' ? (
                            <TagInput
                              value={(Array.isArray(configData[field.name]) ? configData[field.name] : []) as string[]}
                              onChange={(tags) => setConfigData({ ...configData, [field.name]: tags })}
                              placeholder={`Enter ${field.title?.toLowerCase() || field.name} and press Enter...`}
                              transformInput={sourceDetails?.short_name === 'jira' && field.name === 'project_keys' ? (v) => v.toUpperCase() : undefined}
                            />
                          ) : (
                            <input
                              type="text"
                              placeholder=""
                              value={configData[field.name] || ''}
                              onChange={(e) => setConfigData({ ...configData, [field.name]: e.target.value })}
                              className={cn(
                                "w-full px-4 py-2 rounded-lg text-sm",
                                "border bg-transparent",
                                "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                                isDark
                                  ? "border-gray-800 text-white placeholder:text-gray-600"
                                  : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                              )}
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* OAuth option - Sleek toggle or always on for BYOC sources */}
                  {authMode === 'oauth2' && (
                    <div>
                      {requiresCustomOAuth() ? (
                        // For BYOC sources, show info and fields directly
                        <div className="space-y-4">
                          <div className={cn(
                            "flex items-start gap-2 p-3 rounded-lg",
                            isDark ? "bg-blue-900/20 text-blue-400" : "bg-blue-50 text-blue-600"
                          )}>
                            <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                            <p className="text-sm">
                              {sourceName} requires you to provide your own OAuth application credentials.
                              You'll need to create an OAuth app in {sourceName}'s developer console.
                            </p>
                          </div>

                          {/* Help section with hover info */}
                          <div className="flex items-start gap-2 group">
                            <div className="relative">
                              <HelpCircle className={cn(
                                "h-4 w-4 mt-0.5 flex-shrink-0 transition-all cursor-help",
                                isDark
                                  ? "text-gray-500 group-hover:text-blue-400"
                                  : "text-gray-400 group-hover:text-blue-600"
                              )} />

                              {/* Hover tooltip */}
                              <div className={cn(
                                "absolute left-0 top-6 z-50 w-80 p-4 rounded-lg shadow-xl",
                                "opacity-0 invisible group-hover:opacity-100 group-hover:visible",
                                "transition-all duration-200 transform group-hover:translate-y-0 translate-y-1",
                                isDark
                                  ? "bg-gray-800 border border-gray-700"
                                  : "bg-white border border-gray-200"
                              )}>
                                <div className="space-y-3">
                                  <p className={cn(
                                    "text-sm font-medium",
                                    isDark ? "text-white" : "text-gray-900"
                                  )}>
                                    What are OAuth credentials?
                                  </p>
                                  <p className={cn(
                                    "text-xs leading-relaxed",
                                    isDark ? "text-gray-400" : "text-gray-600"
                                  )}>
                                    {isOAuth1() ? (
                                      <>OAuth1 credentials (Consumer Key and Consumer Secret) are like a special key that allows Airweave to securely access your {sourceName} data on your behalf. You create these in {sourceName}'s developer settings, and they ensure only authorized applications can connect to your account.</>
                                    ) : (
                                      <>OAuth credentials (Client ID and Client Secret) are like a special key that allows Airweave to securely access your {sourceName} data on your behalf. You create these in {sourceName}'s developer settings, and they ensure only authorized applications can connect to your account.</>
                                    )}
                                  </p>
                                  <div className={cn(
                                    "text-xs space-y-1 pt-2 border-t",
                                    isDark ? "border-gray-700" : "border-gray-200"
                                  )}>
                                    {isOAuth1() ? (
                                      <>
                                        <p className={cn(isDark ? "text-gray-500" : "text-gray-500")}>
                                          <span className="font-medium">Consumer Key:</span> Public identifier for your app
                                        </p>
                                        <p className={cn(isDark ? "text-gray-500" : "text-gray-500")}>
                                          <span className="font-medium">Consumer Secret:</span> Private key (keep this secure!)
                                        </p>
                                      </>
                                    ) : (
                                      <>
                                        <p className={cn(isDark ? "text-gray-500" : "text-gray-500")}>
                                          <span className="font-medium">Client ID:</span> Public identifier for your app
                                        </p>
                                        <p className={cn(isDark ? "text-gray-500" : "text-gray-500")}>
                                          <span className="font-medium">Client Secret:</span> Private key (keep this secure!)
                                        </p>
                                      </>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>

                            <div className="text-sm">
                              <span className={cn(
                                "font-medium",
                                isDark ? "text-gray-400" : "text-gray-600"
                              )}>
                                Need help setting up OAuth?
                              </span>
                              <a
                                href={`https://docs.airweave.ai/docs/connectors/${selectedSource.replace(/_/g, '-')}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={cn(
                                  "ml-2 inline-flex items-center gap-1 font-medium hover:underline",
                                  isDark ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"
                                )}
                              >
                                View documentation
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            </div>
                          </div>

                          <div className="space-y-2.5">
                            <ValidatedInput
                              type="text"
                              placeholder={isOAuth1() ? "Consumer Key" : "Client ID"}
                              value={clientId}
                              onChange={setClientId}
                              validation={clientIdValidation}
                              className={cn(
                                "focus:border-gray-400 dark:focus:border-gray-600",
                                isDark
                                  ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                  : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                              )}
                            />
                            <ValidatedInput
                              type="password"
                              placeholder={isOAuth1() ? "Consumer Secret" : "Client Secret"}
                              value={clientSecret}
                              onChange={setClientSecret}
                              validation={clientSecretValidation}
                              className={cn(
                                "focus:border-gray-400 dark:focus:border-gray-600",
                                isDark
                                  ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                  : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                              )}
                            />
                          </div>
                        </div>
                      ) : (
                        // For optional OAuth sources, show toggle
                        <>
                          <div className="space-y-3">
                            <label className="flex items-center gap-3 cursor-pointer group">
                              <div className="relative">
                                <input
                                  type="checkbox"
                                  checked={useOwnCredentials}
                                  onChange={(e) => setUseOwnCredentials(e.target.checked)}
                                  className="sr-only"
                                />
                                <div className={cn(
                                  "w-10 h-6 rounded-full transition-colors",
                                  useOwnCredentials
                                    ? "bg-blue-600"
                                    : isDark ? "bg-gray-800" : "bg-gray-200"
                                )}>
                                  <div className={cn(
                                    "absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform",
                                    useOwnCredentials && "translate-x-4"
                                  )} />
                                </div>
                              </div>
                              <span className="text-sm text-gray-600 dark:text-gray-400 group-hover:text-gray-900 dark:group-hover:text-gray-200">
                                Use custom OAuth credentials
                              </span>
                            </label>

                            {/* Help text with hover for optional OAuth */}
                            <div className="flex items-start gap-2 group ml-13">
                              <div className="relative">
                                <HelpCircle className={cn(
                                  "h-3.5 w-3.5 mt-0.5 flex-shrink-0 transition-all cursor-help",
                                  isDark
                                    ? "text-gray-600 group-hover:text-blue-400"
                                    : "text-gray-400 group-hover:text-blue-600"
                                )} />

                                {/* Hover tooltip */}
                                <div className={cn(
                                  "absolute left-0 top-5 z-50 w-72 p-3 rounded-lg shadow-xl",
                                  "opacity-0 invisible group-hover:opacity-100 group-hover:visible",
                                  "transition-all duration-200 transform group-hover:translate-y-0 translate-y-1",
                                  isDark
                                    ? "bg-gray-800 border border-gray-700"
                                    : "bg-white border border-gray-200"
                                )}>
                                  <p className={cn(
                                    "text-xs leading-relaxed",
                                    isDark ? "text-gray-400" : "text-gray-600"
                                  )}>
                                    By default, Airweave uses its own OAuth app to connect. Enable this if you want to use your own OAuth application to show your own name and logo.
                                  </p>
                                </div>
                              </div>

                              <p className={cn(
                                "text-xs",
                                isDark ? "text-gray-500" : "text-gray-500"
                              )}>
                                Optional: Use your own OAuth app for enhanced control.{' '}
                                <a
                                  href="https://docs.airweave.ai/direct-oauth#byoc-bring-your-own-credentials"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className={cn(
                                    "inline-flex items-center gap-0.5 font-medium hover:underline",
                                    isDark ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"
                                  )}
                                >
                                  Learn more
                                  <ExternalLink className="h-2.5 w-2.5" />
                                </a>
                              </p>
                            </div>
                          </div>

                          {useOwnCredentials && (
                            <div className="mt-3 space-y-2.5 pl-13">
                              <ValidatedInput
                                type="text"
                                placeholder={isOAuth1() ? "Consumer Key" : "Client ID"}
                                value={clientId}
                                onChange={setClientId}
                                validation={clientIdValidation}
                                className={cn(
                                  "focus:border-gray-400 dark:focus:border-gray-600",
                                  isDark
                                    ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                    : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                                )}
                              />
                              <ValidatedInput
                                type="password"
                                placeholder={isOAuth1() ? "Consumer Secret" : "Client Secret"}
                                value={clientSecret}
                                onChange={setClientSecret}
                                validation={clientSecretValidation}
                                className={cn(
                                  "focus:border-gray-400 dark:focus:border-gray-600",
                                  isDark
                                    ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                    : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                                )}
                              />
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          {/* OAuth Redirect URL - At the absolute bottom, right above button border */}
          {authMode === 'oauth2' && !connectionUrl && (
            <div className="mt-auto pt-8">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <label className={cn(
                      "text-xs uppercase tracking-wider",
                      isDark ? "text-gray-500" : "text-gray-400"
                    )}>
                      Redirect URL
                    </label>
                    <div className="relative group">
                      <Info className={cn(
                        "h-3 w-3 cursor-help transition-colors",
                        isDark
                          ? "text-gray-600 group-hover:text-gray-400"
                          : "text-gray-400 group-hover:text-gray-600"
                      )} />
                      {/* Hover tooltip */}
                      <div className={cn(
                        "absolute left-0 bottom-5 z-50 w-64 p-3 rounded-lg shadow-xl",
                        "opacity-0 invisible group-hover:opacity-100 group-hover:visible",
                        "transition-all duration-200 transform group-hover:-translate-y-1",
                        isDark
                          ? "bg-gray-800 border border-gray-700"
                          : "bg-white border border-gray-200"
                      )}>
                        <p className={cn(
                          "text-xs leading-relaxed",
                          isDark ? "text-gray-400" : "text-gray-600"
                        )}>
                          This is the URL where users are redirected after they complete OAuth authorization for services like Google Drive, Notion, etc.
                          <br /><br />
                          Your application should handle this callback to process the OAuth response and complete the connection setup.
                          <br /><br />
                          By default, this is set to the current application URL, but you can customize it for your specific integration needs.
                        </p>
                      </div>
                    </div>
                  </div>
                  {!showCustomRedirect && (
                    <button
                      type="button"
                      onClick={() => {
                        setShowCustomRedirect(true);
                        // Pre-populate with https:// so user can continue typing
                        setCustomRedirectUrl('https://');
                      }}
                      className={cn(
                        "text-xs hover:underline transition-colors",
                        isDark
                          ? "text-gray-600 hover:text-gray-400"
                          : "text-gray-500 hover:text-gray-700"
                      )}
                    >
                      Customize
                    </button>
                  )}
                </div>

                {showCustomRedirect ? (
                  <div className="space-y-2">
                    <ValidatedInput
                      type="text"
                      value={customRedirectUrl}
                      onChange={handleRedirectUrlChange}
                      placeholder={getDefaultRedirectUrl()}
                      validation={redirectUrlValidation}
                      className={cn(
                        "text-xs",
                        "focus:border-gray-400 dark:focus:border-gray-600",
                        isDark
                          ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                          : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                      )}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setShowCustomRedirect(false);
                        setCustomRedirectUrl('');
                      }}
                      className={cn(
                        "text-xs hover:underline transition-colors",
                        isDark
                          ? "text-gray-600 hover:text-gray-400"
                          : "text-gray-500 hover:text-gray-700"
                      )}
                    >
                      Use default
                    </button>
                  </div>
                ) : (
                  <div className={cn(
                    "px-3 py-2 rounded-lg text-xs font-mono",
                    isDark
                      ? "bg-gray-900/50 text-gray-500 border border-gray-800"
                      : "bg-gray-50 text-gray-400 border border-gray-100"
                  )}>
                    {getDefaultRedirectUrl()}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom actions - Clean minimal */}
      <div className={cn(
        "px-8 py-6 border-t",
        isDark ? "border-gray-800" : "border-gray-200"
      )}>
        <div className="flex gap-3">
          <button
            onClick={() => handleBackFromSourceConfig()}
            className={cn(
              "px-6 py-2 rounded-lg text-sm font-medium transition-colors",
              isDark
                ? "text-gray-400 hover:text-gray-200"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            Back
          </button>

          {!connectionUrl && (
            <button
              onClick={handleCreate}
              disabled={isCreating || !isFormValid()}
              className={cn(
                "flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                isFormValid() && !isCreating
                  ? "bg-blue-600 hover:bg-blue-700 text-white"
                  : "bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
              )}
            >
              {isCreating ? 'Creating...' : 'Create'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
