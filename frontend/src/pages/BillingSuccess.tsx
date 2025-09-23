import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, Loader2, Users } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { useAuth0 } from '@auth0/auth0-react';
import { useTheme } from '@/lib/theme-provider';

export const BillingSuccess = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { resolvedTheme } = useTheme();
  const { fetchUserOrganizations, currentOrganization } = useOrganizationStore();
  const { isAuthenticated, isLoading: authLoading } = useAuth0();
  const [isProcessing, setIsProcessing] = useState(true);
  const [invitesSent, setInvitesSent] = useState(false);
  const [hasProcessed, setHasProcessed] = useState(false);

  const isDark = resolvedTheme === 'dark';

  useEffect(() => {
    const processSuccess = async () => {
      // Prevent multiple executions
      if (hasProcessed) return;

      // Wait for auth to be ready
      if (authLoading || !isAuthenticated) {
        return;
      }

      try {
        // Wait a moment to ensure auth token is fully available
        await new Promise(resolve => setTimeout(resolve, 500));

        // Refresh organizations to get updated billing status
        await fetchUserOrganizations();

        // Wait for currentOrganization to be available
        // Don't mark as processed until we've actually checked for invites
        if (!currentOrganization) {
          return;
        }

        // Now we can safely mark as processed since we have the organization data
        setHasProcessed(true);

        // Get the current organization with metadata
        if (currentOrganization.org_metadata?.onboarding?.teamInvites) {
          const invites = currentOrganization.org_metadata.onboarding.teamInvites;

          // Send team invites
          for (const invite of invites) {
            try {
              const response = await apiClient.post(`/organizations/${currentOrganization.id}/invite`, {
                email: invite.email,
                role: invite.role,
              });

              if (!response.ok) {
                console.error(`Failed to invite ${invite.email}`);
              }
            } catch (error) {
              console.error(`Error inviting ${invite.email}:`, error);
            }
          }

          if (invites.length > 0) {
            setInvitesSent(true);
            toast.success(`Sent ${invites.length} team invitation${invites.length > 1 ? 's' : ''}`);
          }
        }

        // Wait a moment for visual feedback
        setTimeout(() => {
          setIsProcessing(false);
          // Redirect to dashboard after 2 seconds
          setTimeout(() => {
            navigate('/');
          }, 2000);
        }, 1500);

      } catch (error) {
        console.error('Error processing billing success:', error);
        toast.error('Something went wrong. Please contact support.');
        setIsProcessing(false);
        // Mark as processed even on error to prevent infinite retries
        setHasProcessed(true);
      }
    };

    processSuccess();
  }, [authLoading, isAuthenticated, hasProcessed, fetchUserOrganizations, navigate, currentOrganization]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo header */}
        <div className="mb-12 text-center">
          <img
            src={isDark ? "/logo-airweave-darkbg.svg" : "/logo-airweave-lightbg.svg"}
            alt="Airweave"
            className="h-8 w-auto mx-auto mb-2"
            style={{ maxWidth: '180px' }}
          />
          <p className="text-xs text-muted-foreground">
            Build smarter agents
          </p>
        </div>

        {/* Content */}
        <div className="text-center space-y-8">
          {isProcessing ? (
            <>
              <Loader2 className="w-12 h-12 mx-auto animate-spin text-primary/60" />
              <div className="space-y-2">
                <h1 className="text-2xl font-normal">Setting up your account</h1>
                <p className="text-muted-foreground">
                  This will just take a moment
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="w-16 h-16 mx-auto rounded-full bg-green-50 dark:bg-green-950/20 flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-500" />
              </div>
              <div className="space-y-3">
                <h1 className="text-2xl font-normal">Welcome to Airweave!</h1>
                <p className="text-muted-foreground">
                  Your subscription is now active
                </p>
                {invitesSent && (
                  <div className="flex items-center justify-center gap-2 mt-6 text-sm text-muted-foreground">
                    <Users className="w-4 h-4" />
                    <span>Team invitations have been sent</span>
                  </div>
                )}
              </div>
              <p className="text-sm text-muted-foreground/70">
                Redirecting to your dashboard...
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default BillingSuccess;
