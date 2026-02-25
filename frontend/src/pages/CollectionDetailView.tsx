import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Alert } from "@/components/ui/alert";
import { AlertCircle, RefreshCw, Pencil, Trash, Plus, Clock, Play, Plug, Copy, Check, Loader2, RotateCw, AlertTriangle } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useUsageStore } from "@/lib/stores/usage";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { StatusBadge, statusConfig } from "@/components/ui/StatusBadge";
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
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import SourceConnectionStateView from "@/components/collection/SourceConnectionStateView";
import { emitCollectionEvent, onCollectionEvent, COLLECTION_DELETED, SOURCE_CONNECTION_UPDATED } from "@/lib/events";
import { Search } from '@/search/Search';
// import { DialogFlow } from '@/components/shared'; // TODO: Implement DialogFlow component
import { protectedPaths } from "@/constants/paths";
import { useEntityStateStore } from "@/stores/entityStateStore";
import { useSidePanelStore } from "@/lib/stores/sidePanelStore";
import { useCollectionCreationStore } from "@/stores/collectionCreationStore";
import { redirectWithError } from "@/lib/error-utils";
import { SingleActionCheckResponse } from "@/types";
import { DESIGN_SYSTEM } from "@/lib/design-system";


interface DeleteCollectionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void;
    collectionReadableId: string;
    confirmText: string;
    setConfirmText: (text: string) => void;
}

