import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Users,
  ChevronRight,
  ChevronLeft,
  Check,
  Sparkles,
  Rocket,
  X,
  Code2,
  Database,
  Cloud,
  Shield,
  Cpu,
  Globe,
  Loader2,
  LogOut
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { useAuth } from '@/lib/auth-context';
import authConfig from '@/config/auth';
import { posthog } from '@/lib/posthog-provider';

interface OnboardingData {
  organizationName: string;
  organizationSize: string;
  userRole: string;
  organizationType: string;
  subscriptionPlan: string;
  teamEmails: string[];
}

interface TeamMember {
  email: string;
  role: 'member' | 'admin';
}

const ORGANIZATION_SIZES = [
  { value: '1', label: '1', description: 'Solo' },
  { value: '2-5', label: '2-5', description: 'Small team' },
  { value: '6-20', label: '6-20', description: 'Growing startup' },
  { value: '21-100', label: '21-100', description: 'Scale-up' },
  { value: '101-500', label: '101-500', description: 'Mid-market' },
  { value: '500+', label: '500+', description: 'Enterprise' },
];

const USER_ROLES = [
  { value: 'founder', label: 'Founder/CEO', icon: Sparkles },
  { value: 'engineering', label: 'Engineering', icon: Code2 },
  { value: 'data', label: 'Data/AI', icon: Database },
  { value: 'product', label: 'Product', icon: Rocket },
  { value: 'devops', label: 'DevOps', icon: Cloud },
  { value: 'other', label: 'Other', icon: Users },
];

const ORGANIZATION_TYPES = [
  { value: 'ai_startup', label: 'AI/ML Startup', icon: Cpu, description: 'Building AI-powered products' },
  { value: 'saas', label: 'SaaS Platform', icon: Cloud, description: 'Cloud-based software services' },
  { value: 'data_platform', label: 'Data Platform', icon: Database, description: 'Data infrastructure & analytics' },
  { value: 'dev_tools', label: 'Developer Tools', icon: Code2, description: 'Tools for developers' },
  { value: 'fintech', label: 'Fintech', icon: Shield, description: 'Financial technology' },
  { value: 'other', label: 'Other', icon: Globe, description: 'Other industries' },
];

const SUBSCRIPTION_PLANS = [
  {
    value: 'developer',
    label: 'Developer',
    price: 'Free',
    period: '',
    description: 'Perfect for personal agents and side projects. No credit card required.',
    features: [
      '10 source connections',
      '500 queries / mo',
      '50K entities / mo',
      '1 team member',
      'Community support',
    ],
    teamMemberLimit: 1,
    recommended: false,
    hasTrial: false,
  },
  {
    value: 'pro',
    label: 'Pro',
    price: '$20',
    period: 'per month',
    description: 'Take your agent to the next level',
    features: [
      '50 source connections',
      '2K queries / mo',
      '100K entities / mo',
      '2 team members',
      'Email support',
    ],
    teamMemberLimit: 2,
    recommended: true,
    hasTrial: false,
  },
  {
    value: 'team',
    label: 'Team',
    price: '$299',
    period: 'per month',
    description: 'For fast-moving teams that need scale and control',
    features: [
      '1000 source connections',
      '10K queries / mo',
      '1M entities synced / mo',
      '10 team members',
      'Dedicated Slack support',
      'Dedicated onboarding',
    ],
    teamMemberLimit: 10,
    recommended: false,
    hasTrial: false,
  },
  {
    value: 'enterprise',
    label: 'Enterprise',
    price: 'Custom',
    period: '',
    description: 'Tailored solutions for large organizations',
    features: [
      'Unlimited source connections',
      'Custom usage limits',
      'Tailored onboarding',
      'Dedicated priority support',
      'Custom integrations (Optional)',
      'On-premise deployment (Optional)',
      'SLAs (Optional)'
    ],
    teamMemberLimit: 1000,
    recommended: false,
    hasTrial: false,
  },
];

