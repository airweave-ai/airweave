import React, { useState, useEffect, useMemo } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  RefreshCw, GitBranch, ArrowRightLeft,
  Layers, Play, ChevronDown, Trash2, ArrowUp, ArrowDown, ChevronRight, FolderOpen, Search
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { getAppIconUrl } from '@/lib/utils/icons';

// ============ TYPES ============

interface DestinationSlot {
  slot_id: string;
  connection_id: string;
  connection_name: string;
  role: 'active' | 'shadow' | 'deprecated';
}

interface SyncMigrationInfo {
  sync_id: string;
  sync_name: string;
  collection_id: string;
  collection_readable_id: string;
  collection_name: string;
  organization_id: string;
  organization_name: string;
  source_connection_id: string | null;
  source_short_name: string | null;
  destination_slots: DestinationSlot[];
  created_at: string;
}

interface CollectionMigrationInfo {
  collection_id: string;
  collection_readable_id: string;
  collection_name: string;
  organization_id: string;
  organization_name: string;
  syncs: SyncMigrationInfo[];
}

interface DestinationConnection {
  id: string;
  name: string;
  short_name: string;
}

interface OrganizationOption {
  id: string;
  name: string;
}

interface SyncMigrationsTabProps {
  organizations: OrganizationOption[];
}

