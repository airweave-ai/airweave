/**
 * Hook for creating an organization with billing setup
 */

import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";

import { authConfig } from "@/config/auth";
import {
  createCheckoutSession,
  createOrganization,
  type Organization,
} from "@/lib/api/organizations";
import { useAuth0 } from "@/lib/auth-provider";
import { generateOrgSlug } from "@/lib/org-utils";

import type { OnboardingData } from "../utils/constants";

interface CreateOrganizationResult {
  organization: Organization;
  redirectUrl: string | null;
}

export function useCreateOrganization(formData: OnboardingData) {
  const navigate = useNavigate();
  const { getAccessTokenSilently } = useAuth0();

  return useMutation({
    mutationFn: async (): Promise<CreateOrganizationResult> => {
      const token = await getAccessTokenSilently();

      const org_metadata = {
        onboarding: {
          organizationSize: formData.organizationSize,
          userRole: formData.userRole,
          organizationType: formData.organizationType,
          subscriptionPlan: formData.subscriptionPlan,
          teamInvites: formData.teamMembers,
          completedAt: new Date().toISOString(),
        },
      };

      const organization = await createOrganization(token, {
        name: formData.organizationName,
        description: `${formData.organizationType} company with ${formData.organizationSize} people`,
        org_metadata,
      });

      // Handle billing based on environment
      if (!authConfig.authEnabled) {
        return { organization, redirectUrl: null };
      }

      if (formData.subscriptionPlan === "developer") {
        return { organization, redirectUrl: null };
      }

      try {
        const isEligibleForYearly = ["pro", "team"].includes(
          formData.subscriptionPlan
        );
        const yearly =
          formData.billingPeriod === "yearly" && isEligibleForYearly;

        const { checkout_url } = await createCheckoutSession(
          token,
          {
            plan: formData.subscriptionPlan,
            success_url: `${window.location.origin}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
            cancel_url: `${window.location.origin}/billing/cancel`,
          },
          yearly
        );

        return { organization, redirectUrl: checkout_url };
      } catch {
        console.warn("Billing setup failed, but organization was created");
        return { organization, redirectUrl: null };
      }
    },
    onSuccess: ({ organization, redirectUrl }) => {
      if (redirectUrl) {
        window.location.href = redirectUrl;
      } else {
        toast.success("Organization created successfully!");
        navigate({
          to: "/$orgSlug",
          params: { orgSlug: generateOrgSlug(organization) },
        });
      }
    },
    onError: (error: Error) => {
      toast.error("Failed to complete setup. Please try again.", {
        description: error.message,
      });
    },
  });
}
