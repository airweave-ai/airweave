import React, { useState, useRef, useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import type { DialogViewProps } from "@/components/types/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { Loader2, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";

export interface EditAuthProviderViewProps extends DialogViewProps {
    viewData?: {
        authProviderConnectionId?: string;
        authProviderName?: string;
        authProviderShortName?: string;
        dialogId?: string;
        [key: string]: any;
    };
}

export const EditAuthProviderView: React.FC<EditAuthProviderViewProps> = ({
    onNext,
    onCancel,
    onComplete,
    viewData = {},
    onError,
}) => {
    const { authProviderConnectionId, authProviderName, authProviderShortName } = viewData;
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const { fetchAuthProviderConnections } = useAuthProvidersStore();

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [loading, setLoading] = useState(true);
    const [connectionDetails, setConnectionDetails] = useState<any>(null);
    const [authProviderDetails, setAuthProviderDetails] = useState<any>(null);
    const [authFieldValues, setAuthFieldValues] = useState<Record<string, any>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});

    // Form state
    const [nameValue, setNameValue] = useState("");

    // Form validation schema
    const formSchema = z.object({
        name: z.string().optional(),
    });

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            name: "",
        },
    });

    // Fetch connection details
    useEffect(() => {
        if (!authProviderConnectionId) {
            console.warn('⚠️ [EditAuthProviderView] No authProviderConnectionId provided');
            setLoading(false);
            return;
        }

        const fetchDetails = async () => {
            console.log('🔍 [EditAuthProviderView] Fetching connection details for:', authProviderConnectionId);
            setLoading(true);
            try {
                // Fetch connection details
                const connResponse = await apiClient.get(`/auth-providers/connections/${authProviderConnectionId}`);
                if (connResponse.ok) {
                    const connData = await connResponse.json();
                    console.log('✅ [EditAuthProviderView] Connection details loaded:', connData);
                    setConnectionDetails(connData);
                    setNameValue(connData.name);
                    form.setValue("name", connData.name);
                } else {
                    throw new Error("Failed to load connection details");
                }

                // Fetch auth provider details for field definitions
                if (authProviderShortName) {
                    const providerResponse = await apiClient.get(`/auth-providers/detail/${authProviderShortName}`);
                    if (providerResponse.ok) {
                        const providerData = await providerResponse.json();
                        console.log('✅ [EditAuthProviderView] Auth provider details loaded:', providerData);
                        setAuthProviderDetails(providerData);

                        // Initialize auth field values as empty (user will fill only what they want to update)
                        if (providerData.auth_fields && providerData.auth_fields.fields) {
                            const initialValues: Record<string, any> = {};
                            providerData.auth_fields.fields.forEach((field: any) => {
                                if (field.name) {
                                    initialValues[field.name] = '';
                                }
                            });
                            setAuthFieldValues(initialValues);
                        }
                    }
                }
            } catch (error) {
                console.error("Error fetching details:", error);
                if (onError) {
                    onError(error instanceof Error ? error : new Error(String(error)), authProviderName);
                }
            } finally {
                setLoading(false);
            }
        };

        fetchDetails();
    }, [authProviderConnectionId, authProviderShortName, authProviderName, onError, form]);

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
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        setIsSubmitting(true);

        try {
            // Build update payload - only include fields that have been modified
            const updateData: any = {};

            // Include name only if it changed
            if (nameValue && nameValue !== connectionDetails?.name) {
                updateData.name = nameValue;
            }

            // Include auth_fields only if any field has a value
            const filledAuthFields = Object.entries(authFieldValues)
                .filter(([_, value]) => value && String(value).trim() !== '')
                .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});

            if (Object.keys(filledAuthFields).length > 0) {
                updateData.auth_fields = filledAuthFields;
            }

            // If nothing to update, just go back
            if (Object.keys(updateData).length === 0) {
                toast.info("No changes to update");
                // Close dialog without changes
                if (onComplete) {
                    onComplete({
                        success: false,
                        action: 'no-changes',
                    });
                }
                return;
            }

            console.log('🚀 [EditAuthProviderView] Updating with data:', updateData);

            // Update auth provider connection
            const response = await apiClient.put(`/auth-providers/${authProviderConnectionId}`, undefined, updateData);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to update auth provider connection: ${errorText}`);
            }

            const updatedConnection = await response.json();

            // Show success message
            toast.success(`Successfully updated ${authProviderName} connection`);

            // Refresh connections in store
            await fetchAuthProviderConnections();

            // Complete the edit flow and return to auth provider list
            if (onComplete) {
                console.log('🚀 [EditAuthProviderView] Edit complete, closing dialog');
                onComplete({
                    success: true,
                    action: 'updated',
                    authProviderConnectionId: updatedConnection.readable_id,
                    authProviderName,
                    authProviderShortName,
                });
            }
        } catch (error) {
            console.error("Error updating auth provider connection:", error);
            toast.error(error instanceof Error ? error.message : "Failed to update connection");
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
        <div className="flex flex-col h-full">
            {/* Content area - scrollable */}
            <div className="flex-grow overflow-y-auto">
                <div className="p-8 h-full flex flex-col">
                    {/* Heading */}
                    <DialogTitle className="text-4xl font-semibold text-left mb-4">
                        Edit {authProviderName} Connection
                    </DialogTitle>
                    <DialogDescription className="text-sm text-muted-foreground mb-8">
                        Update your connection details. Leave fields empty to keep current values.
                    </DialogDescription>

                    {/* Small spacer to push emblem down 10% */}
                    <div style={{ height: "5%" }}></div>

                    {/* Auth Provider Icon */}
                    {authProviderShortName && (
                        <div className="flex justify-center items-center mb-6" style={{ minHeight: "20%" }}>
                            <div className={cn(
                                "w-64 h-64 flex items-center justify-center border rounded-lg p-2",
                                isDark ? "border-gray-700" : "border-gray-300"
                            )}>
                                <img
                                    src={getAuthProviderIconUrl(authProviderShortName, resolvedTheme)}
                                    alt={`${authProviderName} icon`}
                                    className="w-full h-full object-contain"
                                onError={(e) => {
                                    e.currentTarget.style.display = 'none';
                                    const parent = e.currentTarget.parentElement!;

                                    // Create elements safely without innerHTML to prevent XSS
                                    const wrapper = document.createElement('div');
                                    wrapper.className = `w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'}`;

                                    const span = document.createElement('span');
                                    span.className = `text-5xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}`;
                                    span.textContent = authProviderShortName.substring(0, 2).toUpperCase();

                                    wrapper.appendChild(span);
                                    parent.appendChild(wrapper);
                                }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Reduced spacer to bring form up closer to emblem */}
                    <div className="flex-grow" style={{ minHeight: "15%" }}></div>

                    {/* Form - positioned closer to emblem */}
                    <div className="px-2 max-w-md mx-auto w-full">
                        <form onSubmit={handleSubmit} className="space-y-6">
                            {/* Name field */}
                            <div className="space-y-1">
                                <label className="text-sm font-medium ml-1">Name</label>
                                <div className="relative">
                                    <input
                                        type="text"
                                        className={cn(
                                            "w-full py-2 px-3 rounded-md border bg-transparent pr-10",
                                            isDark
                                                ? "border-gray-700 focus:border-blue-500"
                                                : "border-gray-300 focus:border-blue-500",
                                            "focus:outline-none",
                                            form.formState.errors.name ? "border-red-500" : ""
                                        )}
                                        value={nameValue}
                                        onChange={handleNameChange}
                                        placeholder={connectionDetails?.name || "Connection name"}
                                    />
                                    <Pencil className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground opacity-70" />
                                </div>
                                {form.formState.errors.name && (
                                    <p className="text-sm text-red-500 mt-1">
                                        {form.formState.errors.name.message}
                                    </p>
                                )}
                            </div>

                            {/* Auth fields */}
                            {authProviderDetails?.auth_fields?.fields && authProviderDetails.auth_fields.fields.length > 0 && (
                                <div className="space-y-4 mt-6">
                                    <p className="text-sm text-muted-foreground">
                                        Update authentication credentials (leave empty to keep current values)
                                    </p>
                                    {authProviderDetails.auth_fields.fields.map((field: any) => (
                                        <div key={field.name} className="space-y-1">
                                            <label className="text-sm font-medium ml-1">
                                                {field.title || field.name}
                                            </label>
                                            {field.description && (
                                                <p className="text-xs text-muted-foreground mb-1">{field.description}</p>
                                            )}
                                            <input
                                                type={field.secret ? 'password' : 'text'}
                                                className={cn(
                                                    "w-full py-2 px-3 rounded-md border bg-transparent",
                                                    isDark
                                                        ? "border-gray-700 focus:border-blue-500"
                                                        : "border-gray-300 focus:border-blue-500",
                                                    "focus:outline-none",
                                                    errors[field.name] ? "border-red-500" : ""
                                                )}
                                                value={authFieldValues[field.name] || ''}
                                                onChange={(e) => handleAuthFieldChange(field.name, e.target.value)}
                                                placeholder={field.secret ? '••••••••' : `Enter new ${field.title || field.name}`}
                                            />
                                            {errors[field.name] && (
                                                <p className="text-xs text-red-500">{errors[field.name]}</p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </form>
                    </div>

                    {/* Small spacer at bottom */}
                    <div style={{ height: "5%" }}></div>
                </div>
            </div>

            {/* Footer - fixed at bottom */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="flex justify-end gap-3 p-6">
                    <Button
                        type="button"
                        variant="outline"
                        onClick={onCancel}
                        className={cn(
                            "px-6",
                            isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                        )}
                    >
                        Cancel
                    </Button>
                    <Button
                        type="button"
                        onClick={handleSubmit}
                        disabled={isSubmitting}
                        className="px-6 bg-blue-600 hover:bg-blue-700 text-white"
                    >
                        {isSubmitting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Updating...
                            </>
                        ) : (
                            "Update"
                        )}
                    </Button>
                </DialogFooter>
            </div>
        </div>
    );
};

export default EditAuthProviderView;
