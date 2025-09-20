import React, { useState, useEffect } from "react";
import type { DialogViewProps } from "@/components/types/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { Copy, Check, Trash, Pencil, AlertTriangle, AlertCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";
import { format } from "date-fns";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { clearStoredErrorDetails } from "@/lib/error-utils";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";

// Delete Connection Dialog component
interface DeleteConnectionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void;
    connectionReadableId: string;
    confirmText: string;
    setConfirmText: (text: string) => void;
    isDeleting: boolean;
    isDark: boolean;
}

const DeleteConnectionDialog: React.FC<DeleteConnectionDialogProps> = ({
    open,
    onOpenChange,
    onConfirm,
    connectionReadableId,
    confirmText,
    setConfirmText,
    isDeleting,
    isDark
}) => {
    const isConfirmValid = confirmText === connectionReadableId;

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent className={cn(
                "border-border max-w-md",
                isDark ? "bg-card-solid text-foreground" : "bg-white"
            )}>
                <AlertDialogHeader className="space-y-4">
                    {/* Header with warning icon */}
                    <div className="flex items-center gap-3">
                        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
                            <AlertTriangle className="w-5 h-5 text-destructive" />
                        </div>
                        <div>
                            <AlertDialogTitle className="text-lg font-semibold text-foreground">
                                Delete Auth Provider Connection
                            </AlertDialogTitle>
                            <p className="text-sm text-muted-foreground mt-1">
                                This action cannot be undone
                            </p>
                        </div>
                    </div>

                    {/* Warning content */}
                    <AlertDialogDescription className="space-y-4">
                        <div className="bg-destructive/5 border border-destructive/20 rounded-lg p-4">
                            <p className="font-medium text-foreground mb-3">
                                This will permanently delete:
                            </p>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                                    <span>This auth provider connection</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                                    <span>All source connections created using this auth provider</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                                    <span>All associated sync configurations and data</span>
                                </li>
                            </ul>
                        </div>

                        {/* Critical warning */}
                        <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
                            <div className="flex items-start gap-2">
                                <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
                                <div className="text-sm">
                                    <p className="font-medium text-amber-800 dark:text-amber-200 mb-1">
                                        Critical Impact
                                    </p>
                                    <p className="text-amber-700 dark:text-amber-300">
                                        Source connections will stop working immediately and cannot be recovered.
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Confirmation input */}
                        <div className="space-y-3">
                            <div>
                                <label htmlFor="confirm-delete" className="text-sm font-medium text-foreground block mb-2">
                                    Type <span className="font-mono font-semibold text-destructive bg-destructive/10 px-1.5 py-0.5 rounded">
                                        {connectionReadableId}
                                    </span> to confirm deletion
                                </label>
                                <Input
                                    id="confirm-delete"
                                    value={confirmText}
                                    onChange={(e) => setConfirmText(e.target.value)}
                                    disabled={isDeleting}
                                    className={cn(
                                        "w-full transition-colors",
                                        isConfirmValid && confirmText.length > 0
                                            ? "border-green-500 focus:border-green-500 focus:ring-green-500/20"
                                            : confirmText.length > 0
                                                ? "border-destructive focus:border-destructive focus:ring-destructive/20"
                                                : ""
                                    )}
                                    placeholder={connectionReadableId}
                                />
                            </div>

                            {/* Validation feedback */}
                            {confirmText.length > 0 && !isDeleting && (
                                <div className="flex items-center gap-2 text-sm">
                                    {isConfirmValid ? (
                                        <>
                                            <Check className="w-4 h-4 text-green-500" />
                                            <span className="text-green-600 dark:text-green-400">
                                                Confirmation matches
                                            </span>
                                        </>
                                    ) : (
                                        <>
                                            <AlertCircle className="w-4 h-4 text-destructive" />
                                            <span className="text-destructive">
                                                Confirmation does not match
                                            </span>
                                        </>
                                    )}
                                </div>
                            )}
                        </div>
                    </AlertDialogDescription>
                </AlertDialogHeader>

                <AlertDialogFooter className="gap-3">
                    <AlertDialogCancel disabled={isDeleting} className="flex-1">
                        Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                        onClick={onConfirm}
                        disabled={!isConfirmValid || isDeleting}
                        className={cn(
                            "flex-1 bg-destructive text-destructive-foreground hover:bg-destructive/90",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "transition-all duration-200"
                        )}
                    >
                        {isDeleting ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Deleting...
                            </>
                        ) : (
                            <>
                                <Trash className="w-4 h-4 mr-2" />
                                Delete Connection
                            </>
                        )}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
};

