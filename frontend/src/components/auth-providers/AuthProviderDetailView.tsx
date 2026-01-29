import React, { useState, useEffect } from "react";
import type { DialogViewProps } from "@/components/types/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { Copy, Check, Trash, Pencil, AlertTriangle, AlertCircle, Loader2, Link } from "lucide-react";
import { toast } from "sonner";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";
import { format } from "date-fns";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { clearStoredErrorDetails } from "@/lib/error-utils";
import '@/styles/connection-animation.css';
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
                    <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
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
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                    View and manage your {authProviderName} connection details
                </p>
            </div>

            {/* Content area - scrollable */}
            <div className="px-8 py-10 flex-1 overflow-auto min-h-0">
                <div className="space-y-8">

                    {/* Connected Animation */}
                    {authProviderShortName && (
                        <div className="flex justify-center py-6">
                            <div className="relative flex items-center gap-12">
                                {/* Connection Beam */}
                                <div className="absolute left-16 right-16 top-1/2 transform -translate-y-1/2 translate-y-3 pointer-events-none z-5">
                                    <div className="relative w-full h-0.5 overflow-hidden">
                                        {/* Main beam */}
                                        <div
                                            className={cn(
                                                "absolute w-full h-full top-1/2 transform -translate-y-1/2",
                                                "bg-gradient-to-r from-green-400/20 via-green-300/40 to-green-400/20"
                                            )}
                                            style={{
                                                animation: 'connectionBeam 3s ease-in-out infinite'
                                            }}
                                        />

                                        {/* Left endpoint pulse (Airweave side) */}
                                        <div
                                            className={cn(
                                                "absolute w-4 h-full top-1/2 transform -translate-y-1/2 left-0",
                                                "bg-gradient-to-r from-green-400/40 to-transparent rounded-l-full"
                                            )}
                                            style={{
                                                animation: 'beamEndpointPulse 3s ease-in-out infinite'
                                            }}
                                        />

                                        {/* Right endpoint pulse (Auth Provider side) */}
                                        <div
                                            className={cn(
                                                "absolute w-4 h-full top-1/2 transform -translate-y-1/2 right-0",
                                                "bg-gradient-to-l from-green-400/40 to-transparent rounded-r-full"
                                            )}
                                            style={{
                                                animation: 'beamEndpointPulse 3s ease-in-out infinite 1.5s'
                                            }}
                                        />
                                    </div>
                                </div>

                                {/* Animated Packet Container */}
                                <div className="absolute left-16 right-16 top-1/2 transform -translate-y-1/2 translate-y-3 pointer-events-none z-10">
                                    <div className="relative w-full h-0.5 overflow-hidden">
                                        {/* Primary packet */}
                                        <div
                                            className={cn(
                                                "absolute w-1.5 h-0.5 top-1/2 transform -translate-y-1/2 rounded-full",
                                                "shadow-sm",
                                                isDark
                                                    ? "bg-gradient-to-r from-green-400 to-green-300 shadow-green-400/50"
                                                    : "bg-gradient-to-r from-green-500 to-green-400 shadow-green-500/50"
                                            )}
                                            style={{
                                                animation: 'packetTravel 3s ease-in-out infinite'
                                            }}
                                        />

                                        {/* Secondary packet (staggered) */}
                                        <div
                                            className={cn(
                                                "absolute w-1.5 h-0.5 top-1/2 transform -translate-y-1/2 rounded-full",
                                                "shadow-sm",
                                                isDark
                                                    ? "bg-gradient-to-r from-green-300 to-green-200 shadow-green-300/40"
                                                    : "bg-gradient-to-r from-green-400 to-green-300 shadow-green-400/40"
                                            )}
                                            style={{
                                                animation: 'packetTravel2 3s ease-in-out infinite'
                                            }}
                                        />

                                        {/* Third packet (more staggered) */}
                                        <div
                                            className={cn(
                                                "absolute w-1.5 h-0.5 top-1/2 transform -translate-y-1/2 rounded-full",
                                                "shadow-sm",
                                                isDark
                                                    ? "bg-gradient-to-r from-green-200 to-green-100 shadow-green-200/30"
                                                    : "bg-gradient-to-r from-green-300 to-green-200 shadow-green-300/30"
                                            )}
                                            style={{
                                                animation: 'packetTravel3 3s ease-in-out infinite'
                                            }}
                                        />

                                        {/* Packet trail effects */}
                                        <div
                                            className={cn(
                                                "absolute w-1 h-0.25 top-1/2 transform -translate-y-1/2 rounded-full",
                                                "opacity-0",
                                                isDark
                                                    ? "bg-green-300/30"
                                                    : "bg-green-400/30"
                                            )}
                                            style={{
                                                left: '20%',
                                                animation: 'packetTrail 1.5s ease-out infinite'
                                            }}
                                        />
                                        <div
                                            className={cn(
                                                "absolute w-1 h-0.25 top-1/2 transform -translate-y-1/2 rounded-full",
                                                "opacity-0",
                                                isDark
                                                    ? "bg-green-300/30"
                                                    : "bg-green-400/30"
                                            )}
                                            style={{
                                                left: '60%',
                                                animation: 'packetTrail 1.5s ease-out infinite 0.75s'
                                            }}
                                        />
                                    </div>
                                </div>
                                {/* Airweave Logo */}
                                <div className="flex flex-col items-center gap-2">
                                    <div className="relative">
                                        <div className={cn(
                                            "w-16 h-16 rounded-xl flex items-center justify-center p-3",
                                            "transition-all duration-500 ease-in-out",
                                            isDark ? "bg-gray-800/50" : "bg-white/80",
                                            "shadow-lg ring-2 ring-green-400/30"
                                        )}>
                                            <img
                                                src={isDark ? "/airweave-logo-svg-white-darkbg.svg" : "/airweave-logo-svg-lightbg-blacklogo.svg"}
                                                alt="Airweave"
                                                className="w-full h-full object-contain"
                                                onError={(e) => {
                                                    e.currentTarget.style.display = 'none';
                                                    const parent = e.currentTarget.parentElement!;

                                                    // Create elements safely without innerHTML to prevent XSS
                                                    const wrapper = document.createElement('div');
                                                    wrapper.className = `w-full h-full rounded flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'}`;

                                                    const span = document.createElement('span');
                                                    span.className = `text-xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}`;
                                                    span.textContent = 'AW';

                                                    wrapper.appendChild(span);
                                                    parent.appendChild(wrapper);
                                                }}
                                            />
                                        </div>

                                        {/* Connection Icon - Bottom Right */}
                                        <div className="absolute -bottom-1 -right-1">
                                            <div className="relative">
                                                {/* Main Icon Container */}
                                                <div className={cn(
                                                    "w-5 h-5 rounded-full flex items-center justify-center border-2",
                                                    "transition-all duration-500 ease-in-out",
                                                    isDark ? "border-green-400 bg-gray-900" : "border-green-500 bg-white"
                                                )}
                                                    style={{
                                                        animation: 'unlockGlow 2s ease-in-out infinite, iconPing 3s ease-in-out infinite'
                                                    }}>
                                                    <Link className={cn(
                                                        "h-2.5 w-2.5",
                                                        isDark ? "text-green-400" : "text-green-500"
                                                    )}
                                                        style={{
                                                            animation: 'unlockKey 2s ease-in-out infinite',
                                                            transformOrigin: 'center'
                                                        }} />
                                                </div>

                                                {/* Glow Ring Animation */}
                                                <div className={cn(
                                                    "absolute inset-0 rounded-full border-2",
                                                    "animate-spin",
                                                    isDark ? "border-green-400/30" : "border-green-500/30"
                                                )}
                                                    style={{
                                                        animationDuration: '3s',
                                                        animationTimingFunction: 'linear'
                                                    }}
                                                />

                                                {/* Glow Ring Animation - Reverse */}
                                                <div className={cn(
                                                    "absolute inset-0 rounded-full border-2",
                                                    "animate-spin",
                                                    isDark ? "border-green-300/20" : "border-green-600/20"
                                                )}
                                                    style={{
                                                        animationDuration: '4s',
                                                        animationDirection: 'reverse',
                                                        animationTimingFunction: 'linear'
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Active Connection Text */}
                                <div className="flex items-center justify-center transform -translate-y-2">
                                    <p className={cn(
                                        "text-sm font-medium relative transition-all duration-500 ease-in-out",
                                        "bg-clip-text text-transparent",
                                        isDark
                                            ? "bg-gradient-to-r from-gray-400 via-white to-gray-400"
                                            : "bg-gradient-to-r from-gray-500 via-gray-900 to-gray-500"
                                    )}
                                        style={{
                                            backgroundSize: '200% 100%',
                                            animation: 'shimmerIntensify 3s ease-in-out infinite'
                                        }}>
                                        Active Connection
                                    </p>
                                </div>

                                {/* Auth Provider Logo */}
                                <div className="flex flex-col items-center gap-2">
                                    <div className="relative">
                                        <div className={cn(
                                            "w-16 h-16 rounded-xl flex items-center justify-center p-3",
                                            "transition-all duration-500 ease-in-out",
                                            isDark ? "bg-gray-800/50" : "bg-white/80",
                                            "shadow-lg ring-2 ring-green-400/30"
                                        )}>
                                            <img
                                                src={getAuthProviderIconUrl(authProviderShortName, resolvedTheme)}
                                                alt={authProviderName}
                                                className="w-full h-full object-contain"
                                                onError={(e) => {
                                                    e.currentTarget.style.display = 'none';
                                                    const parent = e.currentTarget.parentElement!;

                                                    // Create elements safely without innerHTML to prevent XSS
                                                    const wrapper = document.createElement('div');
                                                    wrapper.className = `w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'}`;

                                                    const span = document.createElement('span');
                                                    span.className = `text-xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}`;
                                                    span.textContent = authProviderShortName.substring(0, 2).toUpperCase();

                                                    wrapper.appendChild(span);
                                                    parent.appendChild(wrapper);
                                                }}
                                            />
                                        </div>

                                        {/* Connection Icon - Bottom Right */}
                                        <div className="absolute -bottom-1 -right-1">
                                            <div className="relative">
                                                {/* Main Icon Container */}
                                                <div className={cn(
                                                    "w-5 h-5 rounded-full flex items-center justify-center border-2",
                                                    "transition-all duration-500 ease-in-out",
                                                    isDark ? "border-green-400 bg-gray-900" : "border-green-500 bg-white"
                                                )}
                                                    style={{
                                                        animation: 'unlockGlow 2s ease-in-out infinite, iconPing 3s ease-in-out infinite'
                                                    }}>
                                                    <Link className={cn(
                                                        "h-2.5 w-2.5",
                                                        isDark ? "text-green-400" : "text-green-500"
                                                    )}
                                                        style={{
                                                            animation: 'unlockKey 2s ease-in-out infinite',
                                                            transformOrigin: 'center'
                                                        }} />
                                                </div>

                                                {/* Glow Ring Animation */}
                                                <div className={cn(
                                                    "absolute inset-0 rounded-full border-2",
                                                    "animate-spin",
                                                    isDark ? "border-green-400/30" : "border-green-500/30"
                                                )}
                                                    style={{
                                                        animationDuration: '3s',
                                                        animationTimingFunction: 'linear'
                                                    }}
                                                />

                                                {/* Glow Ring Animation - Reverse */}
                                                <div className={cn(
                                                    "absolute inset-0 rounded-full border-2",
                                                    "animate-spin",
                                                    isDark ? "border-green-300/20" : "border-green-600/20"
                                                )}
                                                    style={{
                                                        animationDuration: '4s',
                                                        animationDirection: 'reverse',
                                                        animationTimingFunction: 'linear'
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Connection Details - Clean minimal design */}
                    <div className="space-y-6">
                        {/* Name */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                Name
                            </label>
                            <div className={cn(
                                "w-full px-4 py-2.5 rounded-lg text-sm",
                                "border transition-colors",
                                isDark
                                    ? "bg-gray-800 border-gray-700 text-white"
                                    : "bg-white border-gray-200 text-gray-900"
                            )}>
                                {connectionDetails.name}
                            </div>
                        </div>

                        {/* Readable ID */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                Readable ID
                            </label>
                            <div className={cn(
                                "w-full px-4 py-2.5 rounded-lg text-sm flex items-center justify-between group",
                                "border transition-colors",
                                isDark
                                    ? "bg-gray-800 border-gray-700 text-white"
                                    : "bg-white border-gray-200 text-gray-900"
                            )}>
                                <span className="font-mono text-sm break-all">{connectionDetails.readable_id}</span>
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
                                        <Check className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <Copy className="h-4 w-4 text-gray-400" />
                                    )}
                                </button>
                            </div>
                        </div>

                        {/* Created By */}
                        {connectionDetails.created_by_email && (
                            <div>
                                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                    Created By
                                </label>
                                <div className={cn(
                                    "w-full px-4 py-2.5 rounded-lg text-sm",
                                    "border transition-colors",
                                    isDark
                                        ? "bg-gray-800 border-gray-700 text-white"
                                        : "bg-white border-gray-200 text-gray-900"
                                )}>
                                    {connectionDetails.created_by_email}
                                </div>
                            </div>
                        )}

                        {/* Created At */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                Created At
                            </label>
                            <div className={cn(
                                "w-full px-4 py-2.5 rounded-lg text-sm",
                                "border transition-colors",
                                isDark
                                    ? "bg-gray-800 border-gray-700 text-white"
                                    : "bg-white border-gray-200 text-gray-900"
                            )}>
                                {formatDate(connectionDetails.created_at)}
                            </div>
                        </div>

                        {/* Modified By */}
                        {connectionDetails.modified_by_email && (
                            <div>
                                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                    Modified By
                                </label>
                                <div className={cn(
                                    "w-full px-4 py-2.5 rounded-lg text-sm",
                                    "border transition-colors",
                                    isDark
                                        ? "bg-gray-800 border-gray-700 text-white"
                                        : "bg-white border-gray-200 text-gray-900"
                                )}>
                                    {connectionDetails.modified_by_email}
                                </div>
                            </div>
                        )}

                        {/* Modified At */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                Modified At
                            </label>
                            <div className={cn(
                                "w-full px-4 py-2.5 rounded-lg text-sm",
                                "border transition-colors",
                                isDark
                                    ? "bg-gray-800 border-gray-700 text-white"
                                    : "bg-white border-gray-200 text-gray-900"
                            )}>
                                {formatDate(connectionDetails.modified_at)}
                            </div>
                        </div>

                        {/* Client ID (if available for OAuth providers like Pipedream) */}
                        {connectionDetails.masked_client_id && (
                            <div>
                                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                                    Client ID
                                </label>
                                <div className={cn(
                                    "w-full px-4 py-2.5 rounded-lg text-sm flex items-center justify-between group",
                                    "border transition-colors",
                                    isDark
                                        ? "bg-gray-800 border-gray-700 text-white"
                                        : "bg-white border-gray-200 text-gray-900"
                                )}>
                                    <span className="font-mono text-sm">{connectionDetails.masked_client_id}</span>
                                    <button
                                        onClick={() => handleCopy(connectionDetails.masked_client_id, "Client ID")}
                                        className={cn(
                                            "p-1 rounded transition-opacity opacity-0 group-hover:opacity-100",
                                            isDark
                                                ? "hover:bg-gray-700/50"
                                                : "hover:bg-gray-200/50"
                                        )}
                                    >
                                        {copiedField === "Client ID" ? (
                                            <Check className="h-4 w-4 text-green-500" />
                                        ) : (
                                            <Copy className="h-4 w-4 text-gray-400" />
                                        )}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Bottom actions - minimal and clean */}
            <div className="px-8 py-6 border-t border-gray-200 dark:border-gray-800">
                <button
                    onClick={onCancel}
                    className={cn(
                        "w-full py-2.5 px-4 rounded-lg text-sm font-medium transition-all duration-150",
                        "border",
                        isDark
                            ? "bg-gray-800 border-gray-700 text-gray-100 hover:bg-gray-700"
                            : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"
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
