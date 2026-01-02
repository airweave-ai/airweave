import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api';
import { Shield, Building2, Layers } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { OrganizationsTab, SyncMigrationsTab } from '@/components/admin';

// ============ TYPES ============

type TabType = 'organizations' | 'sync-migrations';

interface OrganizationOption {
  id: string;
  name: string;
}

// ============ MAIN COMPONENT ============

export function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Tab state
  const initialTab = (searchParams.get('tab') as TabType) || 'organizations';
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);

  // Organizations for the sync migrations tab filter
  const [organizations, setOrganizations] = useState<OrganizationOption[]>([]);

  useEffect(() => {
    if (user && !user.is_admin) {
      toast.error('Admin access required');
      navigate('/');
      return;
    }

    if (user?.is_admin) {
      loadOrganizations();
    }
  }, [user, navigate]);

  // Update tab when URL changes
  useEffect(() => {
    const tabFromUrl = (searchParams.get('tab') as TabType) || 'organizations';
    setActiveTab(tabFromUrl);
  }, [searchParams]);

  const loadOrganizations = async () => {
    try {
      const response = await apiClient.get('/admin/organizations?limit=10000');
      if (response.ok) {
        const orgs = await response.json();
        setOrganizations(orgs.map((org: { id: string; name: string }) => ({ id: org.id, name: org.name })));
      }
    } catch (error) {
      console.error('Failed to load organizations:', error);
    }
  };

  const handleTabChange = (tabId: TabType) => {
    setActiveTab(tabId);
    const newParams = new URLSearchParams(searchParams);
    if (tabId === 'organizations') {
      newParams.delete('tab');
    } else {
      newParams.set('tab', tabId);
    }
    setSearchParams(newParams, { replace: true });
  };

  if (!user?.is_admin) return null;

  const tabs = [
    { id: 'organizations' as TabType, label: 'Organizations', icon: <Building2 className="h-4 w-4" /> },
    { id: 'sync-migrations' as TabType, label: 'Sync Migrations', icon: <Layers className="h-4 w-4" /> },
  ];

  // ============ RENDER ============

  return (
    <div className="container mx-auto py-6 px-4 max-w-[1800px]">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-3xl font-bold">Admin Dashboard</h1>
            <p className="text-muted-foreground">Platform management and migrations</p>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id)}
            className={cn(
              "flex items-center gap-2 py-3 px-1 text-sm font-medium transition-colors border-b-2 border-transparent mr-8",
              activeTab === tab.id
                ? "text-foreground border-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'organizations' && (
        <OrganizationsTab userEmail={user?.email} />
      )}

      {activeTab === 'sync-migrations' && (
        <SyncMigrationsTab organizations={organizations} />
      )}
    </div>
  );
}
