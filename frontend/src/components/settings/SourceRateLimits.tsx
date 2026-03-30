import { useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Save, Trash2, Building2, User, Loader2, Activity } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { useOrganizationContext } from '@/hooks/use-organization-context';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';

interface SourceRateLimitRow {
    source_short_name: string;
    rate_limit_level: 'org' | 'connection' | null;
    limit: number | null;
    window_seconds: number | null;
    id: string | null;
}

export const SourceRateLimits = () => {
    const [limits, setLimits] = useState<SourceRateLimitRow[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [editingRows, setEditingRows] = useState<
        Map<string, { limit: string; window: string }>
    >(new Map());
    const [savingRows, setSavingRows] = useState<Set<string>>(new Set());
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const { canManageOrganization } = useOrganizationContext();
    const canManage = canManageOrganization();

    useEffect(() => {
        fetchLimits();
    }, []);

    const fetchLimits = async () => {
        try {
            setIsLoading(true);
            const response = await apiClient.get('/source-rate-limits');

            if (!response.ok) {
                throw new Error('Failed to fetch rate limits');
            }

            const data = await response.json();
            setLimits(data);
        } catch (error) {
            toast.error('Failed to load rate limits');
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleEditChange = (
        sourceShortName: string,
        field: 'limit' | 'window',
        value: string
    ) => {
        const current = editingRows.get(sourceShortName) || {
            limit: '',
            window: '',
        };

        // Find the row to get current values
        const row = limits.find((r) => r.source_short_name === sourceShortName);
        if (!row) return;

        const newValues = {
            limit: field === 'limit' ? value : current.limit || String(row.limit || ''),
            window: field === 'window' ? value : current.window || String(row.window_seconds || ''),
        };

        setEditingRows(new Map(editingRows.set(sourceShortName, newValues)));
    };

    const handleSaveRow = async (sourceShortName: string) => {
        const edited = editingRows.get(sourceShortName);
        if (!edited) return;

        const limit = parseInt(edited.limit);
        const windowSeconds = parseInt(edited.window);

        if (isNaN(limit) || isNaN(windowSeconds) || limit <= 0 || windowSeconds <= 0) {
            toast.error('Please enter both limit and window (positive numbers required)');
            return;
        }

        try {
            setSavingRows(new Set(savingRows.add(sourceShortName)));

            const response = await apiClient.put(`/source-rate-limits/${sourceShortName}`, undefined, {
                limit,
                window_seconds: windowSeconds,
            });

            if (!response.ok) {
                throw new Error('Failed to update rate limit');
            }

            toast.success(`Updated ${sourceShortName} rate limit`);
            fetchLimits(); // Refresh
            editingRows.delete(sourceShortName);
            setEditingRows(new Map(editingRows));
        } catch (error) {
            toast.error('Failed to update rate limit');
            console.error(error);
        } finally {
            setSavingRows((prev) => {
                const newSet = new Set(prev);
                newSet.delete(sourceShortName);
                return newSet;
            });
        }
    };

    const handleDeleteRow = async (sourceShortName: string) => {
        try {
            setSavingRows(new Set(savingRows.add(sourceShortName)));

            const response = await apiClient.delete(`/source-rate-limits/${sourceShortName}`);

            if (!response.ok) {
                throw new Error('Failed to remove rate limit');
            }

            toast.success(`Removed ${sourceShortName} rate limit`);
            fetchLimits();
            editingRows.delete(sourceShortName);
            setEditingRows(new Map(editingRows));
        } catch (error) {
            toast.error('Failed to remove rate limit');
            console.error(error);
        } finally {
            setSavingRows((prev) => {
                const newSet = new Set(prev);
                newSet.delete(sourceShortName);
                return newSet;
            });
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <TooltipProvider delayDuration={100}>
            <div className="space-y-4">
                {/* Header Section */}
                <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                        Configure rate limits to prevent exhausting API quotas across your organization
                    </p>
                    {!canManage && (
                        <p className="text-xs text-amber-600 dark:text-amber-400">
                            Only admins and owners can manage rate limits.
                        </p>
                    )}
                </div>

                {/* Source Limits - Minimal, list-based design */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2 px-1 py-1">
                        <Activity className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Source Limits</span>
                    </div>

                    <div className="space-y-1.5">
                        {limits.map((row) => {
                            const isEditing = editingRows.has(row.source_short_name);
                            const isSaving = savingRows.has(row.source_short_name);
                            const edited = editingRows.get(row.source_short_name);
                            const hasChanges = edited && (
                                edited.limit !== (row.limit !== null ? String(row.limit) : '') ||
                                edited.window !== (row.window_seconds !== null ? String(row.window_seconds) : '')
                            );

                            return (
                                <div
                                    key={row.source_short_name}
                                    className={cn(
                                        "rounded-lg border p-3 transition-all duration-200",
                                        isDark ? "bg-gray-900/50" : "bg-white",
                                        !row.rate_limit_level && "opacity-50"
                                    )}
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        {/* Source name and badge */}
                                        <div className="flex items-center gap-2.5 min-w-[140px]">
                                            <span className="text-sm font-medium capitalize">{row.source_short_name}</span>
                                            {row.rate_limit_level === 'org' && (
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <div className={cn(
                                                            "h-5 px-1.5 rounded flex items-center gap-1",
                                                            isDark ? "bg-blue-500/10" : "bg-blue-50"
                                                        )}>
                                                            <Building2 className={cn("h-2.5 w-2.5", isDark ? "text-blue-400" : "text-blue-600")} />
                                                            <span className={cn("text-[10px] font-medium", isDark ? "text-blue-400" : "text-blue-600")}>ORG</span>
                                                        </div>
                                                    </TooltipTrigger>
                                                    <TooltipContent><p className="text-xs">Organization-wide tracking</p></TooltipContent>
                                                </Tooltip>
                                            )}
                                            {row.rate_limit_level === 'connection' && (
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <div className={cn(
                                                            "h-5 px-1.5 rounded flex items-center gap-1",
                                                            isDark ? "bg-purple-500/10" : "bg-purple-50"
                                                        )}>
                                                            <User className={cn("h-2.5 w-2.5", isDark ? "text-purple-400" : "text-purple-600")} />
                                                            <span className={cn("text-[10px] font-medium", isDark ? "text-purple-400" : "text-purple-600")}>CONN</span>
                                                        </div>
                                                    </TooltipTrigger>
                                                    <TooltipContent><p className="text-xs">Per-connection tracking</p></TooltipContent>
                                                </Tooltip>
                                            )}
                                            {!row.rate_limit_level && (
                                                <span className="text-[10px] text-muted-foreground">Not supported</span>
                                            )}
                                        </div>

                                        {/* Inline inputs and controls */}
                                        {row.rate_limit_level ? (
                                            <div className="flex items-center gap-2">
                                                <div className="flex items-center gap-1.5">
                                                    <Input
                                                        type="number"
                                                        placeholder="800"
                                                        value={edited?.limit ?? row.limit ?? ''}
                                                        onChange={(e) =>
                                                            handleEditChange(row.source_short_name, 'limit', e.target.value)
                                                        }
                                                        className="h-7 w-20 text-xs"
                                                        min="1"
                                                        disabled={isSaving}
                                                        readOnly={!canManage}
                                                    />
                                                    <span className="text-[11px] text-muted-foreground">req</span>
                                                </div>
                                                <span className="text-xs text-muted-foreground">/</span>
                                                <div className="flex items-center gap-1.5">
                                                    <Input
                                                        type="number"
                                                        placeholder="60"
                                                        value={edited?.window ?? row.window_seconds ?? ''}
                                                        onChange={(e) =>
                                                            handleEditChange(row.source_short_name, 'window', e.target.value)
                                                        }
                                                        className="h-7 w-16 text-xs"
                                                        min="1"
                                                        disabled={isSaving}
                                                        readOnly={!canManage}
                                                    />
                                                    <span className="text-[11px] text-muted-foreground">sec</span>
                                                </div>
                                                <div className="flex gap-1">
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <button
                                                                onClick={() => handleSaveRow(row.source_short_name)}
                                                                disabled={!canManage || isSaving || !isEditing || !hasChanges}
                                                                className={cn(
                                                                    "h-7 w-7 rounded-md flex items-center justify-center transition-all duration-200",
                                                                    !canManage || isSaving || !isEditing || !hasChanges
                                                                        ? "opacity-40 cursor-not-allowed"
                                                                        : isDark
                                                                            ? "bg-primary/90 hover:bg-primary text-white"
                                                                            : "bg-primary hover:bg-primary/90 text-white"
                                                                )}
                                                            >
                                                                {isSaving ? (
                                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                                ) : (
                                                                    <Save className="h-3 w-3" />
                                                                )}
                                                            </button>
                                                        </TooltipTrigger>
                                                        <TooltipContent><p className="text-xs">Save changes</p></TooltipContent>
                                                    </Tooltip>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <button
                                                                onClick={() => handleDeleteRow(row.source_short_name)}
                                                                disabled={!canManage || isSaving || !row.id}
                                                                className={cn(
                                                                    "h-7 w-7 rounded-md flex items-center justify-center transition-all duration-200",
                                                                    !canManage || isSaving || !row.id
                                                                        ? "opacity-40 cursor-not-allowed"
                                                                        : isDark
                                                                            ? "hover:bg-red-500/10 text-red-400"
                                                                            : "hover:bg-red-50 text-red-600"
                                                                )}
                                                            >
                                                                {isSaving ? (
                                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                                ) : (
                                                                    <Trash2 className="h-3 w-3" />
                                                                )}
                                                            </button>
                                                        </TooltipTrigger>
                                                        <TooltipContent><p className="text-xs">Remove limit</p></TooltipContent>
                                                    </Tooltip>
                                                </div>
                                            </div>
                                        ) : (
                                            <span className="text-xs text-muted-foreground">No rate limiting available</span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </TooltipProvider>
    );
};
