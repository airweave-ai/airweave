import React, { useState, useRef, useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import type { DialogViewProps } from "@/components/types/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";
import { ExternalLink, Loader2, Key } from "lucide-react";
import '@/styles/connection-animation.css';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Generates a random suffix for the readable ID
 * This ensures uniqueness for similar connection names
 *
 * @returns Random alphanumeric string of length 6
 */
const generateRandomSuffix = () => {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < 6; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
};

/**
 * Helper to generate the base readable ID from a name
 * Transforms name to lowercase, replaces spaces with hyphens, and removes special characters
 *
 * @param name Connection name to transform
 * @returns Sanitized base readable ID (without suffix)
 */
const generateReadableIdBase = (name: string): string => {
    if (!name || name.trim() === "") return "";

    // Convert to lowercase and replace spaces with hyphens
    let readable_id = name.toLowerCase().trim();

    // Replace any character that's not a letter, number, or space with nothing
    readable_id = readable_id.replace(/[^a-z0-9\s]/g, "");

    // Replace spaces with hyphens
    readable_id = readable_id.replace(/\s+/g, "-");

    // Ensure no consecutive hyphens
    readable_id = readable_id.replace(/-+/g, "-");

    // Trim hyphens from start and end
    readable_id = readable_id.replace(/^-|-$/g, "");

    return readable_id;
};

export interface ConfigureAuthProviderViewProps extends DialogViewProps {
    viewData?: {
        authProviderName?: string;
        authProviderShortName?: string;
        dialogId?: string;
        [key: string]: any;
    };
}

// Secure fallback components for image errors
const AirweaveFallback: React.FC<{ isDark: boolean }> = ({ isDark }) => (
    <div className={cn(
        "w-full h-full rounded flex items-center justify-center",
        isDark ? "bg-blue-900" : "bg-blue-100"
    )}>
        <span className={cn(
            "text-xl font-bold",
            isDark ? "text-blue-400" : "text-blue-600"
        )}>
            AW
        </span>
    </div>
);

const AuthProviderFallback: React.FC<{
    authProviderShortName: string;
    isDark: boolean
}> = ({ authProviderShortName, isDark }) => {
    // Safely extract initials from authProviderShortName
    const initials = authProviderShortName
        ? authProviderShortName.substring(0, 2).toUpperCase()
        : "AP";

    return (
        <div className={cn(
            "w-full h-full rounded-lg flex items-center justify-center",
            isDark ? "bg-blue-900" : "bg-blue-100"
        )}>
            <span className={cn(
                "text-xl font-bold",
                isDark ? "text-blue-400" : "text-blue-600"
            )}>
                {initials}
            </span>
        </div>
    );
};

export const ConfigureAuthProviderView: React.FC<ConfigureAuthProviderViewProps> = ({
    onNext,
    onCancel,
    onComplete,
    viewData = {},
    onError,
}) => {
    const { authProviderName, authProviderShortName } = viewData;
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const navigate = useNavigate();
    const { fetchAuthProviderConnections } = useAuthProvidersStore();

    // Log component lifecycle
    useEffect(() => {
        console.log('🌟 [ConfigureAuthProviderView] Component mounted:', {
            authProviderName,
            authProviderShortName,
            viewData
        });

        return () => {
            console.log('💥 [ConfigureAuthProviderView] Component unmounting');
        };
    }, []);

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [loading, setLoading] = useState(true);
    const [authProviderDetails, setAuthProviderDetails] = useState<any>(null);
    const [authFieldValues, setAuthFieldValues] = useState<Record<string, any>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});
    const [formError, setFormError] = useState<string | null>(null);

    // Image error state for secure fallbacks
    const [airweaveImageError, setAirweaveImageError] = useState(false);
    const [authProviderImageError, setAuthProviderImageError] = useState(false);

    // Log loading state changes
    useEffect(() => {
        console.log('⏳ [ConfigureAuthProviderView] Loading state:', loading);
    }, [loading]);

    // Default name for the connection
    const defaultConnectionName = authProviderName ? `My ${authProviderName} Connection` : "My Connection";

    // Random suffix for readable ID (stored in ref to persist across renders)
    const randomSuffixRef = useRef(generateRandomSuffix());
    const previousNameRef = useRef(defaultConnectionName);
    const [userEditedId, setUserEditedId] = useState(false);

    // Direct input values to avoid one-keypress delay
    const [nameValue, setNameValue] = useState(defaultConnectionName);
    const [readableIdValue, setReadableIdValue] = useState("");

    // Form validation schema
    const formSchema = z.object({
        name: z.string().min(1, "Name is required").max(255, "Name must be less than 255 characters"),
        readable_id: z.string().optional().refine(
            (val) => !val || /^[a-z0-9-]+$/.test(val),
            { message: "Readable ID must contain only lowercase letters, numbers, and hyphens" }
        ),
    });

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            name: defaultConnectionName,
            readable_id: getReadableId(defaultConnectionName),
        },
    });

    // Reset form when dialog opens
    useEffect(() => {
        randomSuffixRef.current = generateRandomSuffix();
        previousNameRef.current = defaultConnectionName;
        setNameValue(defaultConnectionName);
        const generatedId = getReadableId(defaultConnectionName);
        setReadableIdValue(generatedId);

        form.reset({
            name: defaultConnectionName,
            readable_id: generatedId,
        });

        setUserEditedId(false);
    }, [defaultConnectionName, form]);

    // Fetch auth provider details
    useEffect(() => {
        console.log('🔍 [ConfigureAuthProviderView] Auth provider details effect triggered:', {
            authProviderShortName,
            currentLoading: loading
        });

        if (!authProviderShortName) {
            console.log('⚠️ [ConfigureAuthProviderView] No authProviderShortName, skipping fetch');
            setLoading(false);
            return;
        }

        const fetchDetails = async () => {
            console.log('🚀 [ConfigureAuthProviderView] Starting to fetch auth provider details');
            setLoading(true);
            try {
                const response = await apiClient.get(`/auth-providers/detail/${authProviderShortName}`);
                console.log('📡 [ConfigureAuthProviderView] Auth provider details response:', response.ok);

                if (response.ok) {
                    const data = await response.json();
                    console.log('✅ [ConfigureAuthProviderView] Auth provider details loaded:', {
                        hasAuthFields: !!data.auth_fields,
                        fieldsCount: data.auth_fields?.fields?.length || 0
                    });
                    setAuthProviderDetails(data);

                    // Initialize auth field values
                    if (data.auth_fields && data.auth_fields.fields) {
                        const initialValues: Record<string, any> = {};
                        data.auth_fields.fields.forEach((field: any) => {
                            if (field.name) {
                                initialValues[field.name] = '';
                            }
                        });
                        setAuthFieldValues(initialValues);
                    }
                } else {
                    const errorText = await response.text();
                    console.error('❌ [ConfigureAuthProviderView] Failed to load auth provider details:', errorText);
                    throw new Error(`Failed to load auth provider details: ${errorText}`);
                }
            } catch (error) {
                console.error("Error fetching auth provider details:", error);
                if (onError) {
                    onError(error instanceof Error ? error : new Error(String(error)), authProviderName);
                }
            } finally {
                console.log('🏁 [ConfigureAuthProviderView] Setting loading to false');
                setLoading(false);
            }
        };

        fetchDetails();
    }, [authProviderShortName, authProviderName, onError]);

    function getReadableId(name: string) {
        if (!name || name.trim() === "") {
            return "";
        }

        const base = generateReadableIdBase(name);
        return base ? `${base}-${randomSuffixRef.current}` : "";
    }

    const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newName = e.target.value;

        setNameValue(newName);
        form.setValue("name", newName);

        // Clear name validation error if it exists
        if (errors.name) {
            setErrors(prev => {
                const updated = { ...prev };
                delete updated.name;
                return updated;
            });
        }

        // Clear form error when user starts typing
        if (formError) {
            setFormError(null);
        }

        if (previousNameRef.current && newName === "" && !userEditedId) {
            randomSuffixRef.current = generateRandomSuffix();
        }

        if (!userEditedId) {
            if (!newName || newName.trim() === "") {
                const emptyId = "";
                setReadableIdValue(emptyId);
                form.setValue("readable_id", emptyId);
            } else {
                const newId = getReadableId(newName);
                setReadableIdValue(newId);
                form.setValue("readable_id", newId);
            }
        }

        previousNameRef.current = newName;
    };

    const handleReadableIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newId = e.target.value;

        setReadableIdValue(newId);
        form.setValue("readable_id", newId);

        // Clear readable_id validation error if it exists
        if (errors.readable_id || form.formState.errors.readable_id) {
            setErrors(prev => {
                const updated = { ...prev };
                delete updated.readable_id;
                return updated;
            });
        }

        if (!nameValue || nameValue.trim() === "") {
            setUserEditedId(true);
            return;
        }

        const currentNameBase = generateReadableIdBase(nameValue);
        const currentFullId = `${currentNameBase}-${randomSuffixRef.current}`;

        if (newId !== currentFullId) {
            setUserEditedId(true);
        } else {
            setUserEditedId(false);
        }
    };

    const validateAuthFields = (): boolean => {
        const newErrors: Record<string, string> = {};
        let isValid = true;

        // Validate all auth fields are filled
        if (authProviderDetails?.auth_fields?.fields) {
            authProviderDetails.auth_fields.fields.forEach((field: any) => {
                if (!authFieldValues[field.name] || authFieldValues[field.name].trim() === '') {
                    newErrors[field.name] = `${field.title || field.name} is required`;
                    isValid = false;
                }
            });
        }

        setErrors(newErrors);
        return isValid;
    };

    // Helper function to check if any required fields are empty (similar to ConfigureSourceView)
    const hasEmptyRequiredFields = (): boolean => {
        // Check if name is empty (backend requires min_length=1)
        if (!nameValue || nameValue.trim() === '') {
            return true;
        }

        // Check if any auth fields are empty
        if (authProviderDetails?.auth_fields?.fields) {
            return authProviderDetails.auth_fields.fields.some((field: any) =>
                !authFieldValues[field.name] || authFieldValues[field.name].trim() === ''
            );
        }

        return false;
    };

    const handleAuthFieldChange = (key: string, value: string) => {
        setAuthFieldValues(prev => ({
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

        // Clear form error when user starts typing (gives them a chance to retry)
        if (formError) {
            setFormError(null);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        // Only validate if the button is somehow clicked while disabled
        if (hasEmptyRequiredFields()) {
            return;
        }

        // Validate form
        const formValid = await form.trigger();
        if (!formValid) return;

        // Validate auth fields (this will set errors but we shouldn't reach here if button is properly disabled)
        if (!validateAuthFields()) return;

        setIsSubmitting(true);
        setFormError(null); // Clear any previous form errors

        try {
            // Create auth provider connection
            const connectionData = {
                name: nameValue,
                readable_id: readableIdValue,
                short_name: authProviderShortName,
                auth_fields: authFieldValues,
            };

            const response = await apiClient.post('/auth-providers/', connectionData);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to create auth provider connection: ${errorText}`);
            }

            const connection = await response.json();

            // Add a small delay to simulate connection process and show loading state
            await new Promise(resolve => setTimeout(resolve, 1500));

            // Show success message after delay
            toast.success(`Successfully connected to ${authProviderName}`, {
                description: 'Your connection is now active and ready to use.',
                duration: 5000,
            });

            // Navigate to detail view BEFORE refreshing connections
            console.log('🎯 [ConfigureAuthProviderView] Connection created successfully:', {
                connectionId: connection.id,
                readableId: connection.readable_id,
                name: connection.name,
                shortName: connection.short_name
            });

            if (onNext) {
                console.log('🚀 [ConfigureAuthProviderView] Calling onNext to navigate to detail view');
                onNext({
                    authProviderConnectionId: connection.readable_id,
                    authProviderName: authProviderName,  // Use the original auth provider name, not connection name
                    authProviderShortName: connection.short_name,
                    isNewConnection: true  // Flag to indicate this is a new connection
                });

                // Refresh connections after navigation - testing without delay
                console.log('📡 [ConfigureAuthProviderView] Refreshing auth provider connections after navigation');
                fetchAuthProviderConnections();
            } else {
                console.warn('⚠️ [ConfigureAuthProviderView] onNext is not defined!');
                // If no onNext, refresh immediately
                await fetchAuthProviderConnections();
            }
        } catch (error) {
            console.error("Error creating auth provider connection:", error);

            // Extract error message from the response
            let errorMessage = "Failed to create connection";
            if (error instanceof Error) {
                errorMessage = error.message;

                // Try to extract more specific error from API response
                if (errorMessage.includes("Failed to create auth provider connection:")) {
                    const apiError = errorMessage.replace("Failed to create auth provider connection:", "").trim();
                    try {
                        // Try to parse as JSON in case it's a structured error
                        const parsedError = JSON.parse(apiError);
                        errorMessage = parsedError.detail || apiError;
                    } catch {
                        // If not JSON, use as-is
                        errorMessage = apiError;
                    }
                }
            }

            // Set form error state for inline display
            setFormError(errorMessage);

            // Also show error as a toast for better visibility
            toast.error("Connection Failed", {
                description: errorMessage,
                duration: 8000, // Longer duration for error messages
            });

            // Don't call onError to avoid redirect - just stay on the form
        } finally {
            setIsSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center py-8">
                <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col max-h-[90vh]">
            {/* Fixed header */}
            <div className={cn(
                "px-6 pt-6 pb-4 border-b",
                isDark ? "border-gray-800/50" : "border-gray-100"
            )}>
                <div>
                    <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
                        Connect to {authProviderName}
                    </h2>
                    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                        Create a connection to {authProviderName} that can be used to authenticate to data sources
                    </p>
                </div>
            </div>

            {/* Content area - scrollable */}
            <div className="px-8 py-10 flex-1 overflow-auto min-h-0">
                <div className="space-y-8">

                    {/* Connection Animation */}
                    {authProviderShortName && (
                        <div className="flex justify-center py-6">
                            <div className="relative flex items-center gap-8">
                                {/* Airweave Logo */}
                                <div className="flex flex-col items-center gap-2">
                                    <div className={cn(
                                        "w-16 h-16 rounded-xl flex items-center justify-center p-3",
                                        "transition-all duration-500 ease-in-out",
                                        isDark ? "bg-gray-800/50" : "bg-white/80",
                                        "shadow-lg ring-2 ring-gray-400/30"
                                    )}>
                                        {airweaveImageError ? (
                                            <AirweaveFallback isDark={isDark} />
                                        ) : (
                                            <img
                                                src={isDark ? "/airweave-logo-svg-white-darkbg.svg" : "/airweave-logo-svg-lightbg-blacklogo.svg"}
                                                alt="Airweave"
                                                className="w-full h-full object-contain"
                                                onError={() => setAirweaveImageError(true)}
                                            />
                                        )}
                                    </div>
                                </div>

                                {/* Connecting Status Text */}
                                <div className="flex items-center justify-center">
                                    <p className={cn(
                                        "text-sm font-medium relative transition-all duration-500 ease-in-out",
                                        "bg-clip-text text-transparent",
                                        isDark
                                            ? "bg-gradient-to-r from-gray-400 via-white to-gray-400"
                                            : "bg-gradient-to-r from-gray-500 via-gray-900 to-gray-500"
                                    )}
                                        style={{
                                            backgroundSize: '200% 100%',
                                            animation: 'textShimmer 2.5s ease-in-out infinite'
                                        }}>
                                        Waiting for connection...
                                    </p>
                                </div>

                                {/* Auth Provider Logo */}
                                <div className="flex flex-col items-center gap-2">
                                    <div className={cn(
                                        "w-16 h-16 rounded-xl flex items-center justify-center p-3",
                                        "transition-all duration-500 ease-in-out",
                                        isDark ? "bg-gray-800/50" : "bg-white/80",
                                        "shadow-lg ring-2 ring-gray-400/30"
                                    )}>
                                        {authProviderImageError ? (
                                            <AuthProviderFallback
                                                authProviderShortName={authProviderShortName || ''}
                                                isDark={isDark}
                                            />
                                        ) : (
                                            <img
                                                src={getAuthProviderIconUrl(authProviderShortName, resolvedTheme)}
                                                alt={authProviderName}
                                                className="w-full h-full object-contain"
                                                onError={() => setAuthProviderImageError(true)}
                                            />
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Form fields - Clean minimal design */}
                    <div className="space-y-6">
                        {/* Name field */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                Name
                            </label>
                            <input
                                type="text"
                                value={nameValue}
                                onChange={handleNameChange}
                                placeholder="My Connection"
                                className={cn(
                                    "w-full px-4 py-2.5 rounded-lg text-sm",
                                    "border transition-colors",
                                    "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                                    isDark
                                        ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                        : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400",
                                    form.formState.errors.name ? "border-red-500" : ""
                                )}
                            />
                            {form.formState.errors.name && (
                                <p className="text-xs text-red-500 mt-1">
                                    {form.formState.errors.name.message}
                                </p>
                            )}
                        </div>

                        {/* Readable ID field */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                Readable ID
                            </label>
                            <input
                                type="text"
                                value={readableIdValue}
                                onChange={handleReadableIdChange}
                                placeholder="Auto-generated"
                                className={cn(
                                    "w-full px-4 py-2.5 rounded-lg text-sm",
                                    "border transition-colors",
                                    "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                                    isDark
                                        ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                        : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400",
                                    errors.readable_id || form.formState.errors.readable_id ? "border-red-500" : ""
                                )}
                            />
                            {form.formState.errors.readable_id && (
                                <p className="text-xs text-red-500 mt-1">
                                    {form.formState.errors.readable_id.message}
                                </p>
                            )}
                        </div>

                        {/* Auth fields */}
                        {authProviderDetails?.auth_fields?.fields && authProviderDetails.auth_fields.fields.length > 0 && (
                            <>
                                <div className="pt-2">
                                    <div className="flex items-center justify-between mb-4">
                                        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                            Authentication
                                        </label>

                                        {/* Auth Provider Platform Buttons with Tooltips */}
                                        {(authProviderShortName === 'composio' || authProviderShortName === 'pipedream') && (
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <button
                                                            onClick={() => {
                                                                const url = authProviderShortName === 'composio'
                                                                    ? 'https://platform.composio.dev/'
                                                                    : 'https://pipedream.com/settings/api';
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
                                                                src={getAuthProviderIconUrl(authProviderShortName, resolvedTheme)}
                                                                alt={authProviderShortName}
                                                                className="w-3 h-3 object-contain"
                                                                onError={(e) => {
                                                                    e.currentTarget.style.display = 'none';
                                                                }}
                                                            />
                                                            {authProviderShortName === 'composio' ? 'Get API Key from Composio' : 'Get Client ID & Secret from Pipedream'}
                                                            <ExternalLink className="w-3 h-3" />
                                                        </button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>Opens {authProviderShortName === 'composio' ? 'Composio platform to retrieve your API credentials' : 'Pipedream settings to retrieve your client ID and secret'}</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        )}
                                    </div>
                                    <div className="space-y-4">
                                        {authProviderDetails.auth_fields.fields.map((field: any) => (
                                            <div key={field.name}>
                                                <label className="block text-sm font-medium mb-1.5">
                                                    {field.title || field.name}
                                                    {field.required && <span className="text-red-500 ml-1">*</span>}
                                                </label>
                                                {field.description && (
                                                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                                                        {field.description}
                                                    </p>
                                                )}
                                                <input
                                                    type={field.secret ? 'password' : 'text'}
                                                    value={authFieldValues[field.name] || ''}
                                                    onChange={(e) => handleAuthFieldChange(field.name, e.target.value)}
                                                    placeholder={field.secret ? '••••••••' : `Enter ${field.title || field.name}`}
                                                    className={cn(
                                                        "w-full px-4 py-2.5 rounded-lg text-sm",
                                                        "border bg-transparent",
                                                        "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                                                        isDark
                                                            ? "border-gray-800 text-white placeholder:text-gray-600"
                                                            : "border-gray-200 text-gray-900 placeholder:text-gray-400",
                                                        errors[field.name] ? "border-red-500" : ""
                                                    )}
                                                />
                                                {errors[field.name] && (
                                                    <p className="text-xs text-red-500 mt-1">{errors[field.name]}</p>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </div>

            {/* Bottom actions - Clean minimal */}
            <div className={cn(
                "px-8 py-6 border-t flex-shrink-0",
                isDark ? "border-gray-800" : "border-gray-200"
            )}>
                {/* Form Error Display */}
                {formError && (
                    <div className={cn(
                        "mb-4 p-4 rounded-lg border",
                        "bg-red-50/50 border-red-200/60",
                        "dark:bg-red-950/20 dark:border-red-800/30"
                    )}>
                        <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 mt-0.5">
                                <svg className="w-4 h-4 text-red-500 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                                </svg>
                            </div>
                            <div className="flex-1">
                                <p className="text-sm text-red-700 dark:text-red-300 font-medium">
                                    {formError}
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                <div className="flex gap-3">
                    <button
                        onClick={onCancel}
                        className={cn(
                            "px-6 py-2 rounded-lg text-sm font-medium transition-colors",
                            isDark
                                ? "text-gray-400 hover:text-gray-200"
                                : "text-gray-600 hover:text-gray-900"
                        )}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={isSubmitting || hasEmptyRequiredFields()}
                        className={cn(
                            "flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all duration-200",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "bg-blue-600 hover:bg-blue-700 text-white",
                            "flex items-center justify-center gap-2"
                        )}
                    >
                        {isSubmitting ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                <span>Connecting...</span>
                            </>
                        ) : (
                            'Connect'
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ConfigureAuthProviderView;
