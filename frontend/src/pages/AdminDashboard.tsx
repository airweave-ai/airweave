import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
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
import { Shield, Plus, Crown, Building2, ArrowUpCircle, UserPlus, Search, ArrowUpDown, Users, Database, Activity, Flag } from 'lucide-react';
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

export function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [organizations, setOrganizations] = useState<OrganizationMetrics[]>([]);
  const [isLoading, setIsLoading] = useState(true);
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
    // Redirect if not admin
    if (user && !user.is_admin) {
      toast.error('Admin access required');
      navigate('/');
      return;
    }

    if (user?.is_admin) {
      loadOrganizations();
      loadAvailableFeatureFlags();
    }
  }, [user, navigate]);

  const loadAvailableFeatureFlags = async () => {
    try {
      const response = await apiClient.get('/admin/feature-flags');
      if (response.ok) {
        const flags = await response.json();
        setAvailableFeatureFlags(flags);
      } else {
        throw new Error('Failed to load available feature flags');
      }
    } catch (error) {
      console.error('Failed to load available feature flags:', error);
      // Don't show error toast, this is not critical
    }
  };

  const loadOrganizations = async () => {
    try {
      setIsLoading(true);
      // Fetch all organizations with comprehensive metrics
      const params = new URLSearchParams({
        limit: '10000',
        sort_by: sortField,
        sort_order: sortOrder,
      });

      if (searchTerm) {
        params.set('search', searchTerm);
      }

      const response = await apiClient.get(`/admin/organizations?${params.toString()}`);
      if (response.ok) {
        const data = await response.json();
        setOrganizations(data);
      } else {
        throw new Error('Failed to load organizations');
      }
    } catch (error) {
      console.error('Failed to load organizations:', error);
      toast.error('Failed to load organizations');
    } finally {
      setIsLoading(false);
    }
  };

  // Reload when search/sort changes (debounced search)
  useEffect(() => {
    if (!user?.is_admin) return;

    const timer = setTimeout(() => {
      loadOrganizations();
    }, searchTerm ? 300 : 0);

    return () => clearTimeout(timer);
  }, [searchTerm, sortField, sortOrder]);

  // Filter and sort organizations (membership-based operations done client-side)
  const filteredOrganizations = useMemo(() => {
    let filtered = organizations;

    // Apply membership filter
    if (membershipFilter === 'member') {
      filtered = filtered.filter(org => org.is_member);
    } else if (membershipFilter === 'non-member') {
      filtered = filtered.filter(org => !org.is_member);
    }

    // Apply client-side sorting if sorting by membership (not handled by backend)
    if (sortField === 'is_member') {
      filtered = [...filtered].sort((a, b) => {
        const aValue = a.is_member ? 1 : 0;
        const bValue = b.is_member ? 1 : 0;
        return sortOrder === 'asc' ? aValue - bValue : bValue - aValue;
      });
    }

    return filtered;
  }, [organizations, membershipFilter, sortField, sortOrder]);

  // Calculate aggregate stats
  const stats = useMemo(() => {
    return {
      totalOrgs: organizations.length,
      totalUsers: organizations.reduce((sum, org) => sum + org.user_count, 0),
      totalSourceConnections: organizations.reduce((sum, org) => sum + org.source_connection_count, 0),
      totalEntities: organizations.reduce((sum, org) => sum + org.entity_count, 0),
      enterpriseCount: organizations.filter(org => org.billing_plan === 'enterprise').length,
      trialCount: organizations.filter(org => org.billing_plan === 'trial').length,
      memberCount: organizations.filter(org => org.is_member).length,
    };
  }, [organizations]);

  const handleJoinOrg = async () => {
    if (!selectedOrg) return;

    try {
      setIsSubmitting(true);
      const response = await apiClient.post(
        `/admin/organizations/${selectedOrg.id}/add-self?role=${selectedRole}`
      );

      if (response.ok) {
        toast.success(`Successfully joined ${selectedOrg.name} as ${selectedRole}`);
        setActionType(null);
        setSelectedOrg(null);
        loadOrganizations();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to join organization');
      }
    } catch (error: any) {
      console.error('Failed to join organization:', error);
      toast.error(error.message || 'Failed to join organization');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpgradeToEnterprise = async () => {
    if (!selectedOrg) return;

    try {
      setIsSubmitting(true);
      const response = await apiClient.post(
        `/admin/organizations/${selectedOrg.id}/upgrade-to-enterprise`
      );

      if (response.ok) {
        toast.success(`Successfully upgraded ${selectedOrg.name} to Enterprise`);
        setActionType(null);
        setSelectedOrg(null);
        loadOrganizations();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to upgrade organization');
      }
    } catch (error: any) {
      console.error('Failed to upgrade organization:', error);
      toast.error(error.message || 'Failed to upgrade organization');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateEnterpriseOrg = async () => {
    if (!newOrgName || !ownerEmail) {
      toast.error('Organization name and owner email are required');
      return;
    }

    try {
      setIsSubmitting(true);
      const response = await apiClient.post('/admin/organizations/create-enterprise', {
        name: newOrgName,
        description: newOrgDescription,
        owner_email: ownerEmail,
      });

      if (response.ok) {
        toast.success(`Successfully created enterprise organization ${newOrgName}`);
        setActionType(null);
        setNewOrgName('');
        setNewOrgDescription('');
        setOwnerEmail('');
        loadOrganizations();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create organization');
      }
    } catch (error: any) {
      console.error('Failed to create organization:', error);
      toast.error(error.message || 'Failed to create organization');
    } finally {
      setIsSubmitting(false);
    }
  };

  const loadFeatureFlags = (org: OrganizationMetrics) => {
    // Feature flags are already loaded from the organization data
    setEnabledFeatureFlags(org.enabled_features || []);
  };

  const handleToggleFeatureFlag = async (flag: string, currentlyEnabled: boolean) => {
    if (!selectedOrg) return;

    try {
      const action = currentlyEnabled ? 'disable' : 'enable';
      const response = await apiClient.post(
        `/admin/organizations/${selectedOrg.id}/feature-flags/${flag}/${action}`
      );

      if (response.ok) {
        toast.success(`Feature ${flag} ${currentlyEnabled ? 'disabled' : 'enabled'}`);
        // Update local state
        if (currentlyEnabled) {
          setEnabledFeatureFlags(enabledFeatureFlags.filter(f => f !== flag));
        } else {
          setEnabledFeatureFlags([...enabledFeatureFlags, flag]);
        }
        // Reload organizations to get fresh data
        loadOrganizations();
      } else {
        const error = await response.json();
        throw new Error(error.detail || `Failed to ${action} feature flag`);
      }
    } catch (error: any) {
      console.error('Failed to toggle feature flag:', error);
      toast.error(error.message || 'Failed to update feature flag');
    }
  };

  const openFeatureFlagsDialog = (org: OrganizationMetrics) => {
    setSelectedOrg(org);
    setActionType('feature-flags');
    loadFeatureFlags(org);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
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
      // Toggle order if same field
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc'); // Default to desc for new field
    }
  };

  if (!user?.is_admin) {
    return null;
  }

  return (
    <div className="container mx-auto py-6 px-4 max-w-[1800px]">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-3xl font-bold">Admin Dashboard</h1>
            <p className="text-muted-foreground">Manage organizations across the platform</p>
          </div>
        </div>

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
            <div className="text-sm font-medium truncate">{user.email}</div>
            <Badge variant="outline" className="mt-1 text-xs">Admin</Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Platform
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-sm font-medium">Airweave</div>
            <p className="text-xs text-muted-foreground mt-1">Admin Panel</p>
          </CardContent>
        </Card>
      </div>

      {/* Organizations Table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>All Organizations</CardTitle>
              <CardDescription>
                View and manage all organizations on the platform
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Select value={membershipFilter} onValueChange={(value: MembershipFilter) => setMembershipFilter(value)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by membership" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Organizations</SelectItem>
                  <SelectItem value="member">Member ({stats.memberCount})</SelectItem>
                  <SelectItem value="non-member">Non-member ({stats.totalOrgs - stats.memberCount})</SelectItem>
                </SelectContent>
              </Select>
              <div className="relative w-72">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search organizations..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="text-center py-12 text-muted-foreground">Loading organizations...</div>
          ) : filteredOrganizations.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              {searchTerm ? 'No organizations match your search' :
                membershipFilter !== 'all' ? `No ${membershipFilter === 'member' ? 'member' : 'non-member'} organizations found` :
                  'No organizations found'}
            </div>
          ) : (
            <div className="border-t">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-[220px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -ml-3 data-[state=open]:bg-accent"
                        onClick={() => handleSort('name')}
                      >
                        Organization
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[120px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -ml-3"
                        onClick={() => handleSort('billing_plan')}
                      >
                        Plan
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[110px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -ml-3"
                        onClick={() => handleSort('is_member')}
                      >
                        Membership
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[100px] text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -mr-3"
                        onClick={() => handleSort('user_count')}
                      >
                        Users
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[120px] text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -mr-3"
                        onClick={() => handleSort('source_connection_count')}
                      >
                        Connections
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[110px] text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -mr-3"
                        onClick={() => handleSort('entity_count')}
                      >
                        Entities
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[100px] text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -mr-3"
                        onClick={() => handleSort('query_count')}
                      >
                        Queries
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[130px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -ml-3"
                        onClick={() => handleSort('last_active_at')}
                      >
                        Last Active
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[130px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 -ml-3"
                        onClick={() => handleSort('created_at')}
                      >
                        Created
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right w-[200px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredOrganizations.map((org) => (
                    <TableRow key={org.id} className="hover:bg-muted/30">
                      <TableCell className="py-2">
                        <div className="flex items-center gap-2">
                          <Building2 className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="font-medium truncate">{org.name}</div>
                            {org.description && (
                              <div className="text-xs text-muted-foreground truncate">
                                {org.description}
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="py-2">
                        {getBillingPlanBadge(org.billing_plan)}
                      </TableCell>
                      <TableCell className="py-2">
                        {org.is_member ? (
                          <Badge variant="outline" className="text-xs px-2 py-0.5 h-5 gap-1">
                            {org.member_role === 'owner' && <Crown className="h-3 w-3 text-brand-lime/90" />}
                            {org.member_role === 'admin' && <Shield className="h-3 w-3 text-brand-lime/90" />}
                            {org.member_role}
                          </Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right py-2 font-mono text-sm">
                        {formatNumber(org.user_count)}
                      </TableCell>
                      <TableCell className="text-right py-2 font-mono text-sm">
                        {formatNumber(org.source_connection_count)}
                      </TableCell>
                      <TableCell className="text-right py-2 font-mono text-sm">
                        {formatNumber(org.entity_count)}
                      </TableCell>
                      <TableCell className="text-right py-2 font-mono text-sm">
                        {formatNumber(org.query_count)}
                      </TableCell>
                      <TableCell className="py-2 text-xs text-muted-foreground">
                        {org.last_active_at ? formatDate(org.last_active_at) : '—'}
                      </TableCell>
                      <TableCell className="py-2 text-xs text-muted-foreground">
                        {formatDate(org.created_at)}
                      </TableCell>
                      <TableCell className="text-right py-2">
                        <div className="flex justify-end gap-1.5">
                          {org.is_member ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled
                              className="h-7 gap-1.5 text-xs text-muted-foreground"
                            >
                              <UserPlus className="h-3 w-3" />
                              Member
                            </Button>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setSelectedOrg(org);
                                setActionType('join');
                                setSelectedRole('owner');
                              }}
                              className="h-7 gap-1.5 text-xs"
                            >
                              <UserPlus className="h-3 w-3" />
                              Join
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openFeatureFlagsDialog(org)}
                            className="h-7 gap-1.5 text-xs"
                          >
                            <Flag className="h-3 w-3" />
                            Features
                          </Button>
                          {/* Only show Upgrade for non-enterprise plans */}
                          {org.billing_plan !== 'enterprise' && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setSelectedOrg(org);
                                setActionType('upgrade');
                              }}
                              className="h-7 gap-1.5 text-xs"
                            >
                              <ArrowUpCircle className="h-3 w-3" />
                              Upgrade
                            </Button>
                          )}
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

      {/* Join Organization Dialog */}
      <Dialog open={actionType === 'join'} onOpenChange={(open) => !open && setActionType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Join Organization</DialogTitle>
            <DialogDescription>
              Add yourself to {selectedOrg?.name} with a specific role
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Select value={selectedRole} onValueChange={(value: any) => setSelectedRole(value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="owner">
                    <div className="flex items-center gap-2">
                      <Crown className="h-4 w-4 text-brand-lime/90" />
                      Owner
                    </div>
                  </SelectItem>
                  <SelectItem value="admin">
                    <div className="flex items-center gap-2">
                      <Shield className="h-4 w-4 text-brand-lime/90" />
                      Admin
                    </div>
                  </SelectItem>
                  <SelectItem value="member">Member</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setActionType(null)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleJoinOrg} disabled={isSubmitting}>
              {isSubmitting ? 'Joining...' : 'Join Organization'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upgrade to Enterprise Dialog */}
      <Dialog open={actionType === 'upgrade'} onOpenChange={(open) => !open && setActionType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upgrade to Enterprise</DialogTitle>
            <DialogDescription>
              Upgrade {selectedOrg?.name} to an Enterprise plan. This will bypass Stripe and set the organization directly to enterprise.
            </DialogDescription>
          </DialogHeader>

          <div className="bg-muted/50 p-4 rounded-lg my-4">
            <p className="text-sm text-muted-foreground">
              This action will:
            </p>
            <ul className="list-disc list-inside text-sm text-muted-foreground mt-2 space-y-1">
              <li>Set the billing plan to "enterprise"</li>
              <li>Remove subscription limits</li>
              <li>Create or update billing record</li>
            </ul>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setActionType(null)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleUpgradeToEnterprise} disabled={isSubmitting}>
              {isSubmitting ? 'Upgrading...' : 'Confirm Upgrade'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Enterprise Organization Dialog */}
      <Dialog open={actionType === 'create'} onOpenChange={(open) => !open && setActionType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Enterprise Organization</DialogTitle>
            <DialogDescription>
              Create a new organization directly on the Enterprise plan
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="orgName">Organization Name *</Label>
              <Input
                id="orgName"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="Acme Corporation"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="orgDescription">Description</Label>
              <Input
                id="orgDescription"
                value={newOrgDescription}
                onChange={(e) => setNewOrgDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ownerEmail">Owner Email *</Label>
              <Input
                id="ownerEmail"
                type="email"
                value={ownerEmail}
                onChange={(e) => setOwnerEmail(e.target.value)}
                placeholder="owner@example.com"
              />
              <p className="text-xs text-muted-foreground">
                The user must already exist in the system
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setActionType(null)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleCreateEnterpriseOrg} disabled={isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Create Organization'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Feature Flags Dialog */}
      <Dialog open={actionType === 'feature-flags'} onOpenChange={(open) => !open && setActionType(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Feature Flags</DialogTitle>
            <DialogDescription>
              Manage feature flags for {selectedOrg?.name}
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {availableFeatureFlags.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                Loading available features...
              </div>
            ) : (
              <div className="space-y-3">
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
    </div>
  );
}