export function SyncMigrationsTab({ organizations }: SyncMigrationsTabProps) {
  // Sync migrations state
  const [syncs, setSyncs] = useState<SyncMigrationInfo[]>([]);
  const [syncsLoading, setSyncsLoading] = useState(false);
  const [syncSearchTerm, setSyncSearchTerm] = useState('');
  const [selectedOrgFilter, setSelectedOrgFilter] = useState<string>('all');
  const [expandedCollections, setExpandedCollections] = useState<Set<string>>(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Fork dialog state
  const [availableDestinations, setAvailableDestinations] = useState<DestinationConnection[]>([]);
  const [selectedDestinationId, setSelectedDestinationId] = useState<string>('');
  const [replayFromArf, setReplayFromArf] = useState(false);

  // Collection-level state
  const [selectedCollection, setSelectedCollection] = useState<CollectionMigrationInfo | null>(null);
  const [collectionActionType, setCollectionActionType] = useState<'fork' | null>(null);

  // Per-sync fork state
  const [selectedSync, setSelectedSync] = useState<SyncMigrationInfo | null>(null);
  const [syncActionType, setSyncActionType] = useState<'fork' | null>(null);

  // ============ LOAD DATA ============

  const loadSyncs = async () => {
    try {
      setSyncsLoading(true);
      const params = new URLSearchParams({ limit: '500' });
      if (selectedOrgFilter && selectedOrgFilter !== 'all') {
        params.set('organization_id', selectedOrgFilter);
      }
      if (syncSearchTerm) {
        params.set('search', syncSearchTerm);
      }

      const response = await apiClient.get(`/admin/syncs?${params.toString()}`);
      if (response.ok) {
        setSyncs(await response.json());
      } else {
        toast.error('Failed to load syncs');
      }
    } catch (error) {
      console.error('Failed to load syncs:', error);
      toast.error('Failed to load syncs');
    } finally {
      setSyncsLoading(false);
    }
  };

  useEffect(() => {
    loadSyncs();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => loadSyncs(), syncSearchTerm ? 300 : 0);
    return () => clearTimeout(timer);
  }, [syncSearchTerm, selectedOrgFilter]);

  // ============ COMPUTED ============

  const collections = useMemo(() => {
    const filtered = syncs.filter(sync => {
      const matchesOrg = selectedOrgFilter === 'all' || sync.organization_id === selectedOrgFilter;
      const matchesSearch = !syncSearchTerm ||
        sync.collection_name.toLowerCase().includes(syncSearchTerm.toLowerCase()) ||
        sync.collection_readable_id.toLowerCase().includes(syncSearchTerm.toLowerCase());
      return matchesOrg && matchesSearch;
    });

    const grouped = new Map<string, CollectionMigrationInfo>();
    for (const sync of filtered) {
      if (!grouped.has(sync.collection_id)) {
        grouped.set(sync.collection_id, {
          collection_id: sync.collection_id,
          collection_readable_id: sync.collection_readable_id,
          collection_name: sync.collection_name,
          organization_id: sync.organization_id,
          organization_name: sync.organization_name,
          syncs: [],
        });
      }
      grouped.get(sync.collection_id)!.syncs.push(sync);
    }
    return Array.from(grouped.values());
  }, [syncs, selectedOrgFilter, syncSearchTerm]);

  // ============ HANDLERS ============

  const toggleCollection = (collectionId: string) => {
    setExpandedCollections(prev => {
      const next = new Set(prev);
      if (next.has(collectionId)) {
        next.delete(collectionId);
      } else {
        next.add(collectionId);
      }
      return next;
    });
  };

  const loadDestinations = async (orgId: string) => {
    try {
      const response = await apiClient.get(`/admin/organizations/${orgId}/destination-connections`);
      if (response.ok) {
        setAvailableDestinations(await response.json());
      }
    } catch (error) {
      console.error('Failed to load destinations:', error);
    }
  };

  // Collection-level handlers
  const openCollectionForkDialog = async (collection: CollectionMigrationInfo) => {
    setSelectedCollection(collection);
    setCollectionActionType('fork');
    loadDestinations(collection.organization_id);
  };

  const handleCollectionFork = async () => {
    if (!selectedCollection || !selectedDestinationId) return;
    try {
      setIsSubmitting(true);
      const response = await apiClient.post(
        `/admin/collections/${selectedCollection.collection_id}/destinations/fork?destination_connection_id=${selectedDestinationId}&replay_from_arf=${replayFromArf}`
      );
      if (response.ok) {
        const data = await response.json();
        let message = `Forked destination to ${data.syncs_updated} syncs`;
        if (data.replay_jobs && data.replay_jobs.length > 0) {
          message += `, started ${data.replay_jobs.length} replay jobs`;
        }
        toast.success(message);
        setCollectionActionType(null);
        setSelectedCollection(null);
        setSelectedDestinationId('');
        setReplayFromArf(false);
        loadSyncs();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to fork destination');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fork';
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCollectionForceResync = async (collectionId: string) => {
    if (!confirm('This will trigger a full resync for ALL syncs in this collection. Continue?')) return;
    try {
      const response = await apiClient.post(`/admin/collections/${collectionId}/force-resync`);
      if (response.ok) {
        const data = await response.json();
        toast.success(`Started ${data.jobs_started.length} resync jobs`);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start resync');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to start resync';
      toast.error(errorMessage);
    }
  };

  const handleCollectionSetRole = async (collectionId: string, connectionId: string, role: string) => {
    try {
      const response = await apiClient.post(
        `/admin/collections/${collectionId}/destinations/${connectionId}/set-role?role=${role}`
      );
      if (response.ok) {
        const data = await response.json();
        toast.success(`Updated role to ${role} for ${data.syncs_updated} syncs`);
        loadSyncs();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update role');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to update role';
      toast.error(errorMessage);
    }
  };

  const handleCollectionRemoveDestination = async (collectionId: string, connectionId: string) => {
    if (!confirm('Remove this destination from all syncs in the collection?')) return;
    try {
      const response = await apiClient.delete(`/admin/collections/${collectionId}/destinations/${connectionId}`);
      if (response.ok) {
        toast.success('Destination removed from collection');
        loadSyncs();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to remove destination');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to remove';
      toast.error(errorMessage);
    }
  };

  // Per-sync handlers
  const openForkDialog = (sync: SyncMigrationInfo) => {
    setSelectedSync(sync);
    setSyncActionType('fork');
    loadDestinations(sync.organization_id);
  };

  const handleFork = async () => {
    if (!selectedSync || !selectedDestinationId) return;

    try {
      setIsSubmitting(true);
      const response = await apiClient.post(`/syncs/${selectedSync.sync_id}/destinations/fork`, {
        destination_connection_id: selectedDestinationId,
        replay_from_arf: replayFromArf,
      });

      if (response.ok) {
        toast.success('Shadow destination added successfully');
        setSyncActionType(null);
        setSelectedSync(null);
        setSelectedDestinationId('');
        setReplayFromArf(false);
        loadSyncs();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to fork destination');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fork destination';
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSetRole = async (syncId: string, slotId: string, role: string) => {
    try {
      const response = await apiClient.post(`/syncs/${syncId}/destinations/${slotId}/set-role?role=${role}`);
      if (response.ok) {
        toast.success(`Destination role updated to ${role}`);
        loadSyncs();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update role');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to update role';
      toast.error(errorMessage);
    }
  };

  const handleRemoveDestination = async (syncId: string, slotId: string) => {
    if (!confirm('Remove this destination from the sync?')) return;
    try {
      const response = await apiClient.delete(`/syncs/${syncId}/destinations/${slotId}`);
      if (response.ok) {
        toast.success('Destination removed');
        loadSyncs();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to remove destination');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to remove destination';
      toast.error(errorMessage);
    }
  };

  const handleForceResync = async (syncId: string) => {
    if (!confirm('This will trigger a full resync from scratch. Continue?')) return;
    try {
      const response = await apiClient.post(`/admin/syncs/${syncId}/force-resync`);
      if (response.ok) {
        const data = await response.json();
        toast.success(`Full resync started (job: ${data.sync_job_id.slice(0, 8)}...)`);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start resync');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to start resync';
      toast.error(errorMessage);
    }
  };

  // ============ HELPERS ============

  const getRoleBadge = (role: string) => {
    const colors: Record<string, string> = {
      active: 'bg-green-500/20 text-green-400 border-green-500/30',
      shadow: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      deprecated: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    };
    return <Badge variant="outline" className={colors[role] || ''}>{role}</Badge>;
  };

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5" />
                Collection Migrations
              </CardTitle>
              <CardDescription>Manage destination slots for vector DB migrations. Collections group all syncs that must migrate together.</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Select value={selectedOrgFilter} onValueChange={setSelectedOrgFilter}>
                <SelectTrigger className="w-[200px]"><SelectValue placeholder="Filter by org" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Organizations</SelectItem>
                  {organizations.map(org => (
                    <SelectItem key={org.id} value={org.id}>{org.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="relative w-64">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input placeholder="Search collections..." value={syncSearchTerm} onChange={(e) => setSyncSearchTerm(e.target.value)} className="pl-8" />
              </div>
              <Button variant="outline" size="sm" onClick={loadSyncs} disabled={syncsLoading}>
                <RefreshCw className={cn("h-4 w-4", syncsLoading && "animate-spin")} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {syncsLoading ? (
            <div className="text-center py-12 text-muted-foreground">Loading collections...</div>
          ) : collections.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">No collections found</div>
          ) : (
            <div className="border-t">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-[40px]"></TableHead>
                    <TableHead className="w-[200px]">Collection / Sync</TableHead>
                    <TableHead className="w-[150px]">Organization</TableHead>
                    <TableHead className="w-[120px]">Source</TableHead>
                    <TableHead className="w-[300px]">Destinations</TableHead>
                    <TableHead className="text-right w-[120px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {collections.map((collection) => (
                    <React.Fragment key={collection.collection_id}>
                      {/* Collection Row */}
                      <TableRow className="hover:bg-muted/30 bg-muted/10">
                        <TableCell className="py-2 w-[40px] cursor-pointer" onClick={() => toggleCollection(collection.collection_id)}>
                          {expandedCollections.has(collection.collection_id) ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                        </TableCell>
                        <TableCell className="py-2 cursor-pointer" onClick={() => toggleCollection(collection.collection_id)}>
                          <div className="flex items-center gap-2">
                            <FolderOpen className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <div className="font-medium">{collection.collection_name}</div>
                              <div className="text-xs text-muted-foreground">{collection.collection_readable_id}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="py-2 text-sm">{collection.organization_name}</TableCell>
                        <TableCell className="py-2 text-sm text-muted-foreground">
                          {collection.syncs.length} sync{collection.syncs.length !== 1 ? 's' : ''}
                        </TableCell>
                        <TableCell className="py-2">
                          {/* Show collection-level destinations with role management */}
                          <div className="flex flex-wrap gap-1.5">
                            {(() => {
                              // Aggregate destinations from all syncs
                              const destMap = new Map<string, { name: string; roles: Set<string>; connectionId: string }>();
                              for (const sync of collection.syncs) {
                                for (const slot of sync.destination_slots) {
                                  if (!destMap.has(slot.connection_id)) {
                                    destMap.set(slot.connection_id, { name: slot.connection_name, roles: new Set(), connectionId: slot.connection_id });
                                  }
                                  destMap.get(slot.connection_id)!.roles.add(slot.role);
                                }
                              }

                              return Array.from(destMap.values()).map((dest) => {
                                const roles = Array.from(dest.roles);
                                const effectiveRole = roles.length === 1 ? roles[0] : 'mixed';

                                return (
                                  <DropdownMenu key={dest.connectionId}>
                                    <DropdownMenuTrigger asChild>
                                      <button className="flex items-center gap-1 hover:opacity-80 cursor-pointer">
                                        {effectiveRole === 'mixed' ? (
                                          <Badge variant="outline" className="text-xs bg-yellow-500/20 text-yellow-400 border-yellow-500/30">mixed</Badge>
                                        ) : (
                                          getRoleBadge(effectiveRole as 'active' | 'shadow' | 'deprecated')
                                        )}
                                        <span className="text-xs text-muted-foreground">{dest.name}</span>
                                        <ChevronDown className="h-3 w-3 text-muted-foreground" />
                                      </button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="start">
                                      <div className="px-2 py-1 text-xs text-muted-foreground">
                                        Apply to all {collection.syncs.length} syncs
                                      </div>
                                      <DropdownMenuSeparator />
                                      {effectiveRole !== 'active' && (
                                        <DropdownMenuItem onClick={() => handleCollectionSetRole(collection.collection_id, dest.connectionId, 'active')}>
                                          <ArrowUp className="h-3 w-3 mr-2 text-green-500" />
                                          Promote to Active
                                        </DropdownMenuItem>
                                      )}
                                      {effectiveRole !== 'shadow' && (
                                        <DropdownMenuItem onClick={() => handleCollectionSetRole(collection.collection_id, dest.connectionId, 'shadow')}>
                                          <ArrowRightLeft className="h-3 w-3 mr-2 text-blue-500" />
                                          {effectiveRole === 'active' ? 'Demote to Shadow' : 'Set as Shadow'}
                                        </DropdownMenuItem>
                                      )}
                                      {effectiveRole !== 'deprecated' && (
                                        <DropdownMenuItem onClick={() => handleCollectionSetRole(collection.collection_id, dest.connectionId, 'deprecated')}>
                                          <ArrowDown className="h-3 w-3 mr-2 text-gray-500" />
                                          Mark Deprecated
                                        </DropdownMenuItem>
                                      )}
                                      {effectiveRole !== 'active' && (
                                        <>
                                          <DropdownMenuSeparator />
                                          <DropdownMenuItem
                                            onClick={() => handleCollectionRemoveDestination(collection.collection_id, dest.connectionId)}
                                            className="text-destructive"
                                          >
                                            <Trash2 className="h-3 w-3 mr-2" />
                                            Remove from all
                                          </DropdownMenuItem>
                                        </>
                                      )}
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                );
                              });
                            })()}
                          </div>
                        </TableCell>
                        <TableCell className="text-right py-2">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleCollectionForceResync(collection.collection_id)}
                              className="h-7 px-2"
                              title="Force full resync on all syncs"
                            >
                              <Play className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openCollectionForkDialog(collection)}
                              className="h-7 px-2"
                              title="Fork: Add destination to all syncs"
                            >
                              <GitBranch className="h-3 w-3 mr-1" />
                              <span className="text-xs">Fork</span>
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>

                      {/* Expanded Sync Rows */}
                      {expandedCollections.has(collection.collection_id) && collection.syncs.map((sync) => (
                        <TableRow key={sync.sync_id} className="hover:bg-muted/20 bg-background">
                          <TableCell className="py-2 w-[40px]"></TableCell>
                          <TableCell className="py-2 pl-8">
                            <div className="text-sm text-muted-foreground">{sync.sync_name || 'Sync'}</div>
                          </TableCell>
                          <TableCell className="py-2"></TableCell>
                          <TableCell className="py-2">
                            {sync.source_short_name && (
                              <div className="flex items-center gap-2">
                                <img src={getAppIconUrl(sync.source_short_name)} alt="" className="h-4 w-4" />
                                <span className="text-sm">{sync.source_short_name}</span>
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="py-2">
                            <div className="flex flex-wrap gap-1.5">
                              {sync.destination_slots.length === 0 ? (
                                <span className="text-xs text-muted-foreground">No destinations</span>
                              ) : (
                                sync.destination_slots.map((slot) => (
                                  <DropdownMenu key={slot.slot_id}>
                                    <DropdownMenuTrigger asChild>
                                      <button className="flex items-center gap-1 hover:opacity-80 cursor-pointer" onClick={(e) => e.stopPropagation()}>
                                        {getRoleBadge(slot.role)}
                                        <span className="text-xs text-muted-foreground">{slot.connection_name}</span>
                                        <ChevronDown className="h-3 w-3 text-muted-foreground" />
                                      </button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="start">
                                      {slot.role !== 'active' && (
                                        <DropdownMenuItem onClick={() => handleSetRole(sync.sync_id, slot.slot_id, 'active')}>
                                          <ArrowUp className="h-3 w-3 mr-2 text-green-500" />
                                          Promote to Active
                                        </DropdownMenuItem>
                                      )}
                                      {slot.role !== 'shadow' && (
                                        <DropdownMenuItem onClick={() => handleSetRole(sync.sync_id, slot.slot_id, 'shadow')}>
                                          <ArrowRightLeft className="h-3 w-3 mr-2 text-blue-500" />
                                          {slot.role === 'active' ? 'Demote to Shadow' : 'Promote to Shadow'}
                                        </DropdownMenuItem>
                                      )}
                                      {slot.role !== 'deprecated' && (
                                        <DropdownMenuItem onClick={() => handleSetRole(sync.sync_id, slot.slot_id, 'deprecated')}>
                                          <ArrowDown className="h-3 w-3 mr-2 text-gray-500" />
                                          Mark Deprecated
                                        </DropdownMenuItem>
                                      )}
                                      {slot.role !== 'active' && (
                                        <>
                                          <DropdownMenuSeparator />
                                          <DropdownMenuItem
                                            onClick={() => handleRemoveDestination(sync.sync_id, slot.slot_id)}
                                            className="text-destructive"
                                          >
                                            <Trash2 className="h-3 w-3 mr-2" />
                                            Remove
                                          </DropdownMenuItem>
                                        </>
                                      )}
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                ))
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-right py-2">
                            <div className="flex justify-end gap-1">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); handleForceResync(sync.sync_id); }}
                                className="h-7 px-2"
                                title="Force full resync"
                              >
                                <Play className="h-3 w-3" />
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); openForkDialog(sync); }}
                                className="h-7 px-2"
                                title="Fork: Add destination"
                              >
                                <GitBranch className="h-3 w-3" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </React.Fragment>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ============ DIALOGS ============ */}

      {/* Fork Destination Dialog (Single Sync) */}
      <Dialog open={syncActionType === 'fork'} onOpenChange={(open) => !open && setSyncActionType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><GitBranch className="h-5 w-5" /> Fork Destination</DialogTitle>
            <DialogDescription>Add a shadow destination to <strong>{selectedSync?.collection_name}</strong> for migration testing</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Target Destination</Label>
              <Select value={selectedDestinationId} onValueChange={setSelectedDestinationId}>
                <SelectTrigger><SelectValue placeholder="Select destination..." /></SelectTrigger>
                <SelectContent>
                  {availableDestinations.map((dest) => (
                    <SelectItem key={dest.id} value={dest.id}>{dest.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="replay" checked={replayFromArf} onChange={(e) => setReplayFromArf(e.target.checked)} className="rounded" />
              <Label htmlFor="replay" className="text-sm">Replay existing data from ARF storage</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSyncActionType(null)} disabled={isSubmitting}>Cancel</Button>
            <Button onClick={handleFork} disabled={isSubmitting || !selectedDestinationId}>{isSubmitting ? 'Forking...' : 'Fork Destination'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Fork Destination Dialog (Collection-Level) */}
      <Dialog open={collectionActionType === 'fork'} onOpenChange={(open) => !open && setCollectionActionType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Fork Destination to Collection
            </DialogTitle>
            <DialogDescription>
              Add a shadow destination to <strong>all {selectedCollection?.syncs.length} syncs</strong> in <strong>{selectedCollection?.collection_name}</strong>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="bg-muted/50 p-3 rounded-lg text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <FolderOpen className="h-4 w-4" />
                <span>This will add the destination to all syncs in the collection, ensuring consistent migration.</span>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Target Destination</Label>
              <Select value={selectedDestinationId} onValueChange={setSelectedDestinationId}>
                <SelectTrigger><SelectValue placeholder="Select destination..." /></SelectTrigger>
                <SelectContent>
                  {availableDestinations.map((dest) => (
                    <SelectItem key={dest.id} value={dest.id}>{dest.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {availableDestinations.length === 0 && (
                <p className="text-xs text-muted-foreground">No destination connections configured for this organization.</p>
              )}
            </div>
            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="collection-replay"
                checked={replayFromArf}
                onChange={(e) => setReplayFromArf(e.target.checked)}
                className="rounded border-border"
              />
              <Label htmlFor="collection-replay" className="text-sm cursor-pointer">
                Replay existing data from ARF storage
              </Label>
            </div>
            {replayFromArf && (
              <div className="bg-amber-500/10 border border-amber-500/30 p-3 rounded-lg text-sm">
                <div className="flex items-start gap-2 text-amber-500">
                  <RefreshCw className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>This will start replay jobs to copy all existing data to the new destination. This may take a while for large collections.</span>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setCollectionActionType(null); setSelectedDestinationId(''); setReplayFromArf(false); }} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleCollectionFork} disabled={isSubmitting || !selectedDestinationId}>
              {isSubmitting ? 'Forking...' : `Fork to ${selectedCollection?.syncs.length} Syncs`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
