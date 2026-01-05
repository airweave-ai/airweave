/**
 * Onboarding route - Multi-step organization creation wizard
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Check, ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { useBeforeUnload } from "@/hooks/use-before-unload";
import { useKeyboardShortcut } from "@/hooks/use-keyboard-shortcut";

import { ApiForm } from "@/components/ui/api-form";
import { Button } from "@/components/ui/button";
import { Steps } from "@/components/ui/steps";
import { UserAccountDropdown } from "@/components/user-account-dropdown";
import { authConfig } from "@/config/auth";
import {
  DEFAULT_ONBOARDING_DATA,
  StepOrgName,
  StepOrgSize,
  StepOrgType,
  StepSubscription,
  StepTeamInvites,
  StepUserRole,
  type OnboardingData,
} from "@/features/onboarding";
import { useIsDark } from "@/hooks/use-is-dark";
import {
  createCheckoutSession,
  createOrganization,
  fetchOrganizations,
} from "@/lib/api/organizations";
import { useAuth0 } from "@/lib/auth-provider";
import { generateOrgSlug } from "@/lib/org-utils";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/onboarding")({
  component: OnboardingPage,
});

const TOTAL_STEPS = 6;

function OnboardingPage() {
  const navigate = useNavigate();
  const isDark = useIsDark();
  const { user, getAccessTokenSilently } = useAuth0();

  const [currentStep, setCurrentStep] = useState(1);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [formData, setFormData] = useState<OnboardingData>(
    DEFAULT_ONBOARDING_DATA
  );

  // Check if user already has organizations
  const { data: organizations = [] } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
  });

  const hasOrganizations = organizations.length > 0;

  // Handle ESC key to go back to home on first step
  useKeyboardShortcut({
    key: "Escape",
    onKeyDown: () => navigate({ to: "/" }),
    enabled: hasOrganizations,
  });

  // Prevent browser refresh/navigation when user has no organizations
  useBeforeUnload(!hasOrganizations);

  const updateFormData = useCallback(
    <K extends keyof OnboardingData>(field: K, value: OnboardingData[K]) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  // Create organization mutation
  const createOrgMutation = useMutation({
    mutationFn: async () => {
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
        // In local development, skip billing
        return { organization, redirectUrl: null };
      }

      if (formData.subscriptionPlan === "developer") {
        // Free plan: no checkout required
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
        // If billing fails but org was created, still proceed
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

  // Validate organization name
  const validateOrgName = (name: string): string | null => {
    const trimmed = name.trim();

    if (trimmed.length < 4) {
      return "Organization name must be at least 4 characters long";
    }

    const safeCharRegex = /^[a-zA-Z0-9\s\-_]+$/;
    if (!safeCharRegex.test(trimmed)) {
      return "Organization name can only contain letters, numbers, spaces, hyphens, and underscores";
    }

    if (trimmed.includes("  ")) {
      return "Organization name cannot contain consecutive spaces";
    }

    if (trimmed.startsWith(" ") || trimmed.endsWith(" ")) {
      return "Organization name cannot start or end with spaces";
    }

    return null;
  };

  const isStepValid = () => {
    switch (currentStep) {
      case 1:
        return formData.organizationName.trim().length > 0;
      case 2:
        return formData.organizationSize !== "";
      case 3:
        return formData.userRole !== "";
      case 4:
        return formData.organizationType !== "";
      case 5:
        return formData.subscriptionPlan !== "";
      case 6:
        return true; // Team invites are optional
      default:
        return false;
    }
  };

  const handleNext = () => {
    // Special validation for organization name on step 1
    if (currentStep === 1) {
      const error = validateOrgName(formData.organizationName);
      if (error) {
        toast.error(error);
        return;
      }
    }

    if (currentStep < TOTAL_STEPS && isStepValid()) {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentStep((prev) => prev + 1);
        setIsTransitioning(false);
      }, 150);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentStep((prev) => prev - 1);
        setIsTransitioning(false);
      }, 150);
    }
  };

  const handleComplete = () => {
    createOrgMutation.mutate();
  };

  // Handle Enter key for progression
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && isStepValid()) {
      e.preventDefault();

      if (currentStep === 1) {
        const error = validateOrgName(formData.organizationName);
        if (error) {
          toast.error(error);
          return;
        }
      }

      if (currentStep < TOTAL_STEPS) {
        handleNext();
      } else {
        handleComplete();
      }
    }
  };

  // Auto-progress on selection for button-based steps (2-5)
  const handleSelection = <K extends keyof OnboardingData>(
    field: K,
    value: OnboardingData[K]
  ) => {
    updateFormData(field, value);

    // Auto-progress for steps 2-5
    if (currentStep >= 2 && currentStep <= 5) {
      setTimeout(() => {
        setIsTransitioning(true);
        setTimeout(() => {
          setCurrentStep((prev) => prev + 1);
          setIsTransitioning(false);
        }, 150);
      }, 200);
    }
  };

  // Build API request body for the Code view
  const apiRequestBody = {
    name: formData.organizationName,
    description: `${formData.organizationType} company with ${formData.organizationSize} people`,
    org_metadata: {
      onboarding: {
        organizationSize: formData.organizationSize,
        userRole: formData.userRole,
        organizationType: formData.organizationType,
        subscriptionPlan: formData.subscriptionPlan,
        teamInvites: formData.teamMembers,
      },
    },
  };

  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4 py-12">
      <div className="relative w-full max-w-2xl">
        {/* Header with logo branding */}
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

        <Steps
          currentStep={currentStep}
          onStepChange={setCurrentStep}
          totalSteps={TOTAL_STEPS}
        >
          {/* Progress and close button */}
          <div className="mb-8 flex items-center justify-between">
            <Steps.Indicator />

            <div className="flex items-center gap-4">
              <Steps.Counter />

              {hasOrganizations && (
                <button
                  onClick={() => navigate({ to: "/" })}
                  className="hover:bg-muted/50 rounded-lg p-2 transition-colors"
                  title="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>

          {/* Content with fade transition */}
          <div
            className={cn(
              "min-h-[400px] transition-opacity duration-150",
              isTransitioning ? "opacity-0" : "opacity-100"
            )}
          >
            <Steps.Content step={1}>
              <StepOrgName
                value={formData.organizationName}
                onChange={(value) => updateFormData("organizationName", value)}
                onKeyPress={handleKeyPress}
              />
            </Steps.Content>

            <Steps.Content step={2}>
              <StepOrgSize
                value={formData.organizationSize}
                onChange={(value) => handleSelection("organizationSize", value)}
              />
            </Steps.Content>

            <Steps.Content step={3}>
              <StepUserRole
                value={formData.userRole}
                onChange={(value) => handleSelection("userRole", value)}
              />
            </Steps.Content>

            <Steps.Content step={4}>
              <StepOrgType
                value={formData.organizationType}
                onChange={(value) => handleSelection("organizationType", value)}
              />
            </Steps.Content>

            <Steps.Content step={5}>
              <StepSubscription
                value={formData.subscriptionPlan}
                onChange={(value) => handleSelection("subscriptionPlan", value)}
                billingPeriod={formData.billingPeriod}
                onBillingPeriodChange={(period) =>
                  updateFormData("billingPeriod", period)
                }
                authEnabled={authConfig.authEnabled}
              />
            </Steps.Content>

            <Steps.Content step={6}>
              <ApiForm
                method="POST"
                endpoint="/organizations"
                body={apiRequestBody}
                onBodyChange={(newBody) => {
                  if (typeof newBody.name === "string") {
                    updateFormData("organizationName", newBody.name);
                  }
                }}
              >
                <ApiForm.Toggle className="mb-4" />

                <ApiForm.FormView>
                  <StepTeamInvites
                    teamMembers={formData.teamMembers}
                    onChange={(members) =>
                      updateFormData("teamMembers", members)
                    }
                    subscriptionPlan={formData.subscriptionPlan}
                    currentUserEmail={user?.email}
                  />
                </ApiForm.FormView>

                <ApiForm.CodeView />
              </ApiForm>
            </Steps.Content>
          </div>

          {/* Actions */}
          <OnboardingNavigation
            currentStep={currentStep}
            totalSteps={TOTAL_STEPS}
            isStepValid={isStepValid()}
            isCreating={createOrgMutation.isPending}
            authEnabled={authConfig.authEnabled}
            onBack={handleBack}
            onNext={handleNext}
            onComplete={handleComplete}
          />
        </Steps>
      </div>
    </div>
  );
}

