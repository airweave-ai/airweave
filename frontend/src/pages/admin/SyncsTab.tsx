import { useState } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Search, Copy, XCircle, Trash2, CalendarX, AlertCircle, RefreshCw, X } from 'lucide-react';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { SyncConfig, SyncPreset, SYNC_PRESETS, getPresetConfig } from '@/types/sync-config';

interface SyncInfo {
    id: string;
    name: string;
    organization_id: string;
    status: string;
    readable_collection_id?: string;
    source_short_name?: string;
    source_is_authenticated?: boolean;
    total_entity_count?: number;
    total_arf_entity_count?: number;
    total_vespa_entity_count?: number;
    last_job_status?: string;
    last_job_at?: string;
    last_job_error?: string;
    all_tags?: string[];
    created_at: string;
}

interface OrganizationMap {
    [key: string]: {
        name: string;
        id: string;
    };
}

interface OrganizationMetrics {
    id: string;
    name: string;
}

interface SyncFilters {
    syncIds: string;
    organizationId: string;
    collectionId: string;
    sourceType: string;
    status: string;
    lastJobStatus: string;
    isAuthenticated: string;
    ghostSyncsOnly: boolean;
    includeDestinationCounts: boolean;
    includeArfCounts: boolean;
    tags: string;
    excludeTags: string;
    limit: number;
}

