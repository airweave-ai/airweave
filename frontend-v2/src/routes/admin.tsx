import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  Activity,
  ArrowUpCircle,
  ArrowUpDown,
  Building2,
  Crown,
  Database,
  Flag,
  Loader2,
  Plus,
  Search,
  Shield,
  UserPlus,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  adminCreateEnterpriseOrg,
  adminDisableFeatureFlag,
  adminEnableFeatureFlag,
  adminJoinOrganization,
  adminUpgradeToEnterprise,
  fetchAdminOrganizations,
  fetchAvailableFeatureFlags,
  fetchCurrentUser,
} from "@/lib/api";
import type { OrganizationMetrics } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { queryKeys } from "@/lib/query-keys";

export const Route = createFileRoute("/admin")({
  component: AdminDashboardPage,
});

type SortField =
  | "name"
  | "created_at"
  | "billing_plan"
  | "user_count"
  | "source_connection_count"
  | "entity_count"
  | "query_count"
  | "last_active_at"
  | "is_member";
type SortOrder = "asc" | "desc";
type MembershipFilter = "all" | "member" | "non-member";
type ActionType = "join" | "upgrade" | "create" | "feature-flags" | null;

function AdminDashboardPage() {
  const { getAccessTokenSilently } = useAuth0();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedOrg, setSelectedOrg] = useState<OrganizationMetrics | null>(
    null
  );
  const [actionType, setActionType] = useState<ActionType>(null);
  const [enabledFeatureFlags, setEnabledFeatureFlags] = useState<string[]>([]);

  // Search and sort state
  const [searchTerm, setSearchTerm] = useState("");
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [membershipFilter, setMembershipFilter] =
    useState<MembershipFilter>("all");

  // Create enterprise org form
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgDescription, setNewOrgDescription] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");

  // Join org form
  const [selectedRole, setSelectedRole] = useState<"owner" | "admin" | "member">(
    "owner"
  );

  // Check if user is admin
  const { data: currentUser, isLoading: userLoading } = useQuery({
    queryKey: queryKeys.user.current,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchCurrentUser(token);
    },
  });

  // Redirect non-admins
  useEffect(() => {
    if (!userLoading && currentUser && !currentUser.is_admin) {
      toast.error("Admin access required");
      navigate({ to: "/" });
    }
  }, [currentUser, userLoading, navigate]);

  // Fetch organizations
  const {
    data: organizations = [],
    isLoading: orgsLoading,
    refetch: refetchOrganizations,
  } = useQuery({
    queryKey: queryKeys.admin.organizations,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchAdminOrganizations(token, {
        limit: 10000,
        sort_by: sortField,
        sort_order: sortOrder,
        search: searchTerm || undefined,
      });
    },
    enabled: !!currentUser?.is_admin,
  });

  // Fetch available feature flags
  const { data: availableFeatureFlags = [] } = useQuery({
    queryKey: queryKeys.admin.featureFlags,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchAvailableFeatureFlags(token);
    },
    enabled: !!currentUser?.is_admin,
  });

  // Debounced search refetch
  useEffect(() => {
    if (!currentUser?.is_admin) return;

    const timer = setTimeout(
      () => {
        refetchOrganizations();
      },
      searchTerm ? 300 : 0
    );

    return () => clearTimeout(timer);
  }, [searchTerm, sortField, sortOrder, currentUser?.is_admin, refetchOrganizations]);

  // Mutations
  const joinMutation = useMutation({
    mutationFn: async ({
      orgId,
      role,
    }: {
      orgId: string;
      role: "owner" | "admin" | "member";
    }) => {
      const token = await getAccessTokenSilently();
      return adminJoinOrganization(token, orgId, role);
    },
    onSuccess: () => {
      toast.success(`Successfully joined ${selectedOrg?.name} as ${selectedRole}`);
      setActionType(null);
      setSelectedOrg(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.organizations });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to join organization"
      );
    },
  });

  const upgradeMutation = useMutation({
    mutationFn: async (orgId: string) => {
      const token = await getAccessTokenSilently();
      return adminUpgradeToEnterprise(token, orgId);
    },
    onSuccess: () => {
      toast.success(`Successfully upgraded ${selectedOrg?.name} to Enterprise`);
      setActionType(null);
      setSelectedOrg(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.organizations });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to upgrade organization"
      );
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: {
      name: string;
      description?: string;
      owner_email: string;
    }) => {
      const token = await getAccessTokenSilently();
      return adminCreateEnterpriseOrg(token, data);
    },
    onSuccess: () => {
      toast.success(`Successfully created enterprise organization ${newOrgName}`);
      setActionType(null);
      setNewOrgName("");
      setNewOrgDescription("");
      setOwnerEmail("");
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.organizations });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to create organization"
      );
    },
  });

  const featureFlagMutation = useMutation({
    mutationFn: async ({
      orgId,
      flag,
      enable,
    }: {
      orgId: string;
      flag: string;
      enable: boolean;
    }) => {
      const token = await getAccessTokenSilently();
      if (enable) {
        return adminEnableFeatureFlag(token, orgId, flag);
      } else {
        return adminDisableFeatureFlag(token, orgId, flag);
      }
    },
    onSuccess: (_, variables) => {
      toast.success(
        `Feature ${variables.flag} ${variables.enable ? "enabled" : "disabled"}`
      );
      // Update local state
      if (variables.enable) {
        setEnabledFeatureFlags((prev) => [...prev, variables.flag]);
      } else {
        setEnabledFeatureFlags((prev) =>
          prev.filter((f) => f !== variables.flag)
        );
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.organizations });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to update feature flag"
      );
    },
  });

  // Filter and sort organizations
  const filteredOrganizations = useMemo(() => {
    let filtered = organizations;

    // Apply membership filter
    if (membershipFilter === "member") {
      filtered = filtered.filter((org) => org.is_member);
    } else if (membershipFilter === "non-member") {
      filtered = filtered.filter((org) => !org.is_member);
    }

    // Apply client-side sorting if sorting by membership
    if (sortField === "is_member") {
      filtered = [...filtered].sort((a, b) => {
        const aValue = a.is_member ? 1 : 0;
        const bValue = b.is_member ? 1 : 0;
        return sortOrder === "asc" ? aValue - bValue : bValue - aValue;
      });
    }

    return filtered;
  }, [organizations, membershipFilter, sortField, sortOrder]);

  // Calculate aggregate stats
  const stats = useMemo(() => {
    return {
      totalOrgs: organizations.length,
      totalUsers: organizations.reduce((sum, org) => sum + org.user_count, 0),
      totalSourceConnections: organizations.reduce(
        (sum, org) => sum + org.source_connection_count,
        0
      ),
      totalEntities: organizations.reduce(
        (sum, org) => sum + org.entity_count,
        0
      ),
      enterpriseCount: organizations.filter(
        (org) => org.billing_plan === "enterprise"
      ).length,
      trialCount: organizations.filter((org) => org.billing_plan === "trial")
        .length,
      memberCount: organizations.filter((org) => org.is_member).length,
    };
  }, [organizations]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  const openFeatureFlagsDialog = (org: OrganizationMetrics) => {
    setSelectedOrg(org);
    setActionType("feature-flags");
    setEnabledFeatureFlags(org.enabled_features || []);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString("en-US");
  };

  const getBillingPlanBadge = (plan?: string) => {
    if (!plan) return <Badge variant="outline">None</Badge>;

    const variants: Record<
      string,
      { variant: "default" | "secondary" | "outline"; className?: string }
    > = {
      enterprise: {
        variant: "default",
        className: "bg-amber-500/20 text-amber-400 border-amber-500/30",
      },
      pro: {
        variant: "default",
        className: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      },
      starter: { variant: "secondary" },
      trial: { variant: "outline" },
    };

    const config = variants[plan] || { variant: "outline" as const };
    return (
      <Badge variant={config.variant} className={config.className}>
        {plan}
      </Badge>
    );
  };

  // Loading state
  if (userLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="size-8 animate-spin" />
      </div>
    );
  }

  // Non-admin users are redirected, show nothing
  if (!currentUser?.is_admin) {
    return null;
  }

  return (
    <div className="container mx-auto max-w-[1800px] px-4 py-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="text-primary size-8" />
          <div>
            <h1 className="text-3xl font-bold">Admin Dashboard</h1>
            <p className="text-muted-foreground">
              Manage organizations across the platform
            </p>
          </div>
        </div>

        <Button
          onClick={() => {
            setActionType("create");
            setNewOrgName("");
            setNewOrgDescription("");
            setOwnerEmail("");
          }}
          className="gap-2"
        >
          <Plus className="size-4" />
          Create Enterprise Org
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Card className="border-l-4 border-l-amber-500/50">
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-muted-foreground flex items-center gap-2 text-xs font-medium">
              <Building2 className="size-3.5" />
              Organizations
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">
              {formatNumber(stats.totalOrgs)}
            </div>
            <p className="text-muted-foreground mt-1 text-xs">
              {stats.enterpriseCount} enterprise - {stats.trialCount} trial
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-muted-foreground flex items-center gap-2 text-xs font-medium">
              <Users className="size-3.5" />
              Total Users
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">
              {formatNumber(stats.totalUsers)}
            </div>
            <p className="text-muted-foreground mt-1 text-xs">Across all orgs</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-muted-foreground flex items-center gap-2 text-xs font-medium">
              <Database className="size-3.5" />
              Connections
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">
              {formatNumber(stats.totalSourceConnections)}
            </div>
            <p className="text-muted-foreground mt-1 text-xs">
              Source connections
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-muted-foreground flex items-center gap-2 text-xs font-medium">
              <Activity className="size-3.5" />
              Entities
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">
              {formatNumber(stats.totalEntities)}
            </div>
            <p className="text-muted-foreground mt-1 text-xs">Total indexed</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-muted-foreground text-xs font-medium">
              Admin User
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="truncate text-sm font-medium">
              {currentUser.email}
            </div>
            <Badge variant="outline" className="mt-1 text-xs">
              Admin
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-muted-foreground text-xs font-medium">
              Platform
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-sm font-medium">Airweave</div>
            <p className="text-muted-foreground mt-1 text-xs">Admin Panel</p>
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
              <Select
                value={membershipFilter}
                onValueChange={(value: MembershipFilter) =>
                  setMembershipFilter(value)
                }
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by membership" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Organizations</SelectItem>
                  <SelectItem value="member">
                    Member ({stats.memberCount})
                  </SelectItem>
                  <SelectItem value="non-member">
                    Non-member ({stats.totalOrgs - stats.memberCount})
                  </SelectItem>
                </SelectContent>
              </Select>
              <div className="relative w-72">
                <Search className="text-muted-foreground absolute left-2.5 top-2.5 size-4" />
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
          {orgsLoading ? (
            <div className="text-muted-foreground py-12 text-center">
              Loading organizations...
            </div>
          ) : filteredOrganizations.length === 0 ? (
            <div className="text-muted-foreground py-12 text-center">
              {searchTerm
                ? "No organizations match your search"
                : membershipFilter !== "all"
                  ? `No ${membershipFilter === "member" ? "member" : "non-member"} organizations found`
                  : "No organizations found"}
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
                        className="-ml-3 h-8 data-[state=open]:bg-accent"
                        onClick={() => handleSort("name")}
                      >
                        Organization
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[120px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-8"
                        onClick={() => handleSort("billing_plan")}
                      >
                        Plan
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[110px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-8"
                        onClick={() => handleSort("is_member")}
                      >
                        Membership
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[100px] text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-mr-3 h-8"
                        onClick={() => handleSort("user_count")}
                      >
                        Users
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[120px] text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-mr-3 h-8"
                        onClick={() => handleSort("source_connection_count")}
                      >
                        Connections
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[110px] text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-mr-3 h-8"
                        onClick={() => handleSort("entity_count")}
                      >
                        Entities
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[100px] text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-mr-3 h-8"
                        onClick={() => handleSort("query_count")}
                      >
                        Queries
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[130px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-8"
                        onClick={() => handleSort("last_active_at")}
                      >
                        Last Active
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[130px]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-8"
                        onClick={() => handleSort("created_at")}
                      >
                        Created
                        <ArrowUpDown className="ml-2 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[200px] text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredOrganizations.map((org) => (
                    <TableRow key={org.id} className="hover:bg-muted/30">
                      <TableCell className="py-2">
                        <div className="flex items-center gap-2">
                          <Building2 className="text-muted-foreground size-3.5 flex-shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="truncate font-medium">
                              {org.name}
                            </div>
                            {org.description && (
                              <div className="text-muted-foreground truncate text-xs">
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
                          <Badge
                            variant="outline"
                            className="h-5 gap-1 px-2 py-0.5 text-xs"
                          >
                            {org.member_role === "owner" && (
                              <Crown className="text-amber-400/90 size-3" />
                            )}
                            {org.member_role === "admin" && (
                              <Shield className="text-amber-400/90 size-3" />
                            )}
                            {org.member_role}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground text-xs">
                            -
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono text-sm">
                        {formatNumber(org.user_count)}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono text-sm">
                        {formatNumber(org.source_connection_count)}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono text-sm">
                        {formatNumber(org.entity_count)}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono text-sm">
                        {formatNumber(org.query_count)}
                      </TableCell>
                      <TableCell className="text-muted-foreground py-2 text-xs">
                        {org.last_active_at
                          ? formatDate(org.last_active_at)
                          : "-"}
                      </TableCell>
                      <TableCell className="text-muted-foreground py-2 text-xs">
                        {formatDate(org.created_at)}
                      </TableCell>
                      <TableCell className="py-2 text-right">
                        <div className="flex justify-end gap-1.5">
                          {org.is_member ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled
                              className="text-muted-foreground h-7 gap-1.5 text-xs"
                            >
                              <UserPlus className="size-3" />
                              Member
                            </Button>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setSelectedOrg(org);
                                setActionType("join");
                                setSelectedRole("owner");
                              }}
                              className="h-7 gap-1.5 text-xs"
                            >
                              <UserPlus className="size-3" />
                              Join
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openFeatureFlagsDialog(org)}
                            className="h-7 gap-1.5 text-xs"
                          >
                            <Flag className="size-3" />
                            Features
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedOrg(org);
                              setActionType("upgrade");
                            }}
                            className="h-7 gap-1.5 text-xs"
                          >
                            <ArrowUpCircle className="size-3" />
                            Upgrade
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

      {/* Join Organization Dialog */}
      <Dialog
        open={actionType === "join"}
        onOpenChange={(open) => !open && setActionType(null)}
      >
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
              <Select
                value={selectedRole}
                onValueChange={(value: "owner" | "admin" | "member") =>
                  setSelectedRole(value)
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="owner">
                    <div className="flex items-center gap-2">
                      <Crown className="text-amber-400/90 size-4" />
                      Owner
                    </div>
                  </SelectItem>
                  <SelectItem value="admin">
                    <div className="flex items-center gap-2">
                      <Shield className="text-amber-400/90 size-4" />
                      Admin
                    </div>
                  </SelectItem>
                  <SelectItem value="member">Member</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setActionType(null)}
              disabled={joinMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={() =>
                selectedOrg &&
                joinMutation.mutate({
                  orgId: selectedOrg.id,
                  role: selectedRole,
                })
              }
              disabled={joinMutation.isPending}
            >
              {joinMutation.isPending ? "Joining..." : "Join Organization"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upgrade to Enterprise Dialog */}
      <Dialog
        open={actionType === "upgrade"}
        onOpenChange={(open) => !open && setActionType(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upgrade to Enterprise</DialogTitle>
            <DialogDescription>
              Upgrade {selectedOrg?.name} to an Enterprise plan. This will
              bypass Stripe and set the organization directly to enterprise.
            </DialogDescription>
          </DialogHeader>

          <div className="bg-muted/50 my-4 rounded-lg p-4">
            <p className="text-muted-foreground text-sm">
              This action will:
            </p>
            <ul className="text-muted-foreground mt-2 list-inside list-disc space-y-1 text-sm">
              <li>Set the billing plan to "enterprise"</li>
              <li>Remove subscription limits</li>
              <li>Create or update billing record</li>
            </ul>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setActionType(null)}
              disabled={upgradeMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={() =>
                selectedOrg && upgradeMutation.mutate(selectedOrg.id)
              }
              disabled={upgradeMutation.isPending}
            >
              {upgradeMutation.isPending ? "Upgrading..." : "Confirm Upgrade"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Enterprise Organization Dialog */}
      <Dialog
        open={actionType === "create"}
        onOpenChange={(open) => !open && setActionType(null)}
      >
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
              <p className="text-muted-foreground text-xs">
                The user must already exist in the system
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setActionType(null)}
              disabled={createMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!newOrgName || !ownerEmail) {
                  toast.error("Organization name and owner email are required");
                  return;
                }
                createMutation.mutate({
                  name: newOrgName,
                  description: newOrgDescription || undefined,
                  owner_email: ownerEmail,
                });
              }}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? "Creating..." : "Create Organization"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Feature Flags Dialog */}
      <Dialog
        open={actionType === "feature-flags"}
        onOpenChange={(open) => !open && setActionType(null)}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Feature Flags</DialogTitle>
            <DialogDescription>
              Manage feature flags for {selectedOrg?.name}
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {availableFeatureFlags.length === 0 ? (
              <div className="text-muted-foreground py-8 text-center">
                Loading available features...
              </div>
            ) : (
              <div className="space-y-3">
                {availableFeatureFlags.map((flag) => {
                  const isEnabled = enabledFeatureFlags.includes(flag.value);
                  return (
                    <div
                      key={flag.value}
                      className="hover:bg-muted/30 flex items-center justify-between rounded-lg border p-3 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <Flag
                          className={`size-4 ${isEnabled ? "text-amber-400" : "text-muted-foreground"}`}
                        />
                        <div>
                          <div className="text-sm font-medium">
                            {flag.name.replace(/_/g, " ")}
                          </div>
                          <div className="text-muted-foreground text-xs">
                            {flag.value}
                          </div>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant={isEnabled ? "default" : "outline"}
                        onClick={() =>
                          selectedOrg &&
                          featureFlagMutation.mutate({
                            orgId: selectedOrg.id,
                            flag: flag.value,
                            enable: !isEnabled,
                          })
                        }
                        className="h-7 px-3"
                        disabled={featureFlagMutation.isPending}
                      >
                        {isEnabled ? "Enabled" : "Disabled"}
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button onClick={() => setActionType(null)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
