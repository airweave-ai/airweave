import React, { useEffect } from 'react';
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { TagInput } from '@/components/ui/tag-input';
import { cn } from '@/lib/utils';
import { getAppIconUrl } from '@/lib/utils/icons';
import { Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface EditSourceConnectionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    sourceConnection: any;
    editFormData: any;
    setEditFormData: (data: any) => void;
    sourceDetails: any;
    authProviderDetails: any;
    isUpdating: boolean;
    isFormValid: boolean;
    showPasswordFields: Record<string, boolean>;
    setShowPasswordFields: (fields: any) => void;
    handleEditSubmit: () => void;
    formatTimeSince: (date: string) => string;
    isTokenField: (fieldName: string) => boolean;
    isDark: boolean;
    resolvedTheme: string | undefined;
}

export const EditSourceConnectionDialog: React.FC<EditSourceConnectionDialogProps> = ({
    open,
    onOpenChange,
    sourceConnection,
    editFormData,
    setEditFormData,
    sourceDetails,
    authProviderDetails,
    isUpdating,
    isFormValid,
    showPasswordFields,
    setShowPasswordFields,
    handleEditSubmit,
    formatTimeSince,
    isTokenField,
    isDark,
    resolvedTheme
}) => {
    // Check if auth fields should be shown
    const showAuthFields = sourceDetails?.auth_fields?.fields &&
        sourceDetails.auth_fields.fields.length > 0 &&
        !sourceDetails.auth_fields.fields.some((field: any) => isTokenField(field.name));

    // Log field details when dialog opens or sourceDetails changes
    useEffect(() => {
        if (open && sourceDetails && sourceConnection) {
            console.log('📋 Source Details for Edit Dialog:', {
                shortName: sourceConnection.short_name,
                configFields: sourceDetails.config_fields?.fields || [],
                authFields: sourceDetails.auth_fields?.fields || [],
                showAuthFields,
                hasOAuthTokens: sourceDetails.auth_fields?.fields?.some((field: any) => isTokenField(field.name)),
                usingAuthProvider: !!sourceConnection.auth_provider,
                authProvider: sourceConnection.auth_provider || 'none'
            });
        }
        if (open && sourceConnection?.auth_provider) {
            console.log('🔌 Auth Provider Details for Edit Dialog:', {
                authProvider: sourceConnection.auth_provider,
                authProviderDetails: authProviderDetails,
                configFields: authProviderDetails?.config_fields?.fields || [],
                authProviderConfig: editFormData.auth_provider_config
            });
        }
    }, [open, sourceDetails, authProviderDetails, sourceConnection, showAuthFields, editFormData.auth_provider_config]);

    if (!sourceConnection) return null;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className={cn("p-0 rounded-xl border overflow-hidden", isDark ? "bg-background border-gray-800" : "bg-background border-gray-200")}
                style={{
                    width: "600px",
                    height: "80vh",
                    maxWidth: "95vw",
                    maxHeight: "95vh"
                }}
            >
                <div className="flex flex-col h-full overflow-hidden">
                    {/* Content area - scrollable */}
                    <div className="flex-1 overflow-y-auto min-h-0">
                        <div className="px-8 py-6">
                            {/* Heading with Icon */}
                            <div className="flex items-center gap-4 mb-2">
                                {/* Source Icon - smaller */}
                                <div className={cn(
                                    "w-12 h-12 flex-shrink-0 flex items-center justify-center border rounded-lg p-1.5",
                                    isDark ? "border-gray-700" : "border-gray-300"
                                )}>
                                    <img
                                        src={getAppIconUrl(sourceConnection.short_name, resolvedTheme)}
                                        alt={`${sourceConnection.name} icon`}
                                        className="w-full h-full object-contain"
                                        onError={(e) => {
                                            e.currentTarget.style.display = 'none';
                                            const parent = e.currentTarget.parentElement!;

                                            // Create elements safely without innerHTML to prevent XSS
                                            const wrapper = document.createElement('div');
                                            wrapper.className = `w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'}`;

                                            const span = document.createElement('span');
                                            span.className = `text-xs font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}`;
                                            span.textContent = sourceConnection.short_name.substring(0, 2).toUpperCase();

                                            wrapper.appendChild(span);
                                            parent.appendChild(wrapper);
                                        }}
                                    />
                                </div>
                                <DialogTitle className="text-2xl font-semibold text-left">
                                    Edit {sourceConnection.name}
                                </DialogTitle>
                            </div>
                            <DialogDescription className="text-xs text-muted-foreground mb-6">
                                Update your connection details. Leave fields empty to keep current values.
                            </DialogDescription>

                            {/* Form */}
                            <div className="w-full">
                                <form onSubmit={(e) => { e.preventDefault(); handleEditSubmit(); }} className="space-y-8">
                                    {/* Connection Details Section - Non-editable */}
                                    <div className="space-y-3">
                                        <h3 className="text-sm font-semibold text-foreground border-b pb-2 mb-3">Connection Details</h3>
                                        <div className="bg-muted/20 rounded-lg p-3 space-y-2 text-xs">
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">ID:</span>
                                                <span className="font-mono">{sourceConnection.id}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">Short name:</span>
                                                <span>{sourceConnection.short_name}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">Created at:</span>
                                                <span>{formatTimeSince(sourceConnection.created_at)}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">Modified at:</span>
                                                <span>{formatTimeSince(sourceConnection.modified_at)}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">Created by:</span>
                                                <span className="truncate max-w-[200px]">{sourceConnection.created_by_email}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">Modified by:</span>
                                                <span className="truncate max-w-[200px]">{sourceConnection.modified_by_email}</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Basic Information Section */}
                                    <div className="space-y-3">
                                        <h3 className="text-sm font-semibold text-foreground border-b pb-2 mb-3">Basic Information</h3>

                                        {/* Name field */}
                                        <div className="space-y-1">
                                            <Label className="text-xs text-muted-foreground font-normal">Name</Label>
                                            <Input
                                                type="text"
                                                className={cn(
                                                    "w-full h-8 px-3 text-xs rounded-md border bg-transparent",
                                                    isDark
                                                        ? "border-gray-700 focus:border-blue-500"
                                                        : "border-gray-300 focus:border-blue-500",
                                                    "focus:outline-none"
                                                )}
                                                value={editFormData.name}
                                                onChange={(e) => setEditFormData((prev: any) => ({ ...prev, name: e.target.value }))}
                                                placeholder={sourceConnection.name}
                                            />
                                        </div>

                                        {/* Description field */}
                                        <div className="space-y-1">
                                            <Label className="text-xs text-muted-foreground font-normal">Description</Label>
                                            <Textarea
                                                className={cn(
                                                    "w-full py-1.5 px-3 text-xs rounded-md border bg-transparent resize-none",
                                                    isDark
                                                        ? "border-gray-700 focus:border-blue-500"
                                                        : "border-gray-300 focus:border-blue-500",
                                                    "focus:outline-none"
                                                )}
                                                value={editFormData.description}
                                                onChange={(e) => setEditFormData((prev: any) => ({ ...prev, description: e.target.value }))}
                                                placeholder={sourceConnection.description || "Optional description"}
                                                rows={2}
                                            />
                                        </div>
                                    </div>

                                    {/* Configuration Fields Section */}
                                    {sourceDetails?.config_fields?.fields && sourceDetails.config_fields.fields.length > 0 && (
                                        <div className="space-y-3">
                                            <h3 className="text-sm font-semibold text-foreground border-b pb-2 mb-3">Configuration</h3>
                                            {sourceDetails.config_fields.fields.map((field: any) => (
                                                <div key={field.name} className="space-y-1">
                                                    <Label className="text-xs text-muted-foreground font-normal">
                                                        {field.title || field.name}
                                                        {field.required && <span className="text-red-500 ml-1">*</span>}
                                                    </Label>
                                                    {field.description && (
                                                        <p className="text-xs text-muted-foreground opacity-80">{field.description}</p>
                                                    )}
                                                    {field.type === 'array' ? (
                                                        <TagInput
                                                            value={editFormData.config_fields[field.name] || []}
                                                            onChange={(tags) => setEditFormData((prev: any) => ({
                                                                ...prev,
                                                                config_fields: {
                                                                    ...prev.config_fields,
                                                                    [field.name]: tags
                                                                }
                                                            }))}
                                                            placeholder={`Enter ${field.title?.toLowerCase() || field.name} and press Enter...`}
                                                            transformInput={sourceDetails?.short_name === 'jira' && field.name === 'project_keys' ? (v) => v.toUpperCase() : undefined}
                                                        />
                                                    ) : (
                                                        <Input
                                                            type={field.type === 'integer' ? 'number' : 'text'}
                                                            className={cn(
                                                                "w-full h-8 px-3 text-xs rounded-md border bg-transparent",
                                                                isDark
                                                                    ? "border-gray-700 focus:border-blue-500"
                                                                    : "border-gray-300 focus:border-blue-500",
                                                                "focus:outline-none"
                                                            )}
                                                            value={editFormData.config_fields[field.name] || ''}
                                                            onChange={(e) => setEditFormData((prev: any) => ({
                                                                ...prev,
                                                                config_fields: {
                                                                    ...prev.config_fields,
                                                                    [field.name]: e.target.value
                                                                }
                                                            }))}
                                                            placeholder={`Enter ${field.title || field.name}`}
                                                        />
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {/* Authentication Section - Only show if NOT using auth provider */}
                                    {!sourceConnection.auth_provider && sourceDetails?.auth_fields?.fields && sourceDetails.auth_fields.fields.length > 0 && (
                                        <div className="space-y-3">
                                            <h3 className="text-sm font-semibold text-foreground border-b pb-2 mb-3">Authentication</h3>

                                            {/* Show auth fields only for non-OAuth sources */}
                                            {showAuthFields ? (
                                                <>
                                                    {sourceDetails.auth_fields.fields.map((field: any) => (
                                                        <div key={field.name} className="space-y-1">
                                                            <Label className="text-xs text-muted-foreground font-normal">
                                                                {field.title || field.name}
                                                            </Label>
                                                            {field.description && (
                                                                <p className="text-xs text-muted-foreground opacity-80">{field.description}</p>
                                                            )}
                                                            <div className="relative">
                                                                <Input
                                                                    type={field.secret && !showPasswordFields[field.name] ? 'password' : 'text'}
                                                                    className={cn(
                                                                        "w-full h-8 px-3 text-xs rounded-md border bg-transparent pr-10",
                                                                        isDark
                                                                            ? "border-gray-700 focus:border-blue-500"
                                                                            : "border-gray-300 focus:border-blue-500",
                                                                        "focus:outline-none"
                                                                    )}
                                                                    value={editFormData.auth_fields[field.name] || ''}
                                                                    onChange={(e) => setEditFormData((prev: any) => ({
                                                                        ...prev,
                                                                        auth_fields: {
                                                                            ...prev.auth_fields,
                                                                            [field.name]: e.target.value
                                                                        }
                                                                    }))}
                                                                    placeholder={field.secret ? '••••••••' : `Enter new ${field.title || field.name}`}
                                                                />
                                                                {field.secret && (
                                                                    <button
                                                                        type="button"
                                                                        className="absolute right-2 top-1/2 transform -translate-y-1/2"
                                                                        onClick={() => setShowPasswordFields((prev: any) => ({
                                                                            ...prev,
                                                                            [field.name]: !prev[field.name]
                                                                        }))}
                                                                    >
                                                                        {showPasswordFields[field.name] ?
                                                                            <EyeOff className="h-3 w-3 text-muted-foreground" /> :
                                                                            <Eye className="h-3 w-3 text-muted-foreground" />
                                                                        }
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </>
                                            ) : (
                                                <Alert className="mt-2 text-xs">
                                                    <AlertCircle className="h-3 w-3" />
                                                    <AlertDescription className="text-xs">
                                                        This source uses OAuth authentication. Authentication tokens cannot be edited directly.
                                                    </AlertDescription>
                                                </Alert>
                                            )}
                                        </div>
                                    )}

                                    {/* Auth Provider Configuration Section - Only show if using auth provider */}
                                    {sourceConnection.auth_provider && (
                                        <div className="space-y-3">
                                            <h3 className="text-sm font-semibold text-foreground border-b pb-2 mb-3">Auth Provider Configuration</h3>

                                            {/* Auth provider readable_id - editable */}
                                            <div className="space-y-1">
                                                <Label className="text-xs text-muted-foreground font-normal">Auth Provider Connection ID</Label>
                                                <Input
                                                    type="text"
                                                    className={cn(
                                                        "w-full h-8 px-3 text-xs rounded-md border bg-transparent",
                                                        isDark
                                                            ? "border-gray-700 focus:border-blue-500"
                                                            : "border-gray-300 focus:border-blue-500",
                                                        "focus:outline-none"
                                                    )}
                                                    value={editFormData.auth_provider || ''}
                                                    onChange={(e) => setEditFormData((prev: any) => ({ ...prev, auth_provider: e.target.value }))}
                                                    placeholder={sourceConnection.auth_provider || "Enter auth provider connection ID"}
                                                />
                                            </div>

                                            {/* Show editable config fields if any */}
                                            {authProviderDetails?.config_fields?.fields && authProviderDetails.config_fields.fields.length > 0 && (
                                                <>
                                                    {authProviderDetails.config_fields.fields.map((field: any) => (
                                                        <div key={field.name} className="space-y-1">
                                                            <Label className="text-xs text-muted-foreground font-normal">
                                                                {field.title || field.name}
                                                            </Label>
                                                            {field.description && (
                                                                <p className="text-xs text-muted-foreground opacity-80">{field.description}</p>
                                                            )}
                                                            <Input
                                                                type="text"
                                                                className={cn(
                                                                    "w-full h-8 px-3 text-xs rounded-md border bg-transparent",
                                                                    isDark
                                                                        ? "border-gray-700 focus:border-blue-500"
                                                                        : "border-gray-300 focus:border-blue-500",
                                                                    "focus:outline-none"
                                                                )}
                                                                value={editFormData.auth_provider_config[field.name] || ''}
                                                                onChange={(e) => setEditFormData((prev: any) => ({
                                                                    ...prev,
                                                                    auth_provider_config: {
                                                                        ...prev.auth_provider_config,
                                                                        [field.name]: e.target.value
                                                                    }
                                                                }))}
                                                                placeholder={`Enter ${field.title || field.name}`}
                                                            />
                                                        </div>
                                                    ))}
                                                </>
                                            )}
                                        </div>
                                    )}
                                </form>
                            </div>
                        </div>
                    </div>

                    {/* Footer - fixed at bottom */}
                    <div className="flex-shrink-0 border-t">
                        <DialogFooter className="flex justify-end gap-3 p-6">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => onOpenChange(false)}
                                className={cn(
                                    "px-6",
                                    isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                                )}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="button"
                                onClick={handleEditSubmit}
                                disabled={isUpdating || !isFormValid}
                                className={cn(
                                    "px-6",
                                    isFormValid
                                        ? "bg-blue-600 hover:bg-blue-700 text-white"
                                        : "bg-gray-400 text-gray-200 cursor-not-allowed"
                                )}
                            >
                                {isUpdating ? (
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
            </DialogContent>
        </Dialog>
    );
};
