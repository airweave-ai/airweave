import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  Check,
  Copy,
  Key,
  Loader2,
  Save,
  Settings as SettingsIcon,
  Star,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePageHeader } from "@/components/ui/page-header";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  deleteOrganization,
  setPrimaryOrganization,
  updateOrganization,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { generateOrgSlug } from "@/lib/org-utils";
import { queryKeys } from "@/lib/query-keys";

export const Route = createFileRoute("/$orgSlug/settings/")({
  component: SettingsPage,
});

function SettingsPage() {
  const { getAccessTokenSilently } = useAuth0();
  const { organization, organizations } = useOrg();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isCopied, setIsCopied] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  usePageHeader({
    title: "Settings",
    description: "Manage organization settings, preferences, and configuration",
  });

  // Sync form state with organization data
  useEffect(() => {
    if (organization) {
      setName(organization.name);
      setDescription(organization.description || "");
    }
  }, [organization]);

  // Update organization mutation
  const updateMutation = useMutation({
    mutationFn: async (data: { name: string; description: string }) => {
      const token = await getAccessTokenSilently();
      return updateOrganization(token, organization!.id, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.organizations.all });
      toast.success("Organization updated successfully");
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to update organization"
      );
    },
  });

  // Set primary organization mutation
  const setPrimaryMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return setPrimaryOrganization(token, organization!.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.organizations.all });
      toast.success(`${organization!.name} is now your primary organization`);
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to set primary organization"
      );
    },
  });

  // Delete organization mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return deleteOrganization(token, organization!.id);
    },
    onSuccess: () => {
      toast.success("Organization deleted successfully");
      queryClient.invalidateQueries({ queryKey: queryKeys.organizations.all });

      // Navigate to another organization or home
      const remainingOrgs = organizations.filter(
        (org) => org.id !== organization!.id
      );
      if (remainingOrgs.length > 0) {
        const nextOrg =
          remainingOrgs.find((org) => org.is_primary) || remainingOrgs[0];
        navigate({
          to: "/$orgSlug/collections",
          params: { orgSlug: generateOrgSlug(nextOrg) },
        });
      } else {
        navigate({ to: "/onboarding" });
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to delete organization"
      );
    },
  });

  if (!organization) {
    return null;
  }

  const handleSave = () => {
    updateMutation.mutate({ name, description });
  };

  const handlePrimaryToggle = (checked: boolean) => {
    if (!checked) {
      toast.error("You must have at least one primary organization");
      return;
    }
    setPrimaryMutation.mutate();
  };

  const handleCopyId = () => {
    navigator.clipboard.writeText(organization.id);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
    toast.success("Organization ID copied to clipboard");
  };

  const handleDelete = () => {
    deleteMutation.mutate();
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case "owner":
        return <Key className="size-3" />;
      case "admin":
        return <SettingsIcon className="size-3" />;
      default:
        return <Users className="size-3" />;
    }
  };

  const canEdit = ["owner", "admin"].includes(organization.role);
  const canDelete = organization.role === "owner";
  const isLastOrg = organizations.length === 1;
  const hasChanges =
    name !== organization.name ||
    description !== (organization.description || "");

  return (
    <div className="mx-auto max-w-4xl p-6">
      {/* Header with org info */}
      <div className="mb-8 flex flex-col">
        <div className="mb-2 flex items-center gap-3">
          <h1 className="text-xl font-medium">{organization.name}</h1>

          {/* Role indicator */}
          <div className="text-primary flex items-center gap-1">
            {getRoleIcon(organization.role)}
            <span className="text-xs capitalize">{organization.role}</span>
          </div>

          {/* Primary indicator */}
          {organization.is_primary && (
            <div className="flex items-center gap-1 text-amber-500">
              <Star className="size-3" />
              <span className="text-xs">Primary</span>
            </div>
          )}
        </div>

        {/* Organization ID */}
        <button
          type="button"
          onClick={handleCopyId}
          className="text-muted-foreground hover:text-foreground group flex items-center gap-1.5 text-left text-xs transition-colors"
        >
          <span className="font-mono">{organization.id}</span>
          {isCopied ? (
            <Check className="size-3.5" />
          ) : (
            <Copy className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
          )}
        </button>
      </div>

      <div className="space-y-8">
        {/* Basic Information */}
        <section className="max-w-lg space-y-6">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter organization name"
              disabled={!canEdit || updateMutation.isPending}
            />
            {!canEdit && (
              <p className="text-muted-foreground text-xs">
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
              disabled={!canEdit || updateMutation.isPending}
              className="resize-none"
            />
          </div>

          {canEdit && (
            <div className="flex justify-end">
              <Button
                onClick={handleSave}
                disabled={updateMutation.isPending || !hasChanges}
                size="sm"
              >
                {updateMutation.isPending ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Save className="mr-2 size-4" />
                )}
                {updateMutation.isPending ? "Saving..." : "Save changes"}
              </Button>
            </div>
          )}
        </section>

        {/* Primary Organization Setting */}
        <section className="border-border max-w-lg border-t pt-6">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <h3 className="text-sm font-medium">Primary Organization</h3>
              <p className="text-muted-foreground text-xs">
                This organization will be used as the default.
              </p>
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <div>
                  <Switch
                    checked={organization.is_primary}
                    onCheckedChange={handlePrimaryToggle}
                    disabled={
                      setPrimaryMutation.isPending || organization.is_primary
                    }
                  />
                </div>
              </TooltipTrigger>
              {organization.is_primary && (
                <TooltipContent side="left" className="max-w-xs">
                  <p className="text-xs">
                    Cannot unset primary organization directly. Set another
                    organization as primary to change this.
                  </p>
                </TooltipContent>
              )}
            </Tooltip>
          </div>
        </section>

        {/* Danger Zone */}
        {canDelete && (
          <section className="border-border max-w-lg border-t pt-6">
            <div className="space-y-3">
              <div>
                <h3 className="text-sm font-medium">Delete organization</h3>
                <p className="text-muted-foreground mt-0.5 text-xs">
                  Permanently delete this organization and all data
                </p>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setDeleteDialogOpen(true)}
                disabled={deleteMutation.isPending || isLastOrg}
              >
                {deleteMutation.isPending
                  ? "Deleting..."
                  : "Delete organization"}
              </Button>
              {isLastOrg && (
                <p className="text-muted-foreground text-xs">
                  Cannot delete your only organization. You must have at least
                  one organization.
                </p>
              )}
            </div>
          </section>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title={`Delete "${organization.name}"?`}
        confirmValue={organization.name}
        onConfirm={handleDelete}
        isDeleting={deleteMutation.isPending}
        deletedItems={[
          "All collections and data",
          "All source connections",
          "All API keys",
          "All organization settings",
        ]}
        criticalWarning={
          organization.is_primary
            ? {
                title: "This is your primary organization",
                description:
                  "Deleting your primary organization will set another organization as primary.",
              }
            : undefined
        }
        deleteButtonText="Delete organization"
      />
    </div>
  );
}
