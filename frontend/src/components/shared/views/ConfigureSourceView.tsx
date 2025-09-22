import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { redirectWithError } from "@/lib/error-utils";
import { apiClient } from "@/lib/api";
import { authenticateSource } from "@/lib/authenticate";
import { getAppIconUrl } from "@/lib/utils/icons";
import { Switch } from "@/components/ui/switch";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";
import { ExternalLink } from "lucide-react";

export interface ConfigureSourceViewProps {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    viewData?: Record<string, any>;
    onError?: (error: Error | string, errorSource?: string) => void;
}

export const ConfigureSourceView: React.FC<ConfigureSourceViewProps> = ({
    onNext,
    onBack,
    onCancel,
    onComplete,
    viewData = {},
    onError,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [sourceDetails, setSourceDetails] = useState<any>(null);
    const [authValues, setAuthValues] = useState<Record<string, any>>({});
    const [configValues, setConfigValues] = useState<Record<string, any>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});
    const [submitting, setSubmitting] = useState(false);
    const [step, setStep] = useState<'auth' | 'config'>('auth');
    const [validationAttempted, setValidationAttempted] = useState(false);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [dialogState, setDialogState] = useState<any>(null);
    const [connectionName, setConnectionName] = useState<string>(
        viewData.connectionName || `${viewData.sourceName || ""} Connection`
    );
    const [useExternalAuthProvider, setUseExternalAuthProvider] = useState(false);
    const [selectedAuthProviderConnection, setSelectedAuthProviderConnection] = useState<any>(null);
    const [authProviderDetails, setAuthProviderDetails] = useState<any>(null);
    const [authProviderConfigValues, setAuthProviderConfigValues] = useState<Record<string, any>>({});
    const [loadingAuthProviderDetails, setLoadingAuthProviderDetails] = useState(false);

    // Add this new state to store the credential ID
    const [credentialId, setCredentialId] = useState<string | null>(
        viewData.credentialId || null
    );

    // Sources that are temporarily blocked from using auth providers
    // This should match the backend list in source_connections.py
    const SOURCES_BLOCKED_FROM_AUTH_PROVIDERS = [
        "confluence",
        "jira",
        "bitbucket",
        "github",
        "ctti",
        "monday",
        "postgresql"
    ];

    // Use auth providers store
    const {
        authProviderConnections,
        isLoadingConnections,
        fetchAuthProviderConnections
    } = useAuthProvidersStore();

    // Extract data passed from previous views
    const {
        sourceName,
        sourceShortName,
        collectionId,
        collectionName,
        created_collection_id,
        created_collection_name
    } = viewData;

    // Helper function to check if a field is a token field that should be skipped
    const isTokenField = (fieldName: string): boolean => {
        const lowerName = fieldName.toLowerCase();
        return lowerName === 'refresh_token' || lowerName === 'access_token';
    };

    // Helper function to strip whitespace from string values
    const stripWhitespaceFromValues = (values: Record<string, any>): Record<string, any> => {
        return Object.fromEntries(
            Object.entries(values).map(([key, value]) => [
                key,
                typeof value === 'string' ? value.trim() : value
            ])
        );
    };

    // Fetch source details including auth and config fields
    useEffect(() => {
        if (!sourceShortName) return;

        const fetchSourceDetails = async () => {
            setLoading(true);
            try {
                const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                if (response.ok) {
                    const data = await response.json();
                    setSourceDetails(data);
                    console.log("Source details loaded:", data);

                    // Initialize auth values with empty strings (skip token fields)
                    if (data.auth_fields && data.auth_fields.fields) {
                        const initialAuthValues: Record<string, any> = {};
                        // Handle auth_fields.fields as array of objects with name property
                        data.auth_fields.fields.forEach((field: any) => {
                            if (field.name) {
                                // First check if we have a saved value in viewData
                                const savedValue = viewData.authValues && viewData.authValues[field.name];
                                // If saved value exists, use it, otherwise initialize with empty or null
                                initialAuthValues[field.name] = savedValue !== undefined ? savedValue :
                                    (isTokenField(field.name) ? null : '');
                            }
                        });
                        setAuthValues(initialAuthValues);
                    }

                    // Initialize config values with proper default values based on type
                    if (data.config_fields && data.config_fields.fields) {
                        const initialConfigValues: Record<string, any> = {};
                        data.config_fields.fields.forEach((field: any) => {
                            if (field.name) {
                                if (field.type === 'boolean') {
                                    initialConfigValues[field.name] = false; // Default boolean fields to false
                                } else {
                                    initialConfigValues[field.name] = '';
                                }
                            }
                        });
                        setConfigValues(initialConfigValues);
                    }
                } else {
                    const errorText = await response.text();
                    console.error(`Failed to load source details: ${errorText}`);
                    handleError(new Error(`Failed to load source details: ${errorText}`), "Source details fetch error");
                }
            } catch (error) {
                console.error("Error fetching source details:", error);
                handleError(error instanceof Error ? error : new Error(String(error)), "Source details fetch error");
            } finally {
                setLoading(false);
            }
        };

        fetchSourceDetails();
    }, [sourceShortName, viewData.authValues]);

    // Fetch auth provider connections on mount
    useEffect(() => {
        fetchAuthProviderConnections();
    }, [fetchAuthProviderConnections]);

    // Ensure external auth provider is disabled for blocked sources
    useEffect(() => {
        if (sourceShortName && SOURCES_BLOCKED_FROM_AUTH_PROVIDERS.includes(sourceShortName)) {
            setUseExternalAuthProvider(false);
            setSelectedAuthProviderConnection(null);
            setAuthProviderDetails(null);
            setAuthProviderConfigValues({});
        }
    }, [sourceShortName]);

    // Fetch auth provider details when a connection is selected
    const fetchAuthProviderDetails = async (connection: any) => {
        setLoadingAuthProviderDetails(true);
        try {
            const response = await apiClient.get(`/auth-providers/detail/${connection.short_name}`);
            if (response.ok) {
                const data = await response.json();
                setAuthProviderDetails(data);
                console.log("Auth provider details loaded:", data);
                console.log("🔍 Config fields structure:", {
                    hasConfigFields: !!data.config_fields,
                    fieldsArray: data.config_fields?.fields,
                    fieldsCount: data.config_fields?.fields?.length,
                    fields: data.config_fields?.fields?.map((f: any) => ({
                        name: f.name,
                        required: f.required,
                        title: f.title
                    }))
                });

                // Initialize config values with empty strings
                if (data.config_fields && data.config_fields.fields) {
                    const initialConfigValues: Record<string, any> = {};
                    data.config_fields.fields.forEach((field: any) => {
                        if (field.name) {
                            initialConfigValues[field.name] = '';
                        }
                    });
                    setAuthProviderConfigValues(initialConfigValues);
                }
            } else {
                const errorText = await response.text();
                console.error(`Failed to load auth provider details: ${errorText}`);
                handleError(new Error(`Failed to load auth provider details: ${errorText}`), "Auth provider details fetch error");
            }
        } catch (error) {
            console.error("Error fetching auth provider details:", error);
            handleError(error instanceof Error ? error : new Error(String(error)), "Auth provider details fetch error");
        } finally {
            setLoadingAuthProviderDetails(false);
        }
    };

    // Handle auth provider connection selection
    const handleAuthProviderConnectionSelect = async (connection: any) => {
        console.log(`Selected auth provider connection: ${connection.name}`);
        setSelectedAuthProviderConnection(connection);
        await fetchAuthProviderDetails(connection);
    };

    // Create a consistent error handler
    const handleError = (error: Error | string, errorSource?: string) => {
        console.error(`❌ [ConfigureSourceView] Error:`, error);

        // If onError is provided, use it first
        if (onError) {
            onError(error, errorSource || sourceName || sourceShortName);
        } else {
            // Otherwise redirect directly with dialogId
            const errorDetails = {
                serviceName: errorSource || sourceName || sourceShortName || "Source Configuration",
                sourceShortName: sourceShortName,
                errorMessage: error instanceof Error ? error.message : String(error),
                errorDetails: error instanceof Error ? error.stack : undefined,
                dialogId: viewData?.dialogId, // Include dialogId from viewData
                timestamp: Date.now()
            };

            redirectWithError(navigate, errorDetails, errorSource || sourceName || sourceShortName);
        }
    };

    // Simplify validate auth fields - all fields are required
    const validateAuthFields = (): boolean => {
        const newErrors: Record<string, string> = {};
        let isValid = true;

        // All visualized fields are required
        if (sourceDetails?.auth_fields?.fields) {
            sourceDetails.auth_fields.fields
                .filter(field => field.name && !isTokenField(field.name))
                .forEach((field: any) => {
                    if (!authValues[field.name] || authValues[field.name].trim() === '') {
                        newErrors[field.name] = `${field.title || field.name} is required`;
                        isValid = false;
                    }
                });
        }

        setErrors(newErrors);
        logAuthFieldsStatus();
        return isValid;
    };

    // Simplify hasEmptyRequiredAuthFields - all fields are required
    const hasEmptyRequiredAuthFields = (): boolean => {
        if (!sourceDetails?.auth_fields?.fields) return false;

        return sourceDetails.auth_fields.fields
            .filter(field => field.name && !isTokenField(field.name))
            .some(field => !authValues[field.name] || authValues[field.name].trim() === '');
    };

    // Check if required auth provider config fields are empty
    const hasEmptyRequiredAuthProviderConfigFields = (): boolean => {
        console.log('🔍 [hasEmptyRequiredAuthProviderConfigFields] Checking config fields...');
        console.log('  - authProviderDetails:', authProviderDetails);
        console.log('  - config_fields:', authProviderDetails?.config_fields);
        console.log('  - fields array:', authProviderDetails?.config_fields?.fields);

        if (!authProviderDetails?.config_fields?.fields) {
            console.log('  ❌ No config fields found, returning false');
            return false;
        }

        const requiredFields = authProviderDetails.config_fields.fields.filter((field: any) => field.required);
        console.log('  - Required fields:', requiredFields);
        // console.log('  - Current authProviderConfigValues:', authProviderConfigValues);

        const result = requiredFields.some((field: any) => {
            const value = authProviderConfigValues[field.name];
            const isEmpty = !value || value.trim() === '';
            console.log(`  - Field "${field.name}": value="${value}", isEmpty=${isEmpty}`);
            return isEmpty;
        });

        console.log(`  📊 Final result: ${result} (true = has empty required fields)`);
        return result;
    };

    // Simplify the logging function - all fields are required
    const logAuthFieldsStatus = () => {
        if (!sourceDetails?.auth_fields?.fields) return;

        console.group('🔐 Auth Fields Status:');

        sourceDetails.auth_fields.fields
            .filter((field: any) => field.name && !isTokenField(field.name))
            .forEach((field: any) => {
                const value = authValues[field.name] || '';
                const isEmpty = !value || value.trim() === '';
                const status = isEmpty ? '❌ INVALID' : '✅ VALID';

                console.log(
                    `${field.title || field.name}: %c${status}%c | Required: %cYES%c | Value: %c${isEmpty ? '(empty)' : value}`,
                    status.includes('✅') ? 'color: green; font-weight: bold' : 'color: red; font-weight: bold',
                    'color: inherit',
                    'color: orange; font-weight: bold',
                    'color: inherit',
                    isEmpty ? 'color: gray; font-style: italic' : 'color: blue'
                );
            });

        console.log('Has empty fields:', hasEmptyRequiredAuthFields());
        console.groupEnd();
    };

    // Add to handleAuthFieldChange
    const handleAuthFieldChange = (key: string, value: string) => {
        setAuthValues(prev => {
            const newValues = {
                ...prev,
                [key]: value
            };

            // Log after value changes but before validation
            setTimeout(() => {
                console.log(`Field changed: ${key} => "${value}"`);
                logAuthFieldsStatus();
            }, 0);

            return newValues;
        });

        // If validation has been attempted, validate in real-time
        if (validationAttempted) {
            validateAuthFields();
        }

        // Clear error for this field if any
        if (errors[key]) {
            setErrors(prev => {
                const updated = { ...prev };
                delete updated[key];
                return updated;
            });
        }
    };

    const handleConfigFieldChange = (key: string, value: string) => {
        setConfigValues(prev => ({
            ...prev,
            [key]: value
        }));
        // Clear error for this field if any
        if (errors[key]) {
            setErrors(prev => {
                const updated = { ...prev };
                delete updated[key];
                return updated;
            });
        }
    };

    // Add this function to check if there are config fields
    const hasConfigFields = (): boolean => {
        return !!(sourceDetails?.config_fields?.fields &&
            sourceDetails.config_fields.fields.length > 0);
    };

    // Modify handleNextStep
    const handleNextStep = () => {
        console.log('🔄 Attempting to proceed to next step...');
        setValidationAttempted(true);

        let isValid = false;

        if (useExternalAuthProvider) {
            // Validate external auth provider selection and config
            if (!selectedAuthProviderConnection) {
                console.log('❌ No auth provider connection selected');
                setErrors({ _authProvider: 'Please select an auth provider connection' });
                isValid = false;
            } else {
                // Validate auth provider config fields if any
                const newErrors: Record<string, string> = {};
                if (authProviderDetails?.config_fields?.fields) {
                    authProviderDetails.config_fields.fields
                        .filter((field: any) => field.required)
                        .forEach((field: any) => {
                            if (!authProviderConfigValues[field.name] || authProviderConfigValues[field.name].trim() === '') {
                                newErrors[field.name] = `${field.title || field.name} is required`;
                                isValid = false;
                            }
                        });
                }

                if (Object.keys(newErrors).length === 0) {
                    isValid = true;
                }
                setErrors(newErrors);
            }
        } else {
            // Validate regular auth fields
            isValid = validateAuthFields();
        }

        console.log(`Validation result: ${isValid ? '✅ VALID' : '❌ INVALID'}`);

        if (isValid) {
            if (hasConfigFields()) {
                console.log('✅ Proceeding to config step');
                setStep('config');
            } else {
                console.log('✅ No config fields, proceeding directly to connection');
                handleComplete();
            }
        } else {
            console.log('❌ Cannot proceed - validation failed');
        }
    };

    const handleComplete = async () => {
        if (!validateConfigFields()) {
            return;
        }

        setSubmitting(true);
        try {
            // Strip whitespace from all values before processing
            const cleanedAuthValues = stripWhitespaceFromValues(authValues);
            const cleanedConfigValues = stripWhitespaceFromValues(configValues);
            const cleanedAuthProviderConfigValues = stripWhitespaceFromValues(authProviderConfigValues);

            // Determine which collection we're using
            let collectionId = viewData.collectionId;

            // If we need to create a collection (it doesn't exist yet)
            if (viewData.created_collection_id && viewData.created_collection_name) {
                console.log(`🆕 Creating new collection: ${viewData.created_collection_name} (${viewData.created_collection_id})`);

                // Create collection via API
                const collectionResponse = await apiClient.post('/collections', {
                    name: viewData.created_collection_name,
                    readable_id: viewData.created_collection_id
                });

                if (!collectionResponse.ok) {
                    const errorText = await collectionResponse.text();
                    throw new Error(`Failed to create collection: ${errorText}`);
                }

                const collection = await collectionResponse.json();
                console.log(`✅ Collection created successfully: ${collection.readable_id}`);
                collectionId = collection.readable_id;
            }

            // Branch based on authentication method
            let sourceConnectionResponse;

            if (useExternalAuthProvider) {
                // External Auth Provider Path
                if (!selectedAuthProviderConnection) {
                    throw new Error("No auth provider connection selected");
                }

                console.log(`🔌 Creating source connection with auth provider: ${selectedAuthProviderConnection.readable_id}`);

                const sourceConnectionData = {
                    name: viewData.connectionName || connectionName || `${sourceName} Connection`,
                    short_name: sourceShortName,
                    collection: collectionId,
                    auth_provider: selectedAuthProviderConnection.readable_id,
                    auth_provider_config: cleanedAuthProviderConfigValues,
                    config_fields: cleanedConfigValues,
                    sync_immediately: true
                };

                // console.log('Source connection data (auth provider):', sourceConnectionData);

                // Use public endpoint for auth provider connections
                sourceConnectionResponse = await apiClient.post('/source-connections', sourceConnectionData);

            } else {
                // Regular Authentication Path (existing logic)
                // Check both local state and viewData for credential ID
                const effectiveCredentialId = credentialId || viewData.credentialId;

                if (!effectiveCredentialId) {
                    throw new Error("Missing credential ID. Authentication may not have completed properly.");
                }

                console.log(`🔌 Creating source connection with credential: ${effectiveCredentialId}`);

                const sourceConnectionData = {
                    name: viewData.connectionName || connectionName || `${sourceName} Connection`,
                    short_name: sourceShortName,
                    collection: collectionId,
                    credential_id: effectiveCredentialId,
                    config_fields: cleanedConfigValues,
                    sync_immediately: true
                };

                console.log(`📝 Source connection data (credential):`, sourceConnectionData);

                // Use internal endpoint since we're using a credential_id
                sourceConnectionResponse = await apiClient.post('/source-connections/internal/', sourceConnectionData);
            }

            // Handle response (common for both paths)
            if (!sourceConnectionResponse.ok) {
                const errorText = await sourceConnectionResponse.text();
                console.error("Source connection error response:", errorText);

                const errorMessage = `Failed to create source connection: ${errorText}`;
                let errorDetails = errorText;

                try {
                    // Try to parse as JSON for more details
                    const errorObj = JSON.parse(errorText);
                    if (errorObj.detail) {
                        // Keep the original error message but extract detail for UI
                        errorDetails = errorObj.detail;
                    }
                } catch (e) {
                    // Not JSON, use as is
                    console.log("Error response is not JSON:", errorText);
                }

                throw new Error(errorMessage);
            }

            const sourceConnection = await sourceConnectionResponse.json();
            console.log(`✅ Source connection created successfully: ${sourceConnection.id}`);

            // Clear credential from sessionStorage to prevent auto-reopening
            sessionStorage.removeItem('oauth_dialog_state');

            // Complete the process
            if (onComplete) {
                onComplete({
                    success: true,
                    message: "Source connected successfully",
                    source_short_name: sourceShortName,
                    collection_id: collectionId,
                    source_connection_id: sourceConnection.id,
                    isCompleted: true // Signal this is a final completion
                });
            }

            // Redirect to collection detail view
            navigate(`/collections/${collectionId}`);
        } catch (error) {
            // Show an immediate error message in the UI
            setErrors({
                _general: `Connection error: ${error instanceof Error ? error.message : String(error)}`
            });

            // Mark the form as not submitting
            setSubmitting(false);

            // Don't close the dialog right away
            if (onError) {
                onError(error instanceof Error ? error : new Error(String(error)), sourceName || sourceShortName);
            }
        }
    };

    // Add or update this function
    const validateConfigFields = (): boolean => {
        const newErrors: Record<string, string> = {};
        let isValid = true;

        // Check that we have either created_collection_id or collectionId
        if (!viewData.created_collection_id && !viewData.collectionId) {
            newErrors['collection'] = 'Missing collection information';
            isValid = false;
        }

        // Validate config fields if they're present
        if (sourceDetails?.config_fields?.fields) {
            sourceDetails.config_fields.fields
                .filter((field: any) => field.required)
                .forEach((field: any) => {
                    if (!configValues[field.name] || configValues[field.name].trim() === '') {
                        newErrors[field.name] = `${field.title || field.name} is required`;
                        isValid = false;
                    }
                });
        }

        setErrors(newErrors);
        return isValid;
    };

    // Log when the component loads auth fields
    useEffect(() => {
        if (sourceDetails?.auth_fields?.fields) {
            console.log('📋 Source auth fields loaded:');
            sourceDetails.auth_fields.fields.forEach((field: any) => {
                if (field.name && !isTokenField(field.name)) {
                    console.log(`- ${field.title || field.name} (required)`);
                }
            });

            logAuthFieldsStatus();
        }
    }, [sourceDetails]);

    // Create a new handler for the authenticate button
    const handleAuthenticate = async () => {
        if (hasEmptyRequiredAuthFields()) return;

        try {
            // Strip whitespace from auth values before authentication
            const cleanedAuthValues = stripWhitespaceFromValues(authValues);

            // Create a comprehensive dialog state object with all necessary data
            const dialogState = {
                // Source information
                sourceDetails,
                sourceShortName,

                // Collection information from viewData
                ...viewData,

                // Connection name
                connectionName,

                // Current auth values (cleaned)
                authValues: cleanedAuthValues,

                // UI state
                configureStep: step,
                dialogFlowStep: viewData.dialogFlowStep || 1,
                validationAttempted,

                // Location information
                originPath: window.location.pathname,

                // Additional context needed to restore dialog
                dialogMode: viewData.dialogMode || 'source-button',

                // Add timestamp for freshness checking
                timestamp: Date.now()
            };

            console.log("📊 FULL DIALOG STATE BEFORE OAUTH:", JSON.stringify(dialogState, null, 2));

            // Check if this is an OAuth flow
            const isOAuthFlow = sourceDetails.auth_type &&
                sourceDetails.auth_type.startsWith('oauth2');

            // Pass navigate to authenticateSource
            const result = await authenticateSource(dialogState, navigate);

            // Only set authenticated state for non-OAuth flows or if we got a credentialId
            if (result.success) {
                if (result.credentialId) {
                    // Store the credential ID in local state
                    setCredentialId(result.credentialId);

                    // For non-OAuth flows, we update the auth state through onNext
                    onNext?.({
                        credentialId: result.credentialId,
                        isAuthenticated: true
                    });

                    // Only set authenticated for non-OAuth flows or when we have a credentialId
                    if (!isOAuthFlow || result.credentialId) {
                        setIsAuthenticated(true);
                        setValidationAttempted(true);
                        validateAuthFields();
                    }
                }
            }
        } catch (error) {
            console.error("Authentication error:", error);
            handleError(error instanceof Error ? error : new Error(String(error)), "Authentication error");
        }
    };

    // Reset authentication state when auth values change, but not for OAuth credentials
    useEffect(() => {
        // Only reset if we're not using an OAuth credential
        if (isAuthenticated && !viewData.credentialId) {
            setIsAuthenticated(false);
        }
    }, [authValues, viewData.credentialId]);

    // Replace the useEffect for handling credentials
    useEffect(() => {
        // Check if we have credential information from restored dialog state
        if (viewData && viewData.credentialId) {
            console.log("🔍 FULL VIEW DATA IN CONFIGURE SOURCE:", JSON.stringify(viewData, null, 2));
            console.log("🔑 Setting authenticated state with credential:", viewData.credentialId);
            setIsAuthenticated(true);

            // If we have saved auth values, restore them completely
            if (viewData.authValues) {
                setAuthValues(prevValues => ({
                    ...prevValues,
                    ...viewData.authValues,
                    credential_id: viewData.credentialId
                }));
            } else {
                // Just add the credential_id
                setAuthValues(prev => ({
                    ...prev,
                    credential_id: viewData.credentialId
                }));
            }

            // Ensure validation is complete
            setValidationAttempted(true);
        }
    }, [viewData]);

    // Add to useEffect for initialization
    useEffect(() => {
        // Set the step based on viewData if available
        if (viewData && viewData.configureStep) {
            setStep(viewData.configureStep);
        }
    }, [viewData]);

    // Update when sourceName changes to set default - modify around line 330
    useEffect(() => {
        // Only update if viewData.connectionName changes
        if (viewData.connectionName) {
            console.log("📝 Restoring saved connection name:", viewData.connectionName);
            setConnectionName(viewData.connectionName);
        }
    }, [viewData.connectionName]);

    // Add this helper function after the other helper functions (around line 260)
    const hasAuthFieldErrors = (): boolean => {
        if (!sourceDetails?.auth_fields?.fields) return false;

        return sourceDetails.auth_fields.fields
            .filter(field => field.name && !isTokenField(field.name))
            .some(field => errors[field.name]);
    };

    // Render the auth fields step
    const renderAuthStep = () => {
        // Check if there are any visible auth fields
        const hasVisibleAuthFields = sourceDetails?.auth_fields?.fields &&
            sourceDetails.auth_fields.fields.some((field: any) =>
                field.name && !isTokenField(field.name)
            );

        return (
            <div className="space-y-6">
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <DialogTitle className="text-2xl font-semibold text-left">
                            Authenticate Source Connection
                        </DialogTitle>

                        {/* Authentication class and OAuth2 indicators */}
                        <div className="flex items-center gap-2 mt-2">
                            {sourceDetails?.auth_config_class && (
                                <span className="text-xs text-muted-foreground bg-muted-foreground/20 px-2 py-1 rounded">
                                    {sourceDetails.auth_config_class}
                                </span>
                            )}
                            {sourceDetails?.auth_type && sourceDetails.auth_type.startsWith('oauth2') && (
                                <span className="text-xs text-blue-600 bg-blue-100 dark:text-blue-400 dark:bg-blue-950 px-2 py-1 rounded">
                                    OAuth2
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Source image on the right with margin */}
                    {sourceShortName && (
                        <div className="mr-4">
                            <div className={cn(
                                "w-16 h-16 flex items-center justify-center border border-black rounded-lg",
                                isDark ? "border-gray-700" : "border-gray-800"
                            )}>
                                <img
                                    src={getAppIconUrl(sourceShortName, resolvedTheme)}
                                    alt={`${sourceName} icon`}
                                    className="w-full h-full object-contain p-2"
                                    onError={(e) => {
                                        e.currentTarget.style.display = 'none';
                                        e.currentTarget.parentElement!.innerHTML = `
                        <div class="w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'}">
                            <span class="text-2xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}">
                            ${sourceShortName?.substring(0, 2).toUpperCase()}
                            </span>
                        </div>
                        `;
                                    }}
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* Validation error message if validation has been attempted */}
                {validationAttempted && hasAuthFieldErrors() && (
                    <div className="mb-4 p-3 bg-red-500/10 rounded border border-red-500/20">
                        <p className="text-sm text-red-600">
                            <span className="font-medium">Error:</span> Please fill in all fields before proceeding.
                        </p>
                    </div>
                )}

                {/* All form fields in one container */}
                <div className="bg-muted p-6 rounded-lg mb-4">
                    {/* Connection Name field */}
                    <div className="space-y-2 mb-4">
                        <label className="text-base font-medium">
                            Name
                        </label>

                        <p className="text-xs text-muted-foreground mb-2">
                            Enter a descriptive name to identify the source connection in your collection.
                        </p>

                        <input
                            type="text"
                            className={cn(
                                "w-full p-2 rounded border",
                                isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300"
                            )}
                            placeholder="Enter a name for this connection"
                            value={connectionName}
                            onChange={(e) => setConnectionName(e.target.value)}
                        />
                    </div>
                </div>

                {/* External Auth Provider Toggle - Separate Section */}
                {!SOURCES_BLOCKED_FROM_AUTH_PROVIDERS.includes(sourceShortName) && (
                    <div className="bg-muted p-6 rounded-lg mb-4">
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                    <label htmlFor="use-external-auth" className="text-base font-medium">
                                        Use external auth provider to get credentials
                                    </label>
                                    <p className="text-xs text-muted-foreground">
                                        Skip authentication and get credentials for this source from a third-party authentication service.
                                    </p>
                                </div>
                                <Switch
                                    id="use-external-auth"
                                    checked={useExternalAuthProvider}
                                    onCheckedChange={(checked) => {
                                        setUseExternalAuthProvider(checked);
                                        // Reset auth provider state when toggled off
                                        if (!checked) {
                                            setSelectedAuthProviderConnection(null);
                                            setAuthProviderDetails(null);
                                            setAuthProviderConfigValues({});
                                        }
                                    }}
                                    className={cn(
                                        "border-2",
                                        isDark ? "border-gray-600" : "border-gray-300"
                                    )}
                                />
                            </div>

                            {/* Show auth provider connections when toggle is on */}
                            {useExternalAuthProvider && (
                                <div className="space-y-3 mt-4">
                                    {isLoadingConnections ? (
                                        <div className="flex justify-center py-4">
                                            <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                                        </div>
                                    ) : authProviderConnections.length > 0 ? (
                                        <>
                                            <p className="text-sm text-muted-foreground mb-2">
                                                Select a connected auth provider
                                            </p>

                                            {/* Show error if validation attempted and no provider selected */}
                                            {validationAttempted && !selectedAuthProviderConnection && (
                                                <div className="mb-2 p-2 bg-red-500/10 rounded border border-red-500/20">
                                                    <p className="text-xs text-red-600">
                                                        Please select a connected auth provider
                                                    </p>
                                                </div>
                                            )}

                                            <div className="space-y-2">
                                                {authProviderConnections.map((connection) => (
                                                    <div
                                                        key={connection.id}
                                                        className={cn(
                                                            "h-10 flex items-center gap-2 overflow-hidden px-3 py-2 rounded-md cursor-pointer transition-colors",
                                                            selectedAuthProviderConnection?.id === connection.id
                                                                ? "border-2 border-primary"
                                                                : isDark
                                                                    ? "border border-gray-700 bg-gray-800/50 hover:bg-gray-700/70"
                                                                    : "border border-gray-200 bg-white hover:bg-gray-50"
                                                        )}
                                                        onClick={() => handleAuthProviderConnectionSelect(connection)}
                                                    >
                                                        <div className="rounded-md flex items-center justify-center overflow-hidden flex-shrink-0">
                                                            <img
                                                                src={getAuthProviderIconUrl(connection.short_name, resolvedTheme)}
                                                                alt={connection.name}
                                                                className="h-6 w-6 object-contain"
                                                                onError={(e) => {
                                                                    // Fallback to initials if icon fails
                                                                    e.currentTarget.style.display = 'none';
                                                                    const colorClass = connection.short_name.charCodeAt(0) % 8;
                                                                    const colors = [
                                                                        "bg-blue-500", "bg-green-500", "bg-purple-500", "bg-orange-500",
                                                                        "bg-pink-500", "bg-indigo-500", "bg-red-500", "bg-yellow-500"
                                                                    ];
                                                                    e.currentTarget.parentElement!.classList.add(colors[colorClass]);
                                                                    e.currentTarget.parentElement!.innerHTML = `<span class="text-white font-semibold text-xs">${connection.short_name.substring(0, 2).toUpperCase()}</span>`;
                                                                }}
                                                            />
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <span className="text-sm font-medium truncate block">
                                                                {connection.name}
                                                            </span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>

                                            {/* Show config fields when an auth provider is selected */}
                                            {selectedAuthProviderConnection && (
                                                <div className="mt-4 p-4 rounded-md bg-background border border-border">
                                                    {loadingAuthProviderDetails ? (
                                                        <div className="flex items-center justify-center py-4">
                                                            <div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full mr-2"></div>
                                                            <span className="text-sm text-muted-foreground">Loading configuration...</span>
                                                        </div>
                                                    ) : authProviderDetails ? (
                                                        <>
                                                            <p className="text-sm font-medium mb-3">
                                                                Auth Provider Configuration
                                                            </p>

                                                            {/* Show the pre-filled readable_id */}
                                                            <div className="space-y-2 mb-3">
                                                                <label className="text-xs font-medium text-muted-foreground">
                                                                    Auth Provider Connection ID
                                                                </label>
                                                                <input
                                                                    type="text"
                                                                    className={cn(
                                                                        "w-full p-2 rounded border text-sm",
                                                                        isDark ? "bg-gray-800 border-gray-700" : "bg-gray-50 border-gray-300"
                                                                    )}
                                                                    value={selectedAuthProviderConnection.readable_id}
                                                                    disabled
                                                                />
                                                            </div>

                                                            {/* Show config fields if any */}
                                                            {authProviderDetails?.config_fields?.fields && authProviderDetails.config_fields.fields.length > 0 ? (
                                                                <div className="space-y-3">
                                                                    {authProviderDetails.config_fields.fields.map((field: any) => (
                                                                        <div key={field.name} className="space-y-1">
                                                                            <label className="text-xs font-medium">
                                                                                {field.title || field.name}
                                                                                {field.required && <span className="text-red-500 ml-1">*</span>}
                                                                            </label>
                                                                            {field.description && (
                                                                                <p className="text-xs text-muted-foreground">{field.description}</p>
                                                                            )}
                                                                            <input
                                                                                type="text"
                                                                                className={cn(
                                                                                    "w-full p-2 rounded border text-sm",
                                                                                    isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300",
                                                                                    validationAttempted && errors[field.name] ? "border-red-500" : ""
                                                                                )}
                                                                                placeholder={field.placeholder || ''}
                                                                                value={authProviderConfigValues[field.name] || ''}
                                                                                onChange={(e) => {
                                                                                    setAuthProviderConfigValues(prev => ({
                                                                                        ...prev,
                                                                                        [field.name]: e.target.value
                                                                                    }));

                                                                                    // Clear error for this field if any
                                                                                    if (errors[field.name]) {
                                                                                        setErrors(prev => {
                                                                                            const updated = { ...prev };
                                                                                            delete updated[field.name];
                                                                                            return updated;
                                                                                        });
                                                                                    }
                                                                                }}
                                                                            />
                                                                            {validationAttempted && errors[field.name] && (
                                                                                <p className="text-xs text-red-500 mt-1">{errors[field.name]}</p>
                                                                            )}
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            ) : (
                                                                <p className="text-xs text-muted-foreground italic">
                                                                    No additional configuration required for this auth provider.
                                                                </p>
                                                            )}
                                                        </>
                                                    ) : (
                                                        <div className="text-center py-4 text-sm text-red-500">
                                                            Failed to load configuration
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <p className="text-sm text-muted-foreground py-2">
                                            No connected auth providers found, click on the button below to set-up a new connection.
                                        </p>
                                    )}

                                    {/* Button to go to auth providers page */}
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="w-full mt-3"
                                        onClick={() => {
                                            // Navigate to auth providers page
                                            navigate('/auth-providers');
                                        }}
                                    >
                                        <ExternalLink className="h-4 w-4 mr-2" />
                                        Manage Auth Provider Connections
                                    </Button>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Auth fields section - if any */}
                {hasVisibleAuthFields && !useExternalAuthProvider && (
                    <div className="bg-muted p-6 rounded-lg mb-4">
                        {/* Render auth fields (excluding token fields) */}
                        {sourceDetails.auth_fields.fields
                            .filter((field: any) => field.name && !isTokenField(field.name))
                            .map((field: any) => (
                                <div key={field.name} className="space-y-2 mb-4">
                                    <label className="text-base font-medium">
                                        {field.title || field.name}
                                    </label>

                                    {field.description && (
                                        <p className="text-xs text-muted-foreground mb-2">{field.description}</p>
                                    )}

                                    <input
                                        type={field.type === 'password' ? 'password' : 'text'}
                                        className={cn(
                                            "w-full p-2 rounded border",
                                            isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300",
                                            validationAttempted && errors[field.name] ? "border-red-500" : ""
                                        )}
                                        placeholder={''}
                                        value={authValues[field.name] || ''}
                                        onChange={(e) => handleAuthFieldChange(field.name, e.target.value)}
                                    />

                                    {validationAttempted && errors[field.name] && (
                                        <p className="text-xs text-red-500">{errors[field.name]}</p>
                                    )}
                                </div>
                            ))}
                    </div>
                )}
            </div>
        );
    };

    // Render the config fields step
    const renderConfigStep = () => (
        <div className="space-y-6">
            <div className="flex justify-between items-start mb-6">
                <div>
                    <DialogTitle className="text-2xl font-semibold text-left">
                        Configure Source Connection
                    </DialogTitle>

                    {/* Configuration class indicators */}
                    <div className="flex items-center gap-2 mt-2">
                        {sourceDetails?.config_class && (
                            <span className="text-xs text-muted-foreground bg-muted-foreground/20 px-2 py-1 rounded">
                                {sourceDetails.config_class}
                            </span>
                        )}
                    </div>
                </div>

                {/* Source image on the right with margin */}
                {sourceShortName && (
                    <div className="mr-4">
                        <div className={cn(
                            "w-16 h-16 flex items-center justify-center border border-black rounded-lg",
                            isDark ? "border-gray-700" : "border-gray-800"
                        )}>
                            <img
                                src={getAppIconUrl(sourceShortName, resolvedTheme)}
                                alt={`${sourceName} icon`}
                                className="w-full h-full object-contain p-2"
                                onError={(e) => {
                                    e.currentTarget.style.display = 'none';
                                    e.currentTarget.parentElement!.innerHTML = `
                    <div class="w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'}">
                        <span class="text-2xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}">
                        ${sourceShortName?.substring(0, 2).toUpperCase()}
                        </span>
                    </div>
                    `;
                                }}
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* Config fields section */}
            <div className="bg-muted p-6 rounded-lg mb-4">
                {sourceDetails?.config_fields?.fields && sourceDetails.config_fields.fields.length > 0 ? (
                    <div className="space-y-4">
                        {sourceDetails.config_fields.fields.map((field: any) => (
                            <div key={field.name} className="space-y-2 mb-4">
                                <label className="text-base font-medium">
                                    {field.title || field.name}
                                    {field.required && <span className="text-red-500 ml-1">*</span>}
                                </label>

                                {field.description && (
                                    <p className="text-xs text-muted-foreground mb-2">{field.description}</p>
                                )}

                                {field.type === 'boolean' ? (
                                    <div className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            id={field.name}
                                            className={cn(
                                                "h-4 w-4 rounded border",
                                                isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300",
                                                errors[field.name] ? "border-red-500" : ""
                                            )}
                                            checked={configValues[field.name] === true || configValues[field.name] === 'true'}
                                            onChange={(e) => handleConfigFieldChange(field.name, e.target.checked)}
                                        />
                                        <label htmlFor={field.name} className="text-sm">
                                            {field.title || field.name}
                                        </label>
                                    </div>
                                ) : (
                                    <input
                                        type="text"
                                        className={cn(
                                            "w-full p-2 rounded border",
                                            isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300",
                                            errors[field.name] ? "border-red-500" : ""
                                        )}
                                        placeholder={''}
                                        value={configValues[field.name] || ''}
                                        onChange={(e) => handleConfigFieldChange(field.name, e.target.value)}
                                    />
                                )}

                                {errors[field.name] && (
                                    <p className="text-xs text-red-500">{errors[field.name]}</p>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="py-4 text-sm text-muted-foreground italic">
                        No configuration fields required for this source.
                    </div>
                )}
            </div>
        </div>
    );

    return (
        <div className="flex flex-col h-full">
            {/* Content area - scrollable */}
            <div className="flex-grow overflow-y-auto">
                <div className="p-8 h-full flex flex-col">
                    {loading ? (
                        <div className="flex justify-center items-center py-8">
                            <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
                        </div>
                    ) : sourceDetails ? (
                        step === 'auth' ? renderAuthStep() : renderConfigStep()
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No source configuration available
                        </div>
                    )}
                </div>
            </div>

            {/* Authentication button section - fixed above footer */}
            {step === 'auth' && sourceDetails && !useExternalAuthProvider && (
                <div className="flex-shrink-0 px-6 py-4 border-t">
                    {!isAuthenticated && (
                        <p className="text-sm text-center text-muted-foreground mb-3">
                            You must authenticate before you can connect to the source.
                        </p>
                    )}
                    <Button
                        onClick={handleAuthenticate}
                        disabled={loading || hasEmptyRequiredAuthFields() || isAuthenticated}
                        className={cn(
                            "w-full py-3 text-white",
                            isAuthenticated
                                ? "bg-green-600 opacity-100 pointer-events-none"
                                : "bg-blue-600 hover:bg-blue-700",
                            isAuthenticated ? "disabled:opacity-100 disabled:bg-green-600" : ""
                        )}
                    >
                        {isAuthenticated ? "✓ Authenticated" : "Authenticate"}
                    </Button>
                </div>
            )}

            {/* Footer - fixed at bottom */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="flex justify-end gap-3 p-6">
                    {step === 'auth' && onBack && (
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onBack}
                            className={cn("px-6", isDark ? "border-gray-700" : "border-gray-300")}
                        >
                            Back
                        </Button>
                    )}

                    {step === 'config' && (
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setStep('auth')}
                            className={cn("px-6", isDark ? "border-gray-700" : "border-gray-300")}
                        >
                            Back
                        </Button>
                    )}

                    <Button
                        type="button"
                        variant="outline"
                        onClick={onCancel}
                        className={cn("px-6", isDark ? "border-gray-700" : "border-gray-300")}
                    >
                        Cancel
                    </Button>

                    {step === 'auth' ? (
                        (() => {
                            const isDisabled = loading ||
                                (!useExternalAuthProvider && !isAuthenticated) ||
                                (useExternalAuthProvider && (!selectedAuthProviderConnection || loadingAuthProviderDetails || hasEmptyRequiredAuthProviderConfigFields()));

                            console.log('🔘 [Connect Button] Disabled state evaluation:', {
                                loading,
                                useExternalAuthProvider,
                                isAuthenticated,
                                selectedAuthProviderConnection: !!selectedAuthProviderConnection,
                                loadingAuthProviderDetails,
                                hasEmptyRequiredFields: hasEmptyRequiredAuthProviderConfigFields(),
                                finalDisabled: isDisabled
                            });

                            return (
                                <Button
                                    type="button"
                                    onClick={handleNextStep}
                                    className="px-6 bg-blue-600 hover:bg-blue-700 text-white"
                                    disabled={isDisabled}
                                >
                                    {hasConfigFields() ? 'Next' : 'Connect'}
                                </Button>
                            );
                        })()
                    ) : (
                        <Button
                            type="button"
                            onClick={handleComplete}
                            className="px-6 bg-blue-600 hover:bg-blue-700 text-white"
                            disabled={loading || submitting}
                        >
                            {submitting ? 'Connecting...' : 'Connect'}
                        </Button>
                    )}
                </DialogFooter>
            </div>
        </div>
    );
};

export default ConfigureSourceView;
