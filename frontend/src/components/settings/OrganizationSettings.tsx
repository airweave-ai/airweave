import { useState, useEffect } from "react";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Loader2, Save } from 'lucide-react';
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

  const handleDeleteOrganization = async () => {
    if (!currentOrganization) return;

    // Safety check: Verify user is owner
    if (currentOrganization.role !== 'owner') {
      toast.error('Only organization owners can delete the organization');
      return;
    }

    // Check if this is the last organization
    if (organizations.length === 1) {
      toast.error('Cannot delete your only organization. You must have at least one organization.');
      return;
    }

    // Extra warning if this is the primary organization
    const warningMessage = currentOrganization.is_primary
      ? `⚠️ WARNING: You are about to delete your PRIMARY organization "${currentOrganization.name}".\n\n` +
        'This will permanently delete:\n' +
        '• All collections and data\n' +
        '• All source connections\n' +
        '• All API keys\n' +
        '• All organization settings\n\n' +
        'This action CANNOT be undone.\n\n' +
        'Type the organization name to confirm:'
      : `Are you sure you want to delete "${currentOrganization.name}"?\n\n` +
        'This will permanently delete:\n' +
        '• All collections and data\n' +
        '• All source connections\n' +
        '• All API keys\n' +
        '• All organization settings\n\n' +
        'This action CANNOT be undone.\n\n' +
        'Type the organization name to confirm:';

    // Require typing the organization name for confirmation
    const userInput = window.prompt(warningMessage);

    if (!userInput) {
      // User cancelled
      return;
    }

    if (userInput.trim() !== currentOrganization.name) {
      toast.error('Organization name does not match. Deletion cancelled.');
      return;
    }

    try {
      setIsLoading(true);

      const response = await apiClient.delete(`/organizations/${currentOrganization.id}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to delete organization: ${response.status}`);
      }

      toast.success('Organization deleted successfully');

      // Remove the organization from the store, which will automatically switch to the next best org
      removeOrganization(currentOrganization.id);

      // Check if there are any remaining organizations
      const remainingOrgs = organizations.filter(org => org.id !== currentOrganization.id);

      if (remainingOrgs.length === 0) {
        // No organizations left, redirect to no-organization page
        navigate('/no-organization');
      } else {
        // There are other organizations, navigate to dashboard which will show the new current org
        // Use window.location.href to ensure a full page reload and proper state initialization
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
    </div>
  );
};
