import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { CheckCircle, Loader2, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useIsDark } from "@/hooks/use-is-dark";
import {
  fetchOrganizations,
  inviteOrganizationMember,
} from "@/lib/api/organizations";
import { useAuth0 } from "@/lib/auth-provider";
import { queryKeys } from "@/lib/query-keys";

export const Route = createFileRoute("/billing/success")({
  component: BillingSuccessPage,
});

function BillingSuccessPage() {
  const navigate = useNavigate();
  const isDark = useIsDark();
  const queryClient = useQueryClient();
  const {
    isAuthenticated,
    isLoading: authLoading,
    getAccessTokenSilently,
  } = useAuth0();

  const [isProcessing, setIsProcessing] = useState(true);
  const [invitesSent, setInvitesSent] = useState(false);
  const [hasProcessed, setHasProcessed] = useState(false);

  const { data: organizations = [] } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
    enabled: isAuthenticated && !authLoading,
  });

  const currentOrganization =
    organizations.find((org) => org.is_primary) || organizations[0];

  useEffect(() => {
    if (
      hasProcessed ||
      authLoading ||
      !isAuthenticated ||
      !currentOrganization
    ) {
      return;
    }

    setHasProcessed(true);

    const processSuccess = async () => {
      try {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.organizations.all,
        });

        const orgMetadata = currentOrganization.org_metadata as
          | {
              onboarding?: {
                teamInvites?: Array<{ email: string; role: string }>;
              };
            }
          | undefined;

        if (orgMetadata?.onboarding?.teamInvites) {
          const invites = orgMetadata.onboarding.teamInvites;
          const token = await getAccessTokenSilently();

          for (const invite of invites) {
            try {
              await inviteOrganizationMember(
                token,
                currentOrganization.id,
                invite.email,
                invite.role
              );
            } catch (error) {
              console.error(`Failed to invite ${invite.email}:`, error);
            }
          }

          if (invites.length > 0) {
            setInvitesSent(true);
            toast.success(
              `Sent ${invites.length} team invitation${invites.length > 1 ? "s" : ""}`
            );
          }
        }

        setTimeout(() => {
          setIsProcessing(false);
          setTimeout(() => {
            navigate({ to: "/" });
          }, 2000);
        }, 1500);
      } catch (error) {
        console.error("Error processing billing success:", error);
        toast.error("Something went wrong. Please contact support.");
        setIsProcessing(false);
      }
    };

    processSuccess();
  }, [
    authLoading,
    isAuthenticated,
    hasProcessed,
    currentOrganization,
    queryClient,
    getAccessTokenSilently,
    navigate,
  ]);

  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="mb-12 text-center">
          <img
            src={
              isDark
                ? "/airweave-logo-svg-white-darkbg.svg"
                : "/airweave-logo-svg-lightbg-blacklogo.svg"
            }
            alt="Airweave"
            className="mx-auto mb-2 h-8 w-auto"
            style={{ maxWidth: "180px" }}
          />
          <p className="text-muted-foreground text-xs">Build smarter agents</p>
        </div>

        <div className="space-y-8 text-center">
          {isProcessing ? (
            <>
              <Loader2 className="text-primary/60 mx-auto h-12 w-12 animate-spin" />
              <div className="space-y-2">
                <h1 className="text-2xl font-normal">
                  Setting up your account
                </h1>
                <p className="text-muted-foreground">
                  This will just take a moment
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-50 dark:bg-green-950/20">
                <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-500" />
              </div>
              <div className="space-y-3">
                <h1 className="text-2xl font-normal">Welcome to Airweave!</h1>
                <p className="text-muted-foreground">
                  Your subscription is now active
                </p>
                {invitesSent && (
                  <div className="text-muted-foreground mt-6 flex items-center justify-center gap-2 text-sm">
                    <Users className="h-4 w-4" />
                    <span>Team invitations have been sent</span>
                  </div>
                )}
              </div>
              <p className="text-muted-foreground/70 text-sm">
                Redirecting to your dashboard...
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
