import { useEffect, useState } from 'react';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { TooltipProvider } from '@/components/ui/tooltip';
import {
  Plus, Settings as SettingsIcon, Key, Users, Check, Copy, Star, CreditCard, MousePointerBan, TrendingUp, Gauge
} from 'lucide-react';
import { APIKeysSettings } from '@/components/settings/APIKeysSettings';
import { MembersSettings } from '@/components/settings/MembersSettings';
import { BillingSettings } from '@/components/settings/BillingSettings';
import { UsageDashboard } from '@/components/settings/UsageDashboard';
import { SourceRateLimits } from '@/components/settings/SourceRateLimits';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { FeatureFlags } from '@/lib/constants/feature-flags';

import { OrganizationSettings } from '@/components/settings/OrganizationSettings';

type TabType = 'settings' | 'api-keys' | 'members' | 'billing' | 'usage' | 'rate-limiting';

export const OrganizationSettingsUnified = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const {
    currentOrganization,
    updateOrganization,
    fetchUserOrganizations,
    setPrimaryOrganization
  } = useOrganizationStore();

  // Tab state - get initial tab from URL params
  const initialTab = searchParams.get('tab') as TabType || 'settings';
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);

  // Add state for copy animation
  const [isCopied, setIsCopied] = useState(false);

  // Add state for primary toggle loading
  const [isPrimaryToggleLoading, setIsPrimaryToggleLoading] = useState(false);

  // Update tab when URL params change
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab') as TabType || 'settings';
    setActiveTab(tabFromUrl);
  }, [searchParams]);

  // Check for billing success parameter
  useEffect(() => {
    if (searchParams.get('success') === 'true' && activeTab === 'billing') {
      toast.success('Subscription activated successfully!');
      // Remove the success parameter from URL
      const newSearchParams = new URLSearchParams(searchParams);
      newSearchParams.delete('success');
      navigate(`/organization/settings?${newSearchParams.toString()}`, { replace: true });
    }
  }, [searchParams, activeTab, navigate]);



  // Enhanced organization update handler that also refreshes organizations list
  const handleOrganizationUpdate = async (id: string, updates: Partial<any>) => {
    // Update the organization in the store
    updateOrganization(id, updates);

    // Refresh the organizations list to ensure all components are updated
    try {
      await fetchUserOrganizations();
    } catch (error) {
      console.error('Failed to refresh organizations after update:', error);
    }
  };

  // Handle primary organization toggle
  const handlePrimaryToggle = async (checked: boolean) => {
    if (!currentOrganization || isPrimaryToggleLoading) return;

    // If unchecking, we don't allow it since there should always be a primary
    if (!checked) {
      toast.error('You must have at least one primary organization');
      return;
    }

    setIsPrimaryToggleLoading(true);

    try {
      const success = await setPrimaryOrganization(currentOrganization.id);

      if (success) {
        toast.success(`${currentOrganization.name} is now your primary organization`);
        // Refresh to ensure UI is in sync
        await fetchUserOrganizations();
      } else {
        toast.error('Failed to set primary organization');
      }
    } catch (error) {
      console.error('Error setting primary organization:', error);
      toast.error('Failed to set primary organization');
    } finally {
      setIsPrimaryToggleLoading(false);
    }
  };

  // Handle copy to clipboard
  const handleCopyId = () => {
    if (currentOrganization?.id) {
      navigator.clipboard.writeText(currentOrganization.id);
      setIsCopied(true);

      // Reset after animation completes
      setTimeout(() => {
        setIsCopied(false);
      }, 1500);

      toast.success('Organization ID copied to clipboard');
    }
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'owner': return <Key className="h-3 w-3" />;
      case 'admin': return <SettingsIcon className="h-3 w-3" />;
      default: return <Users className="h-3 w-3" />;
    }
  };

  const handleTabChange = (tabId: TabType) => {
    setActiveTab(tabId);
    const newSearchParams = new URLSearchParams(searchParams);
    if (tabId === 'settings') {
      newSearchParams.delete('tab');
    } else {
      newSearchParams.set('tab', tabId);
    }
    navigate(`/organization/settings?${newSearchParams.toString()}`, { replace: true });
  };

  if (!currentOrganization) {
    return (
      <div className="max-w-2xl mx-auto pt-16">
        <div className="text-center">
          <h2 className="text-xl font-medium mb-2">No organization selected</h2>
          <p className="text-muted-foreground text-sm mb-6">
            Create your first organization to get started
          </p>
          <Button
            onClick={() => navigate('/onboarding')}
            size="sm"
            className="h-8 px-3 text-sm"
          >
            <Plus className="h-3 w-3 mr-1" />
            Create organization
          </Button>
        </div>
      </div>
    );
  }

  // Check if rate limiting feature is enabled
  const hasRateLimitingFeature = currentOrganization?.enabled_features?.includes(
    FeatureFlags.SOURCE_RATE_LIMITING
  );

  const tabs = [
    { id: 'settings' as TabType, label: 'Settings', icon: <SettingsIcon className="h-3.5 w-3.5" /> },
    { id: 'api-keys' as TabType, label: 'API Keys', icon: <Key className="h-3.5 w-3.5" /> },
    { id: 'members' as TabType, label: 'Members', icon: <Users className="h-3.5 w-3.5" /> },
    { id: 'usage' as TabType, label: 'Usage', icon: <TrendingUp className="h-3.5 w-3.5" /> },
    { id: 'billing' as TabType, label: 'Billing', icon: <CreditCard className="h-3.5 w-3.5" /> },
    ...(hasRateLimitingFeature
      ? [{ id: 'rate-limiting' as TabType, label: 'Rate Limiting', icon: <Gauge className="h-3.5 w-3.5" /> }]
      : []),
  ];

  return (
    <>
      <TooltipProvider delayDuration={200}>
        <div className="max-w-4xl mx-auto py-8">
          {/* Header - Simplified without primary toggle */}
          <div className="flex items-start justify-between mb-8">
            <div className="flex flex-col">
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-xl font-medium">{currentOrganization.name}</h1>

                {/* Subtle role indicator */}
                <div className="flex items-center gap-1 text-brand-lime/90">
                  {getRoleIcon(currentOrganization.role)}
                  <span className="text-xs capitalize">{currentOrganization.role}</span>
                </div>

                {/* Subtle primary indicator */}
                {currentOrganization.is_primary && (
                  <div className="flex items-center gap-1 text-brand-yellow">
                    <Star className="h-3 w-3" />
                    <span className="text-xs">Primary</span>
                  </div>
                )}
              </div>

              {/* Organization ID under title */}
              <p className="text-muted-foreground text-xs group relative flex items-center">
                {currentOrganization.id}
                <button
                  className="ml-1.5 opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100 focus:outline-none"
                  onClick={handleCopyId}
                  title="Copy ID"
                >
                  {isCopied ? (
                    <Check className="h-3.5 w-3.5 text-muted-foreground transition-all" />
                  ) : (
                    <Copy className="h-3.5 w-3.5 text-muted-foreground transition-all" />
                  )}
                </button>
              </p>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex border-b border-border mb-8">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={cn(
                    "flex items-center gap-2 py-3 px-1 text-sm font-medium transition-colors border-b-2 border-transparent mr-8",
                    isActive
                      ? "text-foreground border-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          <div>
            {/* Settings Tab */}
            {activeTab === 'settings' && (
              <div className="space-y-8">
                <TooltipProvider delayDuration={200}>
                  <OrganizationSettings
                    currentOrganization={currentOrganization}
                    onOrganizationUpdate={handleOrganizationUpdate}
                    onPrimaryToggle={handlePrimaryToggle}
                    isPrimaryToggleLoading={isPrimaryToggleLoading}
                  />
                </TooltipProvider>
              </div>
            )}

            {/* API Keys Tab */}
            {activeTab === 'api-keys' && (
              <div>
                <APIKeysSettings />
              </div>
            )}

            {/* Members Tab */}
            {activeTab === 'members' && (
              <MembersSettings
                currentOrganization={currentOrganization}
              />
            )}

            {/* Usage Tab */}
            {activeTab === 'usage' && (
              <div>
                <UsageDashboard organizationId={currentOrganization.id} />
              </div>
            )}

            {/* Billing Tab */}
            {activeTab === 'billing' && (
              <BillingSettings
                organizationId={currentOrganization.id}
              />
            )}

            {/* Rate Limiting Tab */}
            {activeTab === 'rate-limiting' && hasRateLimitingFeature && (
              <div>
                <SourceRateLimits />
              </div>
            )}
          </div>
        </div>
      </TooltipProvider>
    </>
  );
};
