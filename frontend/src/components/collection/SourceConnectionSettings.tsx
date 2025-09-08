import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/hooks/use-toast';
import { MoreVertical, Edit, Clock, Trash } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';
import { SyncSchedule, SyncScheduleConfig, buildCronExpression, isValidCronExpression } from '@/components/sync/SyncSchedule';
import { EditSourceConnectionDialog } from './EditSourceConnectionDialog';
import { emitCollectionEvent, SOURCE_CONNECTION_UPDATED } from '@/lib/events';
import { DESIGN_SYSTEM } from '@/lib/design-system';

interface SourceConnection {
  id: string;
  name: string;
  description?: string;
  short_name: string;
  config_fields?: Record<string, any>;
  sync_id?: string;
  organization_id: string;
  created_at: string;
  modified_at: string;
  connection_id?: string;
  collection: string;
  white_label_id?: string;
  created_by_email: string;
  modified_by_email: string;
  auth_fields?: Record<string, any> | string;
  status?: string;
  latest_sync_job_status?: string;
  latest_sync_job_id?: string;
  latest_sync_job_started_at?: string;
  latest_sync_job_completed_at?: string;
  latest_sync_job_error?: string;
  cron_schedule?: string;
  next_scheduled_run?: string;
  auth_provider?: string;
  auth_provider_config?: Record<string, any>;
}

interface SourceConnectionSettingsProps {
  sourceConnection: SourceConnection;
  onUpdate: (updatedConnection: SourceConnection) => void;
  onDelete?: () => void;
  isDark: boolean;
  resolvedTheme?: string;
}

