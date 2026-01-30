import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { authenticateSource } from "@/lib/authenticate";
import { getAppIconUrl } from "@/lib/utils/icons";
import { toast } from "sonner";
import { safeLogAuthValues, safeLogDialogState } from "@/lib/auth-utils";

export interface MinimalConfigureSourceViewProps {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    viewData?: Record<string, any>;
    onError?: (error: Error | string, errorSource?: string) => void;
}

export const MinimalConfigureSourceView: React.FC<MinimalConfigureSourceViewProps> = ({
    onNext,
    onCancel,
    onComplete,
    viewData = {},
    onError,
}) => {
    console.log('🔧 [MinimalConfigureSourceView] Component rendering with props:', { viewData });

    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [sourceDetails, setSourceDetails] = useState<any>(null);
    const [authValues, setAuthValues] = useState<Record<string, any>>({});
    const [configValues, setConfigValues] = useState<Record<string, any>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});
    const [submitting, setSubmitting] = useState(false);
    const [isAuthenticated, setIsAuthenticated] = useState(false);

    const { sourceName, sourceShortName, sourceId } = viewData;
    console.log('🔧 [MinimalConfigureSourceView] Extracted props:', { sourceName, sourceShortName, sourceId });

    // Helper to check if field should be skipped
    const isTokenField = (fieldName: string): boolean => {
        const lowerName = fieldName.toLowerCase();
        return lowerName === 'refresh_token' || lowerName === 'access_token';
    };

    // Add effect to reset ALL state when sourceShortName changes
    useEffect(() => {
        // Skip if sourceShortName is undefined (might be during restoration)
        if (!sourceShortName) {
            console.log('🔧 [MinimalConfigureSourceView] No sourceShortName, skipping state reset');
            return;
        }

        console.log('🔧 [MinimalConfigureSourceView] Source changed, resetting all state:', sourceShortName);

        // Reset all component state to initial values
        setSourceDetails(null);
        setAuthValues({});
        setConfigValues({});
        setErrors({});
        setIsAuthenticated(false);
        setSubmitting(false);
        setLoading(false);
    }, [sourceShortName]);

    // Check if we're returning from OAuth with credentials
    useEffect(() => {
        console.log('🔧 [MinimalConfigureSourceView] OAuth restoration effect running');
        console.log('🔧 [MinimalConfigureSourceView] ViewData check:', {
            hasCredentialId: !!viewData?.credentialId,
            hasIsAuthenticated: !!viewData?.isAuthenticated,
            viewDataSourceShortName: viewData?.sourceShortName,
            currentSourceShortName: sourceShortName
        });

        // ONLY restore auth state if returning from OAuth AND it's for the same source
        if (viewData?.credentialId && viewData?.isAuthenticated &&
            viewData?.sourceShortName === sourceShortName) {
            console.log("🔑 [MinimalConfigureSourceView] Restoring authenticated state with credential:", viewData.credentialId);
            setIsAuthenticated(true);

            // Restore any saved auth values ONLY if they match the current source
            if (viewData.authValues) {
                safeLogAuthValues(viewData.authValues, '🔑 [MinimalConfigureSourceView] Restoring');
                setAuthValues(viewData.authValues);
            }
        }
    }, [viewData?.credentialId, viewData?.isAuthenticated, viewData?.sourceShortName, sourceShortName]);

    // Generate auto collection name/id
    const generateCollectionInfo = () => {
        const timestamp = Date.now().toString(36);
        const shortRandom = Math.random().toString(36).substring(2, 6);
        const collectionInfo = {
            name: `${sourceName} Collection`,
            readable_id: `${sourceShortName}-${timestamp}-${shortRandom}`
        };
        console.log('🔧 [MinimalConfigureSourceView] Generated collection info:', collectionInfo);
        return collectionInfo;
    };

    // Fetch source details
    useEffect(() => {
        console.log('🔧 [MinimalConfigureSourceView] Source details effect running for:', sourceShortName);

        if (!sourceShortName) {
            console.log('🔧 [MinimalConfigureSourceView] No sourceShortName, returning early');
            return;
        }

        const fetchSourceDetails = async () => {
            console.log('🔧 [MinimalConfigureSourceView] Fetching source details for:', sourceShortName);
            setLoading(true);
            try {
                const response = await apiClient.get(`/sources/${sourceShortName}`);

                if (response.ok) {
                    const data = await response.json();
                    console.log('🔧 [MinimalConfigureSourceView] Source details received:', data);
                    setSourceDetails(data);

                    // Initialize auth values
                    if (data.auth_fields?.fields) {
                        const initialAuthValues: Record<string, any> = {};
                        data.auth_fields.fields.forEach((field: any) => {
                            if (field.name && !isTokenField(field.name)) {
                                initialAuthValues[field.name] = '';
                            }
                        });
                        safeLogAuthValues(initialAuthValues, '🔧 [MinimalConfigureSourceView] Initialized');
                        setAuthValues(initialAuthValues);
                    }

                    // Initialize config values
                    if (data.config_fields?.fields) {
                        const initialConfigValues: Record<string, any> = {};
                        data.config_fields.fields.forEach((field: any) => {
                            if (field.name) {
                                initialConfigValues[field.name] = '';
                            }
                        });
                        console.log('🔧 [MinimalConfigureSourceView] Initialized config values:', initialConfigValues);
                        setConfigValues(initialConfigValues);
                    }
                } else {
                    throw new Error("Failed to load source details");
                }
            } catch (error) {
                console.error("🔧 [MinimalConfigureSourceView] Error fetching source details:", error);
                if (onError) onError(error instanceof Error ? error : new Error(String(error)), "Source details error");
            } finally {
                setLoading(false);
            }
        };

        fetchSourceDetails();
    }, [sourceShortName, onError]);

    // Check if has required config fields
    const hasRequiredConfigFields = (): boolean => {
        const result = sourceDetails?.config_fields?.fields?.some((field: any) => field.required) || false;
        console.log('🔧 [MinimalConfigureSourceView] Has required config fields:', result);
        return result;
    };

    // Check if has empty required auth fields
    const hasEmptyRequiredAuthFields = (): boolean => {
        if (!sourceDetails?.auth_fields?.fields) return false;

        return sourceDetails.auth_fields.fields
            .filter(field => field.name && !isTokenField(field.name))
            .some(field => !authValues[field.name] || authValues[field.name].trim() === '');
    };

    // Handle authentication - updated to handle OAuth redirect flow for semantic-mcp
    const handleAuthenticate = async () => {
        console.log('🔧 [MinimalConfigureSourceView] handleAuthenticate called');

        if (hasEmptyRequiredAuthFields()) {
            console.log('🔧 [MinimalConfigureSourceView] Auth validation failed, not proceeding');
            return;
        }

        try {
            const collectionInfo = generateCollectionInfo();

            const dialogState = {
                sourceDetails,
                sourceShortName,
                authValues,
                ...viewData,
                ...collectionInfo,
                created_collection_name: collectionInfo.name,
                created_collection_id: collectionInfo.readable_id,
                connectionName: `${sourceName} Connection`,
                isSemanticMcp: true, // Flag for semantic-mcp mode
                originPath: '/semantic-mcp', // Return path
                dialogId: viewData.dialogId || 'semantic-mcp-dialog', // Ensure dialogId is preserved
                dialogMode: 'semantic-mcp' // Ensure mode is preserved
            };

            safeLogDialogState(dialogState, '🔧 [MinimalConfigureSourceView]');

            // Check if this is an OAuth flow
            const isOAuthFlow = sourceDetails.auth_type && sourceDetails.auth_type.startsWith('oauth2');

            // For semantic-mcp, we pass null for navigate to handle errors locally
            const result = await authenticateSource(dialogState, null);
            console.log('🔧 [MinimalConfigureSourceView] Authentication result:', result);

            if (result.success) {
                if (result.credentialId) {
                    // For non-OAuth flows, we update the auth state through onNext
                    onNext?.({
                        credentialId: result.credentialId,
                        isAuthenticated: true,
                        ...collectionInfo
                    });

                    // Set authenticated for non-OAuth flows or when we have a credentialId
                    if (!isOAuthFlow || result.credentialId) {
                        setIsAuthenticated(true);
                    }
                } else if (!isOAuthFlow) {
                    // For non-OAuth without credentialId but success, still mark as authenticated
                    setIsAuthenticated(true);
                }
                // Note: For OAuth flows, the page will redirect and state will be restored when returning
            }
        } catch (error) {
            console.error("🔧 [MinimalConfigureSourceView] Authentication error:", error);

            // For semantic-mcp, use onError to show error dialog instead of redirecting
            if (onError) {
                let errorMessage = error instanceof Error ? error.message : String(error);
                const errorDetails = error instanceof Error ? error.stack : undefined;

                // Parse JSON error messages for better display
                if (errorMessage.includes('{"detail"')) {
                    try {
                        const jsonStart = errorMessage.indexOf('{"detail"');
                        const jsonEnd = errorMessage.lastIndexOf('}') + 1;
                        if (jsonStart > -1 && jsonEnd > jsonStart) {
                            const jsonStr = errorMessage.substring(jsonStart, jsonEnd);
                            const parsed = JSON.parse(jsonStr);
                            if (parsed.detail) {
                                errorMessage = parsed.detail;
                            }
                        }
                    } catch (e) {
                        console.error("Error parsing JSON from error message:", e);
                    }
                }

                onError(errorMessage, sourceName || sourceShortName);
            }
        }
    };

    // Reset authentication state when auth values change, but not for OAuth credentials
    useEffect(() => {
        // Only reset if we're not using an OAuth credential
        if (isAuthenticated && !viewData.credentialId) {
            setIsAuthenticated(false);
        }
    }, [authValues, viewData.credentialId]);

    // Handle completion
    const handleComplete = async () => {
        console.log('🔧 [MinimalConfigureSourceView] handleComplete called');

        // Validate config fields if any
        if (hasRequiredConfigFields()) {
            console.log('🔧 [MinimalConfigureSourceView] Validating config fields');
            const configErrors: Record<string, string> = {};
            let configValid = true;

            sourceDetails.config_fields.fields
                .filter((field: any) => field.required)
                .forEach((field: any) => {
                    if (!configValues[field.name]?.trim()) {
                        console.log('🔧 [MinimalConfigureSourceView] Config field validation failed:', field.name);
                        configErrors[field.name] = "Required";
                        configValid = false;
                    }
                });

            if (!configValid) {
                console.log('🔧 [MinimalConfigureSourceView] Config validation failed, not proceeding');
                setErrors(configErrors);
                return;
            }
        }

        setSubmitting(true);
        try {
            // Create collection
            const collectionInfo = viewData.created_collection_id ?
                { name: viewData.created_collection_name, readable_id: viewData.created_collection_id } :
                generateCollectionInfo();

            console.log('🔧 [MinimalConfigureSourceView] Creating collection:', collectionInfo);
            const collectionResponse = await apiClient.post('/collections', collectionInfo);
            if (!collectionResponse.ok) {
                throw new Error("Failed to create collection");
            }
            const collection = await collectionResponse.json();
            console.log('🔧 [MinimalConfigureSourceView] Collection created:', collection);

            // Create source connection
            const sourceConnectionData = {
                name: `${sourceName} Connection`,
                short_name: sourceShortName,
                collection: collection.readable_id,
                credential_id: viewData.credentialId,
                config_fields: configValues,
                sync_immediately: false // Don't start sync for semantic-mcp
            };

            console.log('🔧 [MinimalConfigureSourceView] Creating source connection:', sourceConnectionData);
            const connectionResponse = await apiClient.post('/source-connections/', sourceConnectionData);
            if (!connectionResponse.ok) {
                throw new Error("Failed to create connection");
            }

            const connectionResult = await connectionResponse.json();
            console.log('🔧 [MinimalConfigureSourceView] Source connection created:', connectionResult);

            // Success!
            toast.success(`Connected to ${sourceName}!`);

            const completionResult = {
                success: true,
                collectionId: collection.readable_id,
                sourceId: viewData.sourceId,
                isCompleted: true
            };
            console.log('🔧 [MinimalConfigureSourceView] Calling onComplete with result:', completionResult);

            if (onComplete) {
                onComplete(completionResult);
            }

            // Don't navigate away - let the parent handle what to do
        } catch (error) {
            console.error("🔧 [MinimalConfigureSourceView] Connection error:", error);
            if (onError) onError(error instanceof Error ? error : new Error(String(error)), "Connection error");
        } finally {
            setSubmitting(false);
        }
    };

    // Check if can proceed
    const canProceed = isAuthenticated && (
        !hasRequiredConfigFields() ||
        sourceDetails?.config_fields?.fields?.filter(f => f.required).every(f => configValues[f.name]?.trim())
    );

    console.log('🔧 [MinimalConfigureSourceView] Can proceed check:', {
        isAuthenticated,
        hasRequiredConfigFields: hasRequiredConfigFields(),
        canProceed
    });

    // Log state changes
    useEffect(() => {
        safeLogAuthValues(authValues, '🔧 [MinimalConfigureSourceView] Auth values changed:');
    }, [authValues]);

    useEffect(() => {
        console.log('🔧 [MinimalConfigureSourceView] Config values changed:', configValues);
    }, [configValues]);

    useEffect(() => {
        console.log('🔧 [MinimalConfigureSourceView] Authenticated state changed:', isAuthenticated);
    }, [isAuthenticated]);

    useEffect(() => {
        console.log('🔧 [MinimalConfigureSourceView] Errors changed:', errors);
    }, [errors]);

    if (loading) {
        return (
            <div className="flex justify-center items-center h-full">
                <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    // Show loading if we don't have source information yet (might be during restoration)
    if (!sourceName || !sourceShortName) {
        console.log('🔧 [MinimalConfigureSourceView] Missing source information, showing loading');
        return (
            <div className="flex justify-center items-center h-full">
                <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            <div className="flex-grow overflow-y-auto">
                <div className="p-6">
                    {/* Header */}
                    <div className="flex justify-between items-center mb-4">
                        <DialogTitle className="text-xl font-semibold">
                            Connect to {sourceName}
                        </DialogTitle>
                        {sourceShortName && (
                            <img
                                src={getAppIconUrl(sourceShortName, resolvedTheme)}
                                alt={sourceName}
                                className="w-10 h-10 object-contain"
                            />
                        )}
                    </div>

                    {/* Auth Fields */}
                    {sourceDetails?.auth_fields?.fields?.filter(f => !isTokenField(f.name)).length > 0 && (
                        <div className="space-y-3 mb-4">
                            {sourceDetails.auth_fields.fields
                                .filter(field => field.name && !isTokenField(field.name))
                                .map((field: any) => (
                                    <div key={field.name}>
                                        <label className="text-sm font-medium block mb-1">
                                            {field.title || field.name}
                                        </label>
                                        <input
                                            type={field.type === 'password' ? 'password' : 'text'}
                                            className={cn(
                                                "w-full p-2 rounded border",
                                                isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300",
                                                errors[field.name] ? "border-red-500" : ""
                                            )}
                                            value={authValues[field.name] || ''}
                                            onChange={(e) => {
                                                setAuthValues(prev => ({ ...prev, [field.name]: e.target.value }));
                                                if (errors[field.name]) {
                                                    setErrors(prev => {
                                                        const updated = { ...prev };
                                                        delete updated[field.name];
                                                        return updated;
                                                    });
                                                }
                                            }}
                                            disabled={isAuthenticated}
                                        />
                                        {errors[field.name] && (
                                            <p className="text-xs text-red-500 mt-1">{errors[field.name]}</p>
                                        )}
                                    </div>
                                ))}
                        </div>
                    )}

                    {/* Authenticate Button - Updated to match ConfigureSourceView */}
                    <Button
                        onClick={handleAuthenticate}
                        disabled={loading || hasEmptyRequiredAuthFields() || isAuthenticated}
                        className={cn(
                            "w-full mb-4 text-white",
                            isAuthenticated
                                ? "bg-green-600 opacity-100 pointer-events-none"
                                : "bg-blue-600 hover:bg-blue-700",
                            isAuthenticated ? "disabled:opacity-100 disabled:bg-green-600" : ""
                        )}
                    >
                        {isAuthenticated ? "✓ Authenticated" : "Authenticate"}
                    </Button>

                    {/* Config Fields (only show after auth) */}
                    {isAuthenticated && hasRequiredConfigFields() && (
                        <div className="space-y-3">
                            <h3 className="text-base font-medium">Configuration</h3>
                            {sourceDetails.config_fields.fields
                                .filter((field: any) => field.required)
                                .map((field: any) => (
                                    <div key={field.name}>
                                        <label className="text-sm font-medium block mb-1">
                                            {field.title || field.name}
                                        </label>
                                        <input
                                            type="text"
                                            className={cn(
                                                "w-full p-2 rounded border",
                                                isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300",
                                                errors[field.name] ? "border-red-500" : ""
                                            )}
                                            value={configValues[field.name] || ''}
                                            onChange={(e) => {
                                                setConfigValues(prev => ({ ...prev, [field.name]: e.target.value }));
                                                if (errors[field.name]) {
                                                    setErrors(prev => {
                                                        const updated = { ...prev };
                                                        delete updated[field.name];
                                                        return updated;
                                                    });
                                                }
                                            }}
                                        />
                                        {errors[field.name] && (
                                            <p className="text-xs text-red-500 mt-1">{errors[field.name]}</p>
                                        )}
                                    </div>
                                ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Footer */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="flex justify-end gap-3 p-4">
                    <Button variant="outline" onClick={onCancel}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleComplete}
                        disabled={!canProceed || submitting}
                        className="bg-blue-600 hover:bg-blue-700 text-white"
                    >
                        {submitting ? 'Connecting...' : 'Connect'}
                    </Button>
                </DialogFooter>
            </div>
        </div>
    );
};

export default MinimalConfigureSourceView;
