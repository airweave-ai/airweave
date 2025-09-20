import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '@/lib/api';
import { BillingInfo } from '@/types';
import { useUsageStore } from './usage';

interface Organization {
  id: string;
  name: string;
  description?: string;
  auth0_org_id?: string;
  role: 'owner' | 'admin' | 'member';
  is_primary: boolean;
  created_at?: string;
  modified_at?: string;
  org_metadata?: {
    onboarding?: {
      organizationSize: string;
      userRole: string;
      organizationType: string;
      subscriptionPlan: string;
      teamInvites: Array<{
        email: string;
        role: 'member' | 'admin';
      }>;
      completedAt: string;
    };
    [key: string]: any;
  };
}

interface CreateOrganizationRequest {
  name: string;
  description?: string;
}

interface OrganizationState {
  // Organization state
  organizations: Organization[];
  currentOrganization: Organization | null;
  isLoading: boolean;
  billingInfo: BillingInfo | null;
  billingLoading: boolean;

  // Request deduplication
  inflightOrgRequest: Promise<Organization[]> | null;
  inflightBillingRequest: Promise<BillingInfo | null> | null;
  lastOrgFetch: number;
  lastBillingFetch: number;

  // Actions
  setOrganizations: (orgs: Organization[]) => void;
  setCurrentOrganization: (org: Organization) => void;
  addOrganization: (org: Organization) => void;
  removeOrganization: (orgId: string) => void;
  updateOrganization: (orgId: string, updates: Partial<Organization>) => void;
  setLoading: (loading: boolean) => void;
  createOrganization: (orgData: CreateOrganizationRequest) => Promise<Organization>;
  fetchUserOrganizations: () => Promise<void>;
  switchOrganization: (orgId: string) => void;
  setPrimaryOrganization: (orgId: string) => Promise<boolean>;
  initializeOrganizations: () => Promise<Organization[]>;

  // Billing actions
  fetchBillingInfo: () => Promise<BillingInfo | null>;
  checkBillingStatus: () => Promise<{ requiresAction: boolean; message?: string; redirectUrl?: string }>;
  clearBillingInfo: () => void;

  // Member management actions
  inviteUserToOrganization: (orgId: string, email: string, role: string) => Promise<boolean>;
  removeUserFromOrganization: (orgId: string, userId: string) => Promise<boolean>;
  leaveOrganization: (orgId: string) => Promise<boolean>;
}

// Helper function to select the best organization
const selectBestOrganization = (
  organizations: Organization[],
  currentOrgId?: string | null
): Organization | null => {
  if (organizations.length === 0) return null;

  // Priority:
  // 1. Current organization (if it still exists and is valid)
  // 2. Primary organization
  // 3. First organization

  // Check if current org is still valid
  if (currentOrgId) {
    const currentOrg = organizations.find(org => org.id === currentOrgId);
    if (currentOrg) {
      return currentOrg;
    }
  }

  // Find primary organization
  const primaryOrg = organizations.find(org => org.is_primary);
  if (primaryOrg) {
    return primaryOrg;
  }

  // Fallback to first organization
  return organizations[0];
};

