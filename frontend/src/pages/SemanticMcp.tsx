import React, { useEffect, useState, useRef } from 'react';
import { useTheme } from '@/lib/theme-provider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Sun, Moon, Monitor, Check, Loader2, Eye, EyeOff } from 'lucide-react';
import { useSourcesStore } from '@/lib/stores';
import { SmallSourceButton } from '@/components/dashboard';
import { useSearchParams } from 'react-router-dom';
import { getAppIconUrl } from '@/lib/utils/icons';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';
import { statusConfig } from '@/components/ui/StatusBadge';
import SimplifiedSourceConnectionDetailView from '@/components/collection/SimplifiedSourceConnectionDetailView';
import { QueryToolAndLiveDoc } from '@/components/collection/SimplifiedQueryToolAndLiveDoc';

interface DetailedSource {
    name: string;
    short_name: string;
    description?: string;
    auth_type?: string;
    auth_config_class?: string;
    auth_fields: {
        fields: Array<{
            name: string;
            title: string;
            description?: string;
            type: string;
        }>;
    };
    config_fields?: {
        fields: Array<{
            name: string;
            title: string;
            description?: string;
            type: string;
        }>;
    };
    labels?: string[];
}

interface SourceConnection {
    id: string;
    name: string;
    description?: string;
    short_name: string;
    collection: string;
    status?: string;
    last_sync_job_status?: string;
    last_sync_job_id?: string;
}

