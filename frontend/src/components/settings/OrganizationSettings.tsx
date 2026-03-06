import { useState, useEffect } from "react";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Loader2, Save, TriangleAlert } from 'lucide-react';
import { apiClient } from "@/lib/api";
import { toast } from 'sonner';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { useNavigate } from 'react-router-dom';

interface Organization {
  id: string;
  name: string;
  description?: string;
  role: string;
  is_primary: boolean;
}

interface OrganizationSettingsProps {
  currentOrganization: Organization;
  onOrganizationUpdate: (id: string, updates: Partial<Organization>) => void;
  onPrimaryToggle: (checked: boolean) => Promise<void>;
  isPrimaryToggleLoading: boolean;
}

export const OrganizationSettings = ({
  currentOrganization,
  onOrganizationUpdate,
  onPrimaryToggle,
  isPrimaryToggleLoading
}: OrganizationSettingsProps) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');

  const { removeOrganization, organizations } = useOrganizationStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (currentOrganization) {
      setName(currentOrganization.name);
      setDescription(currentOrganization.description || '');
    }
  }, [currentOrganization]);

  const handleSave = async () => {
    if (!currentOrganization) return;

    try {
      setIsLoading(true);

      const response = await apiClient.put(`/organizations/${currentOrganization.id}`, undefined, {
        name,
        description
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to update organization: ${response.status}`);
      }

      const updatedOrganization = await response.json();

      onOrganizationUpdate(currentOrganization.id, {
        name: updatedOrganization.name,
        description: updatedOrganization.description
      });

      toast.success('Organization updated successfully');

    } catch (error) {
      console.error('Failed to update organization:', error);
      toast.error('Failed to update organization');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteOrganization = () => {
    if (!currentOrganization) return;

    if (currentOrganization.role !== 'owner') {
      toast.error('Only organization owners can delete the organization');
      return;
    }

    if (organizations.length === 1) {
      toast.error('Cannot delete your only organization. You must have at least one organization.');
      return;
    }

    setDeleteConfirmation('');
    setShowDeleteDialog(true);
  };

  const confirmDeleteOrganization = async () => {
    if (!currentOrganization) return;
    if (deleteConfirmation.trim() !== currentOrganization.name) return;

    try {
      setIsLoading(true);
      setShowDeleteDialog(false);

      const response = await apiClient.delete(`/organizations/${currentOrganization.id}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to delete organization: ${response.status}`);
      }

      toast.success('Organization deleted successfully');

      removeOrganization(currentOrganization.id);

      const remainingOrgs = organizations.filter(org => org.id !== currentOrganization.id);

      if (remainingOrgs.length === 0) {
        navigate('/no-organization');
      } else {
        window.location.href = '/';
      }

    } catch (error: any) {
      console.error('Failed to delete organization:', error);
      const errorMessage = error.message || 'Failed to delete organization';
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const canEdit = ['owner', 'admin'].includes(currentOrganization.role);
  const canDelete = currentOrganization.role === 'owner';

  return (
    <div className="space-y-8">
      {/* Basic Information */}
      <div className="space-y-6 max-w-lg">
        <div>
          <Label htmlFor="name" className="text-sm font-medium text-foreground mb-1">Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter organization name"
            disabled={!canEdit}
            className="h-9 mt-1 border-border focus:outline-none focus:ring-0 focus:ring-offset-0 focus:shadow-none focus:border-border"
          />
          {!canEdit && (
            <p className="text-xs text-muted-foreground mt-1">
              Only owners and admins can edit
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Enter organization description (optional)"
            rows={3}
            disabled={!canEdit}
            className="resize-none border-border focus:outline-none focus:ring-0 focus:ring-offset-0 focus:shadow-none focus:border-border placeholder:text-muted-foreground/60 mt-1"
          />
        </div>

        {canEdit && (
          <div className="flex justify-end">
            <Button
              onClick={handleSave}
              disabled={isLoading}
              className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-white h-8 px-3.5 text-sm"
            >
              {isLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Save className="h-3 w-3" />
              )}
              {isLoading ? 'Saving...' : 'Save changes'}
            </Button>
          </div>
        )}
      </div>

      {/* Primary Organization Setting */}
      <div className="pt-6 border-t border-border max-w-lg">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-sm font-medium">Primary Organization</h3>
            <p className="text-xs text-muted-foreground">
              This organization will be used as the default.
            </p>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <Switch
                  checked={currentOrganization.is_primary}
                  onCheckedChange={onPrimaryToggle}
                  disabled={isPrimaryToggleLoading}
                  className="data-[state=checked]:bg-primary data-[state=unchecked]:bg-input"
                />
              </div>
            </TooltipTrigger>
            {currentOrganization.is_primary && (
              <TooltipContent side="left" className="max-w-xs">
                <p className="text-xs">
                  Cannot unset primary organization directly.
                  Set another organization as primary to change this.
                </p>
              </TooltipContent>
            )}
          </Tooltip>
        </div>
      </div>

      {/* Danger Zone */}
      {canDelete && (
        <div className="pt-6 border-t border-border max-w-lg">
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-medium text-foreground">Delete organization</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Permanently delete this organization and all data
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDeleteOrganization}
              disabled={isLoading}
              className="h-8 px-4 text-sm"
            >
              {isLoading ? 'Deleting...' : 'Delete organization'}
            </Button>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <TriangleAlert className="h-5 w-5" />
              Delete organization
            </DialogTitle>
            <DialogDescription className="pt-2 space-y-3">
              {currentOrganization.is_primary && (
                <span className="block text-amber-500 font-medium text-sm">
                  This is your primary organization.
                </span>
              )}
              <span className="block">
                This will permanently delete <span className="font-medium text-foreground">{currentOrganization.name}</span> and all of its data, including collections, source connections, API keys, and settings.
              </span>
              <span className="block font-medium text-foreground text-sm">
                This action cannot be undone.
              </span>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 pt-1">
            <Label htmlFor="delete-confirm" className="text-sm text-muted-foreground">
              Type <span className="font-mono text-foreground select-all">{currentOrganization.name}</span> to confirm
            </Label>
            <Input
              id="delete-confirm"
              value={deleteConfirmation}
              onChange={(e) => setDeleteConfirmation(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && deleteConfirmation.trim() === currentOrganization.name) {
                  confirmDeleteOrganization();
                }
              }}
              placeholder={currentOrganization.name}
              autoFocus
              autoComplete="off"
              className="h-9 border-border focus:outline-none focus:ring-0 focus:ring-offset-0 focus:shadow-none focus:border-border"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDeleteDialog(false)}
              className="h-8"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={confirmDeleteOrganization}
              disabled={deleteConfirmation.trim() !== currentOrganization.name}
              className="h-8"
            >
              Delete organization
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