export const useOrganizationStore = create<OrganizationState>()(
  persist(
    (set, get) => ({
      organizations: [],
      currentOrganization: null,
      isLoading: false,
      billingInfo: null,
      billingLoading: false,
      inflightOrgRequest: null,
      inflightBillingRequest: null,
      lastOrgFetch: 0,
      lastBillingFetch: 0,

      setOrganizations: (organizations) => {
        const currentOrgId = get().currentOrganization?.id;
        const currentOrg = selectBestOrganization(organizations, currentOrgId);

        set({ organizations, currentOrganization: currentOrg });
      },

      setCurrentOrganization: (currentOrganization) => set({ currentOrganization }),

      addOrganization: (org) => set((state) => ({
        organizations: [...state.organizations, org]
      })),

      removeOrganization: (orgId) => set((state) => {
        const newOrganizations = state.organizations.filter(org => org.id !== orgId);
        const newCurrentOrg = state.currentOrganization?.id === orgId
          ? selectBestOrganization(newOrganizations)
          : state.currentOrganization;

        return {
          organizations: newOrganizations,
          currentOrganization: newCurrentOrg
        };
      }),

      updateOrganization: (orgId, updates) => set((state) => ({
        organizations: state.organizations.map(org =>
          org.id === orgId ? { ...org, ...updates } : org
        ),
        currentOrganization: state.currentOrganization?.id === orgId ?
          { ...state.currentOrganization, ...updates } : state.currentOrganization
      })),

      setLoading: (isLoading) => set({ isLoading }),

      switchOrganization: (orgId) => {
        const { organizations } = get();
        const org = organizations.find(o => o.id === orgId);
        if (org) {
          set({ currentOrganization: org, billingInfo: null }); // Clear billing info on switch
          console.log(`🔄 [OrganizationStore] Switched to organization: ${org.name} (${org.id})`);

          // Clear usage cache when switching organizations
          useUsageStore.getState().clearCache();
        }
      },

      setPrimaryOrganization: async (orgId: string): Promise<boolean> => {
        try {
          set({ isLoading: true });

          const response = await apiClient.post(`/organizations/${orgId}/set-primary`);

          if (!response.ok) {
            throw new Error(`Failed to set primary organization: ${response.status}`);
          }

          const updatedOrg = await response.json();

          // Update all organizations - clear is_primary from others, set it for the target
          set((state) => ({
            organizations: state.organizations.map(org => ({
              ...org,
              is_primary: org.id === orgId
            })),
            currentOrganization: state.currentOrganization?.id === orgId ?
              { ...state.currentOrganization, is_primary: true } :
              state.currentOrganization,
            isLoading: false
          }));

          return true;
        } catch (error) {
          console.error('Failed to set primary organization:', error);
          set({ isLoading: false });
          return false;
        }
      },

      initializeOrganizations: async (): Promise<Organization[]> => {
        // Check if we have a recent fetch (within 5 seconds)
        const now = Date.now();
        const { lastOrgFetch, organizations, inflightOrgRequest } = get();

        if (lastOrgFetch && (now - lastOrgFetch) < 5000 && organizations.length > 0) {
          console.log('Using cached organizations (fetched', Math.round((now - lastOrgFetch) / 1000), 'seconds ago)');
          return organizations;
        }

        // If there's already a request in flight, return it
        if (inflightOrgRequest) {
          console.log('Returning existing organization request');
          return inflightOrgRequest;
        }

        // Create new request
        const request = (async () => {
          try {
            set({ isLoading: true });

            // Get organizations directly from the new endpoint
            const response = await apiClient.get('/users/me/organizations');

            if (!response.ok) {
              throw new Error(`Failed to fetch organizations: ${response.status}`);
            }

            const organizations: Organization[] = await response.json();

            // Respect persisted organization selection if available, otherwise prefer primary organization
            const currentOrgId = get().currentOrganization?.id;
            const currentOrg = selectBestOrganization(organizations, currentOrgId);

            set({
              organizations,
              currentOrganization: currentOrg,
              isLoading: false,
              inflightOrgRequest: null,
              lastOrgFetch: Date.now()
            });

            console.log('Organizations initialized:', {
              total: organizations.length,
              selected: currentOrg?.name,
              isPrimary: currentOrg?.is_primary,
              wasFromPersistence: !!currentOrgId && currentOrgId === currentOrg?.id
            });

            return organizations;
          } catch (error) {
            console.error('Failed to initialize organizations:', error);
            set({ isLoading: false, inflightOrgRequest: null });
            throw error;
          }
        })();

        set({ inflightOrgRequest: request });
        return request;
      },

      fetchUserOrganizations: async () => {
        // Just use initializeOrganizations which has deduplication
        return get().initializeOrganizations();
      },

      createOrganization: async (orgData: CreateOrganizationRequest) => {
        try {
          set({ isLoading: true });

          const response = await apiClient.post('/organizations', orgData);

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to create organization: ${response.status}`);
          }

          const newOrganization = await response.json();

          // Add the new organization to the store
          set((state) => ({
            organizations: [...state.organizations, newOrganization],
            currentOrganization: newOrganization, // Set as current organization
            isLoading: false,
          }));

          return newOrganization;
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      // Billing methods
      fetchBillingInfo: async (): Promise<BillingInfo | null> => {
        // Check if we have a recent fetch (within 10 seconds)
        const now = Date.now();
        const { lastBillingFetch, billingInfo, inflightBillingRequest } = get();

        if (lastBillingFetch && (now - lastBillingFetch) < 10000 && billingInfo) {
          console.log('Using cached billing info (fetched', Math.round((now - lastBillingFetch) / 1000), 'seconds ago)');
          return billingInfo;
        }

        // If there's already a request in flight, return it
        if (inflightBillingRequest) {
          console.log('Returning existing billing request');
          return inflightBillingRequest;
        }

        // Create new request
        const request = (async () => {
          try {
            set({ billingLoading: true });

            const response = await apiClient.get('/billing/subscription');

            if (!response.ok) {
              if (response.status === 400) {
                // Billing not enabled (OSS mode)
                set({ billingInfo: null, billingLoading: false, inflightBillingRequest: null });
                return null;
              }
              throw new Error(`Failed to fetch billing info: ${response.status}`);
            }

            const billingInfo: BillingInfo = await response.json();
            set({
              billingInfo,
              billingLoading: false,
              inflightBillingRequest: null,
              lastBillingFetch: Date.now()
            });
            return billingInfo;
          } catch (error) {
            console.error('Failed to fetch billing info:', error);
            set({ billingLoading: false, inflightBillingRequest: null });
            return null;
          }
        })();

        set({ inflightBillingRequest: request });
        return request;
      },

      checkBillingStatus: async (): Promise<{ requiresAction: boolean; message?: string; redirectUrl?: string }> => {
        const billingInfo = await get().fetchBillingInfo();

        if (!billingInfo || billingInfo.is_oss) {
          // OSS mode, no action required
          return { requiresAction: false };
        }

        // Check if payment method is required
        if (billingInfo.requires_payment_method) {
          const gracePeriodExpired = billingInfo.grace_period_ends_at &&
            new Date(billingInfo.grace_period_ends_at) <= new Date();

          if (gracePeriodExpired) {
            return {
              requiresAction: true,
              message: 'Your grace period has expired. Please add a payment method to continue using Airweave.',
              redirectUrl: '/billing/setup'
            };
          } else if (billingInfo.in_grace_period) {
            const daysLeft = Math.ceil(
              (new Date(billingInfo.grace_period_ends_at!).getTime() - new Date().getTime()) /
              (1000 * 60 * 60 * 24)
            );
            return {
              requiresAction: true,
              message: `You have ${daysLeft} days left to add a payment method.`,
              redirectUrl: '/billing/setup'
            };
          }
        }

        // Check if subscription is past due
        if (billingInfo.status === 'past_due') {
          return {
            requiresAction: true,
            message: 'Your subscription payment failed. Please update your payment method.',
            redirectUrl: '/billing/portal'
          };
        }

        // Check if subscription is canceled but still valid
        if (billingInfo.status === 'canceled') {
          // Check if we're past the current period end
          const isExpired = billingInfo.current_period_end &&
            new Date(billingInfo.current_period_end) <= new Date();

          if (isExpired) {
            return {
              requiresAction: true,
              message: 'Your subscription has ended. Please reactivate to continue using Airweave.',
              redirectUrl: '/billing/setup'
            };
          }
          // If canceled but not expired, no action required yet
          return { requiresAction: false };
        }

        // Check if trial expired
        if (billingInfo.status === 'trial_expired') {
          return {
            requiresAction: true,
            message: 'Your trial has expired. Please subscribe to continue using Airweave.',
            redirectUrl: '/billing/setup'
          };
        }

        return { requiresAction: false };
      },

      clearBillingInfo: () => set({ billingInfo: null }),

      // Member management actions
      inviteUserToOrganization: async (orgId: string, email: string, role: string): Promise<boolean> => {
        try {
          set({ isLoading: true });

          const response = await apiClient.post(`/organizations/${orgId}/invite`, {
            email,
            role
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to invite user: ${response.status}`);
          }

          set({ isLoading: false });
          return true;
        } catch (error) {
          console.error('Failed to invite user to organization:', error);
          set({ isLoading: false });
          throw error;
        }
      },

      removeUserFromOrganization: async (orgId: string, userId: string): Promise<boolean> => {
        try {
          set({ isLoading: true });

          const response = await apiClient.delete(`/organizations/${orgId}/members/${userId}`);

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to remove user: ${response.status}`);
          }

          set({ isLoading: false });
          return true;
        } catch (error) {
          console.error('Failed to remove user from organization:', error);
          set({ isLoading: false });
          throw error;
        }
      },

      leaveOrganization: async (orgId: string): Promise<boolean> => {
        try {
          set({ isLoading: true });

          const response = await apiClient.post(`/organizations/${orgId}/leave`);

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to leave organization: ${response.status}`);
          }

          // Remove the organization from the local state
          const { organizations, currentOrganization } = get();
          const newOrganizations = organizations.filter(org => org.id !== orgId);
          const newCurrentOrg = currentOrganization?.id === orgId
            ? selectBestOrganization(newOrganizations)
            : currentOrganization;

          set({
            organizations: newOrganizations,
            currentOrganization: newCurrentOrg,
            isLoading: false
          });

          return true;
        } catch (error) {
          console.error('Failed to leave organization:', error);
          set({ isLoading: false });
          throw error;
        }
      },
    }),
    {
      name: 'organization-storage',
      partialize: (state) => ({
        currentOrganization: state.currentOrganization
      }),
    }
  )
);
