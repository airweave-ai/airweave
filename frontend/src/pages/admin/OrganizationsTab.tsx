import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Plus, Crown, Building2, ArrowUpCircle, UserPlus, Search, ArrowUpDown, Users, Database, Activity, Flag } from 'lucide-react';
import { toast } from 'sonner';

interface AvailableFeatureFlag {
  name: string;
  value: string;
}

interface OrganizationMetrics {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  modified_at: string;
  auth0_org_id?: string;
  billing_plan?: string;
  billing_status?: string;
  stripe_customer_id?: string;
  trial_ends_at?: string;
  user_count: number;
  source_connection_count: number;
  entity_count: number;
  query_count: number;
  last_active_at?: string;
  is_member: boolean;
  member_role?: string;
  enabled_features?: string[];
}

type SortField = 'name' | 'created_at' | 'billing_plan' | 'user_count' | 'source_connection_count' | 'entity_count' | 'query_count' | 'last_active_at' | 'is_member';
type SortOrder = 'asc' | 'desc';
type MembershipFilter = 'all' | 'member' | 'non-member';

export function OrganizationsTab() {
  const { user } = useAuth();
  const [organizations, setOrganizations] = useState<OrganizationMetrics[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedOrg, setSelectedOrg] = useState<OrganizationMetrics | null>(null);
  const [actionType, setActionType] = useState<'join' | 'upgrade' | 'create' | 'feature-flags' | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Feature flags state
  const [availableFeatureFlags, setAvailableFeatureFlags] = useState<AvailableFeatureFlag[]>([]);
  const [enabledFeatureFlags, setEnabledFeatureFlags] = useState<string[]>([]);

  // Search and sort state
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [membershipFilter, setMembershipFilter] = useState<MembershipFilter>('all');

  // Create enterprise org form
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgDescription, setNewOrgDescription] = useState('');
  const [ownerEmail, setOwnerEmail] = useState('');

  // Join org form
  const [selectedRole, setSelectedRole] = useState<'owner' | 'admin' | 'member'>('owner');

  useEffect(() => {
    if (user?.is_admin) {
      loadOrganizations();
      loadAvailableFeatureFlags();
    }
  }, [user]);

  const loadAvailableFeatureFlags = async () => {
    try {
      const response = await apiClient.get('/admin/feature-flags');
      if (response.ok) {
        const flags = await response.json();
        setAvailableFeatureFlags(flags);
      }
    } catch (error) {
      console.error('Failed to load available feature flags:', error);
    }
  };

  const loadOrganizations = async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({
        limit: '1000',
        search: searchTerm,
        sort_by: sortField,
        sort_order: sortOrder,
      });

      const response = await apiClient.get(`/admin/organizations?${params.toString()}`);

      if (!response.ok) {
        throw new Error(`Failed to load organizations: ${response.status}`);
      }

      const data = await response.json();
      setOrganizations(data);
    } catch (error) {
      console.error('Failed to load organizations:', error);
      toast.error('Failed to load organizations');
      setOrganizations([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Filtering and sorting logic
  const filteredOrganizations = useMemo(() => {
    return organizations.filter((org) => {
      const matchesMembership =
        membershipFilter === 'all' ||
        (membershipFilter === 'member' && org.is_member) ||
        (membershipFilter === 'non-member' && !org.is_member);

      return matchesMembership;
    });
  }, [organizations, membershipFilter]);

  const sortedOrganizations = useMemo(() => {
    if (sortField === 'is_member') {
      return [...filteredOrganizations].sort((a, b) => {
        const aVal = a.is_member ? 1 : 0;
        const bVal = b.is_member ? 1 : 0;
        return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
      });
    }
    return filteredOrganizations;
  }, [filteredOrganizations, sortField, sortOrder]);

  const stats = useMemo(() => {
    return {
      totalOrgs: organizations.length,
      enterpriseCount: organizations.filter((o) => o.billing_plan === 'enterprise').length,
      trialCount: organizations.filter((o) => o.billing_status === 'trialing').length,
      totalUsers: organizations.reduce((sum, o) => sum + o.user_count, 0),
      totalSourceConnections: organizations.reduce((sum, o) => sum + o.source_connection_count, 0),
      totalEntities: organizations.reduce((sum, o) => sum + o.entity_count, 0),
    };
  }, [organizations]);

  const handleJoinOrganization = async () => {
    if (!selectedOrg) return;

    setIsSubmitting(true);
    try {
      const response = await apiClient.post(
        `/admin/organizations/${selectedOrg.id}/add-self?role=${selectedRole}`
      );

      if (!response.ok) {
        throw new Error('Failed to join organization');
      }

      toast.success(`Successfully joined ${selectedOrg.name} as ${selectedRole}`);
      await loadOrganizations();
      setActionType(null);
      setSelectedOrg(null);
    } catch (error) {
      console.error('Failed to join organization:', error);
      toast.error('Failed to join organization');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpgradeToEnterprise = async () => {
    if (!selectedOrg) return;

    setIsSubmitting(true);
    try {
      const response = await apiClient.post(
        `/admin/organizations/${selectedOrg.id}/upgrade-to-enterprise`
      );

      if (!response.ok) {
        throw new Error('Failed to upgrade organization');
      }

      toast.success(`Successfully upgraded ${selectedOrg.name} to enterprise`);
      await loadOrganizations();
      setActionType(null);
      setSelectedOrg(null);
    } catch (error) {
      console.error('Failed to upgrade organization:', error);
      toast.error('Failed to upgrade organization');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateEnterprise = async () => {
    if (!newOrgName.trim() || !ownerEmail.trim()) {
      toast.error('Please fill in all required fields');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await apiClient.post('/admin/organizations/create-enterprise', {
        name: newOrgName,
        description: newOrgDescription,
        owner_email: ownerEmail,
      });

      if (!response.ok) {
        throw new Error('Failed to create organization');
      }

      toast.success(`Successfully created enterprise organization: ${newOrgName}`);
      await loadOrganizations();
      setActionType(null);
      setNewOrgName('');
      setNewOrgDescription('');
      setOwnerEmail('');
    } catch (error) {
      console.error('Failed to create organization:', error);
      toast.error('Failed to create organization');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleFeatureFlag = async (flag: string, isEnabled: boolean) => {
    if (!selectedOrg) return;

    try {
      const action = isEnabled ? 'disable' : 'enable';
      const response = await apiClient.post(
        `/admin/organizations/${selectedOrg.id}/feature-flags/${flag}/${action}`
      );

      if (!response.ok) {
        throw new Error(`Failed to ${action} feature flag`);
      }

      toast.success(`Feature flag ${flag} ${isEnabled ? 'disabled' : 'enabled'}`);
      
      // Update local state
      if (isEnabled) {
        setEnabledFeatureFlags(enabledFeatureFlags.filter((f) => f !== flag));
      } else {
        setEnabledFeatureFlags([...enabledFeatureFlags, flag]);
      }
    } catch (error) {
      console.error('Failed to toggle feature flag:', error);
      toast.error('Failed to toggle feature flag');
    }
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString('en-US');
  };

  const getBillingPlanBadge = (plan?: string) => {
    if (!plan) return <Badge variant="outline">None</Badge>;

    const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline', className?: string }> = {
      enterprise: { variant: 'default', className: 'bg-brand-lime/20 text-brand-lime border-brand-lime/30' },
      pro: { variant: 'default', className: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
      starter: { variant: 'secondary' },
      trial: { variant: 'outline' },
    };

    const config = variants[plan] || { variant: 'outline' };
    return <Badge variant={config.variant} className={config.className}>{plan}</Badge>;
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  return (
    <>
      <div className="flex items-center justify-end mb-6">
        <Button
          onClick={() => {
            setActionType('create');
            setNewOrgName('');
            setNewOrgDescription('');
            setOwnerEmail('');
          }}
          className="gap-2"
        >
          <Plus className="h-4 w-4" />
          Create Enterprise Org
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <Card className="border-l-4 border-l-brand-lime/50">
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-2">
              <Building2 className="h-3.5 w-3.5" />
              Organizations
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">{formatNumber(stats.totalOrgs)}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {stats.enterpriseCount} enterprise • {stats.trialCount} trial
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-2">
              <Users className="h-3.5 w-3.5" />
              Total Users
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">{formatNumber(stats.totalUsers)}</div>
            <p className="text-xs text-muted-foreground mt-1">Across all orgs</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-2">
              <Database className="h-3.5 w-3.5" />
              Connections
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">{formatNumber(stats.totalSourceConnections)}</div>
            <p className="text-xs text-muted-foreground mt-1">Source connections</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-2">
              <Activity className="h-3.5 w-3.5" />
              Entities
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">{formatNumber(stats.totalEntities)}</div>
            <p className="text-xs text-muted-foreground mt-1">Total indexed</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Admin User
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-sm font-medium truncate">{user?.email}</div>
            <Badge variant="outline" className="mt-1 text-xs">Admin</Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Results
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">{formatNumber(sortedOrganizations.length)}</div>
            <p className="text-xs text-muted-foreground mt-1">Filtered</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="md:col-span-2">
              <Label htmlFor="org-search">Search Organizations</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="org-search"
                  placeholder="Search by name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="membership-filter">Membership</Label>
              <Select value={membershipFilter} onValueChange={(value) => setMembershipFilter(value as MembershipFilter)}>
                <SelectTrigger id="membership-filter">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Organizations</SelectItem>
                  <SelectItem value="member">Member Of</SelectItem>
                  <SelectItem value="non-member">Not Member</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button onClick={loadOrganizations} disabled={isLoading} className="w-full">
                {isLoading ? 'Loading...' : 'Refresh'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Organizations Table */}
      <Card>
        <CardHeader>
          <CardTitle>Organizations ({sortedOrganizations.length})</CardTitle>
          <CardDescription>
            Manage organizations across the platform
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-12 text-muted-foreground">
              Loading organizations...
            </div>
          ) : sortedOrganizations.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              No organizations found
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="cursor-pointer" onClick={() => handleSort('name')}>
                      <div className="flex items-center gap-1">
                        Name
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </TableHead>
                    <TableHead className="cursor-pointer" onClick={() => handleSort('billing_plan')}>
                      <div className="flex items-center gap-1">
                        Plan
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </TableHead>
                    <TableHead className="text-right cursor-pointer" onClick={() => handleSort('user_count')}>
                      <div className="flex items-center gap-1 justify-end">
                        Users
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </TableHead>
                    <TableHead className="text-right cursor-pointer" onClick={() => handleSort('source_connection_count')}>
                      <div className="flex items-center gap-1 justify-end">
                        Connections
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </TableHead>
                    <TableHead className="text-right cursor-pointer" onClick={() => handleSort('entity_count')}>
                      <div className="flex items-center gap-1 justify-end">
                        Entities
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </TableHead>
                    <TableHead className="cursor-pointer" onClick={() => handleSort('created_at')}>
                      <div className="flex items-center gap-1">
                        Created
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedOrganizations.map((org) => (
                    <TableRow key={org.id}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{org.name}</span>
                          {org.is_member && (
                            <Badge variant="outline" className="w-fit mt-1 text-xs bg-brand-lime/10 text-brand-lime border-brand-lime/30">
                              {org.member_role}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{getBillingPlanBadge(org.billing_plan)}</TableCell>
                      <TableCell className="text-right font-mono text-sm">{formatNumber(org.user_count)}</TableCell>
                      <TableCell className="text-right font-mono text-sm">{formatNumber(org.source_connection_count)}</TableCell>
                      <TableCell className="text-right font-mono text-sm">{formatNumber(org.entity_count)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(org.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {!org.is_member && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setSelectedOrg(org);
                                setActionType('join');
                              }}
                              className="h-7 px-2"
                            >
                              <UserPlus className="h-3.5 w-3.5 mr-1" />
                              Join
                            </Button>
                          )}
                          {org.billing_plan !== 'enterprise' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setSelectedOrg(org);
                                setActionType('upgrade');
                              }}
                              className="h-7 px-2"
                            >
                              <ArrowUpCircle className="h-3.5 w-3.5 mr-1" />
                              Upgrade
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setSelectedOrg(org);
                              setEnabledFeatureFlags(org.enabled_features || []);
                              setActionType('feature-flags');
                            }}
                            className="h-7 px-2"
                          >
                            <Flag className="h-3.5 w-3.5 mr-1" />
                            Features
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialogs */}
      <Dialog open={actionType === 'join'} onOpenChange={(open) => !open && setActionType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Join Organization</DialogTitle>
            <DialogDescription>
              Add yourself to {selectedOrg?.name} with a specific role
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="role">Role</Label>
              <Select value={selectedRole} onValueChange={(value) => setSelectedRole(value as any)}>
                <SelectTrigger id="role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="owner">Owner</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="member">Member</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setActionType(null)}>
              Cancel
            </Button>
            <Button onClick={handleJoinOrganization} disabled={isSubmitting}>
              {isSubmitting ? 'Joining...' : 'Join Organization'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={actionType === 'upgrade'} onOpenChange={(open) => !open && setActionType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upgrade to Enterprise</DialogTitle>
            <DialogDescription>
              Upgrade {selectedOrg?.name} to the enterprise plan
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              This will create a $0 enterprise subscription for this organization.
            </p>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setActionType(null)}>
              Cancel
            </Button>
            <Button onClick={handleUpgradeToEnterprise} disabled={isSubmitting}>
              {isSubmitting ? 'Upgrading...' : 'Upgrade to Enterprise'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={actionType === 'create'} onOpenChange={(open) => !open && setActionType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Enterprise Organization</DialogTitle>
            <DialogDescription>
              Create a new organization on the enterprise plan
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="org-name">Organization Name *</Label>
              <Input
                id="org-name"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="Acme Corp"
              />
            </div>
            <div>
              <Label htmlFor="org-description">Description</Label>
              <Input
                id="org-description"
                value={newOrgDescription}
                onChange={(e) => setNewOrgDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
            <div>
              <Label htmlFor="owner-email">Owner Email *</Label>
              <Input
                id="owner-email"
                type="email"
                value={ownerEmail}
                onChange={(e) => setOwnerEmail(e.target.value)}
                placeholder="owner@example.com"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setActionType(null)}>
              Cancel
            </Button>
            <Button onClick={handleCreateEnterprise} disabled={isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Create Organization'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={actionType === 'feature-flags'} onOpenChange={(open) => !open && setActionType(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Feature Flags</DialogTitle>
            <DialogDescription>
              Manage feature flags for {selectedOrg?.name}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[400px] overflow-y-auto py-4">
            {availableFeatureFlags.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No feature flags available
              </p>
            ) : (
              <div className="space-y-2">
                {availableFeatureFlags.map((flag) => {
                  const isEnabled = enabledFeatureFlags.includes(flag.value);
                  return (
                    <div
                      key={flag.value}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <Flag className={`h-4 w-4 ${isEnabled ? 'text-brand-lime' : 'text-muted-foreground'}`} />
                        <div>
                          <div className="font-medium text-sm">{flag.name.replace(/_/g, ' ')}</div>
                          <div className="text-xs text-muted-foreground">{flag.value}</div>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant={isEnabled ? 'default' : 'outline'}
                        onClick={() => handleToggleFeatureFlag(flag.value, isEnabled)}
                        className="h-7 px-3"
                      >
                        {isEnabled ? 'Enabled' : 'Disabled'}
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button onClick={() => setActionType(null)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

