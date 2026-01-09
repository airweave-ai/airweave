import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Crown, Loader2, Shield, Users, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { SettingsLayout } from "@/components/settings-layout";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePageHeader } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  cancelOrganizationInvitation,
  fetchOrganizationInvitations,
  fetchOrganizationMembers,
  inviteOrganizationMemberWithResponse,
  removeOrganizationMember,
  updateMemberRole,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { useUsageChecks } from "@/stores/usage-store";

export const Route = createFileRoute("/$orgSlug/settings/members")({
  component: MembersSettingsPage,
});

function MembersSettingsPage() {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const queryClient = useQueryClient();
  const { teamMembersAllowed, teamMembersStatus } = useUsageChecks();
  const inviteDisabledMessage =
    teamMembersStatus?.details?.message || "Team member limit reached";

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member");
  const [emailError, setEmailError] = useState("");

  usePageHeader({
    title: "Settings",
    description: "Manage organization settings, preferences, and configuration",
  });

  const {
    data: members = [],
    isLoading: membersLoading,
    error: membersError,
  } = useQuery({
    queryKey: queryKeys.organizations.members(organization?.id ?? ""),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizationMembers(token, organization!.id);
    },
    enabled: !!organization?.id,
  });

  const { data: invitations = [], isLoading: invitationsLoading } = useQuery({
    queryKey: queryKeys.organizations.invitations(organization?.id ?? ""),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizationInvitations(token, organization!.id);
    },
    enabled: !!organization?.id,
  });

  const inviteMutation = useMutation({
    mutationFn: async ({ email, role }: { email: string; role: string }) => {
      const token = await getAccessTokenSilently();
      return inviteOrganizationMemberWithResponse(
        token,
        organization!.id,
        email,
        role
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.organizations.invitations(organization!.id),
      });
      setInviteEmail("");
      setInviteRole("member");
      toast.success("Invitation sent successfully");
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to send invitation"
      );
    },
  });

  const cancelInvitationMutation = useMutation({
    mutationFn: async (invitationId: string) => {
      const token = await getAccessTokenSilently();
      return cancelOrganizationInvitation(
        token,
        organization!.id,
        invitationId
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.organizations.invitations(organization!.id),
      });
      toast.success("Invitation cancelled");
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to cancel invitation"
      );
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: async (memberId: string) => {
      const token = await getAccessTokenSilently();
      return removeOrganizationMember(token, organization!.id, memberId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.organizations.members(organization!.id),
      });
      toast.success("Member removed");
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to remove member"
      );
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: async ({
      memberId,
      role,
    }: {
      memberId: string;
      role: "admin" | "member";
    }) => {
      const token = await getAccessTokenSilently();
      return updateMemberRole(token, organization!.id, memberId, role);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.organizations.members(organization!.id),
      });
      toast.success("Member role updated");
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to update member role"
      );
    },
  });

  const validateEmail = useCallback(
    (email: string, showFormatError = true): string => {
      if (!email) return "";

      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        return showFormatError ? "Please enter a valid email address" : "";
      }

      const existingMember = members.find(
        (member) => member.email.toLowerCase() === email.toLowerCase()
      );
      if (existingMember) {
        return "This person is already a member of the organization";
      }

      const existingInvitation = invitations.find(
        (invitation) => invitation.email.toLowerCase() === email.toLowerCase()
      );
      if (existingInvitation) {
        return "An invitation has already been sent to this email";
      }

      return "";
    },
    [members, invitations]
  );

  useEffect(() => {
    if (inviteEmail) {
      setEmailError(validateEmail(inviteEmail));
    }
  }, [members, invitations, inviteEmail, validateEmail]);

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const email = e.target.value;
    setInviteEmail(email);
    setEmailError(validateEmail(email, false));
  };

  const handleEmailBlur = () => {
    setEmailError(validateEmail(inviteEmail));
  };

  const handleInvite = () => {
    if (!inviteEmail || emailError) return;
    inviteMutation.mutate({ email: inviteEmail, role: inviteRole });
  };

  if (!organization) {
    return null;
  }

  const canEdit = ["owner", "admin"].includes(organization.role);
  const isValidEmail = inviteEmail && !emailError;
  const isLoading = membersLoading || invitationsLoading;

  if (isLoading) {
    return (
      <SettingsLayout organization={organization}>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="size-6 animate-spin" />
          <span className="text-muted-foreground ml-2 text-sm">
            Loading members...
          </span>
        </div>
      </SettingsLayout>
    );
  }

  if (membersError) {
    return (
      <SettingsLayout organization={organization}>
        <div className="text-destructive text-sm">
          Failed to load members. Please try again.
        </div>
      </SettingsLayout>
    );
  }

  return (
    <SettingsLayout organization={organization}>
      <div className="space-y-8">
        <div className="text-muted-foreground text-xs">
          Team members:{" "}
          <span className="text-foreground font-medium">{members.length}</span>
        </div>

        {canEdit && (
          <section className="space-y-4">
            <div>
              <h3 className="text-sm font-medium">Invite new member</h3>
              <p className="text-muted-foreground mt-0.5 text-xs">
                Send an invitation to add a member to your organization
              </p>
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <Input
                  type="email"
                  placeholder="Email address"
                  value={inviteEmail}
                  onChange={handleEmailChange}
                  onBlur={handleEmailBlur}
                  className={cn(
                    "h-9 text-sm",
                    emailError && inviteEmail && "border-destructive/50"
                  )}
                  disabled={inviteMutation.isPending}
                />
                {emailError && inviteEmail && (
                  <p className="text-destructive/80 mt-1 text-xs">
                    {emailError}
                  </p>
                )}
              </div>
              <Select
                value={inviteRole}
                onValueChange={(value: "admin" | "member") =>
                  setInviteRole(value)
                }
              >
                <SelectTrigger className="h-9 w-32 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
              <TooltipProvider delayDuration={100}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span>
                      <Button
                        onClick={handleInvite}
                        disabled={
                          inviteMutation.isPending ||
                          !isValidEmail ||
                          !teamMembersAllowed
                        }
                        size="sm"
                        className="h-9 px-4"
                      >
                        {inviteMutation.isPending ? (
                          <>
                            <Loader2 className="mr-1.5 size-3 animate-spin" />
                            Sending...
                          </>
                        ) : (
                          "Send invite"
                        )}
                      </Button>
                    </span>
                  </TooltipTrigger>
                  {!teamMembersAllowed && (
                    <TooltipContent>
                      <p>{inviteDisabledMessage}</p>
                    </TooltipContent>
                  )}
                </Tooltip>
              </TooltipProvider>
            </div>
          </section>
        )}

        {invitations.length > 0 && (
          <section className="space-y-4">
            <div>
              <h3 className="text-sm font-medium">Pending invitations</h3>
              <p className="text-muted-foreground mt-0.5 text-xs">
                Invitations that haven't been accepted yet
              </p>
            </div>
            <div className="border-border divide-border divide-y rounded-lg border">
              {invitations.map((invitation) => (
                <div
                  key={invitation.id}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex flex-col">
                      <div className="text-sm font-medium">
                        {invitation.email}
                      </div>
                      <div className="text-muted-foreground text-xs">
                        Invited{" "}
                        {new Date(invitation.invited_at).toLocaleDateString()}
                      </div>
                    </div>
                    <Badge variant="outline" className="text-xs opacity-70">
                      {invitation.role}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">
                      Pending
                    </Badge>
                    {canEdit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground hover:text-foreground size-7 p-0"
                        onClick={() =>
                          cancelInvitationMutation.mutate(invitation.id)
                        }
                        disabled={cancelInvitationMutation.isPending}
                      >
                        <X className="size-3.5" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="space-y-4">
          <div>
            <h3 className="text-sm font-medium">Members</h3>
            <p className="text-muted-foreground mt-0.5 text-xs">
              People with access to this organization
            </p>
          </div>

          <div className="space-y-2">
            {members.map((member) => (
              <MemberRow
                key={member.id}
                member={member}
                canEdit={canEdit}
                onRemove={() => removeMemberMutation.mutate(member.id)}
                isRemoving={removeMemberMutation.isPending}
                onRoleChange={(role) =>
                  updateRoleMutation.mutate({ memberId: member.id, role })
                }
                isUpdatingRole={updateRoleMutation.isPending}
              />
            ))}
          </div>
        </section>
      </div>
    </SettingsLayout>
  );
}

interface MemberRowProps {
  member: {
    id: string;
    email: string;
    name: string;
    role: "owner" | "admin" | "member";
  };
  canEdit: boolean;
  onRemove: () => void;
  isRemoving: boolean;
  onRoleChange: (role: "admin" | "member") => void;
  isUpdatingRole: boolean;
}

function MemberRow({
  member,
  canEdit,
  onRemove,
  isRemoving,
  onRoleChange,
  isUpdatingRole,
}: MemberRowProps) {
  const getRoleIcon = (role: string) => {
    switch (role) {
      case "owner":
        return <Crown className="size-3" />;
      case "admin":
        return <Shield className="size-3" />;
      default:
        return <Users className="size-3" />;
    }
  };

  const getRoleBadgeVariant = (
    role: string
  ): "default" | "secondary" | "outline" => {
    switch (role) {
      case "owner":
        return "default";
      case "admin":
        return "secondary";
      default:
        return "outline";
    }
  };

  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase();
  };

  const canEditRole = canEdit && member.role !== "owner";

  return (
    <div className="border-border flex items-center justify-between rounded-md border px-3 py-3">
      <div className="flex items-center gap-3">
        <Avatar className="size-8">
          <AvatarFallback className="text-xs">
            {getInitials(member.name || member.email)}
          </AvatarFallback>
        </Avatar>
        <div>
          <div className="text-sm font-medium">
            {member.name || member.email}
          </div>
          {member.name && (
            <div className="text-muted-foreground text-xs">{member.email}</div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {canEditRole ? (
          <Select
            value={member.role}
            onValueChange={(value: "admin" | "member") => onRoleChange(value)}
            disabled={isUpdatingRole}
          >
            <SelectTrigger className="h-7 w-24 text-xs">
              <SelectValue>
                <span className="flex items-center gap-1">
                  {getRoleIcon(member.role)}
                  {member.role}
                </span>
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="admin">
                <span className="flex items-center gap-1">
                  <Shield className="size-3" />
                  admin
                </span>
              </SelectItem>
              <SelectItem value="member">
                <span className="flex items-center gap-1">
                  <Users className="size-3" />
                  member
                </span>
              </SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <Badge
            variant={getRoleBadgeVariant(member.role)}
            className="text-xs opacity-70"
          >
            <span className="flex items-center gap-1">
              {getRoleIcon(member.role)}
              {member.role}
            </span>
          </Badge>
        )}
        {canEdit && member.role !== "owner" && (
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-destructive size-7 p-0"
            onClick={onRemove}
            disabled={isRemoving}
          >
            <X className="size-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}