const DeleteCollectionDialog = ({
    open,
    onOpenChange,
    onConfirm,
    collectionReadableId,
    confirmText,
    setConfirmText
}: DeleteCollectionDialogProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const isConfirmValid = confirmText === collectionReadableId;

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
                                Delete Collection
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
                                    <span>The collection and all its source connections</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                                    <span>All synced data from the knowledge base</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                                    <span>All sync history and configuration</span>
                                </li>
                            </ul>
                        </div>

                        {/* Confirmation input */}
                        <div className="space-y-3">
                            <div>
                                <label htmlFor="confirm-delete" className="text-sm font-medium text-foreground block mb-2">
                                    Type <span className="font-mono font-semibold text-destructive bg-destructive/10 px-1.5 py-0.5 rounded">
                                        {collectionReadableId}
                                    </span> to confirm deletion
                                </label>
                                <Input
                                    id="confirm-delete"
                                    value={confirmText}
                                    onChange={(e) => setConfirmText(e.target.value)}
                                    className={cn(
                                        "w-full transition-colors",
                                        isConfirmValid && confirmText.length > 0
                                            ? "border-green-500 focus:border-green-500 focus:ring-green-500/20"
                                            : confirmText.length > 0
                                                ? "border-destructive focus:border-destructive focus:ring-destructive/20"
                                                : ""
                                    )}
                                    placeholder={collectionReadableId}
                                />
                            </div>

                            {/* Validation feedback */}
                            {confirmText.length > 0 && (
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
                    <AlertDialogCancel className="flex-1">
                        Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                        onClick={onConfirm}
                        disabled={!isConfirmValid}
                        className={cn(
                            "flex-1 bg-destructive text-destructive-foreground hover:bg-destructive/90",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "transition-all duration-200"
                        )}
                    >
                        <Trash className="w-4 h-4 mr-2" />
                        Delete Collection
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
};

interface Collection {
    name: string;
    readable_id: string;
    id: string;
    created_at: string;
    modified_at: string;
    organization_id: string;
    created_by_email: string;
    modified_by_email: string;
    status?: string;
}

interface SourceConnection {
    id: string;
    name: string;
    description?: string;
    short_name: string;
    readable_collection_id: string;
    config_fields?: Record<string, any>;
    sync_id?: string;
    organization_id: string;
    created_at: string;
    modified_at: string;
    connection_id?: string;
    collection: string;
    created_by_email: string;
    modified_by_email: string;
    auth_fields?: Record<string, any> | string;
    status?: string;
    is_authenticated?: boolean;
    authentication_url?: string;
    last_sync_job_status?: string;
    last_sync_job_id?: string;
    last_sync_job_started_at?: string;
    last_sync_job_completed_at?: string;
    cron_schedule?: string;
    federated_search?: boolean;  // Whether this source uses federated search
}

const Collections = () => {
    /********************************************
     * COMPONENT STATE
     ********************************************/
    const { readable_id } = useParams();
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams(); // Use setSearchParams to clean URL
    const isFromOAuthSuccess = searchParams.get("status") === "success";

    // Entity state store for new architecture
    const entityStateStore = useEntityStateStore();

    // Side panel store
    const { isOpen: isPanelOpen, openPanel } = useSidePanelStore();

    // Collection creation store to track modal state
    const { isOpen: isCreationModalOpen } = useCollectionCreationStore();

    // Page state
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isReloading, setIsReloading] = useState(false);

    // Collection state
    const [collection, setCollection] = useState<Collection | null>(null);
    const [isEditingName, setIsEditingName] = useState(false);
    const nameInputRef = useRef<HTMLDivElement>(null);

    // Source connection state
    const [sourceConnections, setSourceConnections] = useState<SourceConnection[]>([]);
    const [selectedConnection, setSelectedConnection] = useState<SourceConnection | null>(null);

    // Add state for delete dialog
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [confirmText, setConfirmText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);

    // Add state for copy animation
    const [isCopied, setIsCopied] = useState(false);

    // Add state for refreshing all sources
    const [isRefreshingAll, setIsRefreshingAll] = useState(false);
    const [refreshingSourceIds, setRefreshingSourceIds] = useState<string[]>([]);

    // Usage check from store (read-only, checking happens at app level)
    const actionChecks = useUsageStore(state => state.actionChecks);
    const isCheckingUsage = useUsageStore(state => state.isLoading);

    // Derived states from usage store
    const sourceConnectionsAllowed = actionChecks.source_connections?.allowed ?? true;
    const sourceConnectionCheckDetails = actionChecks.source_connections ?? null;
    const entitiesAllowed = actionChecks.entities?.allowed ?? true;
    const entitiesCheckDetails = actionChecks.entities ?? null;

    /********************************************
     * API AND DATA FETCHING FUNCTIONS
     ********************************************/

    // Fetch source connections for a collection with detailed sync job status
    const fetchSourceConnections = async (collectionId: string) => {
        try {
            console.log("Fetching source connections for collection:", collectionId);
            const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);

            if (response.ok) {
                const listData = await response.json();
                console.log("Loaded source connection list:", listData);

                // Fetch detailed data for each connection to get sync job status
                const detailedConnections = await Promise.all(
                    listData.map(async (connection: any) => {
                        try {
                            const detailResponse = await apiClient.get(`/source-connections/${connection.id}`);
                            if (detailResponse.ok) {
                                const detailedData = await detailResponse.json();
                                console.log(`📝 Fetched detailed data for ${connection.name}:`, {
                                    last_sync_job_status: detailedData.last_sync_job_status,
                                    last_sync_job_id: detailedData.last_sync_job_id
                                });
                                return detailedData;
                            } else {
                                console.warn(`Failed to fetch details for connection ${connection.id}`);
                                return connection; // fallback to list data
                            }
                        } catch (err) {
                            console.warn(`Error fetching details for connection ${connection.id}:`, err);
                            return connection; // fallback to list data
                        }
                    })
                );

                setSourceConnections(detailedConnections);

                // Entity state mediator will handle subscriptions automatically

                // Always select the first connection when loading a new collection
                if (detailedConnections.length > 0) {
                    // if a source connection was just added, select that one
                    const newSourceId = searchParams.get("source_connection_id");
                    const newConnection = newSourceId ? detailedConnections.find(c => c.id === newSourceId) : null;
                    if (newConnection) {
                        setSelectedConnection(newConnection);
                    } else {
                        setSelectedConnection(detailedConnections[0]);
                    }
                } else {
                    // If no connections, ensure selectedConnection is null
                    setSelectedConnection(null);
                    console.log("No connections to select");
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
        } finally {
            setIsLoading(false);
        }
    };

    // Update the existing fetchCollection function to use our new function
    const fetchCollection = async () => {
        if (!readable_id) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await apiClient.get(`/collections/${readable_id}`);

            if (response.ok) {
                const data = await response.json();
                setCollection(data);
                // After successful collection fetch, fetch source connections
                fetchSourceConnections(data.readable_id);
            } else {
                if (response.status === 404) {
                    setError("Collection not found");
                } else {
                    const errorText = await response.text();
                    setError(`Failed to load collection: ${errorText}`);
                }
                setIsLoading(false);
            }
        } catch (err) {
            setError(`An error occurred: ${err instanceof Error ? err.message : String(err)}`);
            setIsLoading(false);
        }
    };

    // ** NEW: Handle OAuth callback and toast notification **
    useEffect(() => {
        if (isFromOAuthSuccess) {
            const newSourceId = searchParams.get("source_connection_id");

            // Always refresh source connections when returning from OAuth
            if (collection?.readable_id) {
                fetchSourceConnections(collection.readable_id);
            }

            if (newSourceId && sourceConnections.length > 0) {
                const newConnection = sourceConnections.find(c => c.id === newSourceId);
                if (newConnection) {
                    toast({
                        title: "Success",
                        description: `Source "${newConnection.name}" connected successfully!`
                    });
                }
            }

            // Clean up URL params
            const newSearchParams = new URLSearchParams(searchParams);
            newSearchParams.delete("status");
            newSearchParams.delete("source_connection_id");
            newSearchParams.delete("collection");
            setSearchParams(newSearchParams, { replace: true });
        }
    }, [isFromOAuthSuccess, collection?.readable_id, searchParams, setSearchParams]);

    // ** NEW: Refresh connections when panel or creation modal closes, in case a new one was added **
    useEffect(() => {
        if (!isPanelOpen && !isCreationModalOpen) {
            if (collection?.readable_id) {
                fetchSourceConnections(collection.readable_id);
            }
        }
    }, [isPanelOpen, isCreationModalOpen, collection?.readable_id]);


    /********************************************
     * UI EVENT HANDLERS
     ********************************************/

    // ** MODIFIED: Trigger the modal for adding source to existing collection **
    const handleAddSource = () => {
        if (collection) {
            const store = useCollectionCreationStore.getState();
            store.openForAddToCollection(collection.readable_id, collection.name);
        }
    };

    // Update selected connection
    const handleSelectConnection = async (connection: SourceConnection) => {
        console.log("Manually selecting connection:", connection.id);
        setSelectedConnection(connection);
    };

    // Handle name editing
    const startEditingName = () => {
        setIsEditingName(true);
        setTimeout(() => {
            if (nameInputRef.current) {
                nameInputRef.current.innerText = collection?.name || "";
                // Place cursor at the end of text
                const range = document.createRange();
                const selection = window.getSelection();
                const textNode = nameInputRef.current.firstChild || nameInputRef.current;
                const textLength = nameInputRef.current.innerText.length;

                // Position at the end of text
                range.setStart(textNode, textLength);
                range.setEnd(textNode, textLength);

                if (selection) {
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
                nameInputRef.current.focus();
            }
        }, 0);
    };

    const handleSaveNameChange = async () => {
        const newName = nameInputRef.current?.innerText.trim() || "";

        if (!newName || newName === collection?.name) {
            setIsEditingName(false);
            return;
        }

        try {
            const response = await apiClient.patch(`/collections/${readable_id}`, { name: newName });
            if (!response.ok) throw new Error("Failed to update collection name");

            // Update local state after successful API call
            setCollection(prev => prev ? { ...prev, name: newName } : null);
            setIsEditingName(false);

            toast({
                title: "Success",
                description: "Collection name updated successfully"
            });
        } catch (error) {
            console.error("Error updating collection name:", error);
            toast({
                title: "Error",
                description: "Failed to update collection name",
                variant: "destructive"
            });
            setIsEditingName(false);
        }
    };

    // Handle copy to clipboard
    const handleCopyId = () => {
        if (collection?.readable_id) {
            navigator.clipboard.writeText(collection.readable_id);
            setIsCopied(true);

            // Reset after animation completes
            setTimeout(() => {
                setIsCopied(false);
            }, 1500);

            toast({
                title: "Copied",
                description: "ID copied to clipboard"
            });
        }
    };

    /********************************************
     * UTILITY FUNCTIONS
     ********************************************/

    // Reload data
    const reloadData = async () => {
        if (!readable_id) return;

        setIsReloading(true);
        try {
            await fetchCollection();
        } finally {
            setIsReloading(false);
        }
    };

    /********************************************
     * SIDE EFFECTS
     ********************************************/

    // Initial data loading
    useEffect(() => {
        console.log(`\nFetching collection because of readable id change\n`)
        setSelectedConnection(null);
        fetchCollection();
    }, [readable_id]); // Only depend on readable_id

    // Usage is now checked at app level by UsageChecker component

    // Handle collection deletion
    const handleDeleteCollection = async () => {
        if (!readable_id || confirmText !== readable_id) return;

        setIsDeleting(true);
        try {
            const response = await apiClient.delete(`/collections/${readable_id}`);

            if (response.ok) {
                // Emit event that collection was deleted
                emitCollectionEvent(COLLECTION_DELETED, { id: readable_id });

                toast({
                    title: "Success",
                    description: "Collection and all associated data deleted successfully"
                });
                // Navigate back to dashboard after successful deletion
                navigate(protectedPaths.dashboard);
            } else {
                const errorText = await response.text();
                throw new Error(`Failed to delete collection: ${errorText}`);
            }
        } catch (err) {
            console.error("Error deleting collection:", err);
            toast({
                title: "Error",
                description: err instanceof Error ? err.message : "Failed to delete collection",
                variant: "destructive"
            });
        } finally {
            setIsDeleting(false);
            setShowDeleteDialog(false);
            setConfirmText(''); // Reset confirm text
        }
    };

    // Entity state mediator handles its own cleanup

    // Listen for source connection updates
    useEffect(() => {
        const unsubscribe = onCollectionEvent(SOURCE_CONNECTION_UPDATED, (data) => {
            console.log("Source connection updated:", data);

            // Always refresh the list from server to ensure consistency
            if (collection?.readable_id) {
                fetchSourceConnections(collection.readable_id);
            }

            // If the deleted connection was selected, clear the selection
            // The fetchSourceConnections will auto-select the first connection if any remain
            if (data.deleted && selectedConnection?.id === data.id) {
                setSelectedConnection(null);
            }
        });

        return unsubscribe;
    }, [collection?.readable_id, selectedConnection?.id]);

    // Add right before the source connections section in render
    useEffect(() => {
        console.log("Source connections state:", {
            count: sourceConnections.length,
            connections: sourceConnections,
            selectedId: selectedConnection?.id
        });
    }, [sourceConnections, selectedConnection]);

    // Add this in the Source Connections Section right above the mapping
    console.log("Rendering source connections section", {
        count: sourceConnections.length,
        selectedId: selectedConnection?.id
    });

    // Get connection status indicator based on connection state
    const getConnectionStatusIndicator = (connection: SourceConnection) => {
        // Detect federated sources based on the federated_search field
        const isFederated = connection.federated_search === true;

        // Use the connection's status directly from the API response
        let colorClass = "bg-gray-400";
        let status = "unknown";
        let isAnimated = false;

        // Federated sources have simpler status logic
        if (isFederated) {
            switch (connection.status) {
                case 'pending_auth':
                    colorClass = "bg-cyan-500";
                    status = "Authentication required";
                    break;
                case 'error':
                    colorClass = "bg-red-500";
                    status = "Connection error";
                    break;
                case 'inactive':
                    colorClass = "bg-gray-400";
                    status = "Inactive";
                    break;
                case 'active':
                default:
                    colorClass = "bg-green-500";
                    status = "Ready for real-time search";
                    break;
            }
        } else {
            // Map the backend SourceConnectionStatus enum values for regular sources
            switch (connection.status) {
                case 'pending_auth':
                    colorClass = "bg-cyan-500";
                    status = "Authentication required";
                    break;
                case 'syncing':
                    colorClass = "bg-blue-500";
                    status = "Syncing";
                    isAnimated = true;
                    break;
                case 'error':
                    colorClass = "bg-red-500";
                    status = "Sync failed";
                    break;
                case 'active':
                    colorClass = "bg-green-500";
                    status = "Active";
                    break;
                case 'inactive':
                    colorClass = "bg-gray-400";
                    status = "Inactive";
                    break;
                default:
                    // Fallback for unknown status
                    colorClass = "bg-gray-400";
                    status = "Unknown";
            }
        }

        return (
            <span
                className={cn(
                    "inline-flex h-2 w-2 rounded-full opacity-80",
                    colorClass,
                    isAnimated && "animate-pulse"
                )}
                title={status}
            />
        );
    };

    if (error) {
        return (
            <div className="container mx-auto py-6">
                <h1 className="text-3xl font-bold mb-6 text-foreground">Collection Error</h1>
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <div className="font-medium">Error</div>
                    <div>{error}</div>
                </Alert>
                <div className="mt-4">
                    <Button onClick={() => navigate(protectedPaths.dashboard)}>
                        Return to Dashboard
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className={cn(
            "container mx-auto py-6 flex flex-col items-center",
            isDark ? "text-foreground" : ""
        )}>
            {/* Show loading state when isLoading or no collection data yet */}
            {(isLoading || !collection) && !error ? (
                <div className="w-full h-48 flex flex-col items-center justify-center space-y-4">
                    <Loader2 className="h-10 w-10 animate-spin text-primary" />
                    <p className="text-muted-foreground">Loading collection data...</p>
                </div>
            ) : (
                <>
                    {/* Header with Title and Status Badge */}
                    <div className="w-full max-w-[1000px] flex items-center justify-between py-4">
                        <div className="flex items-center gap-3">
                            {/* Source Icons */}
                            <div className="flex justify-start items-center" style={{ minWidth: "3.5rem" }}>
                                {sourceConnections.slice(0, 3).map((connection, index) => (
                                    <div
                                        key={connection.id}
                                        className={cn(
                                            "w-12 h-12 rounded-md border p-1 flex items-center justify-center overflow-hidden",
                                            isDark ? "bg-gray-900 border-border" : "bg-white border-border"
                                        )}
                                        style={{
                                            marginLeft: index > 0 ? `-${Math.min(index * 8, 24)}px` : "0px",
                                            zIndex: 3 - index
                                        }}
                                    >
                                        <img
                                            src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                            alt={connection.name}
                                            className="max-w-full max-h-full w-auto h-auto object-contain"
                                        />
                                    </div>
                                ))}
                                {sourceConnections.length > 3 && (
                                    <div className="ml-2 text-sm font-medium text-slate-500 dark:text-slate-400">
                                        +{sourceConnections.length - 3}
                                    </div>
                                )}
                            </div>

                            <div className="flex flex-col justify-center">
                                {isEditingName ? (
                                    <div className="flex items-center gap-2">
                                        <div
                                            ref={nameInputRef}
                                            contentEditable
                                            className="text-3xl font-bold tracking-tight text-foreground outline-none p-1 pl-0 pr-3 rounded border border-border/40 transition-all duration-150"
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault();
                                                    handleSaveNameChange();
                                                }
                                                if (e.key === 'Escape') {
                                                    e.preventDefault();
                                                    setIsEditingName(false);
                                                }
                                            }}
                                            onBlur={handleSaveNameChange}
                                        />
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-2">
                                        <h1 className="text-2xl font-bold tracking-tight text-foreground py-1 pl-0">{collection?.name}</h1>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className={cn(
                                                DESIGN_SYSTEM.buttons.heights.compact,
                                                "w-6 text-muted-foreground hover:text-foreground"
                                            )}
                                            onClick={startEditingName}
                                        >
                                            <Pencil className={DESIGN_SYSTEM.icons.inline} />
                                        </Button>
                                        {collection?.status && (
                                            <StatusBadge status={collection.status} showTooltip={true} tooltipContext="collection" />
                                        )}
                                    </div>
                                )}
                                <p className="text-muted-foreground text-sm group relative flex items-center">
                                    {collection?.readable_id}
                                    <button
                                        className="ml-1.5 opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100 focus:outline-none"
                                        onClick={handleCopyId}
                                        title="Copy ID"
                                    >
                                        {isCopied ? (
                                            <Check className="h-3.5 w-3.5 text-muted-foreground  transition-all" />
                                        ) : (
                                            <Copy className="h-3.5 w-3.5 text-muted-foreground transition-all" />
                                        )}
                                    </button>
                                </p>
                            </div>
                        </div>

                        {/* Header action buttons */}
                        <div className="flex gap-1.5 items-center">
                            {/* Refresh Page Button - EXACT match to refresh source button */}
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <button
                                            type="button"
                                            onClick={reloadData}
                                            disabled={isReloading}
                                            className={cn(
                                                "h-8 w-8 rounded-md border shadow-sm flex items-center justify-center transition-all duration-200",
                                                isReloading
                                                    ? isDark
                                                        ? "bg-gray-900 border-border cursor-not-allowed"
                                                        : "bg-white border-border cursor-not-allowed"
                                                    : isDark
                                                        ? "bg-gray-900 border-border hover:bg-muted cursor-pointer"
                                                        : "bg-white border-border hover:bg-muted cursor-pointer"
                                            )}
                                        >
                                            <RotateCw className={cn(
                                                "h-3 w-3 text-muted-foreground",
                                                "transition-transform duration-500",
                                                isReloading && "animate-spin"
                                            )} />
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Reload page</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>

                            {/* Delete Collection Button - EXACT match to refresh button styling */}
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <button
                                            type="button"
                                            onClick={() => setShowDeleteDialog(true)}
                                            className={cn(
                                                "h-8 w-8 rounded-md border shadow-sm flex items-center justify-center transition-all duration-200",
                                                isDark
                                                    ? "bg-gray-900 border-border hover:bg-muted cursor-pointer"
                                                    : "bg-white border-border hover:bg-muted cursor-pointer"
                                            )}
                                        >
                                            <Trash className="h-3 w-3 text-muted-foreground" />
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Delete collection</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>
                    </div>



                    {/* Add Search component when collection has any synced data */}
                    {collection?.readable_id && (
                        <div className="w-full max-w-[1000px] mt-10">
                            <Search
                                collectionReadableId={collection.readable_id}
                                disabled={sourceConnections.length === 0}
                            />
                        </div>
                    )}



                    {/* Source Connections Section */}
                    <div className="w-full max-w-[1000px] mt-8">
                        {sourceConnections.length > 0 && (
                            <div className={cn("flex flex-wrap", DESIGN_SYSTEM.spacing.gaps.standard)}>
                                {sourceConnections.map((connection) => (
                                    <div
                                        key={connection.id}
                                        className={cn(
                                            DESIGN_SYSTEM.buttons.heights.primary,
                                            "flex items-center overflow-hidden flex-shrink-0 flex-grow-0 cursor-pointer",
                                            DESIGN_SYSTEM.spacing.gaps.standard,
                                            DESIGN_SYSTEM.buttons.padding.secondary,
                                            "py-2",
                                            DESIGN_SYSTEM.radius.button,
                                            DESIGN_SYSTEM.transitions.standard,
                                            selectedConnection?.id === connection.id
                                                ? isDark
                                                    ? "border border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/20 ring-2 ring-blue-500/30"
                                                    : "border border-blue-500 bg-blue-50 shadow-lg shadow-blue-500/20 ring-2 ring-blue-500/30"
                                                : isDark
                                                    ? "border border-gray-800/50 bg-gray-900 hover:bg-muted"
                                                    : "border border-gray-200/60 bg-white hover:bg-muted"
                                        )}
                                        onClick={() => handleSelectConnection(connection)}
                                    >
                                        {getConnectionStatusIndicator(connection)}

                                        <div className={cn(
                                            "rounded-md flex items-center justify-center overflow-hidden flex-shrink-0",
                                        )}>
                                            <img
                                                src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                                alt={connection.name}
                                                className={cn(DESIGN_SYSTEM.icons.large, "object-contain")}
                                            />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <span className={cn(
                                                DESIGN_SYSTEM.typography.sizes.header,
                                                DESIGN_SYSTEM.typography.weights.medium,
                                                "truncate block text-foreground"
                                            )}>{connection.name}</span>
                                        </div>
                                    </div>
                                ))}

                                {/* Add Source Button - Row (main UI + usage gating) */}
                                <TooltipProvider delayDuration={100}>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <div
                                                className={cn(
                                                    DESIGN_SYSTEM.buttons.heights.primary,
                                                    "flex items-center overflow-hidden flex-shrink-0 flex-grow-0 cursor-pointer",
                                                    DESIGN_SYSTEM.spacing.gaps.standard,
                                                    DESIGN_SYSTEM.buttons.padding.secondary,
                                                    "py-2",
                                                    DESIGN_SYSTEM.radius.button,
                                                    DESIGN_SYSTEM.transitions.standard,
                                                    "border border-dashed",
                                                    (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                        ? "opacity-50 cursor-not-allowed border-gray-300 dark:border-gray-700"
                                                        : isDark
                                                            ? "border-blue-500/30 bg-blue-500/5 hover:bg-blue-500/15 hover:border-blue-400/40"
                                                            : "border-blue-400/40 bg-blue-50/30 hover:bg-blue-50/70 hover:border-blue-400/50"
                                                )}
                                                onClick={(!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage) ? undefined : handleAddSource}
                                            >
                                                <Plus className={cn(
                                                    DESIGN_SYSTEM.icons.large,
                                                    (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                        ? "text-gray-400"
                                                        : isDark ? "text-blue-400" : "text-blue-500"
                                                )} strokeWidth={1.5} />
                                                <span className={cn(
                                                    DESIGN_SYSTEM.typography.sizes.header,
                                                    DESIGN_SYSTEM.typography.weights.medium,
                                                    "text-foreground"
                                                )}>Add Source</span>
                                            </div>
                                        </TooltipTrigger>
                                        {(!entitiesAllowed || !sourceConnectionsAllowed) && (
                                            <TooltipContent className="max-w-xs">
                                                <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Entity processing limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Source connection limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}for more connections.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                </p>
                                            </TooltipContent>
                                        )}
                                    </Tooltip>
                                </TooltipProvider>
                            </div>
                        )}

                        {sourceConnections.length === 0 && (
                            <div className={cn(
                                "flex flex-col items-center justify-center py-12 rounded-lg border-2 border-dashed",
                                isDark
                                    ? "border-gray-700 bg-gray-900/30"
                                    : "border-gray-200 bg-gray-50/50"
                            )}>
                                <div className={cn(
                                    "w-12 h-12 rounded-full flex items-center justify-center mb-4",
                                    isDark
                                        ? "bg-gray-800 border border-gray-700"
                                        : "bg-white border border-gray-200"
                                )}>
                                    <Plug className={cn(
                                        "h-6 w-6",
                                        isDark ? "text-gray-400" : "text-gray-500"
                                    )} strokeWidth={1.5} />
                                </div>

                                <h3 className={cn(
                                    "text-base font-medium mb-1",
                                    isDark ? "text-gray-200" : "text-gray-900"
                                )}>
                                    No sources connected
                                </h3>
                                <p className={cn(
                                    "text-sm mb-6 max-w-sm text-center",
                                    isDark ? "text-gray-400" : "text-gray-600"
                                )}>
                                    Connect your first data source to start syncing and searching your data
                                </p>

                                <TooltipProvider delayDuration={100}>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <span tabIndex={0}>
                                                <button
                                                    type="button"
                                                    className={cn(
                                                        "inline-flex items-center justify-center",
                                                        "h-9 px-4 py-2",
                                                        "text-sm font-medium",
                                                        "rounded-md",
                                                        "transition-all duration-200",
                                                        "border",
                                                        (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                            ? "opacity-50 cursor-not-allowed border-gray-300 bg-gray-100 text-gray-400"
                                                            : isDark
                                                                ? "border-blue-500 bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 hover:border-blue-400"
                                                                : "border-blue-500 bg-blue-50 text-blue-600 hover:bg-blue-100 hover:border-blue-600"
                                                    )}
                                                    onClick={(!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage) ? undefined : handleAddSource}
                                                    disabled={!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage}
                                                >
                                                    <Plus className="h-4 w-4 mr-1.5" strokeWidth={2} />
                                                    Connect a source
                                                </button>
                                            </span>
                                        </TooltipTrigger>
                                        {(!entitiesAllowed || !sourceConnectionsAllowed) && (
                                            <TooltipContent className="max-w-xs">
                                                <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Entity processing limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Source connection limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}for more connections.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                </p>
                                            </TooltipContent>
                                        )}
                                    </Tooltip>
                                </TooltipProvider>
                            </div>
                        )}
                    </div>

                    {/* NEW: Render SourceConnectionStateView instead of the old DAG view */}
                    {selectedConnection && (
                        <div className="mt-4 w-full max-w-[1000px]">
                            <SourceConnectionStateView
                                key={selectedConnection.id}
                                sourceConnectionId={selectedConnection.id}
                                sourceConnectionData={selectedConnection}
                                collectionId={collection?.readable_id}
                                collectionName={collection?.name}
                                onConnectionDeleted={() => {
                                    // Clear selection and reload connections
                                    setSelectedConnection(null);
                                    if (collection?.readable_id) {
                                        fetchSourceConnections(collection.readable_id);
                                    }
                                }}
                                onConnectionUpdated={() => {
                                    // Refresh the connection data
                                    if (collection?.readable_id) {
                                        fetchSourceConnections(collection.readable_id);
                                    }
                                }}
                            />
                        </div>
                    )}

                    {/* Delete Collection Dialog */}
                    <DeleteCollectionDialog
                        open={showDeleteDialog}
                        onOpenChange={setShowDeleteDialog}
                        onConfirm={handleDeleteCollection}
                        collectionReadableId={collection?.readable_id || ''}
                        confirmText={confirmText}
                        setConfirmText={setConfirmText}
                    />

                </>
            )}
        </div>
    );
};

export default Collections;
