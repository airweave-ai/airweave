import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '@/components/ui/select';
import {
  Crown, Shield, Users, X, Loader2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import { useUsageStore } from '@/lib/stores/usage';

// Member interfaces
interface Member {
  id: string;
  email: string;
  name: string;
  role: string;
  status: 'active' | 'pending';
  is_primary?: boolean;
  auth0_id?: string;
}

interface PendingInvitation {
  id: string;
  email: string;
  role: string;
  invited_at: string;
  status: 'pending' | 'expired';
}

interface Organization {
  id: string;
  name: string;
  description?: string;
  role: string;
}

interface MembersSettingsProps {
  currentOrganization: Organization;
}

export const MembersSettings = ({ currentOrganization }: MembersSettingsProps) => {
  const [members, setMembers] = useState<Member[]>([]);
  const [pendingInvitations, setPendingInvitations] = useState<PendingInvitation[]>([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [isInviting, setIsInviting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [emailError, setEmailError] = useState('');
  const [emailValidationTimeout, setEmailValidationTimeout] = useState<NodeJS.Timeout | null>(null);

  // Use usage store for team member limits
  const actionChecks = useUsageStore(state => state.actionChecks);
  const teamMembersAllowed = actionChecks.team_members?.allowed ?? true;
  const teamMembersCheckDetails = actionChecks.team_members;

  // Fetch members and invitations on mount
  useEffect(() => {
    fetchMembersAndInvitations();
  }, [currentOrganization.id]);

  const fetchMembersAndInvitations = async () => {
    try {
      setIsLoading(true);

      // Fetch members
      const membersResponse = await apiClient.get(`/organizations/${currentOrganization.id}/members`);
      if (membersResponse.ok) {
        const membersData = await membersResponse.json();
        setMembers(membersData);
      }

      // Fetch pending invitations
      const invitationsResponse = await apiClient.get(`/organizations/${currentOrganization.id}/invitations`);
      if (invitationsResponse.ok) {
        const invitationsData = await invitationsResponse.json();
        setPendingInvitations(invitationsData);
      }

      // Team member limits are now handled by the usage store

    } catch (error) {
      console.error('Failed to fetch members and invitations:', error);
      toast.error('Failed to load member data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInvite = async () => {
    if (!inviteEmail || emailError) return;

    // Check if team members are allowed
    if (!teamMembersAllowed) {
      const reason = teamMembersCheckDetails?.reason;
      const message = reason === 'usage_limit_exceeded'
        ? 'Team member limit reached for your plan. Upgrade to add more members.'
        : 'Unable to invite team members at this time.';
      toast.error(message);
      return;
    }

    try {
      setIsInviting(true);

      const response = await apiClient.post(
        `/organizations/${currentOrganization.id}/invite`,
        {
          email: inviteEmail,
          role: inviteRole
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to send invitation: ${response.status}`);
      }

      const result = await response.json();

      // Add to pending invitations list
      const newInvitation: PendingInvitation = {
        id: result.id,
        email: inviteEmail,
        role: inviteRole,
        invited_at: result.invited_at || new Date().toISOString(),
        status: 'pending',
      };

      setPendingInvitations(prev => [...prev, newInvitation]);
      setInviteEmail('');
      setInviteRole('member');
      toast.success('Invitation sent successfully');

    } catch (error: any) {
      console.error('Failed to send invitation:', error);
      toast.error(error.message || 'Failed to send invitation');
    } finally {
      setIsInviting(false);
    }
  };

  const handleRemoveInvitation = async (invitationId: string) => {
    try {
      const response = await apiClient.delete(
        `/organizations/${currentOrganization.id}/invitations/${invitationId}`
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to remove invitation: ${response.status}`);
      }

      setPendingInvitations(prev => prev.filter(i => i.id !== invitationId));
      toast.success('Invitation removed successfully');

    } catch (error: any) {
      console.error('Failed to remove invitation:', error);
      toast.error(error.message || 'Failed to remove invitation');
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    try {
      const response = await apiClient.delete(
        `/organizations/${currentOrganization.id}/members/${memberId}`
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to remove member: ${response.status}`);
      }

      setMembers(prev => prev.filter(m => m.id !== memberId));
      toast.success('Member removed successfully');

    } catch (error: any) {
      console.error('Failed to remove member:', error);
      toast.error(error.message || 'Failed to remove member');
    }
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'owner': return <Crown className="h-3 w-3" />;
      case 'admin': return <Shield className="h-3 w-3" />;
      default: return <Users className="h-3 w-3" />;
    }
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'owner': return 'default';
      case 'admin': return 'secondary';
      default: return 'outline';
    }
  };

  // Email validation function
  const validateEmail = useCallback((email: string) => {
    if (!email) {
      setEmailError('');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setEmailError('Please enter a valid email address');
      return;
    }

    // Check if email already exists as a member
    const existingMember = members.find(member => member.email.toLowerCase() === email.toLowerCase());
    if (existingMember) {
      setEmailError('This person is already a member of the organization');
      return;
    }

    // Check if email already has a pending invitation
    const existingInvitation = pendingInvitations.find(invitation =>
      invitation.email.toLowerCase() === email.toLowerCase()
    );
    if (existingInvitation) {
      setEmailError('An invitation has already been sent to this email');
      return;
    }

    setEmailError('');
  }, [members, pendingInvitations]);

  // Re-validate email when members or pending invitations change (but not on email change)
  useEffect(() => {
    if (inviteEmail) {
      validateEmail(inviteEmail);
    }
  }, [members, pendingInvitations, validateEmail]);

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const email = e.target.value;
    setInviteEmail(email);

    // Clear existing timeout
    if (emailValidationTimeout) {
      clearTimeout(emailValidationTimeout);
    }

    if (!email) {
      setEmailError('');
      return;
    }

    // Check basic email format first
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (emailRegex.test(email)) {
      // For valid format emails, check immediately for duplicates only
      const existingMember = members.find(member => member.email.toLowerCase() === email.toLowerCase());
      if (existingMember) {
        setEmailError('This person is already a member of the organization');
        return;
      }

      const existingInvitation = pendingInvitations.find(invitation =>
        invitation.email.toLowerCase() === email.toLowerCase()
      );
      if (existingInvitation) {
        setEmailError('An invitation has already been sent to this email');
        return;
      }

      setEmailError('');
    } else {
      // Don't show errors while typing - only on blur
      setEmailError('');
    }
  };

  const handleEmailBlur = () => {
    validateEmail(inviteEmail);
  };

  const isValidEmail = inviteEmail && !emailError;
  const canEdit = ['owner', 'admin'].includes(currentOrganization.role);
  const atLimit = !teamMembersAllowed && teamMembersCheckDetails?.reason === 'usage_limit_exceeded';

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="ml-2 text-sm text-muted-foreground">Loading members...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Team Members Usage */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">
          Team members: <span className="font-medium text-foreground">{members.length}</span>
          {teamMembersCheckDetails?.details?.limit ? (
            <span className="text-muted-foreground"> / {teamMembersCheckDetails.details.limit}</span>
          ) : (
            <span className="text-muted-foreground"> / Unlimited</span>
          )}
        </div>
        {atLimit && (
          <Badge variant="secondary" className="text-[11px]">
            Limit reached
          </Badge>
        )}
      </div>
      {/* Invite Members */}
      {canEdit && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-foreground">Invite new member</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {atLimit
                ? 'You have reached the member limit for your plan. Upgrade your plan to invite more.'
                : 'Send an invitation to add a member to your organization'}
            </p>
          </div>
          <div className="space-y-3">
            <div className="flex gap-3">
              <div className="flex-1">
                <Input
                  type="email"
                  placeholder="Email address"
                  value={inviteEmail}
                  onChange={handleEmailChange}
                  onBlur={handleEmailBlur}
                  className={cn(
                    "h-8 text-sm border-border focus:border-border transition-colors placeholder:text-muted-foreground/60",
                    emailError && inviteEmail && "border-destructive/50",
                    atLimit && "opacity-50 cursor-not-allowed"
                  )}
                  disabled={atLimit}
                />
                {emailError && inviteEmail && (
                  <p className="text-xs text-destructive/80 mt-1">{emailError}</p>
                )}
              </div>
              <Select value={inviteRole} onValueChange={setInviteRole}>
                <SelectTrigger className={cn(
                  "w-32 h-8 text-sm border-border focus:border-border transition-colors",
                  atLimit && "opacity-50 cursor-not-allowed"
                )}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
              <Button
                onClick={handleInvite}
                disabled={isInviting || !isValidEmail || atLimit}
                size="sm"
                className={cn(
                  "h-8 px-4 text-sm",
                  atLimit
                    ? "bg-muted text-muted-foreground cursor-not-allowed"
                    : "bg-primary hover:bg-primary/90 text-white"
                )}
              >
                {isInviting ? (
                  <>
                    <Loader2 className="h-3 w-3 mr-1.5 animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    Send invite
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Pending Invitations */}
      {pendingInvitations.length > 0 && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-foreground">Pending invitations</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Invitations that haven't been accepted yet
            </p>
          </div>
          <div className="border border-border rounded-lg divide-y divide-border">
            {pendingInvitations.map((invitation) => (
              <div key={invitation.id} className="flex items-center justify-between py-3 px-4">
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <div className="text-sm font-medium">{invitation.email}</div>
                    <div className="text-xs text-muted-foreground">
                      Invited {new Date(invitation.invited_at).toLocaleDateString()}
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
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                      onClick={() => handleRemoveInvitation(invitation.id)}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current Members */}
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">Members</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            People with access to this organization
          </p>
        </div>

        <div className="space-y-2">
          {members.map((member) => (
            <div key={member.id} className="flex items-center justify-between py-3 px-3 border border-border rounded-md">
              <div className="flex items-center gap-3">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={undefined} />
                  <AvatarFallback className="text-xs">
                    {member.name.split(' ').map(n => n[0]).join('')}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <div className="text-sm font-medium">{member.name}</div>
                  <div className="text-xs text-muted-foreground">{member.email}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={getRoleBadgeVariant(member.role)} className="text-xs opacity-70">
                  <span className="flex items-center gap-1">
                    {getRoleIcon(member.role)}
                    {member.role}
                  </span>
                </Badge>
                {/* Only show remove button for admins/owners, and not for themselves */}
                {canEdit && member.role !== 'owner' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                    onClick={() => handleRemoveMember(member.id)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
