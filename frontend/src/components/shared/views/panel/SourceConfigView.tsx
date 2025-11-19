import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { getAppIconUrl } from "@/lib/utils/icons";
import { Switch } from "@/components/ui/switch";
import { TagInput } from "@/components/ui/tag-input";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";
import { ExternalLink, Loader2 } from "lucide-react";
import { useSidePanelStore } from "@/lib/stores/sidePanelStore";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

interface SourceConfigViewProps {
    context: {
        collectionId?: string;
        collectionName?: string;
        sourceId?: string;
        sourceName?: string;
        sourceShortName?: string;
    };
}

// NOTE: This component adapts the logic from the original ConfigureSourceView
// It's designed to work within the new side panel flow.

export const SourceConfigView: React.FC<SourceConfigViewProps> = ({ context }) => {
    const { collectionId, sourceName, sourceShortName } = context;
    const { setView } = useSidePanelStore.getState();
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const navigate = useNavigate();

    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [sourceDetails, setSourceDetails] = useState<any>(null);
    const [authValues, setAuthValues] = useState<Record<string, any>>({});
    const [configValues, setConfigValues] = useState<Record<string, any>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});

    // External Auth Provider State
    const [useExternalAuthProvider, setUseExternalAuthProvider] = useState(false);
    const [selectedAuthProviderConnection, setSelectedAuthProviderConnection] = useState<any>(null);
    const [authProviderDetails, setAuthProviderDetails] = useState<any>(null);
    const [authProviderConfigValues, setAuthProviderConfigValues] = useState<Record<string, any>>({});
    const [loadingAuthProviderDetails, setLoadingAuthProviderDetails] = useState(false);

    const { authProviderConnections, isLoadingConnections, fetchAuthProviderConnections } = useAuthProvidersStore();


    const isTokenField = (fieldName: string): boolean => {
        const lowerName = fieldName.toLowerCase();
        return lowerName === 'refresh_token' || lowerName === 'access_token';
    };

    useEffect(() => {
        if (!sourceShortName) return;

        const fetchSourceDetails = async () => {
            setLoading(true);
            try {
                const response = await apiClient.get(`/sources/${sourceShortName}`);
                if (response.ok) {
                    const data = await response.json();
                    setSourceDetails(data);

                    if (data.auth_fields?.fields) {
                        const initialAuth: Record<string, any> = {};
                        data.auth_fields.fields.forEach((field: any) => {
                            if (field.name && !isTokenField(field.name)) {
                                initialAuth[field.name] = '';
                            }
                        });
                        setAuthValues(initialAuth);
                    }
                    if (data.config_fields?.fields) {
                        const initialConfig: Record<string, any> = {};
                        data.config_fields.fields.forEach((field: any) => {
                            if (field.name) initialConfig[field.name] = '';
                        });
                        setConfigValues(initialConfig);
                    }
                } else {
                    throw new Error(await response.text());
                }
            } catch (error) {
                toast.error("Failed to load source details.");
                console.error(error);
            } finally {
                setLoading(false);
            }
        };

        fetchSourceDetails();
        fetchAuthProviderConnections();
    }, [sourceShortName, fetchAuthProviderConnections]);

    const handleFieldChange = (setter: React.Dispatch<React.SetStateAction<any>>) => (key: string, value: string) => {
        setter(prev => ({ ...prev, [key]: value }));
        if (errors[key]) {
            setErrors(prev => {
                const newErrors = { ...prev };
                delete newErrors[key];
                return newErrors;
            });
        }
    };

    const handleInitiateConnection = async () => {
        setSubmitting(true);

        // Base payload
        const payload: any = {
            name: `${sourceName} Connection`,
            short_name: sourceShortName,
            collection: collectionId,
            config_fields: Object.fromEntries(Object.entries(configValues).filter(([_, v]) => v !== '')),
            sync_immediately: true,
        };

        // Determine auth_mode and construct payload accordingly
        if (useExternalAuthProvider) {
            payload.auth_mode = 'external_provider';
            payload.auth_provider = selectedAuthProviderConnection.readable_id;
            payload.auth_provider_config = authProviderConfigValues;
        } else if (sourceDetails?.auth_type?.startsWith('oauth2')) {
            payload.auth_mode = 'oauth2';
            // ** FIX STARTS HERE **
            // Spread the authValues (containing client_id, etc.) into the top-level payload
            Object.assign(payload, authValues);
            // ** FIX ENDS HERE **
            payload.redirect_url = window.location.origin + window.location.pathname;
        } else {
            payload.auth_mode = 'direct_auth';
            payload.auth_fields = authValues;
        }

        try {
            const response = await apiClient.post('/source-connections/initiate', payload);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to initiate connection');
            }

            const result = await response.json();

            if (result.status === 'created') {
                useSidePanelStore.getState().closePanel();
                // We need to trigger a refresh of the source connections on the collection page
                // This is now handled in the Collections.tsx component's useEffect
            } else if (result.status === 'pending' && result.authentication?.authentication_url) {
                // Transition panel to show the redirect URL
                setView('oauthRedirect', {
                    authenticationUrl: result.authentication.authentication_url,
                    sourceName: sourceName
                });
            }

        } catch (error) {
            console.error("Connection initiation failed:", error);
            toast.error(error instanceof Error ? error.message : "An unknown error occurred.");
        } finally {
            setSubmitting(false);
        }
    };


    if (loading) {
        return <div className="flex justify-center items-center h-full"><Loader2 className="h-8 w-8 animate-spin" /></div>;
    }

    return (
        <div className="p-6">
            <div className="space-y-6">
                {/* Auth Fields */}
                {!useExternalAuthProvider && sourceDetails?.auth_fields?.fields?.filter((f: any) => !isTokenField(f.name)).length > 0 && (
                    <div className="space-y-4 p-4 border rounded-md">
                        <h3 className="font-semibold">Authentication</h3>
                        {sourceDetails.auth_fields.fields.filter((f: any) => !isTokenField(f.name)).map((field: any) => (
                            <div key={field.name}>
                                <label className="text-sm font-medium">{field.title || field.name}</label>
                                {field.description && <p className="text-xs text-muted-foreground">{field.description}</p>}
                                <input
                                    type={field.secret ? "password" : "text"}
                                    value={authValues[field.name] || ''}
                                    onChange={(e) => handleFieldChange(setAuthValues)(field.name, e.target.value)}
                                    className={cn("w-full p-2 mt-1 rounded border", isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300")}
                                />
                            </div>
                        ))}
                    </div>
                )}

                {/* Config Fields */}
                {sourceDetails?.config_fields?.fields?.length > 0 && (
                    <div className="space-y-4 p-4 border rounded-md">
                        <h3 className="font-semibold">Configuration</h3>
                        {sourceDetails.config_fields.fields.map((field: any) => (
                            <div key={field.name}>
                                <label className="text-sm font-medium">{field.title || field.name}</label>
                                {field.description && <p className="text-xs text-muted-foreground">{field.description}</p>}
                                {field.type === 'array' ? (
                                    <TagInput
                                        value={(Array.isArray(configValues[field.name]) ? configValues[field.name] : []) as string[]}
                                        onChange={(tags) => {
                                            const newValues = { ...configValues, [field.name]: tags };
                                            setConfigValues(newValues);
                                        }}
                                        placeholder={`Enter ${field.title?.toLowerCase() || field.name} and press Enter...`}
                                        transformInput={sourceDetails?.short_name === 'jira' && field.name === 'project_keys' ? (v) => v.toUpperCase() : undefined}
                                    />
                                ) : (
                                    <input
                                        type="text"
                                        value={configValues[field.name] || ''}
                                        onChange={(e) => handleFieldChange(setConfigValues)(field.name, e.target.value)}
                                        className={cn("w-full p-2 mt-1 rounded border", isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300")}
                                    />
                                )}
                            </div>
                        ))}
                    </div>
                )}

                {/* External Auth Provider Toggle */}
                {sourceDetails?.supported_auth_providers && sourceDetails.supported_auth_providers.length > 0 && (
                    <div className="space-y-4 p-4 border rounded-md">
                        <div className="flex items-center justify-between">
                            <div>
                                <label htmlFor="use-external-auth" className="text-sm font-medium">Use external auth provider</label>
                                <p className="text-xs text-muted-foreground">Authenticate via a connected third-party service.</p>
                            </div>
                            <Switch id="use-external-auth" checked={useExternalAuthProvider} onCheckedChange={setUseExternalAuthProvider} />
                        </div>
                        {useExternalAuthProvider && (
                            <div className="pt-4 border-t">
                                {isLoadingConnections ? <Loader2 className="animate-spin" /> : (() => {
                                    // Filter connections to only show providers supported by this source
                                    const supportedAuthProviders = sourceDetails?.supported_auth_providers || [];
                                    const filteredConnections = authProviderConnections.filter(
                                        conn => supportedAuthProviders.includes(conn.short_name)
                                    );
                                    
                                    return filteredConnections.length > 0 ? (
                                        <div className="space-y-2">
                                            {filteredConnections.map(conn => (
                                                <div
                                                    key={conn.id}
                                                    onClick={() => setSelectedAuthProviderConnection(conn)}
                                                    className={cn("h-10 flex items-center gap-2 p-2 rounded-md cursor-pointer border",
                                                        selectedAuthProviderConnection?.id === conn.id ? "border-primary" : "border-transparent hover:bg-accent"
                                                    )}
                                                >
                                                    <img src={getAuthProviderIconUrl(conn.short_name, resolvedTheme)} alt={conn.name} className="h-6 w-6" />
                                                    <span className="text-sm">{conn.name}</span>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-sm text-muted-foreground">
                                            {authProviderConnections.length > 0 
                                                ? "This source is not supported by your connected auth providers."
                                                : "No auth providers connected."}
                                        </p>
                                    );
                                })()}
                            </div>
                        )}
                    </div>
                )}

                <div className="flex justify-end">
                    <Button onClick={handleInitiateConnection} disabled={submitting}>
                        {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Connect
                    </Button>
                </div>
            </div>
        </div>
    );
};