export const SourceConnectionSettings: React.FC<SourceConnectionSettingsProps> = ({
  sourceConnection,
  onUpdate,
  onDelete,
  isDark,
  resolvedTheme
}) => {
  // Dialog states
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [showScheduleDialog, setShowScheduleDialog] = useState(false);
  const [showEditDetailsDialog, setShowEditDetailsDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);

  // Schedule state
  const [scheduleConfig, setScheduleConfig] = useState<SyncScheduleConfig>({
    type: "one-time",
    frequency: "custom"
  });

  // Edit form state
  const [editFormData, setEditFormData] = useState({
    name: '',
    description: '',
    config_fields: {} as Record<string, any>,
    auth_fields: {} as Record<string, any>,
    auth_provider: '',
    auth_provider_config: {} as Record<string, any>
  });
  const [sourceDetails, setSourceDetails] = useState<any>(null);
  const [authProviderDetails, setAuthProviderDetails] = useState<any>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [showPasswordFields, setShowPasswordFields] = useState<Record<string, boolean>>({});

  // Initialize schedule config when sourceConnection changes
  useEffect(() => {
    if (sourceConnection?.cron_schedule) {
      const cronParts = sourceConnection.cron_schedule.split(' ');
      const utcMinute = parseInt(cronParts[0]);
      const utcHour = cronParts[1] !== '*' ? parseInt(cronParts[1]) : undefined;

      setScheduleConfig({
        type: "scheduled",
        frequency: "custom",
        hour: utcHour,
        minute: utcMinute,
        cronExpression: sourceConnection.cron_schedule
      });
    } else {
      setScheduleConfig({
        type: "one-time",
        frequency: "custom"
      });
    }
  }, [sourceConnection]);

  // Fetch source details when edit dialog opens
  const fetchSourceDetailsForEdit = async () => {
    if (!sourceConnection?.short_name) return;

    try {
      // Fetch source details
      const sourceResponse = await apiClient.get(`/sources/detail/${sourceConnection.short_name}`);
      if (sourceResponse.ok) {
        const sourceData = await sourceResponse.json();
        setSourceDetails(sourceData);
      }

      // Fetch auth provider details if using auth provider
      if (sourceConnection.auth_provider) {
        const authProviderResponse = await apiClient.get(`/auth-providers/connections/${sourceConnection.auth_provider}`);

        if (authProviderResponse.ok) {
          const connectionData = await authProviderResponse.json();
          const authProviderShortName = connectionData.short_name;

          const authProviderDetailsResponse = await apiClient.get(`/auth-providers/detail/${authProviderShortName}`);
          if (authProviderDetailsResponse.ok) {
            const authProviderData = await authProviderDetailsResponse.json();
            setAuthProviderDetails(authProviderData);
          }
        }
      }
    } catch (error) {
      console.error("Error fetching source details:", error);
    }
  };

  // Initialize form data when dialog opens
  useEffect(() => {
    if (showEditDetailsDialog && sourceConnection) {
      setEditFormData({
        name: sourceConnection.name || '',
        description: sourceConnection.description || '',
        config_fields: sourceConnection.config_fields || {},
        auth_fields: {},
        auth_provider: sourceConnection.auth_provider || '',
        auth_provider_config: sourceConnection.auth_provider_config || {}
      });

      fetchSourceDetailsForEdit();
    }
  }, [showEditDetailsDialog, sourceConnection]);

  // Handle schedule save
  const handleScheduleSave = async () => {
    try {
      const cronExpression = scheduleConfig.type === "scheduled"
        ? buildCronExpression(scheduleConfig)
        : null;

      if (scheduleConfig.type === "scheduled" &&
        scheduleConfig.frequency === "custom" &&
        scheduleConfig.cronExpression &&
        !isValidCronExpression(scheduleConfig.cronExpression)) {
        toast({
          title: "Validation Error",
          description: "Invalid cron expression. Please check the format.",
          variant: "destructive"
        });
        return;
      }

      const updateData = { cron_schedule: cronExpression };

      const response = await apiClient.put(
        `/source-connections/${sourceConnection.id}`,
        null,
        updateData
      );

      if (!response.ok) {
        throw new Error("Failed to update schedule");
      }

      const updatedConnection = await response.json();
      onUpdate(updatedConnection);
      setShowScheduleDialog(false);

      toast({
        title: "Success",
        description: "Schedule updated successfully"
      });
    } catch (error) {
      console.error("Error updating schedule:", error);
      toast({
        title: "Error",
        description: "Failed to update schedule",
        variant: "destructive"
      });
    }
  };

  // Handle edit form submission
  const handleEditSubmit = async () => {
    setIsUpdating(true);

    try {
      const updateData: any = {};

      if (editFormData.name !== sourceConnection?.name) {
        updateData.name = editFormData.name;
      }

      if (editFormData.description !== sourceConnection?.description) {
        updateData.description = editFormData.description;
      }

      const hasConfigChanges = Object.keys(editFormData.config_fields).some(
        key => editFormData.config_fields[key] !== sourceConnection?.config_fields?.[key]
      );
      if (hasConfigChanges) {
        updateData.config_fields = editFormData.config_fields;
      }

      const filledAuthFields = Object.entries(editFormData.auth_fields)
        .filter(([_, value]) => value && String(value).trim() !== '')
        .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});

      if (Object.keys(filledAuthFields).length > 0) {
        updateData.auth_fields = filledAuthFields;
      }

      if (editFormData.auth_provider !== sourceConnection?.auth_provider) {
        updateData.auth_provider = editFormData.auth_provider;
      }

      if (sourceConnection?.auth_provider || editFormData.auth_provider) {
        const hasAuthProviderConfigChanges = Object.keys(editFormData.auth_provider_config).some(
          key => editFormData.auth_provider_config[key] !== sourceConnection?.auth_provider_config?.[key]
        );
        if (hasAuthProviderConfigChanges) {
          updateData.auth_provider_config = editFormData.auth_provider_config;
        }
      }

      if (Object.keys(updateData).length === 0) {
        toast({
          title: "No changes",
          description: "No changes were made to the connection"
        });
        setShowEditDetailsDialog(false);
        return;
      }

      const response = await apiClient.put(`/source-connections/${sourceConnection?.id}`, null, updateData);

      if (!response.ok) {
        throw new Error("Failed to update source connection");
      }

      const updatedConnection = await response.json();
      onUpdate(updatedConnection);

      emitCollectionEvent(SOURCE_CONNECTION_UPDATED, {
        id: updatedConnection.id,
        collectionId: updatedConnection.collection,
        updatedConnection
      });

      toast({
        title: "Success",
        description: "Source connection updated successfully"
      });

      setShowEditDetailsDialog(false);
    } catch (error) {
      console.error("Error updating source connection:", error);
      toast({
        title: "Error",
        description: "Failed to update source connection",
        variant: "destructive"
      });
    } finally {
      setIsUpdating(false);
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (deleteConfirmText !== sourceConnection.name) return;

    setIsDeleting(true);
    try {
      const response = await apiClient.delete(`/source-connections/${sourceConnection.id}`);

      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || 'Failed to delete source connection');
      }

      setShowDeleteDialog(false);
      setDeleteConfirmText('');

      toast({
        title: "Source connection deleted",
        description: "The source connection and all synced data have been permanently deleted."
      });

      emitCollectionEvent(SOURCE_CONNECTION_UPDATED, {
        id: sourceConnection.id,
        collectionId: sourceConnection.collection,
        deleted: true
      });

      if (onDelete) {
        onDelete();
      }
    } catch (error) {
      console.error('Error deleting source connection:', error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete source connection",
        variant: "destructive"
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Helper to check if field is OAuth token field
  const isTokenField = (fieldName: string): boolean => {
    return fieldName === 'refresh_token' || fieldName === 'access_token';
  };

  // Helper to format time since
  const formatTimeSince = (dateStr: string) => {
    const now = Date.now();
    const date = new Date(dateStr).getTime();
    const diffMs = now - date;
    const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

    if (diffHrs > 24) {
      const days = Math.floor(diffHrs / 24);
      return `${days}d ago`;
    } else if (diffHrs > 0) {
      return `${diffHrs}h ${diffMins}m ago`;
    } else {
      return `${diffMins}m ago`;
    }
  };

  return (
    <>
      {/* Settings Dropdown Menu */}
      <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
        <DropdownMenuTrigger asChild>
          <Button size="sm" variant="ghost" className={cn(
            DESIGN_SYSTEM.buttons.heights.secondary,
            "w-8 p-0"
          )}>
            <MoreVertical className={DESIGN_SYSTEM.icons.inline} />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem onClick={() => {
            setDropdownOpen(false);
            setShowEditDetailsDialog(true);
          }}>
            <Edit className={cn(DESIGN_SYSTEM.icons.inline, "mr-2")} />
            Edit Details
          </DropdownMenuItem>

          <DropdownMenuItem onClick={() => {
            setDropdownOpen(false);
            setShowScheduleDialog(true);
          }}>
            <Clock className={cn(DESIGN_SYSTEM.icons.inline, "mr-2")} />
            Edit Schedule
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem
            className="text-red-600 focus:text-red-600 focus:bg-red-50 dark:focus:bg-red-900/20"
            onClick={() => {
              setDropdownOpen(false);
              setShowDeleteDialog(true);
            }}
          >
            <Trash className={cn(DESIGN_SYSTEM.icons.inline, "mr-2")} />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Schedule Edit Dialog */}
      {showScheduleDialog && (
        <Dialog open={showScheduleDialog} onOpenChange={setShowScheduleDialog}>
          <DialogContent className={cn("max-w-3xl", isDark ? "bg-card-solid border-border" : "")}>
            <DialogHeader>
              <DialogTitle className={isDark ? "text-foreground" : ""}>Edit Sync Schedule</DialogTitle>
            </DialogHeader>

            <div className="py-4">
              <SyncSchedule
                value={scheduleConfig}
                onChange={setScheduleConfig}
              />
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setShowScheduleDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleScheduleSave}>
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Edit Source Connection Dialog */}
      <EditSourceConnectionDialog
        open={showEditDetailsDialog}
        onOpenChange={setShowEditDetailsDialog}
        sourceConnection={sourceConnection}
        editFormData={editFormData}
        setEditFormData={setEditFormData}
        sourceDetails={sourceDetails}
        authProviderDetails={authProviderDetails}
        isUpdating={isUpdating}
        showPasswordFields={showPasswordFields}
        setShowPasswordFields={setShowPasswordFields}
        handleEditSubmit={handleEditSubmit}
        formatTimeSince={formatTimeSince}
        isTokenField={isTokenField}
        isDark={isDark}
        resolvedTheme={resolvedTheme}
      />

      {/* Delete Confirmation Dialog */}
      {showDeleteDialog && (
        <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <AlertDialogContent className={cn(
            "border-border",
            isDark ? "bg-card-solid text-foreground" : "bg-white"
          )}>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Source Connection</AlertDialogTitle>
              <AlertDialogDescription>
                <div className="space-y-4">
                  <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 space-y-3">
                    <ul className="space-y-2 ml-4">
                      <li className="flex items-start">
                        <span className="mr-2">•</span>
                        <div>
                          <p className="text-sm text-muted-foreground">
                            You will need to re-authenticate and reconfigure the connection to sync data from this source again.
                          </p>
                        </div>
                      </li>
                      <li className="flex items-start">
                        <span className="mr-2">•</span>
                        <div>
                          <p className="text-sm text-muted-foreground">
                            All data that was synced from this source will be permanently removed from the knowledge base and cannot be recovered.
                          </p>
                        </div>
                      </li>
                    </ul>
                  </div>
                </div>

                <div className="mt-4">
                  <Label htmlFor="confirm-delete" className="text-sm font-medium block mb-2">
                    Type <span className="font-bold">{sourceConnection.name}</span> to confirm deletion
                  </Label>
                  <Input
                    id="confirm-delete"
                    value={deleteConfirmText}
                    onChange={(e) => setDeleteConfirmText(e.target.value)}
                    className="w-full"
                    placeholder={sourceConnection.name}
                  />
                </div>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => {
                setShowDeleteDialog(false);
                setDeleteConfirmText('');
              }}>
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                disabled={deleteConfirmText !== sourceConnection.name || isDeleting}
                className="bg-red-600 text-white hover:bg-red-700 dark:bg-red-500 dark:text-white dark:hover:bg-red-600 disabled:opacity-50"
              >
                {isDeleting ? 'Deleting...' : 'Delete Connection'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </>
  );
};