const SemanticMcp = () => {
    const { resolvedTheme, setTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const { sources, isLoading, fetchSources } = useSourcesStore();
    const [connectedSources, setConnectedSources] = useState<Set<string>>(new Set());
    const [selectedSource, setSelectedSource] = useState<{ id: string; name: string; short_name: string } | null>(null);
    const [detailedSource, setDetailedSource] = useState<DetailedSource | null>(null);
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [isLoadingDetails, setIsLoadingDetails] = useState(false);
    const [authValues, setAuthValues] = useState<Record<string, string>>({});
    const [configValues, setConfigValues] = useState<Record<string, string>>({});
    const [passwordVisibility, setPasswordVisibility] = useState<Record<string, boolean>>({});
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [searchParams, setSearchParams] = useSearchParams();
    const [credentialId, setCredentialId] = useState<string | null>(null);
    const [currentCollection, setCurrentCollection] = useState<{ id: string; readable_id: string; name: string } | null>(null);
    const [sourceConnections, setSourceConnections] = useState<SourceConnection[]>([]);
    const [selectedConnection, setSelectedConnection] = useState<SourceConnection | null>(null);

    // Track if we've already processed OAuth results to prevent double alerts
    const hasProcessedOAuthRef = useRef(false);

    const logoSrc = resolvedTheme === "dark" ? "/logo-airweave-darkbg.svg" : "/logo-airweave-lightbg.svg";

    // Create or get API key from session
    const ensureApiKey = async () => {
        try {
            // Check if we already have an API key in session
            const existingApiKey = sessionStorage.getItem('semantic_mcp_api_key');
            if (existingApiKey) {
                console.log('🔑 [SemanticMcp] Using existing API key from session');
                return;
            }

            console.log('🔑 [SemanticMcp] Creating new API key...');

            // Create a new API key
            const response = await apiClient.post('/api-keys/', {});
            if (response.ok) {
                const apiKeyData = await response.json();
                const decryptedKey = apiKeyData.decrypted_key;

                // Store in session storage
                sessionStorage.setItem('semantic_mcp_api_key', decryptedKey);
                console.log('✅ [SemanticMcp] API key created and stored in session');
            } else {
                console.error('❌ [SemanticMcp] Failed to create API key:', await response.text());
            }
        } catch (error) {
            console.error('❌ [SemanticMcp] Error creating API key:', error);
        }
    };

    // Get connection status indicator
    const getConnectionStatusIndicator = (connection: SourceConnection) => {
        // Use the status that comes directly from the API
        // Prioritize last_sync_job_status, then fall back to status field
        const statusValue = connection.last_sync_job_status || connection.status || "";

        // Get the color directly from the statusConfig - same logic as StatusBadge
        const getStatusConfig = (statusKey: string = "") => {
            // Try exact match first
            if (statusKey in statusConfig) {
                return statusConfig[statusKey as keyof typeof statusConfig];
            }

            // Try case-insensitive match
            const lowerKey = statusKey.toLowerCase();
            for (const key in statusConfig) {
                if (key.toLowerCase() === lowerKey) {
                    return statusConfig[key as keyof typeof statusConfig];
                }
            }

            // Return default if no match
            return statusConfig["default"];
        };

        const config = getStatusConfig(statusValue);
        const colorClass = config.color;

        // Add animate-pulse class for in-progress statuses
        const isInProgress = statusValue.toLowerCase() === "in_progress";

        return (
            <span
                className={`inline-flex h-2.5 w-2.5 rounded-full ${colorClass} opacity-80 ${isInProgress ? 'animate-pulse' : ''}`}
                title={config.label}
            />
        );
    };

    // Fetch source connections for a collection
    const fetchSourceConnections = async (collectionId: string) => {
        try {
            console.log("🔍 [SemanticMcp] Fetching source connections for collection:", collectionId);
            const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);

            if (response.ok) {
                const data = await response.json();
                console.log("✅ [SemanticMcp] Loaded source connections:", data);
                setSourceConnections(data);

                // Save to session storage
                sessionStorage.setItem('semantic_mcp_source_connections', JSON.stringify(data));

                // Auto-select the first connection if none selected
                if (data.length > 0 && !selectedConnection) {
                    console.log("🎯 [SemanticMcp] Auto-selecting first connection:", data[0]);
                    setSelectedConnection(data[0]);
                }
            } else {
                console.error("Failed to load source connections:", await response.text());
                setSourceConnections([]);
                setSelectedConnection(null);
            }
        } catch (err) {
            console.error("Error fetching source connections:", err);
            setSourceConnections([]);
            setSelectedConnection(null);
        }
    };

    useEffect(() => {
        fetchSources();

        // Ensure we have an API key
        ensureApiKey();

        // Check if there's a saved collection in sessionStorage (in case of page refresh)
        const savedCollectionJson = sessionStorage.getItem('semantic_mcp_collection');
        if (savedCollectionJson) {
            try {
                const savedCollection = JSON.parse(savedCollectionJson);
                console.log('📦 [SemanticMcp] Restored collection from session:', savedCollection);
                setCurrentCollection(savedCollection);
            } catch (e) {
                console.error('Failed to restore collection from session:', e);
            }
        }

        // Check if there are saved connected sources in sessionStorage
        const savedConnectedSourcesJson = sessionStorage.getItem('semantic_mcp_connected_sources');
        if (savedConnectedSourcesJson) {
            try {
                const savedConnectedSources = JSON.parse(savedConnectedSourcesJson);
                console.log('🔗 [SemanticMcp] Restored connected sources from session:', savedConnectedSources);
                setConnectedSources(new Set(savedConnectedSources));
            } catch (e) {
                console.error('Failed to restore connected sources from session:', e);
            }
        }

        // Check if there are saved source connections in sessionStorage
        const savedSourceConnectionsJson = sessionStorage.getItem('semantic_mcp_source_connections');
        if (savedSourceConnectionsJson) {
            try {
                const savedSourceConnections = JSON.parse(savedSourceConnectionsJson);
                console.log('📋 [SemanticMcp] Restored source connections from session:', savedSourceConnections);
                setSourceConnections(savedSourceConnections);

                // Auto-select first if available
                if (savedSourceConnections.length > 0) {
                    setSelectedConnection(savedSourceConnections[0]);
                }
            } catch (e) {
                console.error('Failed to restore source connections from session:', e);
            }
        }
    }, [fetchSources]);

    // Save collection to sessionStorage whenever it changes
    useEffect(() => {
        if (currentCollection) {
            console.log('💾 [SemanticMcp] Saving collection to session:', currentCollection);
            sessionStorage.setItem('semantic_mcp_collection', JSON.stringify(currentCollection));
        }
    }, [currentCollection]);

    // Save connected sources to sessionStorage whenever it changes
    useEffect(() => {
        if (connectedSources.size > 0) {
            const connectedSourcesArray = Array.from(connectedSources);
            console.log('💾 [SemanticMcp] Saving connected sources to session:', connectedSourcesArray);
            sessionStorage.setItem('semantic_mcp_connected_sources', JSON.stringify(connectedSourcesArray));
        }
    }, [connectedSources]);

    // Fetch source connections when collection changes
    useEffect(() => {
        if (currentCollection?.readable_id) {
            fetchSourceConnections(currentCollection.readable_id);
        } else {
            // Clear source connections when no collection
            setSourceConnections([]);
            setSelectedConnection(null);
            sessionStorage.removeItem('semantic_mcp_source_connections');
        }
    }, [currentCollection?.readable_id]);

    // Handle OAuth errors and restoration
    useEffect(() => {
        const errorParam = searchParams.get('error');
        const restoreDialog = searchParams.get('restore_dialog');

        // Prevent duplicate processing
        if (hasProcessedOAuthRef.current) {
            return;
        }

        if (errorParam === 'oauth') {
            hasProcessedOAuthRef.current = true;

            // Handle OAuth error
            const errorDataJson = sessionStorage.getItem('semantic_mcp_error');
            if (errorDataJson) {
                try {
                    const errorData = JSON.parse(errorDataJson);
                    console.error('🚨 [SemanticMcp] OAuth error detected:', errorData);

                    // Show error alert
                    alert(`OAuth Authentication Failed!\n\nSource: ${errorData.sourceName}\nError: ${errorData.message}`);

                    // Clean up error data
                    sessionStorage.removeItem('semantic_mcp_error');
                } catch (e) {
                    console.error('Failed to parse error data:', e);
                    alert('OAuth authentication failed. Please try again.');
                }
            } else {
                alert('OAuth authentication failed. Please try again.');
            }

            // Clear error parameter from URL
            setSearchParams(prev => {
                const newParams = new URLSearchParams(prev);
                newParams.delete('error');
                return newParams;
            });
        } else if (restoreDialog === 'true') {
            hasProcessedOAuthRef.current = true;

            // Handle dialog restoration after successful OAuth
            const savedStateJson = sessionStorage.getItem('oauth_dialog_state');
            if (savedStateJson) {
                try {
                    const savedState = JSON.parse(savedStateJson);
                    console.log('🔄 [SemanticMcp] Restoring dialog after OAuth success:', savedState);

                    // Restore the dialog state
                    if (savedState.selectedSource) {
                        setSelectedSource(savedState.selectedSource);
                    }
                    if (savedState.detailedSource) {
                        setDetailedSource(savedState.detailedSource);
                    }
                    if (savedState.authValues) {
                        setAuthValues(savedState.authValues);
                    }
                    if (savedState.configValues) {
                        setConfigValues(savedState.configValues);
                    }
                    if (savedState.isAuthenticated) {
                        setIsAuthenticated(savedState.isAuthenticated);
                    }
                    if (savedState.credentialId) {
                        setCredentialId(savedState.credentialId);
                    }
                    if (savedState.currentCollection) {
                        setCurrentCollection(savedState.currentCollection);
                    }

                    // Reopen the dialog
                    setIsDialogOpen(true);

                    // Clean up the saved state
                    sessionStorage.removeItem('oauth_dialog_state');
                } catch (e) {
                    console.error('Failed to restore dialog state:', e);
                    alert('Failed to restore dialog state after OAuth. Please try connecting again.');
                }
            }

            // Clear restore parameter from URL
            setSearchParams(prev => {
                const newParams = new URLSearchParams(prev);
                newParams.delete('restore_dialog');
                return newParams;
            });
        }
    }, [searchParams, setSearchParams]);

    // Log authValues metadata whenever they change (without exposing sensitive data)
    useEffect(() => {
        const sensitiveFields = Object.keys(authValues).filter(key =>
            /(?:token|key|secret|password|credential)/i.test(key)
        );
        const nonSensitiveFields = Object.keys(authValues).filter(key =>
            !/(?:token|key|secret|password|credential)/i.test(key)
        );

        console.log('🔐 [SemanticMcp] AuthValues updated - Total fields:', Object.keys(authValues).length,
            'Sensitive fields:', sensitiveFields.length,
            'Non-sensitive:', nonSensitiveFields);
    }, [authValues]);

    // Log configValues whenever they change
    useEffect(() => {
        console.log('⚙️ [SemanticMcp] ConfigValues updated:', configValues);
        console.log('⚙️ [SemanticMcp] ConfigValues keys:', Object.keys(configValues));
    }, [configValues]);

    // Log detailed source auth fields when they're loaded
    useEffect(() => {
        if (detailedSource?.auth_fields?.fields) {
            console.log('📋 [SemanticMcp] All auth fields from API:', detailedSource.auth_fields.fields.map(f => f.name));
            console.log('📋 [SemanticMcp] Filtered auth fields (shown to user):',
                detailedSource.auth_fields.fields
                    .filter(field => field.name !== 'refresh_token' && field.name !== 'access_token')
                    .map(f => f.name)
            );
            console.log('📋 [SemanticMcp] Hidden auth fields:',
                detailedSource.auth_fields.fields
                    .filter(field => field.name === 'refresh_token' || field.name === 'access_token')
                    .map(f => f.name)
            );
        }
    }, [detailedSource]);

    const fetchSourceDetails = async (shortName: string) => {
        setIsLoadingDetails(true);
        try {
            const response = await apiClient.get(`/sources/${shortName}`);
            if (response.ok) {
                const details = await response.json();
                console.log('🔍 [SemanticMcp] Fetched source details:', details);
                setDetailedSource(details);
            } else {
                console.error('Failed to fetch source details:', response.statusText);
            }
        } catch (error) {
            console.error('Error fetching source details:', error);
        } finally {
            setIsLoadingDetails(false);
        }
    };

    const handleSourceClick = async (source: { name: string; short_name: string }) => {
        // Don't handle click if source is already connected
        if (connectedSources.has(source.short_name)) {
            return;
        }
        console.log('🖱️ [SemanticMcp] Source clicked:', source);
        setSelectedSource(source);
        setIsDialogOpen(true);
        setAuthValues({}); // Reset auth values
        setConfigValues({}); // Reset config values
        setPasswordVisibility({}); // Reset password visibility
        setIsAuthenticated(false); // Reset authentication state
        setCredentialId(null); // Reset credential ID
        await fetchSourceDetails(source.short_name);
    };

    const handleDialogClose = () => {
        console.log('❌ [SemanticMcp] Dialog closing. Final authValues:', authValues);
        console.log('❌ [SemanticMcp] Dialog closing. Final configValues:', configValues);
        setIsDialogOpen(false);
        // Delay clearing to avoid showing fallback text during close animation
        setTimeout(() => {
            setSelectedSource(null);
            setDetailedSource(null);
            setAuthValues({});
            setConfigValues({});
            setPasswordVisibility({});
            setIsAuthenticated(false);
            setCredentialId(null);
            // Note: We do NOT clear currentCollection here - we want to preserve it
        }, 200);
    };

    const handleAuthValueChange = (fieldName: string, value: string) => {
        console.log(`🔐 [SemanticMcp] Auth field "${fieldName}" changed to:`, value ? '[REDACTED]' : '[EMPTY]');
        setAuthValues(prev => ({
            ...prev,
            [fieldName]: value
        }));
    };

    const handleConfigValueChange = (fieldName: string, value: string) => {
        console.log(`⚙️ [SemanticMcp] Config field "${fieldName}" changed to:`, value);
        setConfigValues(prev => ({
            ...prev,
            [fieldName]: value
        }));
    };

    // Function for non-OAuth2 authentication flow
    const createCredentialNonOAuth = async (
        authValues: Record<string, string>,
        detailedSource: DetailedSource
    ): Promise<boolean> => {
        try {
            // Prepare the credential data
            const credentialData = {
                name: `${detailedSource.name} Credential`,
                integration_short_name: detailedSource.short_name,
                description: `Credential for ${detailedSource.name}`,
                integration_type: "source",
                auth_type: detailedSource.auth_type,
                auth_config_class: detailedSource.auth_config_class,
                auth_fields: authValues
            };

            console.log('🔐 [SemanticMcp] Creating credentials for non-OAuth2 source:', sourceShortName, 'with', Object.keys(credentialData).length, 'fields');

            // Make API call to create credentials
            const response = await apiClient.post(
                `/connections/credentials/source/${detailedSource.short_name}`,
                credentialData
            );

            if (response.ok) {
                const credential = await response.json();
                console.log('✅ [SemanticMcp] Credentials created successfully:', credential.id);

                // Store the credential ID in component state
                setCredentialId(credential.id);

                return true;
            } else {
                const errorData = await response.json().catch(() => response.text());
                alert(`Failed to authenticate with ${detailedSource.name}: ${typeof errorData === 'string' ? errorData : JSON.stringify(errorData)}`);
                return false;
            }
        } catch (error) {
            alert(`Error authenticating with ${detailedSource.name}: ${error instanceof Error ? error.message : String(error)}`);
            return false;
        }
    };

    // Function for OAuth2 authentication flow
    const createCredentialsOAuth = async (
        authValues: Record<string, string>,
        configValues: Record<string, string>,
        selectedSource: { id: string; name: string; short_name: string },
        detailedSource: DetailedSource
    ): Promise<boolean> => {
        try {
            console.log(`🔄 Starting OAuth2 authentication for ${detailedSource.name}`);
            console.log(`📦 Auth values:`, authValues);
            console.log(`⚙️ Config values:`, configValues);

            // Prepare the dialog state to save
            const dialogState = {
                selectedSource,
                detailedSource,
                authValues,
                configValues,
                isAuthenticated: false,
                currentCollection,  // Save the current collection
                originPath: window.location.pathname,
                timestamp: Date.now(),
                source: 'semantic-mcp'  // This identifies that we came from SemanticMcp
            };

            console.log(`📊 FULL DIALOG STATE FOR OAUTH:`, JSON.stringify(dialogState, null, 2));

            // Save state to sessionStorage (persists only for this tab, cleared on tab close)
            sessionStorage.setItem('oauth_dialog_state', JSON.stringify(dialogState));

            // Check if we have a client_id in auth fields
            let url = `/source-connections/${detailedSource.short_name}/oauth2_url`;

            // If client_id is present in auth values, add it as a query parameter
            if (authValues && authValues.client_id) {
                console.log(`🔑 Using provided client_id: ${authValues.client_id}`);
                url += `?client_id=${encodeURIComponent(authValues.client_id)}`;
            }

            // Get OAuth URL from backend
            console.log(`🔄 Fetching OAuth URL from: ${url}`);
            const response = await apiClient.get(url);

            if (!response.ok) {
                const errorData = await response.json().catch(() => response.text());
                throw new Error(typeof errorData === 'string' ? errorData : JSON.stringify(errorData));
            }

            const data = await response.json();

            // Backend returns the URL in the 'url' field
            const authorizationUrl = data.url;

            if (!authorizationUrl) {
                console.error("No authorization URL returned:", data);
                throw new Error("No authorization URL returned from server");
            }

            console.log(`✅ Redirecting to OAuth provider: ${authorizationUrl}`);

            // Redirect to OAuth provider
            window.location.href = authorizationUrl;

            // Return value doesn't matter as we're redirecting away
            return true;
        } catch (error) {
            console.error("❌ OAuth authorization error:", error);
            alert(`Error starting OAuth authentication for ${detailedSource.name}: ${error instanceof Error ? error.message : String(error)}`);
            return false;
        }
    };

    const handleAuthenticate = async () => {
        if (!detailedSource || !selectedSource) {
            alert('No source details available');
            return;
        }

        if (detailedSource.auth_type?.startsWith('oauth2')) {
            // Handle OAuth2 sources
            console.log('🔐 [SemanticMcp] Handling OAuth2 authentication');
            const success = await createCredentialsOAuth(authValues, configValues, selectedSource, detailedSource);

            // Note: if success is true, we'll be redirecting away and won't reach this point
            // If success is false, an error occurred and was already handled with alert
        } else {
            // Handle non-OAuth2 sources
            console.log('🔐 [SemanticMcp] Handling non-OAuth2 authentication');
            const success = await createCredentialNonOAuth(authValues, detailedSource);

            if (success) {
                setIsAuthenticated(true);
                // credentialId is already set inside createCredentialNonOAuth
            }
            // If failed, setIsAuthenticated remains false and user sees the error alert
        }
    };

    const handleConnect = async () => {
        console.log('🔗 [SemanticMcp] Connect button clicked');
        console.log('🔗 [SemanticMcp] Final authValues:', authValues);
        console.log('🔗 [SemanticMcp] Final configValues:', configValues);

        if (!selectedSource || !detailedSource) {
            alert('No source selected');
            return;
        }

        try {
            // Get credential ID from appropriate source
            let currentCredentialId: string | undefined = credentialId || undefined;

            if (detailedSource.auth_type?.startsWith('oauth2') && !currentCredentialId) {
                // For OAuth2, check if we have it in restored state
                const savedStateJson = sessionStorage.getItem('oauth_dialog_state');
                if (savedStateJson) {
                    const savedState = JSON.parse(savedStateJson);
                    currentCredentialId = savedState.credentialId;
                }
            }

            if (!currentCredentialId) {
                alert('No credential ID found. Please authenticate first.');
                return;
            }

            // Step 1: Check if we already have a collection or create one
            let collection = currentCollection;
            let isNewCollection = false;

            if (!collection) {
                isNewCollection = true;
                console.log('📦 [SemanticMcp] Creating new collection...');
                const timestamp = new Date().toISOString();
                const collectionData = {
                    name: `My Collection`  // Must be at least 4 characters
                };

                const collectionResponse = await apiClient.post('/collections/', collectionData);
                if (!collectionResponse.ok) {
                    const errorData = await collectionResponse.json().catch(() => collectionResponse.text());
                    throw new Error(`Failed to create collection: ${typeof errorData === 'string' ? errorData : JSON.stringify(errorData)}`);
                }

                collection = await collectionResponse.json();
                console.log('✅ [SemanticMcp] Collection created:', collection);

                // Save the collection to state for future use
                setCurrentCollection(collection);
            } else {
                console.log('📦 [SemanticMcp] Using existing collection:', collection.name);
            }

            // Step 2: Create source connection
            console.log('🔗 [SemanticMcp] Creating source connection...');
            const sourceConnectionData = {
                name: `${selectedSource.name} Connection`,  // Must be at least 4 characters
                description: `Connection to ${selectedSource.name}`,
                short_name: selectedSource.short_name,
                collection: collection.readable_id,  // Use the readable_id from the created collection
                config_fields: configValues,
                credential_id: currentCredentialId,
                sync_immediately: true  // Start syncing immediately
            };

            console.log('📋 [SemanticMcp] Source connection data:', sourceConnectionData);

            const connectionResponse = await apiClient.post('/source-connections/', sourceConnectionData);
            if (!connectionResponse.ok) {
                const errorData = await connectionResponse.json().catch(() => connectionResponse.text());
                throw new Error(`Failed to create source connection: ${typeof errorData === 'string' ? errorData : JSON.stringify(errorData)}`);
            }

            const sourceConnection = await connectionResponse.json();
            console.log('✅ [SemanticMcp] Source connection created:', sourceConnection);

            // Alert the sync job ID
            const collectionAction = isNewCollection ? 'Created new' : 'Added to existing';

            // Add source to connected sources
            setConnectedSources(prev => new Set([...prev, selectedSource.id]));

            // Refresh source connections to include the new one
            if (collection?.readable_id) {
                fetchSourceConnections(collection.readable_id);
            }

            // Close the dialog
            handleDialogClose();

            // Clear the OAuth state if it exists
            sessionStorage.removeItem('oauth_dialog_state');

        } catch (error) {
            console.error('❌ [SemanticMcp] Error connecting source:', error);
            alert(`Failed to connect to ${selectedSource.name}:\n\n${error instanceof Error ? error.message : String(error)}`);
        }
    };

    const togglePasswordVisibility = (fieldId: string) => {
        setPasswordVisibility(prev => ({
            ...prev,
            [fieldId]: !prev[fieldId]
        }));
    };

    const isPasswordField = (fieldName: string) => {
        return fieldName.toLowerCase().includes('password') ||
            fieldName.toLowerCase().includes('secret') ||
            fieldName.toLowerCase().includes('key') ||
            fieldName.toLowerCase().includes('token');
    };

    const getInputType = (fieldName: string, fieldType: string, fieldId: string) => {
        if (isPasswordField(fieldName)) {
            return passwordVisibility[fieldId] ? 'text' : 'password';
        }
        if (fieldType === 'email') {
            return 'email';
        }
        if (fieldType === 'number' || fieldType === 'integer') {
            return 'number';
        }
        if (fieldType === 'url') {
            return 'url';
        }
        return 'text';
    };

    // Check if all required fields are filled
    const isFormValid = () => {
        // Check auth fields (non-token fields)
        const authFieldsEmpty = detailedSource?.auth_fields?.fields
            ?.filter(field => field.name !== 'refresh_token' && field.name !== 'access_token')
            ?.some(field => !authValues[field.name]?.trim());
        return !authFieldsEmpty;
    };

    return (
        <div className="min-h-screen relative">
            {/* Theme Toggle Button - Top Right */}
            <div className="absolute top-4 right-4 z-10">
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="rounded-lg h-8 w-8 hover:bg-background-alpha-40 text-muted-foreground transition-all duration-200">
                            {resolvedTheme === 'dark' ? (
                                <Moon className="h-[18px] w-[18px]" />
                            ) : (
                                <Sun className="h-[18px] w-[18px]" />
                            )}
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-32 rounded-lg overflow-hidden">
                        <DropdownMenuItem
                            onClick={() => setTheme('light')}
                            className="flex items-center justify-between cursor-pointer transition-colors"
                        >
                            <div className="flex items-center">
                                <Sun className="mr-2 h-4 w-4" />
                                Light
                            </div>
                            {resolvedTheme === 'light' && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                            onClick={() => setTheme('dark')}
                            className="flex items-center justify-between cursor-pointer transition-colors"
                        >
                            <div className="flex items-center">
                                <Moon className="mr-2 h-4 w-4" />
                                Dark
                            </div>
                            {resolvedTheme === 'dark' && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                            onClick={() => setTheme('system')}
                            className="flex items-center justify-between cursor-pointer transition-colors"
                        >
                            <div className="flex items-center">
                                <Monitor className="mr-2 h-4 w-4" />
                                System
                            </div>
                            {(resolvedTheme !== 'dark' && resolvedTheme !== 'light') && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>

            {/* Logo and Tagline - Perfectly Centered */}
            <div className="flex flex-col items-center justify-center pt-8">
                <img src={logoSrc} alt="Airweave" className="h-20" />
                <p className="text-lg text-muted-foreground text-center mt-4">
                    Turn any app into a semantically searchable MCP server
                </p>
            </div>

            {/* Sources Section with Border */}
            <div className="flex justify-center px-10 mt-6">
                <div className="border border-gray-200 dark:border-gray-700 rounded-xl px-6 py-3 bg-white/50 dark:bg-gray-900/30 backdrop-blur-sm max-w-[900px] w-full mx-auto">
                    <h2 className="text-2xl mb-4 text-center">🔗 Connect to your data sources</h2>

                    <div className="grid grid-cols-8 gap-1 justify-items-center mx-auto">
                        {isLoading ? (
                            <div className="col-span-8 h-40 flex items-center justify-center">
                                <div className="animate-pulse">Loading sources...</div>
                            </div>
                        ) : sources.length === 0 ? (
                            <div className="col-span-8 text-center py-10 text-muted-foreground">
                                No sources available
                            </div>
                        ) : (
                            [...sources]
                                .filter((source) => source.short_name.toLowerCase() !== 'ctti' && source.short_name.toLowerCase() !== 'oracle')
                                .sort((a, b) => a.name.localeCompare(b.name))
                                .map((source) => (
                                    <SmallSourceButton
                                        key={source.short_name}
                                        id={source.short_name}
                                        name={source.name}
                                        shortName={source.short_name}
                                        connected={connectedSources.has(source.short_name)}
                                        onClick={() => handleSourceClick(source)}
                                    />
                                ))
                        )}
                    </div>
                </div>
            </div>

            {/* Show either the empty state or connected sources */}
            {sourceConnections.length === 0 ? (
                /* Empty state - grayed out box */
                <div className="flex justify-center px-10 mt-6">
                    <div className="border border-gray-300/50 dark:border-gray-600/50 rounded-xl px-6 py-3 bg-gray-100/30 dark:bg-gray-800/20 backdrop-blur-sm max-w-[900px] w-full mx-auto">
                        <h2 className="text-2xl mb-4 text-center text-muted-foreground/60">
                            🚀 Data will start syncing once you connect your data
                        </h2>
                    </div>
                </div>
            ) : (
                /* Connected sources with data sync status */
                <div className="flex justify-center px-10 mt-6">
                    <div className="border border-gray-200 dark:border-gray-700 rounded-xl px-6 py-3 bg-white/50 dark:bg-gray-900/30 backdrop-blur-sm max-w-[900px] w-full mx-auto">
                        <h2 className="text-2xl mb-4 text-center">🚀 Data sync</h2>
                        <div className="grid grid-cols-8 gap-1 justify-items-center mx-auto">
                            {sourceConnections.map((connection) => (
                                <div
                                    key={connection.id}
                                    className={cn(
                                        "border rounded-lg overflow-hidden transition-all min-w-[100px] h-[60px] cursor-pointer",
                                        selectedConnection?.id === connection.id
                                            ? "border-2 border-primary"
                                            : isDark
                                                ? "border-gray-700 bg-gray-800/50 hover:bg-gray-700/70"
                                                : "border-gray-200 bg-white hover:bg-gray-50"
                                    )}
                                    onClick={() => setSelectedConnection(connection)}
                                    title={connection.name}
                                >
                                    <div className="p-2 flex items-center justify-between h-full">
                                        {/* Status indicator - in circular container like plus button */}
                                        <div className={cn(
                                            "h-6 w-6 rounded-full flex-shrink-0 flex items-center justify-center",
                                            isDark
                                                ? "bg-gray-800/80"
                                                : "bg-gray-100/80"
                                        )}>
                                            {React.cloneElement(getConnectionStatusIndicator(connection), {
                                                className: `inline-flex h-4 w-4 rounded-full ${getConnectionStatusIndicator(connection).props.className.split('h-2.5 w-2.5').join('').trim()} opacity-80 ${connection.last_sync_job_status?.toLowerCase() === "in_progress" ? 'animate-pulse' : ''}`
                                            })}
                                        </div>

                                        {/* Source icon */}
                                        <div className="flex items-center justify-center w-10 h-10 overflow-hidden rounded-md flex-shrink-0">
                                            <img
                                                src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                                alt={connection.name}
                                                className="w-9 h-9 object-contain"
                                                onError={(e) => {
                                                    // Fallback to initials if icon fails to load
                                                    e.currentTarget.style.display = 'none';
                                                    e.currentTarget.parentElement!.classList.add('bg-blue-500');
                                                    e.currentTarget.parentElement!.innerHTML = `<span class="text-white font-semibold text-sm">${connection.short_name.substring(0, 2).toUpperCase()}</span>`;
                                                }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                        {/* Source Connection Detail View - Show when a connection is selected */}
                        {selectedConnection && (
                            <div className="flex justify-center mt-2">
                                <div className="w-full mx-auto">
                                    <SimplifiedSourceConnectionDetailView
                                        sourceConnectionId={selectedConnection.id}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Query your data section */}
            <div className="flex justify-center px-10 mt-6">
                <div className={cn(
                    "border rounded-xl px-6 py-3 backdrop-blur-sm max-w-[900px] w-full mx-auto relative",
                    sourceConnections.length === 0
                        ? "border-gray-300/50 dark:border-gray-600/50 bg-gray-100/30 dark:bg-gray-800/20"
                        : "border-gray-200 dark:border-gray-700 bg-white/50 dark:bg-gray-900/30"
                )}>
                    <h2 className={cn(
                        "text-2xl mb-4 text-center",
                        sourceConnections.length === 0
                            ? "text-muted-foreground/60"
                            : ""
                    )}>
                        🔎 Query your data
                    </h2>

                    {/* Always show QueryToolAndLiveDoc, but overlay when disabled */}
                    <div className="relative pt-5">
                        {/* Show the component with a dummy collection ID when no connections */}
                        <QueryToolAndLiveDoc
                            collectionReadableId={currentCollection?.readable_id || "my-collection-1234"}
                        />

                        {/* Overlay when no source connections */}
                        {sourceConnections.length === 0 && (
                            <div className="absolute inset-0 bg-gray-50/2 dark:bg-gray-900/2 backdrop-blur-[1px] rounded-lg flex items-center justify-center">
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Source Details Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={(open) => !open && handleDialogClose()}>
                <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle className="flex items-center justify-center gap-3 text-xl">
                            Connect to {selectedSource?.name}
                            {selectedSource && (
                                <div className="flex items-center justify-center w-12 h-12 overflow-hidden rounded-lg border">
                                    <img
                                        src={getAppIconUrl(selectedSource.short_name, resolvedTheme)}
                                        alt={`${selectedSource.short_name} icon`}
                                        className="w-11 h-11 object-contain"
                                        onError={(e) => {
                                            e.currentTarget.style.display = 'none';
                                            const parent = e.currentTarget.parentElement!;
                                            parent.classList.add('bg-blue-500');
                                            parent.innerHTML = `<span class="text-white font-semibold text-xs">${selectedSource.short_name.substring(0, 2).toUpperCase()}</span>`;
                                        }}
                                    />
                                </div>
                            )}
                        </DialogTitle>
                    </DialogHeader>

                    {isLoadingDetails ? (
                        <div className="flex flex-col items-center justify-center py-8">
                            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                            <p className="mt-2 text-sm text-muted-foreground">Loading source details...</p>
                        </div>
                    ) : selectedSource && detailedSource ? (
                        <div className="space-y-6">
                            {/* Authentication Fields */}
                            {detailedSource.auth_fields?.fields?.length > 0 && (
                                <div>
                                    <div className="space-y-4">
                                        {detailedSource.auth_fields.fields
                                            .filter(field => field.name !== 'refresh_token' && field.name !== 'access_token')
                                            .map((field, index) => (
                                                <div key={index} className="space-y-2">
                                                    <Label htmlFor={field.name} className="text-sm font-medium">
                                                        {field.title}
                                                    </Label>
                                                    {field.description && (
                                                        <p className="text-xs text-muted-foreground">
                                                            {field.description}
                                                        </p>
                                                    )}
                                                    <div className="relative">
                                                        <Input
                                                            id={field.name}
                                                            type={getInputType(field.name, field.type, field.name)}
                                                            placeholder={`Enter your ${field.title.toLowerCase()}`}
                                                            value={authValues[field.name] || ''}
                                                            onChange={(e) => handleAuthValueChange(field.name, e.target.value)}
                                                            className="w-full pr-10"
                                                        />
                                                        {isPasswordField(field.name) && (
                                                            <Button
                                                                type="button"
                                                                variant="ghost"
                                                                size="icon"
                                                                className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                                                                onClick={() => togglePasswordVisibility(field.name)}
                                                            >
                                                                {passwordVisibility[field.name] ? (
                                                                    <EyeOff className="h-4 w-4 text-muted-foreground" />
                                                                ) : (
                                                                    <Eye className="h-4 w-4 text-muted-foreground" />
                                                                )}
                                                            </Button>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                    </div>
                                </div>
                            )}

                            {/* Configuration Fields */}
                            {detailedSource.config_fields?.fields?.length > 0 && (
                                <div>
                                    <div className="space-y-3">
                                        {detailedSource.config_fields.fields.map((field, index) => (
                                            <div key={index} className="space-y-2">
                                                <Label htmlFor={`config_${field.name}`} className="text-sm font-medium">
                                                    {field.title}
                                                </Label>
                                                {field.description && (
                                                    <p className="text-xs text-muted-foreground">
                                                        {field.description}
                                                    </p>
                                                )}
                                                <div className="relative">
                                                    <Input
                                                        id={`config_${field.name}`}
                                                        type={getInputType(field.name, field.type, `config_${field.name}`)}
                                                        placeholder={`Enter ${field.title.toLowerCase()}`}
                                                        value={configValues[field.name] || ''}
                                                        onChange={(e) => handleConfigValueChange(field.name, e.target.value)}
                                                        className={`w-full ${isPasswordField(field.name) ? 'pr-10' : ''}`}
                                                    />
                                                    {isPasswordField(field.name) && (
                                                        <Button
                                                            type="button"
                                                            variant="ghost"
                                                            size="icon"
                                                            className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                                                            onClick={() => togglePasswordVisibility(`config_${field.name}`)}
                                                        >
                                                            {passwordVisibility[`config_${field.name}`] ? (
                                                                <EyeOff className="h-4 w-4 text-muted-foreground" />
                                                            ) : (
                                                                <Eye className="h-4 w-4 text-muted-foreground" />
                                                            )}
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Action Buttons */}
                            <div className="flex justify-center gap-3 pt-4">
                                {/* Authenticate Button */}
                                <Button
                                    onClick={handleAuthenticate}
                                    disabled={!isFormValid()}
                                    className={`px-6 flex items-center gap-2 ${isAuthenticated
                                        ? 'bg-green-600 hover:bg-green-700 text-white'
                                        : ''
                                        }`}
                                >
                                    {isAuthenticated && <Check className="h-4 w-4" />}
                                    {isAuthenticated ? 'Authenticated' : 'Authenticate'}
                                </Button>

                                {/* Connect Button */}
                                <Button
                                    onClick={handleConnect}
                                    disabled={!isAuthenticated}
                                    className="px-6"
                                    variant={isAuthenticated ? "default" : "secondary"}
                                >
                                    Connect
                                </Button>
                            </div>
                        </div>
                    ) : selectedSource ? (
                        <div className="flex flex-col items-center space-y-4 py-4">
                            <div className="text-center">
                                <h3 className="text-lg font-semibold">{selectedSource.name}</h3>
                            </div>
                        </div>
                    ) : null}
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default SemanticMcp;