export const Onboarding = () => {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const { setCurrentOrganization } = useOrganizationStore();
  const { user, logout } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [hasOrganizations, setHasOrganizations] = useState(false);
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'yearly'>('monthly');
  const [formData, setFormData] = useState<OnboardingData>({
    organizationName: '',
    organizationSize: '',
    userRole: '',
    organizationType: '',
    subscriptionPlan: 'pro', // Default to pro plan
    teamEmails: [],
  });

  // Team invitation specific state
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'member' | 'admin'>('member');
  const [emailError, setEmailError] = useState('');
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);

  const totalSteps = 6;
  const isDark = resolvedTheme === 'dark';

  // Get the current plan's team member limit
  const currentPlanLimit = SUBSCRIPTION_PLANS.find(
    plan => plan.value === formData.subscriptionPlan
  )?.teamMemberLimit || 2;

  // Check if user already has organizations
  useEffect(() => {
    const checkExistingOrgs = async () => {
      try {
        const organizations = await useOrganizationStore.getState().initializeOrganizations();
        if (organizations.length > 0) {
          setHasOrganizations(true);
          // DO NOT REDIRECT - users with orgs can create additional organizations
        } else {
          setHasOrganizations(false);
        }
      } catch (error) {
        console.error('Failed to check organizations:', error);
        // Assume no orgs if check fails
        setHasOrganizations(false);
      }
    };

    checkExistingOrgs();
  }, []);

  // Handle ESC key to go back to dashboard on first step
  useEffect(() => {
    const handleEscapeKey = (e: KeyboardEvent) => {
      // Only allow ESC if user has organizations
      if (e.key === 'Escape' && hasOrganizations) {
        navigate('/');
      }
    };

    window.addEventListener('keydown', handleEscapeKey);
    return () => window.removeEventListener('keydown', handleEscapeKey);
  }, [navigate, hasOrganizations]);

  // Prevent browser refresh/navigation when user has no organizations
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!hasOrganizations) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasOrganizations]);

  const updateFormData = (field: keyof OnboardingData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleNext = () => {
    // Special validation for organization name on step 1
    if (currentStep === 1) {
      const orgName = formData.organizationName.trim();

      // Check minimum length
      if (orgName.length < 4) {
        toast.error('Organization name must be at least 4 characters long');
        return;
      }

      // Check for safe characters only (alphanumeric, spaces, hyphens, underscores)
      // Avoid special characters that could interfere with Auth0 or other integrations
      const safeCharRegex = /^[a-zA-Z0-9\s\-_]+$/;
      if (!safeCharRegex.test(orgName)) {
        toast.error('Organization name can only contain letters, numbers, spaces, hyphens, and underscores');
        return;
      }

      // Additional safety checks for Auth0 compatibility
      if (orgName.includes('  ')) {
        toast.error('Organization name cannot contain consecutive spaces');
        return;
      }

      if (orgName.startsWith(' ') || orgName.endsWith(' ')) {
        toast.error('Organization name cannot start or end with spaces');
        return;
      }
    }

    if (currentStep < totalSteps && isStepValid()) {
      // Track step completion
      posthog.capture('onboarding_step_completed', {
        step: currentStep,
        step_name: getStepName(currentStep),
        ...getStepData(currentStep),
      });

      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentStep(prev => prev + 1);
        setIsTransitioning(false);
      }, 150);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentStep(prev => prev - 1);
        setIsTransitioning(false);
      }, 150);
    }
  };

  const handleComplete = async () => {
    // Track final step completion
    posthog.capture('onboarding_step_completed', {
      step: currentStep,
      step_name: getStepName(currentStep),
      ...getStepData(currentStep),
    });

    // Update formData with team emails
    const emails = teamMembers.map(member => member.email);

    setIsCreating(true);

    try {
      // Step 1: Create organization with metadata
      const org_metadata = {
        onboarding: {
          organizationSize: formData.organizationSize,
          userRole: formData.userRole,
          organizationType: formData.organizationType,
          subscriptionPlan: formData.subscriptionPlan,
          teamInvites: teamMembers, // Store full team member info with roles
          completedAt: new Date().toISOString(),
        }
      };

      const createOrgResponse = await apiClient.post('/organizations', {
        name: formData.organizationName,
        description: `${formData.organizationType} company with ${formData.organizationSize} people`,
        org_metadata,
      });

      if (!createOrgResponse.ok) {
        throw new Error('Failed to create organization');
      }

      const organization = await createOrgResponse.json();

      // Track successful org creation
      posthog.capture('onboarding_completed', {
        org_id: organization.id,
        org_name: formData.organizationName,
        subscription_plan: formData.subscriptionPlan,
        billing_period: billingPeriod,
        team_members_invited: teamMembers.length,
        org_size: formData.organizationSize,
        user_role: formData.userRole,
        org_type: formData.organizationType,
      });

      // Step 2: Update organization context
      setCurrentOrganization(organization);

      // Step 3: Handle billing based on environment
      if (!authConfig.authEnabled) {
        // In local development, skip billing and go straight to dashboard
        toast.success('Organization created successfully!');
        navigate('/');
        return;
      }

      // Step 4: Billing
      try {
        if (formData.subscriptionPlan === 'developer') {
          // Free plan: backend already created $0 subscription; no checkout required
          toast.success('Organization created successfully!');
          navigate('/'); // TODO: is this redirection correct????
          return;
        }

        const isEligibleForYearly = ['pro', 'team'].includes(formData.subscriptionPlan);
        const endpoint = billingPeriod === 'yearly' && isEligibleForYearly
          ? '/billing/yearly/checkout-session'
          : '/billing/checkout-session';

        const checkoutResponse = await apiClient.post(endpoint, {
          plan: formData.subscriptionPlan,
          success_url: `${window.location.origin}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${window.location.origin}/billing/cancel`,
        });

        if (!checkoutResponse.ok) {
          const errorData = await checkoutResponse.json().catch(() => null);

          // If billing is not enabled on the backend, just navigate to dashboard
          if (errorData?.detail === 'Billing is not enabled for this instance') {
            toast.success('Organization created successfully!');
            navigate('/');
            return;
          }

          throw new Error(errorData?.detail || 'Failed to create billing session');
        }

        const { checkout_url } = await checkoutResponse.json();

        // Step 5: Redirect to Stripe checkout
        window.location.href = checkout_url;
      } catch (billingError) {
        // If billing fails but org was created, still navigate to dashboard
        console.warn('Billing setup failed, but organization was created:', billingError);
        toast.success('Organization created successfully!');
        navigate('/');
      }

    } catch (error) {
      console.error('Onboarding error:', error);
      toast.error('Failed to complete setup. Please try again.');
      setIsCreating(false);
    }
  };

  // Handle Enter key for progression
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && isStepValid()) {
      e.preventDefault();

      // Special validation for organization name on step 1
      if (currentStep === 1) {
        const orgName = formData.organizationName.trim();

        // Check minimum length
        if (orgName.length < 4) {
          toast.error('Organization name must be at least 4 characters long');
          return;
        }

        // Check for safe characters only (alphanumeric, spaces, hyphens, underscores)
        // Avoid special characters that could interfere with Auth0 or other integrations
        const safeCharRegex = /^[a-zA-Z0-9\s\-_]+$/;
        if (!safeCharRegex.test(orgName)) {
          toast.error('Organization name can only contain letters, numbers, spaces, hyphens, and underscores');
          return;
        }

        // Additional safety checks for Auth0 compatibility
        if (orgName.includes('  ')) {
          toast.error('Organization name cannot contain consecutive spaces');
          return;
        }

        if (orgName.startsWith(' ') || orgName.endsWith(' ')) {
          toast.error('Organization name cannot start or end with spaces');
          return;
        }
      }

      if (currentStep < totalSteps) {
        handleNext();
      } else {
        handleComplete();
      }
    }
  };

  // Auto-progress on selection for button-based steps
  const handleSelection = (field: keyof OnboardingData, value: any) => {
    updateFormData(field, value);
    // Auto-progress for steps 2-5
    if (currentStep >= 2 && currentStep <= 5) {
      // Track step completion
      const stepData = { ...getStepData(currentStep), [field]: value };
      posthog.capture('onboarding_step_completed', {
        step: currentStep,
        step_name: getStepName(currentStep),
        ...stepData,
      });

      setTimeout(() => {
        setIsTransitioning(true);
        setTimeout(() => {
          setCurrentStep(prev => prev + 1);
          setIsTransitioning(false);
        }, 150);
      }, 200); // Small delay for visual feedback
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

    // Check if email is the current user's email
    if (user?.email && email.toLowerCase() === user.email.toLowerCase()) {
      setEmailError("You don't need to invite yourself - you'll be the owner");
      return;
    }

    // Check if email already exists in team members
    const existingMember = teamMembers.find(member =>
      member.email.toLowerCase() === email.toLowerCase()
    );
    if (existingMember) {
      setEmailError('This email has already been added');
      return;
    }

    // Check team member limit - the limit includes the owner
    if (teamMembers.length >= currentPlanLimit - 1) {
      setEmailError(`You've reached the maximum team size for the ${formData.subscriptionPlan} plan`);
      return;
    }

    setEmailError('');
  }, [teamMembers, currentPlanLimit, formData.subscriptionPlan, user?.email]);

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const email = e.target.value;
    setInviteEmail(email);

    if (!email) {
      setEmailError('');
      return;
    }

    // Basic format check
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (emailRegex.test(email)) {
      validateEmail(email);
    } else {
      setEmailError('');
    }
  };

  const handleEmailBlur = () => {
    validateEmail(inviteEmail);
  };

  const handleAddTeamMember = () => {
    // First validate the email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(inviteEmail)) {
      setEmailError('Please enter a valid email address');
      return;
    }

    // Then check for other validation errors
    if (emailError) return;

    // Double-check the limit before adding
    if (teamMembers.length >= currentPlanLimit - 1) {
      setEmailError(`Maximum team size reached for ${formData.subscriptionPlan} plan`);
      toast.error('Cannot add more team members - plan limit reached');
      return;
    }

    const newMember: TeamMember = {
      email: inviteEmail,
      role: inviteRole,
    };

    setTeamMembers(prev => [...prev, newMember]);
    setInviteEmail('');
    setInviteRole('member');
    setEmailError('');
  };

  const handleRemoveTeamMember = (email: string) => {
    setTeamMembers(prev => prev.filter(member => member.email !== email));
  };

  const handleTeamEmailKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && inviteEmail && !emailError) {
      e.preventDefault();
      handleAddTeamMember();
    }
  };

  const handleLogout = () => {
    // Track abandonment
    posthog.capture('onboarding_abandoned', {
      step: currentStep,
      step_name: getStepName(currentStep),
      ...getStepData(currentStep),
    });

    // Clear token from localStorage
    apiClient.clearToken();

    // Use the logout from our auth context which handles both Auth0 and non-Auth0 cases
    logout();
  };

  const isStepValid = () => {
    switch (currentStep) {
      case 1:
        return formData.organizationName.trim().length > 0;
      case 2:
        return formData.organizationSize !== '';
      case 3:
        return formData.userRole !== '';
      case 4:
        return formData.organizationType !== '';
      case 5:
        return formData.subscriptionPlan !== '';
      case 6:
        return true; // Team invites are optional
      default:
        return false;
    }
  };

  const isValidEmail = inviteEmail && !emailError && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(inviteEmail);

  // PostHog tracking helpers
  const getStepName = (step: number): string => {
    const names = ['org_name', 'org_size', 'user_role', 'org_type', 'subscription', 'team_invites'];
    return names[step - 1] || 'unknown';
  };

  const getStepData = (step: number): Record<string, any> => {
    switch (step) {
      case 1: return { org_name: formData.organizationName };
      case 2: return { org_size: formData.organizationSize };
      case 3: return { user_role: formData.userRole };
      case 4: return { org_type: formData.organizationType };
      case 5: return { subscription_plan: formData.subscriptionPlan, billing_period: billingPeriod };
      case 6: return { team_members_count: teamMembers.length };
      default: return {};
    }
  };

  // Track step views
  useEffect(() => {
    posthog.capture('onboarding_step_viewed', {
      step: currentStep,
      step_name: getStepName(currentStep),
      has_existing_orgs: hasOrganizations,
    });
  }, [currentStep, hasOrganizations]);

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">What should we call your organization?</h2>
              <p className="text-muted-foreground">
                Choose a name that represents your team or company
              </p>
            </div>

            <div className="space-y-3">
              <input
                type="text"
                placeholder="e.g., Acme AI"
                value={formData.organizationName}
                onChange={(e) => updateFormData('organizationName', e.target.value)}
                onKeyPress={handleKeyPress}
                className={cn(
                  "w-full px-4 py-3 text-lg bg-transparent border rounded-lg",
                  "focus:outline-none focus:ring-1 focus:ring-primary/50",
                  "placeholder:text-muted-foreground/50"
                )}
                autoFocus
              />
              <p className="text-xs text-muted-foreground">
                Use letters, numbers, spaces, hyphens, and underscores only • You can always change this later
              </p>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">How many people are in your organization?</h2>
              <p className="text-muted-foreground">
                This helps us recommend the right plan
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {ORGANIZATION_SIZES.map((size) => (
                <button
                  key={size.value}
                  onClick={() => handleSelection('organizationSize', size.value)}
                  className={cn(
                    "p-6 rounded-lg border text-center transition-all",
                    "hover:border-primary/50",
                    formData.organizationSize === size.value
                      ? "border-primary bg-primary/5"
                      : "border-border"
                  )}
                >
                  <div className="text-2xl font-light mb-1">{size.label}</div>
                  <div className="text-xs text-muted-foreground">{size.description}</div>
                </button>
              ))}
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">What's your role?</h2>
              <p className="text-muted-foreground">
                We'll customize your experience based on your needs
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {USER_ROLES.map((role) => {
                const Icon = role.icon;
                return (
                  <button
                    key={role.value}
                    onClick={() => handleSelection('userRole', role.value)}
                    className={cn(
                      "p-6 rounded-lg border text-center transition-all group",
                      "hover:border-primary/50",
                      formData.userRole === role.value
                        ? "border-primary bg-primary/5"
                        : "border-border"
                    )}
                  >
                    <Icon className={cn(
                      "w-8 h-8 mx-auto mb-3 transition-colors",
                      formData.userRole === role.value
                        ? "text-primary"
                        : "text-muted-foreground group-hover:text-foreground"
                    )} />
                    <div className="text-sm">{role.label}</div>
                  </button>
                );
              })}
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">What type of company are you?</h2>
              <p className="text-muted-foreground">
                This helps us understand your data integration needs
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {ORGANIZATION_TYPES.map((type) => {
                const Icon = type.icon;
                return (
                  <button
                    key={type.value}
                    onClick={() => handleSelection('organizationType', type.value)}
                    className={cn(
                      "p-6 rounded-lg border text-left transition-all group",
                      "hover:border-primary/50",
                      formData.organizationType === type.value
                        ? "border-primary bg-primary/5"
                        : "border-border"
                    )}
                  >
                    <div className="flex items-start space-x-4">
                      <Icon className={cn(
                        "w-6 h-6 mt-0.5 flex-shrink-0 transition-colors",
                        formData.organizationType === type.value
                          ? "text-primary"
                          : "text-muted-foreground group-hover:text-foreground"
                      )} />
                      <div>
                        <div className="font-medium mb-1">{type.label}</div>
                        <div className="text-xs text-muted-foreground">{type.description}</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );

      case 5:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">Choose your plan</h2>
              <p className="text-muted-foreground">
                You can always upgrade or downgrade later
              </p>
              {!authConfig.authEnabled && (
                <div className="mt-2 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                  <p className="text-xs text-amber-600 dark:text-amber-400">
                    <strong>Local Development Mode:</strong> Billing is disabled. You'll go straight to the dashboard after setup.
                  </p>
                </div>
              )}
            </div>

            {/* Monthly/Yearly Toggle - Only show when auth is enabled */}
            {authConfig.authEnabled && (
              <div className="flex justify-center relative">
                <div className="relative">
                  <div className="relative inline-flex items-center p-1 bg-muted rounded-lg shadow-sm border">
                    {/* Sliding background indicator - dynamically sized */}
                    <div
                      className={cn(
                        'absolute top-1 h-[calc(100%-8px)] rounded-md bg-blue/20 shadow-sm transition-all duration-200',
                        billingPeriod === 'monthly' ? 'left-1 w-[80px]' : 'left-[80px] w-[140px]'
                      )}
                    />
                    <button
                      type="button"
                      onClick={() => setBillingPeriod('monthly')}
                      className={cn(
                        'relative z-10 px-4 py-2 text-sm rounded-md transition-all w-[80px]',
                        billingPeriod === 'monthly'
                          ? 'text-foreground'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      Monthly
                    </button>
                    <button
                      type="button"
                      onClick={() => setBillingPeriod('yearly')}
                      className={cn(
                        'relative z-10 px-4 py-2 text-sm rounded-md transition-all flex items-center gap-2 w-[140px] justify-center',
                        billingPeriod === 'yearly'
                          ? 'text-foreground'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      Yearly
                      <span className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                        Save 20%
                      </span>
                    </button>
                  </div>
                  {/* Absolute positioned message - doesn't affect layout */}
                  <div className={cn(
                    "absolute top-full mt-1 left-1/2 -translate-x-1/2 transition-opacity duration-200",
                    billingPeriod === 'yearly' ? 'opacity-100' : 'opacity-0 pointer-events-none'
                  )}>
                    <p className="text-xs text-muted-foreground text-center whitespace-nowrap">
                      After 12 months, your plan will renew at monthly rates. You can re-enable yearly billing anytime to keep the discount.
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="grid gap-4">
              {SUBSCRIPTION_PLANS.map((plan) => (
                <button
                  key={plan.value}
                  onClick={() => {
                    if (plan.value === 'enterprise') {
                      window.open('https://cal.com/lennert-airweave/airweave-demo', '_blank', 'noopener,noreferrer');
                      return;
                    }
                    handleSelection('subscriptionPlan', plan.value);
                  }}
                  className={cn(
                    "relative p-6 rounded-lg border text-left transition-all",
                    "hover:border-primary/50",
                    formData.subscriptionPlan === plan.value
                      ? "border-primary bg-primary/5"
                      : "border-border"
                  )}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-lg">{plan.label}</h3>
                        {/* Trials disabled */}
                      </div>
                      <p className="text-sm text-muted-foreground">{plan.description}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-light">
                        {!authConfig.authEnabled ? 'Free' : (
                          billingPeriod === 'yearly' && (plan.value === 'pro' || plan.value === 'team')
                            ? (plan.value === 'pro' ? '$16' : '$239')
                            : plan.price
                        )}
                      </div>
                      {plan.period && !authConfig.authEnabled && (
                        <div className="text-xs text-muted-foreground">local dev</div>
                      )}
                      {plan.period && authConfig.authEnabled && (
                        <div className="text-xs text-muted-foreground">
                          {billingPeriod === 'yearly' && (plan.value === 'pro' || plan.value === 'team')
                            ? 'per month (billed yearly)'
                            : plan.period}
                        </div>
                      )}
                      {plan.recommended && (
                        <div className="text-xs text-primary mt-1">
                          Recommended
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-muted-foreground">
                    {plan.features.map((feature, index) => (
                      <div key={index} className="flex items-center">
                        <Check className="w-3 h-3 mr-2 text-primary flex-shrink-0" />
                        {feature}
                      </div>
                    ))}
                  </div>
                </button>
              ))}
            </div>

            {/* Enterprise now included as a plan card above */}
          </div>
        );

      case 6:
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
                <h3 className="text-sm font-medium text-foreground">Add team members</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Your {formData.subscriptionPlan} plan includes up to {currentPlanLimit} team members
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex gap-3">
                  <div className="flex-1">
                    <input
                      type="email"
                      placeholder="Email address"
                      value={inviteEmail}
                      onChange={handleEmailChange}
                      onBlur={handleEmailBlur}
                      onKeyPress={handleTeamEmailKeyPress}
                      className={cn(
                        "w-full h-8 px-3 text-sm bg-transparent border rounded-md",
                        "focus:outline-none focus:ring-0 focus:border-border",
                        "placeholder:text-muted-foreground/60 transition-colors",
                        emailError && inviteEmail && "border-destructive/50",
                        teamMembers.length >= currentPlanLimit - 1 && "opacity-50 cursor-not-allowed"
                      )}
                      disabled={teamMembers.length >= currentPlanLimit - 1}
                    />
                    {emailError && inviteEmail && (
                      <p className="text-xs text-destructive/80 mt-1">{emailError}</p>
                    )}
                  </div>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as 'member' | 'admin')}
                    className={cn(
                      "w-24 h-8 px-2 text-sm bg-transparent border rounded-md",
                      "focus:outline-none focus:ring-0 focus:border-border transition-colors",
                      teamMembers.length >= currentPlanLimit - 1 && "opacity-50 cursor-not-allowed"
                    )}
                    disabled={teamMembers.length >= currentPlanLimit - 1}
                  >
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button
                    onClick={handleAddTeamMember}
                    disabled={!isValidEmail || teamMembers.length >= currentPlanLimit - 1}
                    className={cn(
                      "h-8 px-4 text-sm rounded-md transition-all",
                      isValidEmail && teamMembers.length < currentPlanLimit - 1
                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                        : "bg-muted text-muted-foreground cursor-not-allowed"
                    )}
                  >
                    Add
                  </button>
                </div>
              </div>

              {/* Team members list */}
              {teamMembers.length > 0 && (
                <div className="space-y-4 mt-6">
                  <div>
                    <h3 className="text-sm font-medium text-foreground pt-2">Team members to invite</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {teamMembers.length} of {currentPlanLimit - 1} team members added
                    </p>
                  </div>

                  <div className="border border-border rounded-lg divide-y divide-border">
                    {teamMembers.map((member, index) => (
                      <div key={index} className="flex items-center justify-between py-2 px-4">
                        <div className="flex items-center gap-3">
                          <div className="text-sm">{member.email}</div>
                          <span className={cn(
                            "text-xs px-2 py-0.5 rounded-full",
                            member.role === 'admin'
                              ? "bg-primary/10 text-primary"
                              : "bg-muted text-muted-foreground"
                          )}>
                            {member.role}
                          </span>
                        </div>
                        <button
                          onClick={() => handleRemoveTeamMember(member.email)}
                          className="p-1 rounded hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground"
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

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl relative">
        {/* Header with logo branding */}
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

        {/* Progress and close button */}
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center space-x-6">
            {/* Step indicators */}
            <div className="flex items-center space-x-2">
              {Array.from({ length: totalSteps }, (_, i) => (
                <div
                  key={i}
                  className={cn(
                    "h-1.5 rounded-full transition-all duration-300",
                    i < currentStep
                      ? "w-6 bg-primary"
                      : i === currentStep - 1
                        ? "w-12 bg-primary"
                        : "w-6 bg-muted"
                  )}
                />
              ))}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              Step {currentStep} of {totalSteps}
            </span>

            {hasOrganizations && (
              <button
                onClick={() => navigate('/')}
                className="p-2 rounded-lg hover:bg-muted/50 transition-colors"
                title="Close"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Content with fade transition */}
        <div className={cn(
          "min-h-[400px] transition-opacity duration-150",
          isTransitioning ? "opacity-0" : "opacity-100"
        )}>
          {renderStep()}
        </div>

        {/* Actions */}
        <div className="mt-12 flex items-center justify-between relative">
          {/* Back button - only show after first step */}
          {currentStep > 1 && (
            <button
              onClick={handleBack}
              className="flex items-center space-x-2 px-4 py-2 rounded-lg transition-all hover:bg-muted/50 text-muted-foreground hover:text-foreground"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
          )}

          {/* Logout button - only show on first step */}
          {currentStep === 1 && (
            <button
              onClick={handleLogout}
              className="flex items-center space-x-2 px-4 py-2 rounded-lg transition-all bg-blue-500/10 text-muted-foreground hover:bg-blue-500/20"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>
          )}

          {/* Right side - Continue/Complete button */}
          {currentStep < totalSteps ? (
            <button
              onClick={handleNext}
              disabled={!isStepValid()}
              className={cn(
                "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all",
                isStepValid()
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
            >
              <span>Continue</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleComplete}
              disabled={!isStepValid() || isCreating}
              className={cn(
                "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all",
                isStepValid() && !isCreating
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
            >
              {isCreating ? (
                <>
                  <span>{!authConfig.authEnabled ? 'Creating Organization' : 'Complete Setup'}</span>
                  <Loader2 className="w-4 h-4 animate-spin" />
                </>
              ) : (
                <>
                  <span>{!authConfig.authEnabled ? 'Create Organization' : 'Complete Setup'}</span>
                  <Check className="w-4 h-4" />
                </>
              )}
            </button>
          )}
        </div>

      </div>
    </div>
  );
};

export default Onboarding;