export interface AuthProviderDetailViewProps extends DialogViewProps {
    viewData?: {
        authProviderConnectionId?: string;
        authProviderName?: string;
        authProviderShortName?: string;
        dialogId?: string;
        [key: string]: any;
    };
}

export const AuthProviderDetailView: React.FC<AuthProviderDetailViewProps> = ({
    onCancel,
    onComplete,
    viewData = {},
    onError,
}) => {
    const { authProviderConnectionId, authProviderName, authProviderShortName } = viewData;
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const { fetchAuthProviderConnections } = useAuthProvidersStore();

    const [loading, setLoading] = useState(true);
    const [connectionDetails, setConnectionDetails] = useState<any>(null);
    const [copiedField, setCopiedField] = useState<string | null>(null);

    // Delete dialog state
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [confirmText, setConfirmText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);
    const [isClosing, setIsClosing] = useState(false);

    console.log('🔍 [AuthProviderDetailView] Component mounted with:', {
        authProviderConnectionId,
        authProviderName,
        authProviderShortName,
        viewData
    });

    // Log component lifecycle
    useEffect(() => {
        console.log('🌟 [AuthProviderDetailView] useEffect mount check');

        return () => {
            console.log('💥 [AuthProviderDetailView] Component unmounting');
            // Clear any stored errors when component unmounts
            clearStoredErrorDetails();
        };
    }, []);

    // Fetch connection details
    useEffect(() => {
        if (!authProviderConnectionId || isClosing) {
            if (!authProviderConnectionId) {
                console.warn('⚠️ [AuthProviderDetailView] No authProviderConnectionId provided');
            }
            return;
        }

        let isMounted = true;

        const fetchConnectionDetails = async () => {
            console.log('📡 [AuthProviderDetailView] Fetching connection details for:', authProviderConnectionId);
            setLoading(true);
            try {
                const response = await apiClient.get(`/auth-providers/connections/${authProviderConnectionId}`);
                if (response.ok && isMounted) {
                    const data = await response.json();
                    setConnectionDetails(data);
                } else if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Failed to load connection details: ${errorText}`);
                }
            } catch (error) {
                if (isMounted && !isClosing) {
                    console.error("Error fetching connection details:", error);
                    if (onError) {
                        onError(error instanceof Error ? error : new Error(String(error)), authProviderName);
                    }
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };

        fetchConnectionDetails();

        return () => {
            isMounted = false;
        };
    }, [authProviderConnectionId, authProviderName, onError, isClosing]);

    const handleCopy = async (value: string, fieldName: string) => {
        try {
            await navigator.clipboard.writeText(value);
            setCopiedField(fieldName);
            toast.success(`${fieldName} copied to clipboard`);

            // Reset copied state after 2 seconds
            setTimeout(() => {
                setCopiedField(null);
            }, 2000);
        } catch (error) {
            toast.error("Failed to copy to clipboard");
        }
    };

    const formatDate = (dateString: string) => {
        try {
            return format(new Date(dateString), "PPP 'at' p");
        } catch {
            return dateString;
        }
    };

    const handleDeleteConnection = async () => {
        if (!authProviderConnectionId || confirmText !== connectionDetails?.readable_id) return;

        setIsDeleting(true);
        setIsClosing(true);  // Prevent any further fetches

        try {
            const response = await apiClient.delete(`/auth-providers/${authProviderConnectionId}`);

            if (response.ok) {
                toast.success("Auth provider connection deleted successfully");

                // Clear any stored error details to prevent error dialog on navigation
                clearStoredErrorDetails();

                // Close the delete dialog immediately
                setShowDeleteDialog(false);
                setConfirmText('');

                // Refresh auth provider connections in the store
                await fetchAuthProviderConnections();

                // Close the main dialog using onComplete to properly cleanup
                if (onComplete) {
                    onComplete({ success: true, action: 'deleted' });
                }

                // Navigate will be handled by the parent component after dialog closes
            } else {
                const errorText = await response.text();
                throw new Error(`Failed to delete auth provider connection: ${errorText}`);
            }
        } catch (err) {
            console.error("Error deleting auth provider connection:", err);
            toast.error(err instanceof Error ? err.message : "Failed to delete auth provider connection");
            setIsDeleting(false);
            setShowDeleteDialog(false);
            setConfirmText(''); // Reset confirm text
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center py-8">
                <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    if (!connectionDetails) {
        return (
            <div className="text-center py-8 text-muted-foreground">
                <p>No connection details available</p>
            </div>
        );
    }

    const DeleteConnectionDialogComponent = (
        <DeleteConnectionDialog
            open={showDeleteDialog}
            onOpenChange={setShowDeleteDialog}
            onConfirm={handleDeleteConnection}
            connectionReadableId={connectionDetails?.readable_id}
            confirmText={confirmText}
            setConfirmText={setConfirmText}
            isDeleting={isDeleting}
            isDark={isDark}
        />
    );

    return (
        <div className="h-full flex flex-col max-h-[90vh]">
            {/* Fixed header with action buttons */}
            <div className={cn(
                "px-6 pt-6 pb-4 border-b",
                isDark ? "border-gray-800/50" : "border-gray-100"
            )}>
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        {authProviderName} Connection
                    </h2>

                    {/* Action buttons - more subtle */}
                    <div className="flex gap-1">
                        <button
                            onClick={() => {
                                if (onComplete) {
                                    onComplete({
                                        action: 'edit',
                                        authProviderConnectionId,
                                        authProviderName,
                                        authProviderShortName
                                    });
                                }
                            }}
                            className={cn(
                                "h-8 w-8 rounded-lg transition-all duration-150 flex items-center justify-center",
                                isDark
                                    ? "hover:bg-gray-800/60 text-gray-400 hover:text-gray-200"
                                    : "hover:bg-gray-100 text-gray-500 hover:text-gray-700"
                            )}
                            title="Edit connection"
                        >
                            <Pencil className="h-4 w-4" />
                        </button>

                        <button
                            onClick={() => setShowDeleteDialog(true)}
                            className={cn(
                                "h-8 w-8 rounded-lg transition-all duration-150 flex items-center justify-center",
                                isDark
                                    ? "hover:bg-gray-800/60 text-gray-400 hover:text-red-400"
                                    : "hover:bg-gray-100 text-gray-500 hover:text-red-500"
                            )}
                            title="Delete connection"
                        >
                            <Trash className="h-4 w-4" />
                        </button>
                    </div>
                </div>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    View and manage your {authProviderName} connection details
                </p>
            </div>

            {/* Content area - scrollable with better spacing */}
            <div className="flex-1 overflow-y-auto px-6 py-6">
                <div className="space-y-6 pb-6">
                    {/* Auth Provider Icon - more integrated */}
                    {authProviderShortName && (
                        <div className="flex justify-center py-4">
                            <div className={cn(
                                "w-20 h-20 flex items-center justify-center rounded-xl p-3",
                                isDark ? "bg-gray-800/30" : "bg-gray-50/70"
                            )}>
                                <img
                                    src={getAuthProviderIconUrl(authProviderShortName, resolvedTheme)}
                                    alt={`${authProviderName} icon`}
                                    className="w-full h-full object-contain"
                                    onError={(e) => {
                                        e.currentTarget.style.display = 'none';
                                        e.currentTarget.parentElement!.innerHTML = `
                                            <div class="w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900/50' : 'bg-blue-50'}">
                                                <span class="text-xl font-semibold ${isDark ? 'text-blue-400' : 'text-blue-600'}">
                                                    ${authProviderShortName.substring(0, 2).toUpperCase()}
                                                </span>
                                            </div>
                                        `;
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Connection Details - cleaner design */}
                    <div className="space-y-4">
                        {/* Name */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                Name
                            </label>
                            <div className={cn(
                                "w-full px-3 py-2 rounded-md text-sm",
                                isDark
                                    ? "bg-gray-800/40 text-gray-100"
                                    : "bg-gray-50 text-gray-900"
                            )}>
                                {connectionDetails.name}
                            </div>
                        </div>

                        {/* Readable ID */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                Readable ID
                            </label>
                            <div className={cn(
                                "w-full px-3 py-2 rounded-md text-sm flex items-center justify-between group",
                                isDark
                                    ? "bg-gray-800/40 text-gray-100"
                                    : "bg-gray-50 text-gray-900"
                            )}>
                                <span className="font-mono text-xs break-all">{connectionDetails.readable_id}</span>
                                <button
                                    onClick={() => handleCopy(connectionDetails.readable_id, "Readable ID")}
                                    className={cn(
                                        "p-1 rounded transition-opacity opacity-0 group-hover:opacity-100",
                                        isDark
                                            ? "hover:bg-gray-700/50"
                                            : "hover:bg-gray-200/50"
                                    )}
                                >
                                    {copiedField === "Readable ID" ? (
                                        <Check className="h-3.5 w-3.5 text-green-500" />
                                    ) : (
                                        <Copy className="h-3.5 w-3.5 text-gray-400" />
                                    )}
                                </button>
                            </div>
                        </div>

                        {/* Created By */}
                        {connectionDetails.created_by_email && (
                            <div className="space-y-1.5">
                                <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                    Created By
                                </label>
                                <div className={cn(
                                    "w-full px-3 py-2 rounded-md text-sm",
                                    isDark
                                        ? "bg-gray-800/40 text-gray-100"
                                        : "bg-gray-50 text-gray-900"
                                )}>
                                    {connectionDetails.created_by_email}
                                </div>
                            </div>
                        )}

                        {/* Created At */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                Created At
                            </label>
                            <div className={cn(
                                "w-full px-3 py-2 rounded-md text-sm",
                                isDark
                                    ? "bg-gray-800/40 text-gray-100"
                                    : "bg-gray-50 text-gray-900"
                            )}>
                                {formatDate(connectionDetails.created_at)}
                            </div>
                        </div>

                        {/* Modified By */}
                        {connectionDetails.modified_by_email && (
                            <div className="space-y-1.5">
                                <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                    Modified By
                                </label>
                                <div className={cn(
                                    "w-full px-3 py-2 rounded-md text-sm",
                                    isDark
                                        ? "bg-gray-800/40 text-gray-100"
                                        : "bg-gray-50 text-gray-900"
                                )}>
                                    {connectionDetails.modified_by_email}
                                </div>
                            </div>
                        )}

                        {/* Modified At */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                Modified At
                            </label>
                            <div className={cn(
                                "w-full px-3 py-2 rounded-md text-sm",
                                isDark
                                    ? "bg-gray-800/40 text-gray-100"
                                    : "bg-gray-50 text-gray-900"
                            )}>
                                {formatDate(connectionDetails.modified_at)}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Bottom actions - minimal and clean */}
            <div className={cn(
                "px-6 py-4 border-t",
                isDark ? "border-gray-800/50" : "border-gray-100"
            )}>
                <button
                    onClick={onCancel}
                    className={cn(
                        "w-full py-2 px-4 rounded-lg text-sm font-medium transition-all duration-150",
                        isDark
                            ? "bg-gray-800 hover:bg-gray-700 text-gray-100"
                            : "bg-gray-100 hover:bg-gray-200 text-gray-700"
                    )}
                >
                    Done
                </button>
            </div>

            {/* Delete Connection Dialog */}
            {DeleteConnectionDialogComponent}
        </div>
    );
};

export default AuthProviderDetailView;
