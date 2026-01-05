/**
 * Hook for onboarding form validation
 */

import { useCallback } from "react";
import { toast } from "sonner";

import type { OnboardingData } from "../utils/constants";

interface UseOnboardingValidationOptions {
  formData: OnboardingData;
  currentStep: number;
}

interface ValidationResult {
  isStepValid: boolean;
  validateAndProceed: () => boolean;
}

/**
 * Validates organization name format
 */
function validateOrgName(name: string): string | null {
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
}

export function useOnboardingValidation({
  formData,
  currentStep,
}: UseOnboardingValidationOptions): ValidationResult {
  const isStepValid = useCallback((): boolean => {
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
  }, [currentStep, formData]);

  const validateAndProceed = useCallback((): boolean => {
    if (currentStep === 1) {
      const error = validateOrgName(formData.organizationName);
      if (error) {
        toast.error(error);
        return false;
      }
    }
    return isStepValid();
  }, [currentStep, formData.organizationName, isStepValid]);

  return {
    isStepValid: isStepValid(),
    validateAndProceed,
  };
}
