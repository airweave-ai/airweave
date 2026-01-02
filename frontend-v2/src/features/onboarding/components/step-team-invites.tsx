import { X } from "lucide-react";
import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import { SUBSCRIPTION_PLANS, type TeamMember } from "../utils/constants";

interface StepTeamInvitesProps {
  teamMembers: TeamMember[];
  onChange: (members: TeamMember[]) => void;
  subscriptionPlan: string;
  currentUserEmail?: string;
}

export function StepTeamInvites({
  teamMembers,
  onChange,
  subscriptionPlan,
  currentUserEmail,
}: StepTeamInvitesProps) {
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"member" | "admin">("member");
  const [emailError, setEmailError] = useState("");

  // Get the current plan's team member limit
  const currentPlanLimit =
    SUBSCRIPTION_PLANS.find((plan) => plan.value === subscriptionPlan)
      ?.teamMemberLimit || 2;

  // Email validation
  const validateEmail = useCallback(
    (email: string) => {
      if (!email) {
        setEmailError("");
        return false;
      }

      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        setEmailError("Please enter a valid email address");
        return false;
      }

      // Check if email is the current user's email
      if (
        currentUserEmail &&
        email.toLowerCase() === currentUserEmail.toLowerCase()
      ) {
        setEmailError(
          "You don't need to invite yourself - you'll be the owner"
        );
        return false;
      }

      // Check if email already exists in team members
      const existingMember = teamMembers.find(
        (member) => member.email.toLowerCase() === email.toLowerCase()
      );
      if (existingMember) {
        setEmailError("This email has already been added");
        return false;
      }

      // Check team member limit - the limit includes the owner
      if (teamMembers.length >= currentPlanLimit - 1) {
        setEmailError(
          `You've reached the maximum team size for the ${subscriptionPlan} plan`
        );
        return false;
      }

      setEmailError("");
      return true;
    },
    [teamMembers, currentPlanLimit, subscriptionPlan, currentUserEmail]
  );

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const email = e.target.value;
    setInviteEmail(email);

    if (!email) {
      setEmailError("");
      return;
    }

    // Only validate format on change, full validation on blur/submit
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (emailRegex.test(email)) {
      validateEmail(email);
    } else {
      setEmailError("");
    }
  };

  const handleAddTeamMember = () => {
    if (!validateEmail(inviteEmail)) return;

    const newMember: TeamMember = {
      email: inviteEmail,
      role: inviteRole,
    };

    onChange([...teamMembers, newMember]);
    setInviteEmail("");
    setInviteRole("member");
    setEmailError("");
  };

  const handleRemoveTeamMember = (email: string) => {
    onChange(teamMembers.filter((member) => member.email !== email));
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && inviteEmail && !emailError) {
      e.preventDefault();
      handleAddTeamMember();
    }
  };

  const isValidEmail =
    inviteEmail &&
    !emailError &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(inviteEmail);

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-normal">Invite your team</h2>
        <p className="text-muted-foreground">
          Get your team onboard from day one
        </p>
      </div>

      {/* Add team member form */}
      <div className="space-y-4">
        <div>
          <h3 className="text-foreground text-sm font-medium">
            Add team members
          </h3>
          <p className="text-muted-foreground mt-0.5 text-xs">
            Your {subscriptionPlan} plan includes up to {currentPlanLimit} team
            members
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
                onBlur={() => validateEmail(inviteEmail)}
                onKeyDown={handleKeyPress}
                className={cn(
                  "h-8 px-3 text-sm",
                  emailError && inviteEmail && "border-destructive/50",
                  teamMembers.length >= currentPlanLimit - 1 &&
                    "cursor-not-allowed opacity-50"
                )}
                disabled={teamMembers.length >= currentPlanLimit - 1}
              />
              {emailError && inviteEmail && (
                <p className="text-destructive/80 mt-1 text-xs">{emailError}</p>
              )}
            </div>
            <select
              value={inviteRole}
              onChange={(e) =>
                setInviteRole(e.target.value as "member" | "admin")
              }
              className={cn(
                "h-8 w-24 rounded-md border bg-transparent px-2 text-sm",
                "focus:border-border focus:ring-0 focus:outline-none",
                "transition-colors",
                teamMembers.length >= currentPlanLimit - 1 &&
                  "cursor-not-allowed opacity-50"
              )}
              disabled={teamMembers.length >= currentPlanLimit - 1}
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
            <Button
              type="button"
              size="sm"
              onClick={handleAddTeamMember}
              disabled={
                !isValidEmail || teamMembers.length >= currentPlanLimit - 1
              }
              className="h-8"
            >
              Add
            </Button>
          </div>
        </div>

        {/* Team members list */}
        {teamMembers.length > 0 && (
          <div className="mt-6 space-y-4">
            <div>
              <h3 className="text-foreground pt-2 text-sm font-medium">
                Team members to invite
              </h3>
              <p className="text-muted-foreground mt-0.5 text-xs">
                {teamMembers.length} of {currentPlanLimit - 1} team members
                added
              </p>
            </div>

            <div className="border-border divide-border divide-y rounded-lg border">
              {teamMembers.map((member, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between px-4 py-2"
                >
                  <div className="flex items-center gap-3">
                    <div className="text-sm">{member.email}</div>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs",
                        member.role === "admin"
                          ? "bg-primary/10 text-primary"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      {member.role}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveTeamMember(member.email)}
                    className="text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded p-1 transition-colors"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