// Navigation component
interface OnboardingNavigationProps {
  currentStep: number;
  totalSteps: number;
  isStepValid: boolean;
  isCreating: boolean;
  authEnabled: boolean;
  onBack: () => void;
  onNext: () => void;
  onComplete: () => void;
}

function OnboardingNavigation({
  currentStep,
  totalSteps,
  isStepValid,
  isCreating,
  authEnabled,
  onBack,
  onNext,
  onComplete,
}: OnboardingNavigationProps) {
  return (
    <div className="relative mt-12 flex items-center justify-between">
      {/* Back button - only show after first step */}
      {currentStep > 1 && (
        <Button variant="ghost" onClick={onBack}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
      )}

      {/* User dropdown - only show on first step */}
      {currentStep === 1 && <UserAccountDropdown variant="standalone" />}

      {/* Right side - Continue/Complete button */}
      {currentStep < totalSteps ? (
        <Button onClick={onNext} disabled={!isStepValid} className="ml-auto">
          Continue
          <ChevronRight className="ml-2 h-4 w-4" />
        </Button>
      ) : (
        <Button
          onClick={onComplete}
          disabled={!isStepValid || isCreating}
          className="ml-auto"
        >
          {isCreating ? (
            <>
              {!authEnabled ? "Creating Organization" : "Complete Setup"}
              <Loader2 className="ml-2 h-4 w-4 animate-spin" />
            </>
          ) : (
            <>
              {!authEnabled ? "Create Organization" : "Complete Setup"}
              <Check className="ml-2 h-4 w-4" />
            </>
          )}
        </Button>
      )}
    </div>
  );
}