export function SyncsTab() {
    const [syncs, setSyncs] = useState<SyncInfo[]>([]);
    const [isSyncsLoading, setIsSyncsLoading] = useState(false);
    const [syncFilters, setSyncFilters] = useState<SyncFilters>({
        syncIds: '',
        organizationId: '',
        collectionId: '',
        sourceType: '',
        status: 'all',
        lastJobStatus: 'all',
        isAuthenticated: 'all',
        ghostSyncsOnly: false,
        includeDestinationCounts: false,
        includeArfCounts: false,
        tags: '',
        excludeTags: '',
        limit: 100,
    });
    const [organizationMap, setOrganizationMap] = useState<OrganizationMap>({});
    const [cancellingSync, setCancellingSync] = useState<string | null>(null);
    const [deletingSync, setDeletingSync] = useState<string | null>(null);
    const [resyncDialogOpen, setResyncDialogOpen] = useState(false);
    const [bulkResyncDialogOpen, setBulkResyncDialogOpen] = useState(false);
    const [selectedSyncs, setSelectedSyncs] = useState<Set<string>>(new Set());
    const [resyncingSync, setResyncingSync] = useState<{ id: string; name: string } | null>(null);
    const [selectedPreset, setSelectedPreset] = useState<SyncPreset>('default');
    const [resyncConfig, setResyncConfig] = useState<SyncConfig>(getPresetConfig('default'));
    const [resyncTags, setResyncTags] = useState<string[]>([]);
    const [tagInput, setTagInput] = useState<string>('');

    const loadSyncs = async () => {
        setIsSyncsLoading(true);
        try {
            const params = new URLSearchParams();
            params.append('limit', syncFilters.limit.toString());

            if (syncFilters.syncIds.trim()) {
                params.append('sync_ids', syncFilters.syncIds.trim());
            }
            if (syncFilters.organizationId.trim()) {
                params.append('organization_id', syncFilters.organizationId.trim());
            }
            if (syncFilters.collectionId.trim()) {
                params.append('collection_id', syncFilters.collectionId.trim());
            }
            if (syncFilters.sourceType.trim()) {
                params.append('source_type', syncFilters.sourceType.trim());
            }
            if (syncFilters.status !== 'all') {
                params.append('status', syncFilters.status);
            }
            if (syncFilters.lastJobStatus !== 'all') {
                params.append('last_job_status', syncFilters.lastJobStatus);
            }
            if (syncFilters.isAuthenticated !== 'all') {
                params.append('is_authenticated', syncFilters.isAuthenticated);
            }
            if (syncFilters.ghostSyncsOnly) {
                params.append('ghost_syncs_last_n', '5');
            }
            if (syncFilters.includeDestinationCounts) {
                params.append('include_destination_counts', 'true');
            }
            if (syncFilters.includeArfCounts) {
                params.append('include_arf_counts', 'true');
            }
            if (syncFilters.tags.trim()) {
                params.append('tags', syncFilters.tags.trim());
            }
            if (syncFilters.excludeTags.trim()) {
                params.append('exclude_tags', syncFilters.excludeTags.trim());
            }

            const response = await apiClient.get(`/admin/syncs?${params.toString()}`);

            if (!response.ok) {
                throw new Error(`Failed to load syncs: ${response.status}`);
            }

            const data = await response.json();
            setSyncs(data);

            const uniqueOrgIds = [...new Set(data.map((s: SyncInfo) => s.organization_id))] as string[];
            await fetchOrganizationNames(uniqueOrgIds);

            toast.success(`Loaded ${data.length} sync(s)`);
        } catch (error) {
            console.error('Failed to load syncs:', error);
            toast.error('Failed to load syncs');
            setSyncs([]);
        } finally {
            setIsSyncsLoading(false);
        }
    };

    const fetchOrganizationNames = async (orgIds: string[]) => {
        try {
            const response = await apiClient.get('/admin/organizations?limit=10000');
            if (response.ok) {
                const allOrgs = await response.json();
                const map: OrganizationMap = {};
                allOrgs.forEach((org: OrganizationMetrics) => {
                    map[org.id] = {
                        name: org.name,
                        id: org.id,
                    };
                });
                setOrganizationMap(map);
            }
        } catch (error) {
            console.error('Failed to fetch organization names:', error);
        }
    };

    const copyToClipboard = (text: string, label: string) => {
        navigator.clipboard.writeText(text);
        toast.success(`${label} copied to clipboard`);
    };

    const formatNumber = (num: number) => {
        return num.toLocaleString('en-US');
    };

    // Selection handlers
    const toggleSelectAll = () => {
        if (selectedSyncs.size === syncs.length) {
            setSelectedSyncs(new Set());
        } else {
            setSelectedSyncs(new Set(syncs.map(s => s.id)));
        }
    };

    const toggleSelectSync = (syncId: string) => {
        const newSelected = new Set(selectedSyncs);
        if (newSelected.has(syncId)) {
            newSelected.delete(syncId);
        } else {
            newSelected.add(syncId);
        }
        setSelectedSyncs(newSelected);
    };

    const getSelectedSyncsDetails = () => {
        return syncs.filter(s => selectedSyncs.has(s.id));
    };

    // Bulk action handlers
    const openBulkResyncDialog = () => {
        setBulkResyncDialogOpen(true);
    };

    const handleBulkResync = async () => {
        const selected = getSelectedSyncsDetails();

        toast.info(`Triggering resync for ${selected.length} sync(s)...`);
        let successful = 0;
        let failed = 0;

        // Use nested SyncConfig structure
        for (const sync of selected) {
            try {
                const response = await apiClient.post(`/admin/resync/${sync.id}`, resyncConfig);

                if (response.ok) {
                    successful++;
                } else {
                    failed++;
                }
            } catch (error) {
                failed++;
                console.error(`Failed to resync ${sync.name}:`, error);
            }
        }

        if (failed > 0) {
            toast.warning(`Triggered ${successful}/${selected.length} resyncs. ${failed} failed.`);
        } else {
            toast.success(`Successfully triggered ${successful} resync(s)`);
        }

        setBulkResyncDialogOpen(false);
        setSelectedSyncs(new Set());
        await loadSyncs();
    };

    const handleBulkCancel = async () => {
        const selected = getSelectedSyncsDetails();
        if (!confirm(`Cancel all active jobs for ${selected.length} sync(s)?`)) {
            return;
        }

        toast.info(`Cancelling jobs for ${selected.length} sync(s)...`);
        let totalCancelled = 0;
        let totalFailed = 0;

        for (const sync of selected) {
            try {
                const response = await apiClient.post(`/admin/syncs/${sync.id}/cancel`);
                if (response.ok) {
                    const result = await response.json();
                    totalCancelled += result.cancelled;
                    totalFailed += result.failed;
                }
            } catch (error) {
                console.error(`Failed to cancel jobs for ${sync.name}:`, error);
            }
        }

        if (totalCancelled > 0) {
            toast.success(`Cancelled ${totalCancelled} job(s)`);
        } else {
            toast.info('No active jobs to cancel');
        }

        if (totalFailed > 0) {
            toast.warning(`${totalFailed} job(s) failed to cancel`);
        }

        setSelectedSyncs(new Set());
        await loadSyncs();
    };

    const handleBulkDelete = async () => {
        const selected = getSelectedSyncsDetails();
        const confirmMessage = `⚠️ DELETE ${selected.length} SYNC(S)?\n\nThis will permanently delete ALL data including:\n• Vespa data\n• ARF storage\n• All jobs and schedules\n\n⚠️ THIS CANNOT BE UNDONE!\n\nType DELETE to confirm:`;

        const userInput = prompt(confirmMessage);
        if (userInput !== 'DELETE') {
            if (userInput !== null) {
                toast.error('Deletion cancelled.');
            }
            return;
        }

        toast.info(`Deleting ${selected.length} sync(s)...`);
        let successful = 0;
        let failed = 0;

        for (const sync of selected) {
            try {
                const response = await apiClient.delete(`/admin/syncs/${sync.id}`);
                if (response.ok) {
                    successful++;
                } else {
                    failed++;
                }
            } catch (error) {
                failed++;
                console.error(`Failed to delete ${sync.name}:`, error);
            }
        }

        if (failed > 0) {
            toast.warning(`Deleted ${successful}/${selected.length} sync(s). ${failed} failed.`);
        } else {
            toast.success(`Successfully deleted ${successful} sync(s)`);
        }

        setSelectedSyncs(new Set());
        await loadSyncs();
    };

    const handleCancelSync = async (syncId: string, syncName: string) => {
        if (!confirm(`Cancel all active jobs for sync "${syncName}"?\n\nThis will cancel all pending and running jobs for this sync.`)) {
            return;
        }

        setCancellingSync(syncId);
        try {
            const response = await apiClient.post(`/admin/syncs/${syncId}/cancel`);

            if (!response.ok) {
                const error = await response.text();
                throw new Error(error || 'Failed to cancel sync');
            }

            const result = await response.json();

            if (result.cancelled === 0 && result.total_jobs === 0) {
                toast.info('No active jobs to cancel');
            } else if (result.failed > 0) {
                toast.warning(`Cancelled ${result.cancelled}/${result.total_jobs} job(s). ${result.failed} failed.`);
            } else {
                toast.success(`Successfully cancelled ${result.cancelled} job(s)`);
            }

            // Optionally refresh the syncs list to show updated job statuses
            if (syncs.length > 0) {
                await loadSyncs();
            }
        } catch (error) {
            console.error('Failed to cancel sync:', error);
            toast.error(error instanceof Error ? error.message : 'Failed to cancel sync');
        } finally {
            setCancellingSync(null);
        }
    };

    const handleDeleteSync = async (syncId: string, syncName: string) => {
        const confirmMessage = `⚠️ DELETE SYNC: "${syncName}"?\n\nThis will permanently delete:\n• The sync and all its data\n• All jobs and schedules\n• Data from Vespa\n• ARF storage\n• Postgres records\n\n⚠️ THIS CANNOT BE UNDONE!\n\nType DELETE to confirm:`;

        const userInput = prompt(confirmMessage);

        if (userInput !== 'DELETE') {
            if (userInput !== null) {
                toast.error('Deletion cancelled.');
            }
            return;
        }

        setDeletingSync(syncId);
        try {
            const response = await apiClient.delete(`/admin/syncs/${syncId}`);

            if (!response.ok) {
                const error = await response.text();
                throw new Error(error || 'Failed to delete sync');
            }

            const result = await response.json();
            toast.success(`Successfully deleted sync "${syncName}"`);

            // Remove the deleted sync from the list
            setSyncs(syncs.filter(s => s.id !== syncId));
        } catch (error) {
            console.error('Failed to delete sync:', error);
            toast.error(error instanceof Error ? error.message : 'Failed to delete sync');
        } finally {
            setDeletingSync(null);
        }
    };

    const openResyncDialog = (syncId: string, syncName: string) => {
        setResyncingSync({ id: syncId, name: syncName });
        // Reset to default preset
        setSelectedPreset('default');
        setResyncConfig(getPresetConfig('default'));
        setResyncDialogOpen(true);
    };

    const handlePresetChange = (presetId: SyncPreset) => {
        setSelectedPreset(presetId);
        setResyncConfig(getPresetConfig(presetId));
    };

    const handleAddTag = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && tagInput.trim()) {
            e.preventDefault();
            const newTag = tagInput.trim();
            if (!resyncTags.includes(newTag)) {
                setResyncTags([...resyncTags, newTag]);
            }
            setTagInput('');
        }
    };

    const handleRemoveTag = (tagToRemove: string) => {
        setResyncTags(resyncTags.filter(tag => tag !== tagToRemove));
    };

    const handleResync = async () => {
        if (!resyncingSync) return;

        try {
            // Build request body with config and optional tags
            const requestBody: any = {
                execution_config: resyncConfig
            };

            // Add tags if provided
            if (resyncTags.length > 0) {
                requestBody.tags = resyncTags;
            }

            const response = await apiClient.post(
                `/admin/resync/${resyncingSync.id}`,
                requestBody
            );

            if (!response.ok) {
                const error = await response.text();
                throw new Error(error || 'Failed to trigger resync');
            }

            const result = await response.json();
            toast.success(`Resync job created for "${resyncingSync.name}" (Job ID: ${result.id})`);
            setResyncDialogOpen(false);
            setResyncingSync(null);
            setResyncTags([]); // Clear tags after successful resync
            setTagInput('');
        } catch (error) {
            console.error('Failed to trigger resync:', error);
            toast.error(error instanceof Error ? error.message : 'Failed to trigger resync');
        }
    };

    return (
        <>
            {/* Search Form */}
            <Card className="mb-6">
                <CardHeader>
                    <CardTitle>Search Syncs</CardTitle>
                    <CardDescription>
                        Find syncs across all organizations. Press Search to load results.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 gap-4 mb-4">
                        <div>
                            <Label htmlFor="sync-ids-filter">Sync ID(s)</Label>
                            <Input
                                id="sync-ids-filter"
                                placeholder="Comma-separated UUIDs (e.g., uuid1,uuid2,uuid3)"
                                value={syncFilters.syncIds}
                                onChange={(e) => setSyncFilters({ ...syncFilters, syncIds: e.target.value })}
                            />
                            <p className="text-xs text-muted-foreground mt-1">
                                Search by specific sync IDs. Leave empty to search all syncs.
                            </p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                        <div>
                            <Label htmlFor="sync-org-filter">Organization ID</Label>
                            <Input
                                id="sync-org-filter"
                                placeholder="UUID or leave empty"
                                value={syncFilters.organizationId}
                                onChange={(e) => setSyncFilters({ ...syncFilters, organizationId: e.target.value })}
                            />
                        </div>
                        <div>
                            <Label htmlFor="sync-collection-filter">Collection ID</Label>
                            <Input
                                id="sync-collection-filter"
                                placeholder="Readable ID"
                                value={syncFilters.collectionId}
                                onChange={(e) => setSyncFilters({ ...syncFilters, collectionId: e.target.value })}
                            />
                        </div>
                        <div>
                            <Label htmlFor="sync-source-filter">Source Type</Label>
                            <Input
                                id="sync-source-filter"
                                placeholder="e.g., linear, github"
                                value={syncFilters.sourceType}
                                onChange={(e) => setSyncFilters({ ...syncFilters, sourceType: e.target.value })}
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                        <div>
                            <Label htmlFor="sync-status-filter">Sync Status</Label>
                            <Select
                                value={syncFilters.status}
                                onValueChange={(value) => setSyncFilters({ ...syncFilters, status: value })}
                            >
                                <SelectTrigger id="sync-status-filter">
                                    <SelectValue placeholder="All statuses" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All</SelectItem>
                                    <SelectItem value="active">Active</SelectItem>
                                    <SelectItem value="inactive">Inactive</SelectItem>
                                    <SelectItem value="error">Error</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label htmlFor="last-job-status-filter">Last Job Status</Label>
                            <Select
                                value={syncFilters.lastJobStatus}
                                onValueChange={(value) => setSyncFilters({ ...syncFilters, lastJobStatus: value })}
                            >
                                <SelectTrigger id="last-job-status-filter">
                                    <SelectValue placeholder="All" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All</SelectItem>
                                    <SelectItem value="completed">Completed</SelectItem>
                                    <SelectItem value="failed">Failed</SelectItem>
                                    <SelectItem value="running">Running</SelectItem>
                                    <SelectItem value="pending">Pending</SelectItem>
                                    <SelectItem value="cancelled">Cancelled</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label htmlFor="sync-auth-filter">Authentication</Label>
                            <Select
                                value={syncFilters.isAuthenticated}
                                onValueChange={(value) => setSyncFilters({ ...syncFilters, isAuthenticated: value })}
                            >
                                <SelectTrigger id="sync-auth-filter">
                                    <SelectValue placeholder="All" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All</SelectItem>
                                    <SelectItem value="true">Authenticated</SelectItem>
                                    <SelectItem value="false">Needs Reauth</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label htmlFor="sync-limit">Results Limit</Label>
                            <Input
                                id="sync-limit"
                                type="number"
                                min="10"
                                max="500"
                                value={syncFilters.limit}
                                onChange={(e) => setSyncFilters({ ...syncFilters, limit: parseInt(e.target.value) || 100 })}
                            />
                        </div>
                    </div>

                    {/* Tag Filters */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                        <div>
                            <Label htmlFor="tags-filter">Include Tags</Label>
                            <Input
                                id="tags-filter"
                                placeholder="Comma-separated (e.g., vespa-backfill-01-22-2026)"
                                value={syncFilters.tags}
                                onChange={(e) => setSyncFilters({ ...syncFilters, tags: e.target.value })}
                            />
                            <p className="text-xs text-muted-foreground mt-1">
                                Show only syncs with these tags (matches ANY tag)
                            </p>
                        </div>
                        <div>
                            <Label htmlFor="exclude-tags-filter">Exclude Tags</Label>
                            <Input
                                id="exclude-tags-filter"
                                placeholder="Comma-separated (e.g., vespa-backfill-01-22-2026)"
                                value={syncFilters.excludeTags}
                                onChange={(e) => setSyncFilters({ ...syncFilters, excludeTags: e.target.value })}
                            />
                            <p className="text-xs text-muted-foreground mt-1">
                                Hide syncs with these tags (useful for filtering out already-backfilled syncs)
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-6 mb-4">
                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="ghost-syncs-filter"
                                checked={syncFilters.ghostSyncsOnly}
                                onCheckedChange={(checked) => setSyncFilters({ ...syncFilters, ghostSyncsOnly: checked as boolean })}
                            />
                            <Label
                                htmlFor="ghost-syncs-filter"
                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                            >
                                Ghost Syncs Only (last 5 jobs failed)
                            </Label>
                        </div>
                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="destination-counts-filter"
                                checked={syncFilters.includeDestinationCounts}
                                onCheckedChange={(checked) => setSyncFilters({ ...syncFilters, includeDestinationCounts: checked as boolean })}
                            />
                            <Label
                                htmlFor="destination-counts-filter"
                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                            >
                                Include Destination Counts (Vespa - slower)
                            </Label>
                        </div>
                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="arf-counts-filter"
                                checked={syncFilters.includeArfCounts}
                                onCheckedChange={(checked) => setSyncFilters({ ...syncFilters, includeArfCounts: checked as boolean })}
                            />
                            <Label
                                htmlFor="arf-counts-filter"
                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                            >
                                Include ARF Counts (slower)
                            </Label>
                        </div>
                    </div>

                    <div className="flex gap-2">
                        <Button onClick={loadSyncs} disabled={isSyncsLoading} className="gap-2">
                            <Search className="h-4 w-4" />
                            {isSyncsLoading ? 'Searching...' : 'Search'}
                        </Button>
                        {syncs.length > 0 && (
                            <Button variant="outline" onClick={() => setSyncs([])}>
                                Clear Results
                            </Button>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Stats Cards */}
            {syncs.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
                    <Card>
                        <CardHeader className="pb-2 pt-3">
                            <CardTitle className="text-xs font-medium text-muted-foreground">
                                Total Syncs
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pb-3">
                            <div className="text-2xl font-bold">{syncs.length}</div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2 pt-3">
                            <CardTitle className="text-xs font-medium text-muted-foreground">
                                Active
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pb-3">
                            <div className="text-2xl font-bold text-green-500">
                                {syncs.filter(s => s.status === 'active').length}
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2 pt-3">
                            <CardTitle className="text-xs font-medium text-muted-foreground">
                                Ghost Syncs
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pb-3">
                            <div className="text-2xl font-bold text-red-500">
                                {syncs.filter(s => s.last_job_status === 'failed').length}
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2 pt-3">
                            <CardTitle className="text-xs font-medium text-muted-foreground">
                                Total Entities
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pb-3">
                            <div className="text-2xl font-bold">
                                {formatNumber(syncs.reduce((sum, s) => sum + (s.total_entity_count || 0), 0))}
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2 pt-3">
                            <CardTitle className="text-xs font-medium text-muted-foreground">
                                Needs Reauth
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pb-3">
                            <div className="text-2xl font-bold text-amber-500">
                                {syncs.filter(s => s.source_is_authenticated === false).length}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Results Table */}
            {syncs.length > 0 && (
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle>Sync Results ({syncs.length})</CardTitle>
                                <CardDescription>
                                    Showing syncs matching your search criteria
                                    {selectedSyncs.size > 0 && ` • ${selectedSyncs.size} selected`}
                                </CardDescription>
                            </div>
                            {selectedSyncs.size > 0 && (
                                <div className="flex gap-2">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={openBulkResyncDialog}
                                        className="gap-2"
                                    >
                                        <RefreshCw className="h-4 w-4" />
                                        Resync ({selectedSyncs.size})
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={handleBulkCancel}
                                        className="gap-2"
                                    >
                                        <XCircle className="h-4 w-4" />
                                        Cancel Jobs ({selectedSyncs.size})
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="destructive"
                                        onClick={handleBulkDelete}
                                        className="gap-2"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                        Delete ({selectedSyncs.size})
                                    </Button>
                                </div>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[50px]">
                                            <Checkbox
                                                checked={selectedSyncs.size === syncs.length && syncs.length > 0}
                                                onCheckedChange={toggleSelectAll}
                                                aria-label="Select all syncs"
                                            />
                                        </TableHead>
                                        <TableHead>Sync Name / ID</TableHead>
                                        <TableHead>Organization</TableHead>
                                        <TableHead>Collection</TableHead>
                                        <TableHead>Source</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Auth</TableHead>
                                        <TableHead className="text-right">Entity Counts</TableHead>
                                        <TableHead>Last Job</TableHead>
                                        <TableHead>Tags</TableHead>
                                        <TableHead>Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {syncs.map((sync) => {
                                        const orgInfo = organizationMap[sync.organization_id];
                                        const isSelected = selectedSyncs.has(sync.id);
                                        return (
                                            <TableRow key={sync.id} className={isSelected ? 'bg-blue-500/5' : ''}>
                                                <TableCell>
                                                    <Checkbox
                                                        checked={isSelected}
                                                        onCheckedChange={() => toggleSelectSync(sync.id)}
                                                        aria-label={`Select sync ${sync.name}`}
                                                    />
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    <div className="flex flex-col gap-1">
                                                        <span className="truncate max-w-[200px]">{sync.name}</span>
                                                        <div className="flex items-center gap-1">
                                                            <span className="text-xs text-muted-foreground font-mono">
                                                                {sync.id}
                                                            </span>
                                                            <button
                                                                onClick={() => copyToClipboard(sync.id, 'Sync ID')}
                                                                className="text-muted-foreground hover:text-foreground transition-colors"
                                                            >
                                                                <Copy className="h-3 w-3" />
                                                            </button>
                                                        </div>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex flex-col gap-1">
                                                        <span className="text-sm font-medium">
                                                            {orgInfo?.name || 'Unknown'}
                                                        </span>
                                                        <div className="flex items-center gap-1">
                                                            <span className="text-xs text-muted-foreground font-mono">
                                                                {sync.organization_id}
                                                            </span>
                                                            <button
                                                                onClick={() => copyToClipboard(sync.organization_id, 'Organization ID')}
                                                                className="text-muted-foreground hover:text-foreground transition-colors"
                                                            >
                                                                <Copy className="h-3 w-3" />
                                                            </button>
                                                        </div>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <span className="text-sm">{sync.readable_collection_id || '-'}</span>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="outline">{sync.source_short_name || 'Unknown'}</Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge
                                                        variant={sync.status === 'active' ? 'default' : 'secondary'}
                                                        className={sync.status === 'active' ? 'bg-green-500/20 text-green-400 border-green-500/30' : ''}
                                                    >
                                                        {sync.status}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    {sync.source_is_authenticated === true && (
                                                        <Badge variant="outline" className="bg-green-500/10 text-green-400 border-green-500/30">
                                                            ✓
                                                        </Badge>
                                                    )}
                                                    {sync.source_is_authenticated === false && (
                                                        <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/30">
                                                            ✗
                                                        </Badge>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <div className="flex flex-col gap-1 items-end text-xs font-mono">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-muted-foreground">PG:</span>
                                                            <span>{formatNumber(sync.total_entity_count || 0)}</span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-muted-foreground">ARF:</span>
                                                            <span>{sync.total_arf_entity_count !== null && sync.total_arf_entity_count !== undefined ? formatNumber(sync.total_arf_entity_count) : '-'}</span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-muted-foreground">Vespa:</span>
                                                            <span>{sync.total_vespa_entity_count !== null && sync.total_vespa_entity_count !== undefined ? formatNumber(sync.total_vespa_entity_count) : '-'}</span>
                                                        </div>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    {sync.last_job_status && (
                                                        <div className="flex flex-col gap-1">
                                                            <div className="flex items-center gap-1">
                                                                <Badge
                                                                    variant="outline"
                                                                    className={
                                                                        sync.last_job_status === 'completed'
                                                                            ? 'bg-green-500/10 text-green-400 border-green-500/30'
                                                                            : sync.last_job_status === 'failed'
                                                                                ? 'bg-red-500/10 text-red-400 border-red-500/30'
                                                                                : sync.last_job_status === 'running'
                                                                                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                                                                                    : ''
                                                                    }
                                                                >
                                                                    {sync.last_job_status}
                                                                </Badge>
                                                                {sync.last_job_status === 'failed' && sync.last_job_error && (
                                                                    <TooltipProvider>
                                                                        <Tooltip delayDuration={100}>
                                                                            <TooltipTrigger asChild>
                                                                                <button className="text-red-400 hover:text-red-300 transition-colors">
                                                                                    <AlertCircle className="h-4 w-4" />
                                                                                </button>
                                                                            </TooltipTrigger>
                                                                            <TooltipContent
                                                                                className="max-w-md p-3 bg-red-950/90 border-red-500/30"
                                                                                side="left"
                                                                            >
                                                                                <div className="space-y-1">
                                                                                    <p className="font-semibold text-red-300 text-xs">Last Error:</p>
                                                                                    <p className="text-xs text-red-200 font-mono whitespace-pre-wrap break-words">
                                                                                        {sync.last_job_error}
                                                                                    </p>
                                                                                </div>
                                                                            </TooltipContent>
                                                                        </Tooltip>
                                                                    </TooltipProvider>
                                                                )}
                                                            </div>
                                                            {sync.last_job_at && (
                                                                <span className="text-xs text-muted-foreground">
                                                                    {new Date(sync.last_job_at).toLocaleString()}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    {sync.all_tags && sync.all_tags.length > 0 ? (
                                                        <div className="flex flex-wrap gap-1 max-w-[200px]">
                                                            {sync.all_tags.map((tag) => (
                                                                <Badge
                                                                    key={tag}
                                                                    variant="secondary"
                                                                    className="text-xs px-1.5 py-0.5 bg-blue-500/10 text-blue-400 border-blue-500/30"
                                                                >
                                                                    {tag}
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    ) : (
                                                        <span className="text-xs text-muted-foreground">-</span>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex gap-1">
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => openResyncDialog(sync.id, sync.name)}
                                                            disabled={cancellingSync === sync.id || deletingSync === sync.id}
                                                            className="h-7 px-2 hover:bg-blue-500/10 hover:text-blue-500 hover:border-blue-500/30"
                                                            title="Resync with custom config"
                                                        >
                                                            <RefreshCw className="h-3.5 w-3.5" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleCancelSync(sync.id, sync.name)}
                                                            disabled={cancellingSync === sync.id || deletingSync === sync.id}
                                                            className="h-7 px-2"
                                                            title="Cancel active jobs"
                                                        >
                                                            <XCircle className="h-3.5 w-3.5" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            disabled
                                                            className="h-7 px-2"
                                                            title="Deschedule sync (coming soon)"
                                                        >
                                                            <CalendarX className="h-3.5 w-3.5" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleDeleteSync(sync.id, sync.name)}
                                                            disabled={deletingSync === sync.id || cancellingSync === sync.id}
                                                            className="h-7 px-2 hover:bg-red-500/10 hover:text-red-500 hover:border-red-500/30"
                                                            title="Delete sync permanently"
                                                        >
                                                            <Trash2 className="h-3.5 w-3.5" />
                                                        </Button>
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Empty State */}
            {syncs.length === 0 && !isSyncsLoading && (
                <Card>
                    <CardContent className="py-12">
                        <div className="text-center text-muted-foreground">
                            <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>No syncs loaded. Use the search form above to find syncs.</p>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Resync Dialog */}
            <Dialog open={resyncDialogOpen} onOpenChange={setResyncDialogOpen}>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Resync: {resyncingSync?.name}</DialogTitle>
                        <DialogDescription>
                            Select a preset or manually configure execution options. Presets cover common use cases like ARF capture and replay.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-6 py-4">
                        {/* Preset Selector */}
                        <div className="space-y-3">
                            <Label htmlFor="preset-select" className="text-sm font-semibold">
                                Configuration Preset
                            </Label>
                            <Select value={selectedPreset} onValueChange={handlePresetChange}>
                                <SelectTrigger id="preset-select">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {SYNC_PRESETS.map((preset) => (
                                        <SelectItem key={preset.id} value={preset.id}>
                                            <div className="flex flex-col">
                                                <span className="font-medium">{preset.label}</span>
                                                <span className="text-xs text-muted-foreground">{preset.description}</span>
                                            </div>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Destination Toggles */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold">Destination Toggles</h3>
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="skip-vespa"
                                        checked={resyncConfig.destinations?.skip_vespa || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                destinations: { ...resyncConfig.destinations, skip_vespa: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="skip-vespa" className="text-sm cursor-pointer">
                                        Skip Vespa
                                    </Label>
                                </div>
                            </div>
                        </div>

                        {/* Handler Toggles */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold">Handler Toggles</h3>
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="enable-vector"
                                        checked={resyncConfig.handlers?.enable_vector_handlers ?? true}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                handlers: { ...resyncConfig.handlers, enable_vector_handlers: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="enable-vector" className="text-sm cursor-pointer">
                                        Enable Vector Handlers (embeddings)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="enable-arf"
                                        checked={resyncConfig.handlers?.enable_raw_data_handler ?? true}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                handlers: { ...resyncConfig.handlers, enable_raw_data_handler: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="enable-arf" className="text-sm cursor-pointer">
                                        Enable ARF Handler (raw data capture)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="enable-postgres"
                                        checked={resyncConfig.handlers?.enable_postgres_handler ?? true}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                handlers: { ...resyncConfig.handlers, enable_postgres_handler: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="enable-postgres" className="text-sm cursor-pointer">
                                        Enable Postgres Handler (metadata)
                                    </Label>
                                </div>
                            </div>
                        </div>

                        {/* Cursor Behavior */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold">Cursor Behavior</h3>
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="skip-cursor"
                                        checked={resyncConfig.cursor?.skip_load || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                cursor: { ...resyncConfig.cursor, skip_load: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="skip-cursor" className="text-sm cursor-pointer">
                                        Skip Cursor Load (force full sync - fetch all entities)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="skip-cursor-updates"
                                        checked={resyncConfig.cursor?.skip_updates || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                cursor: { ...resyncConfig.cursor, skip_updates: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="skip-cursor-updates" className="text-sm cursor-pointer">
                                        Skip Cursor Updates (don't save progress)
                                    </Label>
                                </div>
                            </div>
                        </div>

                        {/* Sync Behavior */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold">Sync Behavior</h3>
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="skip-hash"
                                        checked={resyncConfig.behavior?.skip_hash_comparison || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                behavior: { ...resyncConfig.behavior, skip_hash_comparison: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="skip-hash" className="text-sm cursor-pointer">
                                        Skip Hash Comparison (force INSERT all entities)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="replay-arf"
                                        checked={resyncConfig.behavior?.replay_from_arf || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                behavior: { ...resyncConfig.behavior, replay_from_arf: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="replay-arf" className="text-sm cursor-pointer">
                                        Replay from ARF (read from ARF storage instead of source)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="skip-guardrails"
                                        checked={resyncConfig.behavior?.skip_guardrails || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                behavior: { ...resyncConfig.behavior, skip_guardrails: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="skip-guardrails" className="text-sm cursor-pointer">
                                        Skip Guardrails (bypass entity count limits for admin resyncs)
                                    </Label>
                                </div>
                            </div>
                        </div>

                        {/* Tags Input */}
                        <div className="space-y-3">
                            <Label htmlFor="resync-tags" className="text-sm font-semibold">
                                Tags (Optional)
                            </Label>
                            <div className="space-y-2">
                                {/* Tag badges */}
                                {resyncTags.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {resyncTags.map((tag) => (
                                            <Badge
                                                key={tag}
                                                variant="secondary"
                                                className="pl-2 pr-1 py-1 gap-1 bg-blue-500/10 text-blue-400 border-blue-500/30 hover:bg-blue-500/20"
                                            >
                                                <span>{tag}</span>
                                                <button
                                                    onClick={() => handleRemoveTag(tag)}
                                                    className="ml-1 rounded-full hover:bg-blue-500/30 p-0.5"
                                                    type="button"
                                                >
                                                    <X className="h-3 w-3" />
                                                </button>
                                            </Badge>
                                        ))}
                                    </div>
                                )}
                                {/* Tag input */}
                                <Input
                                    id="resync-tags"
                                    placeholder="Type a tag and press Enter (e.g., vespa-backfill-01-22-2026)"
                                    value={tagInput}
                                    onChange={(e) => setTagInput(e.target.value)}
                                    onKeyDown={handleAddTag}
                                />
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Press <kbd className="px-1.5 py-0.5 text-xs bg-muted border rounded">Enter</kbd> to add each tag. Tags help filter and organize sync jobs for tracking backfills or manual operations.
                            </p>
                        </div>

                        {/* Info Box */}
                        <div className="bg-blue-950/30 border border-blue-500/30 rounded-md p-3">
                            <p className="text-xs text-blue-300">
                                <strong>Tip:</strong> Use "ARF Replay to Vector DBs" preset to re-process existing data without calling the source API.
                                Perfect for Vespa backfills or reprocessing after schema changes.
                            </p>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setResyncDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleResync} className="gap-2">
                            <RefreshCw className="h-4 w-4" />
                            Start Resync
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Bulk Resync Dialog */}
            <Dialog open={bulkResyncDialogOpen} onOpenChange={setBulkResyncDialogOpen}>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Bulk Resync: {selectedSyncs.size} Sync(s)</DialogTitle>
                        <DialogDescription>
                            Select a preset or configure options. The same config will be applied to all selected syncs.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-6 py-4">
                        {/* Preset Selector */}
                        <div className="space-y-3">
                            <Label htmlFor="bulk-preset-select" className="text-sm font-semibold">
                                Configuration Preset
                            </Label>
                            <Select value={selectedPreset} onValueChange={handlePresetChange}>
                                <SelectTrigger id="bulk-preset-select">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {SYNC_PRESETS.map((preset) => (
                                        <SelectItem key={preset.id} value={preset.id}>
                                            <div className="flex flex-col">
                                                <span className="font-medium">{preset.label}</span>
                                                <span className="text-xs text-muted-foreground">{preset.description}</span>
                                            </div>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Destination Toggles */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold">Destination Toggles</h3>
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-skip-vespa"
                                        checked={resyncConfig.destinations?.skip_vespa || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                destinations: { ...resyncConfig.destinations, skip_vespa: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-skip-vespa" className="text-sm cursor-pointer">
                                        Skip Vespa
                                    </Label>
                                </div>
                            </div>
                        </div>

                        {/* Handler Toggles */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold">Handler Toggles</h3>
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-enable-vector"
                                        checked={resyncConfig.handlers?.enable_vector_handlers ?? true}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                handlers: { ...resyncConfig.handlers, enable_vector_handlers: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-enable-vector" className="text-sm cursor-pointer">
                                        Enable Vector Handlers (embeddings)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-enable-arf"
                                        checked={resyncConfig.handlers?.enable_raw_data_handler ?? true}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                handlers: { ...resyncConfig.handlers, enable_raw_data_handler: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-enable-arf" className="text-sm cursor-pointer">
                                        Enable ARF Handler (raw data capture)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-enable-postgres"
                                        checked={resyncConfig.handlers?.enable_postgres_handler ?? true}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                handlers: { ...resyncConfig.handlers, enable_postgres_handler: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-enable-postgres" className="text-sm cursor-pointer">
                                        Enable Postgres Handler (metadata)
                                    </Label>
                                </div>
                            </div>
                        </div>

                        {/* Cursor Behavior */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold">Cursor Behavior</h3>
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-skip-cursor"
                                        checked={resyncConfig.cursor?.skip_load || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                cursor: { ...resyncConfig.cursor, skip_load: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-skip-cursor" className="text-sm cursor-pointer">
                                        Skip Cursor Load (force full sync - fetch all entities)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-skip-cursor-updates"
                                        checked={resyncConfig.cursor?.skip_updates || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                cursor: { ...resyncConfig.cursor, skip_updates: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-skip-cursor-updates" className="text-sm cursor-pointer">
                                        Skip Cursor Updates (don't save progress)
                                    </Label>
                                </div>
                            </div>
                        </div>

                        {/* Sync Behavior */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold">Sync Behavior</h3>
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-skip-hash"
                                        checked={resyncConfig.behavior?.skip_hash_comparison || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                behavior: { ...resyncConfig.behavior, skip_hash_comparison: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-skip-hash" className="text-sm cursor-pointer">
                                        Skip Hash Comparison (force INSERT all entities)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-replay-arf"
                                        checked={resyncConfig.behavior?.replay_from_arf || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                behavior: { ...resyncConfig.behavior, replay_from_arf: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-replay-arf" className="text-sm cursor-pointer">
                                        Replay from ARF (read from ARF storage instead of source)
                                    </Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="bulk-skip-guardrails"
                                        checked={resyncConfig.behavior?.skip_guardrails || false}
                                        onCheckedChange={(checked) => {
                                            setSelectedPreset('custom');
                                            setResyncConfig({
                                                ...resyncConfig,
                                                behavior: { ...resyncConfig.behavior, skip_guardrails: checked as boolean },
                                            });
                                        }}
                                    />
                                    <Label htmlFor="bulk-skip-guardrails" className="text-sm cursor-pointer">
                                        Skip Guardrails (bypass entity count limits for admin resyncs)
                                    </Label>
                                </div>
                            </div>
                        </div>

                        {/* Info Box */}
                        <div className="bg-amber-950/30 border border-amber-500/30 rounded-md p-3">
                            <p className="text-xs text-amber-300">
                                <strong>Warning:</strong> This configuration will be applied to all {selectedSyncs.size} selected sync(s).
                                Consider using "ARF Replay to Vector DBs" preset for common bulk backfill operations.
                            </p>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setBulkResyncDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleBulkResync} className="gap-2">
                            <RefreshCw className="h-4 w-4" />
                            Start Bulk Resync ({selectedSyncs.size})
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}

