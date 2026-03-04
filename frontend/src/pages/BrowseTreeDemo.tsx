import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import {
  ChevronRight,
  ChevronDown,
  Globe,
  List,
  Folder,
  FileText,
  File,
  Loader2,
  ArrowLeft,
  ArrowRight,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  Play,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TreeNode {
  id: string;
  source_connection_id: string;
  parent_id: string | null;
  node_type: string;
  source_node_id: string;
  title: string;
  description: string | null;
  item_count: number | null;
  node_metadata: Record<string, any> | null;
  is_public: boolean;
  has_children: boolean;
}

interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  readable_collection_id: string;
  config_fields?: Record<string, any>;
}

interface SyncJob {
  id: string;
  status: string;
  entities_inserted: number;
  entities_updated: number;
}

interface SearchResult {
  id: string;
  entity_id: string;
  title: string;
  content: string;
  similarity_score: number;
  retrieval_score: number;
  combined_score: number;
  source_metadata?: Record<string, any>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NODE_ICONS: Record<string, React.ElementType> = {
  site: Globe,
  list: List,
  folder: Folder,
  file: FileText,
  item: File,
};

const STEPS = [
  { number: 1, label: "Browse Tree" },
  { number: 2, label: "Create User SC" },
  { number: 3, label: "Select & Sync" },
  { number: 4, label: "Search" },
];

// ---------------------------------------------------------------------------
// Step Indicator
// ---------------------------------------------------------------------------

function StepIndicator({ currentStep }: { currentStep: number }) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <div className="flex items-center justify-center gap-0 mb-8">
      {STEPS.map((step, i) => (
        <div key={step.number} className="flex items-center">
          <div className="flex flex-col items-center">
            <div
              className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium border transition-all",
                currentStep === step.number
                  ? "bg-blue-500 text-white border-blue-500"
                  : currentStep > step.number
                    ? "bg-green-500 text-white border-green-500"
                    : isDark
                      ? "bg-gray-800 text-gray-400 border-gray-700"
                      : "bg-gray-100 text-gray-500 border-gray-300"
              )}
            >
              {currentStep > step.number ? (
                <CheckCircle2 className="w-4 h-4" />
              ) : (
                step.number
              )}
            </div>
            <span
              className={cn(
                "text-xs mt-1 whitespace-nowrap",
                currentStep === step.number
                  ? "text-blue-500 font-medium"
                  : "text-muted-foreground"
              )}
            >
              {step.label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className={cn(
                "w-16 h-0.5 mx-2 mb-5",
                currentStep > step.number
                  ? "bg-green-500"
                  : isDark
                    ? "bg-gray-700"
                    : "bg-gray-300"
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tree Node Component
// ---------------------------------------------------------------------------

function TreeNodeRow({
  node,
  depth,
  isSelected,
  isExpanded,
  isLoading,
  onToggle,
  onSelect,
  onExpand,
}: {
  node: TreeNode;
  depth: number;
  isSelected: boolean;
  isExpanded: boolean;
  isLoading: boolean;
  onToggle: () => void;
  onSelect: () => void;
  onExpand: () => void;
}) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const Icon = NODE_ICONS[node.node_type] || File;

  return (
    <div
      className={cn(
        "flex items-center gap-2 py-1.5 px-2 rounded-md transition-colors",
        isDark ? "hover:bg-gray-800" : "hover:bg-gray-50"
      )}
      style={{ paddingLeft: `${depth * 24 + 8}px` }}
    >
      {/* Expand/collapse chevron */}
      <button
        onClick={onExpand}
        className={cn(
          "w-5 h-5 flex items-center justify-center rounded",
          node.has_children
            ? "cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700"
            : "invisible"
        )}
        disabled={!node.has_children}
      >
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
        ) : isExpanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
        )}
      </button>

      {/* Checkbox */}
      <Checkbox
        checked={isSelected}
        onCheckedChange={onSelect}
        className="mr-1"
      />

      {/* Icon */}
      <Icon
        className={cn(
          "w-4 h-4 flex-shrink-0",
          node.node_type === "site"
            ? "text-blue-500"
            : node.node_type === "list"
              ? "text-orange-500"
              : node.node_type === "folder"
                ? "text-yellow-500"
                : "text-muted-foreground"
        )}
      />

      {/* Title */}
      <span className="text-sm text-foreground truncate">{node.title}</span>

      {/* Item count */}
      {node.item_count != null && (
        <Badge variant="secondary" className="text-xs ml-auto flex-shrink-0">
          {node.item_count} items
        </Badge>
      )}

      {/* Node type badge */}
      <Badge
        variant="outline"
        className="text-xs flex-shrink-0 text-muted-foreground"
      >
        {node.node_type}
      </Badge>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function BrowseTreeDemo() {
  const { readable_id } = useParams<{ readable_id: string }>();
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  // Wizard state
  const [step, setStep] = useState(1);

  // Step 1: Browse tree
  const [sourceConnections, setSourceConnections] = useState<SourceConnection[]>([]);
  const [adminScId, setAdminScId] = useState("");
  const [userPrincipal, setUserPrincipal] = useState("hr_demo");
  const [treeNodes, setTreeNodes] = useState<Map<string | null, TreeNode[]>>(new Map());
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [loadingNodes, setLoadingNodes] = useState<Set<string>>(new Set());
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());
  const [treeLoading, setTreeLoading] = useState(false);
  const [treeLoaded, setTreeLoaded] = useState(false);

  // Step 2: Create user SC
  const [scName, setScName] = useState("SP HR Workspace");
  const [spUsername, setSpUsername] = useState("hr_demo");
  const [spPassword, setSpPassword] = useState("xK9mPwR2qJ7nL#");
  const [spDomain, setSpDomain] = useState("AIRWEAVE-SP2019");
  const [adUsername, setAdUsername] = useState("sp2019admin");
  const [adPassword, setAdPassword] = useState("OEtJV0DenQDF21gug#");
  const [adDomain, setAdDomain] = useState("AIRWEAVE-SP2019");
  const [userScId, setUserScId] = useState("");
  const [creatingUserSc, setCreatingUserSc] = useState(false);
  const [userScCreated, setUserScCreated] = useState(false);

  // Step 3: Select & Sync
  const [syncing, setSyncing] = useState(false);
  const [syncJobId, setSyncJobId] = useState("");
  const [syncStatus, setSyncStatus] = useState("");
  const [syncEntities, setSyncEntities] = useState(0);
  const [syncDone, setSyncDone] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Step 4: Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // ---------------------------------------------------------------------------
  // Load source connections on mount
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!readable_id) return;
    (async () => {
      const resp = await apiClient.get(`/source-connections/?collection=${readable_id}`);
      if (resp.ok) {
        const data = await resp.json();
        setSourceConnections(data);
        if (data.length === 1) setAdminScId(data[0].id);
      }
    })();
  }, [readable_id]);

  // Cleanup poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Step 1: Load tree
  // ---------------------------------------------------------------------------

  const loadTree = useCallback(
    async (parentId: string | null = null) => {
      if (!adminScId) return;

      if (!parentId) {
        setTreeLoading(true);
        setTreeLoaded(false);
      } else {
        setLoadingNodes((prev) => new Set(prev).add(parentId));
      }

      try {
        const params: Record<string, string> = {};
        if (userPrincipal) params.user_principal = userPrincipal;
        if (parentId) params.parent_id = parentId;

        const qs = new URLSearchParams(params).toString();
        const resp = await apiClient.get(
          `/source-connections/${adminScId}/browse-tree${qs ? `?${qs}` : ""}`
        );

        if (resp.ok) {
          const data = await resp.json();
          setTreeNodes((prev) => {
            const next = new Map(prev);
            next.set(parentId, data.nodes);
            return next;
          });
          if (!parentId) setTreeLoaded(true);
        }
      } finally {
        if (!parentId) setTreeLoading(false);
        if (parentId)
          setLoadingNodes((prev) => {
            const next = new Set(prev);
            next.delete(parentId);
            return next;
          });
      }
    },
    [adminScId, userPrincipal]
  );

  const handleExpand = useCallback(
    (nodeId: string) => {
      setExpandedNodes((prev) => {
        const next = new Set(prev);
        if (next.has(nodeId)) {
          next.delete(nodeId);
        } else {
          next.add(nodeId);
          // Load children if not already loaded
          if (!treeNodes.has(nodeId)) {
            loadTree(nodeId);
          }
        }
        return next;
      });
    },
    [loadTree, treeNodes]
  );

  const handleSelect = useCallback((sourceNodeId: string) => {
    setSelectedNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(sourceNodeId)) {
        next.delete(sourceNodeId);
      } else {
        next.add(sourceNodeId);
      }
      return next;
    });
  }, []);

  // Render tree recursively
  const renderNodes = (parentId: string | null, depth: number): React.ReactNode => {
    const nodes = treeNodes.get(parentId) || [];
    return nodes.map((node) => (
      <div key={node.id}>
        <TreeNodeRow
          node={node}
          depth={depth}
          isSelected={selectedNodeIds.has(node.source_node_id)}
          isExpanded={expandedNodes.has(node.id)}
          isLoading={loadingNodes.has(node.id)}
          onToggle={() => handleSelect(node.source_node_id)}
          onSelect={() => handleSelect(node.source_node_id)}
          onExpand={() => handleExpand(node.id)}
        />
        {expandedNodes.has(node.id) && renderNodes(node.id, depth + 1)}
      </div>
    ));
  };

  // ---------------------------------------------------------------------------
  // Step 2: Create user SC
  // ---------------------------------------------------------------------------

  const handleCreateUserSc = async () => {
    if (!readable_id || !adminScId) return;
    setCreatingUserSc(true);

    try {
      // Get admin SC details for config
      const adminResp = await apiClient.get(`/source-connections/${adminScId}`);
      if (!adminResp.ok) throw new Error("Failed to fetch admin SC details");
      const adminSc = await adminResp.json();

      const payload = {
        name: scName,
        short_name: adminSc.short_name,
        readable_collection_id: readable_id,
        config: adminSc.config_fields || {
          site_url: "http://sharepoint-2019.demos.airweave.ai",
          ad_server: "ldaps://108.143.169.156:636",
          ad_search_base: "DC=AIRWEAVE-SP2019,DC=local",
        },
        sync_immediately: false,
        authentication: {
          credentials: {
            sharepoint_username: spUsername,
            sharepoint_password: spPassword,
            sharepoint_domain: spDomain,
            ad_username: adUsername,
            ad_password: adPassword,
            ad_domain: adDomain,
          },
        },
      };

      const resp = await apiClient.post("/source-connections/", payload);
      if (resp.ok) {
        const data = await resp.json();
        setUserScId(data.id);
        setUserScCreated(true);
      } else {
        const errText = await resp.text();
        alert(`Failed to create user SC: ${errText}`);
      }
    } catch (err) {
      alert(`Error: ${err}`);
    } finally {
      setCreatingUserSc(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Step 3: Select & Sync
  // ---------------------------------------------------------------------------

  const handleSelectAndSync = async () => {
    if (!userScId || selectedNodeIds.size === 0) return;
    setSyncing(true);
    setSyncStatus("submitting");

    try {
      const resp = await apiClient.post(
        `/source-connections/${userScId}/browse-tree/select`,
        {
          admin_source_connection_id: adminScId,
          source_node_ids: Array.from(selectedNodeIds),
        }
      );

      if (resp.ok) {
        const data = await resp.json();
        setSyncJobId(data.sync_job_id);
        setSyncStatus("pending");

        // Start polling
        pollRef.current = setInterval(async () => {
          const jobResp = await apiClient.get(
            `/source-connections/${userScId}/jobs`
          );
          if (jobResp.ok) {
            const jobs: SyncJob[] = await jobResp.json();
            if (jobs.length > 0) {
              const latest = jobs[0];
              setSyncStatus(latest.status.toLowerCase());
              setSyncEntities(
                (latest.entities_inserted || 0) + (latest.entities_updated || 0)
              );
              if (
                ["completed", "failed", "cancelled"].includes(
                  latest.status.toLowerCase()
                )
              ) {
                if (pollRef.current) clearInterval(pollRef.current);
                setSyncDone(true);
                setSyncing(false);
              }
            }
          }
        }, 5000);
      } else {
        const errText = await resp.text();
        setSyncStatus("error");
        alert(`Failed to select nodes: ${errText}`);
        setSyncing(false);
      }
    } catch (err) {
      setSyncStatus("error");
      alert(`Error: ${err}`);
      setSyncing(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Step 4: Search
  // ---------------------------------------------------------------------------

  const handleSearch = async () => {
    if (!readable_id || !searchQuery) return;
    setSearching(true);

    try {
      const resp = await apiClient.post(
        `/collections/${readable_id}/search`,
        {
          query: searchQuery,
          source_connection_ids: userScId ? [userScId] : undefined,
          generate_answer: false,
          rerank: false,
        }
      );

      if (resp.ok) {
        const data = await resp.json();
        setSearchResults(data.results || []);
      }
    } finally {
      setSearching(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const selectedNodes = (): TreeNode[] => {
    const all: TreeNode[] = [];
    treeNodes.forEach((nodes) => {
      nodes.forEach((n) => {
        if (selectedNodeIds.has(n.source_node_id)) all.push(n);
      });
    });
    return all;
  };

  const getSyncIcon = () => {
    switch (syncStatus) {
      case "completed":
        return <CheckCircle2 className="w-5 h-5 text-green-500" />;
      case "failed":
      case "cancelled":
      case "error":
        return <XCircle className="w-5 h-5 text-red-500" />;
      case "running":
      case "in_progress":
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case "pending":
      case "submitting":
        return <Clock className="w-5 h-5 text-yellow-500" />;
      default:
        return <Play className="w-5 h-5 text-muted-foreground" />;
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div
      className={cn(
        "container mx-auto py-6 flex flex-col items-center max-w-[900px]",
        isDark ? "text-foreground" : ""
      )}
    >
      {/* Back button */}
      <div className="w-full flex items-center gap-3 mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/collections/${readable_id}`)}
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Collection
        </Button>
        <h1 className="text-xl font-bold text-foreground">
          Browse Tree Demo
        </h1>
      </div>

      <StepIndicator currentStep={step} />

      {/* ============================================================ */}
      {/* STEP 1: Browse Filtered Tree */}
      {/* ============================================================ */}
      {step === 1 && (
        <div
          className={cn(
            "w-full rounded-lg border p-6",
            isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          )}
        >
          <h2 className="text-lg font-semibold mb-4">
            Step 1: Browse Filtered Tree
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            Select the admin source connection and enter a user principal to see
            the tree filtered by that user&apos;s access.
          </p>

          {/* Admin SC selector */}
          <div className="flex gap-3 mb-4">
            <div className="flex-1">
              <label className="text-sm font-medium text-foreground block mb-1">
                Admin Source Connection
              </label>
              <select
                value={adminScId}
                onChange={(e) => {
                  setAdminScId(e.target.value);
                  setTreeLoaded(false);
                  setTreeNodes(new Map());
                  setExpandedNodes(new Set());
                  setSelectedNodeIds(new Set());
                }}
                className={cn(
                  "w-full h-9 rounded-md border px-3 text-sm",
                  isDark
                    ? "bg-gray-800 border-gray-700 text-foreground"
                    : "bg-white border-gray-300"
                )}
              >
                <option value="">Select...</option>
                {sourceConnections.map((sc) => (
                  <option key={sc.id} value={sc.id}>
                    {sc.name} ({sc.short_name})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex-1">
              <label className="text-sm font-medium text-foreground block mb-1">
                User Principal
              </label>
              <Input
                value={userPrincipal}
                onChange={(e) => setUserPrincipal(e.target.value)}
                placeholder="e.g., user:hr_demo"
              />
            </div>

            <div className="flex items-end">
              <Button
                onClick={() => loadTree(null)}
                disabled={!adminScId || treeLoading}
              >
                {treeLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-1" />
                ) : null}
                Load Tree
              </Button>
            </div>
          </div>

          {/* Tree view */}
          {treeLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
              <span className="ml-2 text-muted-foreground">Loading tree...</span>
            </div>
          )}

          {treeLoaded && (treeNodes.get(null)?.length ?? 0) === 0 && (
            <div
              className={cn(
                "text-center py-8 rounded-md border border-dashed",
                isDark ? "border-gray-700" : "border-gray-300"
              )}
            >
              <p className="text-muted-foreground">
                No nodes found — metadata sync may still be running.
              </p>
            </div>
          )}

          {treeLoaded && (treeNodes.get(null)?.length ?? 0) > 0 && (
            <div
              className={cn(
                "rounded-md border max-h-[400px] overflow-y-auto",
                isDark ? "border-gray-800" : "border-gray-200"
              )}
            >
              {renderNodes(null, 0)}
            </div>
          )}

          {/* Selected count & Next */}
          <div className="flex items-center justify-between mt-4">
            <span className="text-sm text-muted-foreground">
              {selectedNodeIds.size} node(s) selected
            </span>
            <Button
              onClick={() => setStep(2)}
              disabled={selectedNodeIds.size === 0}
            >
              Next
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* STEP 2: Create User Source Connection */}
      {/* ============================================================ */}
      {step === 2 && (
        <div
          className={cn(
            "w-full rounded-lg border p-6",
            isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          )}
        >
          <h2 className="text-lg font-semibold mb-4">
            Step 2: Create User Source Connection
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            Create a source connection with the HR user&apos;s credentials. This
            will be used for the targeted sync of selected nodes.
          </p>

          {userScCreated ? (
            <div className="flex flex-col items-center py-6 gap-3">
              <CheckCircle2 className="w-10 h-10 text-green-500" />
              <p className="text-foreground font-medium">
                User source connection created!
              </p>
              <code className="text-xs text-muted-foreground bg-gray-100 dark:bg-gray-800 px-3 py-1 rounded">
                ID: {userScId}
              </code>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="text-sm font-medium block mb-1">Name</label>
                <Input value={scName} onChange={(e) => setScName(e.target.value)} />
              </div>

              <div>
                <label className="text-sm font-medium block mb-1">
                  SP Username
                </label>
                <Input
                  value={spUsername}
                  onChange={(e) => setSpUsername(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">
                  SP Password
                </label>
                <Input
                  type="password"
                  value={spPassword}
                  onChange={(e) => setSpPassword(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">
                  SP Domain
                </label>
                <Input
                  value={spDomain}
                  onChange={(e) => setSpDomain(e.target.value)}
                />
              </div>

              <div className="col-span-2 border-t pt-3 mt-1">
                <p className="text-xs text-muted-foreground mb-3">
                  Active Directory credentials (shared infrastructure)
                </p>
              </div>

              <div>
                <label className="text-sm font-medium block mb-1">
                  AD Username
                </label>
                <Input
                  value={adUsername}
                  onChange={(e) => setAdUsername(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">
                  AD Password
                </label>
                <Input
                  type="password"
                  value={adPassword}
                  onChange={(e) => setAdPassword(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">
                  AD Domain
                </label>
                <Input
                  value={adDomain}
                  onChange={(e) => setAdDomain(e.target.value)}
                />
              </div>

              <div className="col-span-2 mt-2">
                <Button
                  onClick={handleCreateUserSc}
                  disabled={creatingUserSc || !spUsername || !spPassword}
                  className="w-full"
                >
                  {creatingUserSc ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-1" />
                  ) : null}
                  Create Source Connection
                </Button>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between mt-4">
            <Button variant="ghost" onClick={() => setStep(1)}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
            <Button onClick={() => setStep(3)} disabled={!userScCreated}>
              Next
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* STEP 3: Select & Sync */}
      {/* ============================================================ */}
      {step === 3 && (
        <div
          className={cn(
            "w-full rounded-lg border p-6",
            isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          )}
        >
          <h2 className="text-lg font-semibold mb-4">
            Step 3: Select Nodes & Trigger Sync
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            The selected nodes will be saved on the user&apos;s source connection
            and a targeted sync will be triggered automatically.
          </p>

          {/* Selected nodes summary */}
          <div
            className={cn(
              "rounded-md border p-3 mb-4",
              isDark ? "border-gray-800 bg-gray-800/50" : "border-gray-200 bg-gray-50"
            )}
          >
            <p className="text-sm font-medium mb-2">
              Selected Nodes ({selectedNodeIds.size})
            </p>
            {selectedNodes().map((node) => (
              <div
                key={node.source_node_id}
                className="flex items-center gap-2 text-sm text-muted-foreground py-0.5"
              >
                {(() => {
                  const Icon = NODE_ICONS[node.node_type] || File;
                  return <Icon className="w-3.5 h-3.5" />;
                })()}
                <span>{node.title}</span>
                {node.item_count != null && (
                  <span className="text-xs">({node.item_count} items)</span>
                )}
              </div>
            ))}
          </div>

          {/* Sync status */}
          {syncStatus && (
            <div
              className={cn(
                "rounded-md border p-4 mb-4 flex items-center gap-3",
                syncStatus === "completed"
                  ? isDark
                    ? "border-green-800 bg-green-900/20"
                    : "border-green-200 bg-green-50"
                  : syncStatus === "failed" || syncStatus === "error"
                    ? isDark
                      ? "border-red-800 bg-red-900/20"
                      : "border-red-200 bg-red-50"
                    : isDark
                      ? "border-gray-800 bg-gray-800/50"
                      : "border-gray-200 bg-gray-50"
              )}
            >
              {getSyncIcon()}
              <div>
                <p className="text-sm font-medium">
                  Sync: {syncStatus}
                </p>
                {syncJobId && (
                  <p className="text-xs text-muted-foreground">
                    Job ID: {syncJobId}
                  </p>
                )}
                {syncEntities > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Entities processed: {syncEntities}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Action */}
          {!syncStatus && (
            <Button
              onClick={handleSelectAndSync}
              disabled={syncing || selectedNodeIds.size === 0}
              className="w-full"
            >
              {syncing ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1" />
              ) : null}
              Select & Sync ({selectedNodeIds.size} nodes)
            </Button>
          )}

          <div className="flex items-center justify-between mt-4">
            <Button variant="ghost" onClick={() => setStep(2)}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
            <Button onClick={() => setStep(4)} disabled={!syncDone}>
              Next
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* STEP 4: Search */}
      {/* ============================================================ */}
      {step === 4 && (
        <div
          className={cn(
            "w-full rounded-lg border p-6",
            isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          )}
        >
          <h2 className="text-lg font-semibold mb-4">Step 4: Search</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Search within the synced data, scoped to the user&apos;s source
            connection.
          </p>

          <div className="flex gap-3 mb-4">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search query..."
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1"
            />
            <Button onClick={handleSearch} disabled={searching || !searchQuery}>
              {searching ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1" />
              ) : (
                <Search className="w-4 h-4 mr-1" />
              )}
              Search
            </Button>
          </div>

          {/* Results */}
          {searchResults.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">
                {searchResults.length} result(s)
              </p>
              {searchResults.map((result, i) => (
                <div
                  key={result.id || i}
                  className={cn(
                    "rounded-md border p-3",
                    isDark ? "border-gray-800" : "border-gray-200"
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-foreground">
                      {result.title || "Untitled"}
                    </span>
                    <Badge variant="secondary" className="text-xs">
                      score: {(result.combined_score ?? result.similarity_score ?? 0).toFixed(2)}
                    </Badge>
                  </div>
                  {result.content && (
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {result.content}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {searchResults.length === 0 && searchQuery && !searching && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No results found.
            </p>
          )}

          <div className="flex items-center justify-between mt-4">
            <Button variant="ghost" onClick={() => setStep(3)}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
            <Button
              variant="ghost"
              onClick={() => navigate(`/collections/${readable_id}`)}
            >
              Done
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
