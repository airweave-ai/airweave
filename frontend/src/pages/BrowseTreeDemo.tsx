import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
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
  Shield,
  RefreshCw,
  User,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BrowseNode {
  source_node_id: string;
  node_type: string;
  title: string;
  description: string | null;
  item_count: number | null;
  has_children: boolean;
  node_metadata: Record<string, any> | null;
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

const PAGE_SIZE = 10;

const STEPS = [
  { number: 1, label: "Browse Tree" },
  { number: 2, label: "Select & Sync" },
  { number: 3, label: "Search" },
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
  onSelect,
  onExpand,
}: {
  node: BrowseNode;
  depth: number;
  isSelected: boolean;
  isExpanded: boolean;
  isLoading: boolean;
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
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  // Auto-select SC from URL ?sc= param (set by creation flow)
  const scFromUrl = searchParams.get("sc") || "";
  const isFromCreationFlow = !!scFromUrl;

  // Wizard state
  const [step, setStep] = useState(1);

  // Step 1: Browse tree
  const [sourceConnections, setSourceConnections] = useState<SourceConnection[]>([]);
  const [scId, setScId] = useState(scFromUrl);
  const [treeNodes, setTreeNodes] = useState<Map<string | null, BrowseNode[]>>(new Map());
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [loadingNodes, setLoadingNodes] = useState<Set<string>>(new Set());
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());
  const [treeLoading, setTreeLoading] = useState(false);
  const [treeLoaded, setTreeLoaded] = useState(false);
  const [visibleCounts, setVisibleCounts] = useState<Map<string, number>>(new Map());

  // ACL sync state
  const [aclSyncing, setAclSyncing] = useState(false);
  const [aclSyncDone, setAclSyncDone] = useState(false);
  const [aclSyncError, setAclSyncError] = useState("");
  const aclPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Step 2: Select & Sync
  const [syncing, setSyncing] = useState(false);
  const [syncJobId, setSyncJobId] = useState("");
  const [syncStatus, setSyncStatus] = useState("");
  const [syncEntities, setSyncEntities] = useState(0);
  const [syncDone, setSyncDone] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Step 3: Search
  const [searchQuery, setSearchQuery] = useState("");
  const [userPrincipal, setUserPrincipal] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Track whether auto-load has been triggered
  const autoLoadTriggered = useRef(false);

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
        // Only auto-select if no SC from URL and only one available
        if (!scFromUrl && data.length === 1) setScId(data[0].id);
      }
    })();
  }, [readable_id, scFromUrl]);

  // Cleanup polls on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (aclPollRef.current) clearInterval(aclPollRef.current);
    };
  }, []);

  // ---------------------------------------------------------------------------
  // ACL Sync
  // ---------------------------------------------------------------------------

  const handleAclSync = useCallback(async () => {
    if (!scId) return;
    setAclSyncing(true);
    setAclSyncDone(false);
    setAclSyncError("");

    try {
      const resp = await apiClient.post(`/admin/source-connections/${scId}/sync-acl`);
      if (resp.ok) {
        const data = await resp.json();
        // Poll sync job for ACL completion
        const jobId = data.sync_job_id;
        if (jobId) {
          aclPollRef.current = setInterval(async () => {
            const jobResp = await apiClient.get(`/source-connections/${scId}/jobs`);
            if (jobResp.ok) {
              const jobs: SyncJob[] = await jobResp.json();
              const aclJob = jobs.find((j) => j.id === jobId);
              if (aclJob && ["completed", "failed", "cancelled"].includes(aclJob.status.toLowerCase())) {
                if (aclPollRef.current) clearInterval(aclPollRef.current);
                setAclSyncing(false);
                if (aclJob.status.toLowerCase() === "completed") {
                  setAclSyncDone(true);
                } else {
                  setAclSyncError(`ACL sync ${aclJob.status.toLowerCase()}`);
                }
              }
            }
          }, 3000);
        } else {
          // No job ID — may have completed synchronously
          setAclSyncing(false);
          setAclSyncDone(true);
        }
      } else {
        const errText = await resp.text();
        setAclSyncError(errText);
        setAclSyncing(false);
      }
    } catch (err) {
      setAclSyncError(String(err));
      setAclSyncing(false);
    }
  }, [scId]);

  // ---------------------------------------------------------------------------
  // Step 1: Load tree (lazy-loaded from source API)
  // ---------------------------------------------------------------------------

  const loadTree = useCallback(
    async (parentNodeId: string | null = null): Promise<BrowseNode[]> => {
      if (!scId) return [];

      if (!parentNodeId) {
        setTreeLoading(true);
        setTreeLoaded(false);
      } else {
        setLoadingNodes((prev) => new Set(prev).add(parentNodeId));
      }

      try {
        const params: Record<string, string> = {};
        if (parentNodeId) params.parent_node_id = parentNodeId;

        const qs = new URLSearchParams(params).toString();
        const resp = await apiClient.get(
          `/admin/source-connections/${scId}/browse-tree${qs ? `?${qs}` : ""}`
        );

        if (resp.ok) {
          const data = await resp.json();
          const nodes: BrowseNode[] = data.nodes;
          setTreeNodes((prev) => {
            const next = new Map(prev);
            next.set(parentNodeId, nodes);
            return next;
          });
          if (!parentNodeId) setTreeLoaded(true);
          return nodes;
        }
        return [];
      } finally {
        if (!parentNodeId) setTreeLoading(false);
        if (parentNodeId)
          setLoadingNodes((prev) => {
            const next = new Set(prev);
            next.delete(parentNodeId);
            return next;
          });
      }
    },
    [scId]
  );

  // Auto-load tree + depth-2 greedy prefetch when scId is set
  useEffect(() => {
    if (!scId || autoLoadTriggered.current) return;
    autoLoadTriggered.current = true;

    (async () => {
      // Auto-trigger ACL sync if arriving from creation flow
      if (isFromCreationFlow) {
        handleAclSync();
      }

      // Load root
      const rootNodes = await loadTree(null);

      // Depth-2 prefetch: expand all root nodes that have children
      const expandIds = new Set<string>();
      for (const node of rootNodes) {
        if (node.has_children) {
          expandIds.add(node.source_node_id);
          // Fire child load (don't await — let them run in parallel)
          loadTree(node.source_node_id);
        }
      }
      if (expandIds.size > 0) {
        setExpandedNodes((prev) => new Set([...prev, ...expandIds]));
      }
    })();
  }, [scId, loadTree, isFromCreationFlow, handleAclSync]);

  const handleExpand = useCallback(
    (sourceNodeId: string) => {
      setExpandedNodes((prev) => {
        const next = new Set(prev);
        if (next.has(sourceNodeId)) {
          next.delete(sourceNodeId);
        } else {
          next.add(sourceNodeId);
          // Load children if not already loaded
          if (!treeNodes.has(sourceNodeId)) {
            loadTree(sourceNodeId);
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

  // "Show next 10" helper
  const getVisibleLimit = (parentKey: string) => visibleCounts.get(parentKey) ?? PAGE_SIZE;
  const showMore = (parentKey: string) => {
    setVisibleCounts((prev) => {
      const next = new Map(prev);
      next.set(parentKey, (prev.get(parentKey) ?? PAGE_SIZE) + PAGE_SIZE);
      return next;
    });
  };

  // Render tree recursively with pagination
  const renderNodes = (parentNodeId: string | null, depth: number): React.ReactNode => {
    const nodes = treeNodes.get(parentNodeId) || [];
    const parentKey = parentNodeId ?? "__root__";
    const limit = getVisibleLimit(parentKey);
    const visible = nodes.slice(0, limit);
    const remaining = nodes.length - limit;

    return (
      <>
        {visible.map((node) => (
          <div key={node.source_node_id}>
            <TreeNodeRow
              node={node}
              depth={depth}
              isSelected={selectedNodeIds.has(node.source_node_id)}
              isExpanded={expandedNodes.has(node.source_node_id)}
              isLoading={loadingNodes.has(node.source_node_id)}
              onSelect={() => handleSelect(node.source_node_id)}
              onExpand={() => handleExpand(node.source_node_id)}
            />
            {expandedNodes.has(node.source_node_id) &&
              renderNodes(node.source_node_id, depth + 1)}
          </div>
        ))}
        {remaining > 0 && (
          <button
            onClick={() => showMore(parentKey)}
            className="text-xs text-blue-500 hover:text-blue-400 py-1 px-2 ml-4"
            style={{ paddingLeft: `${depth * 24 + 32}px` }}
          >
            Show next {Math.min(PAGE_SIZE, remaining)} of {remaining} remaining...
          </button>
        )}
      </>
    );
  };

  // ---------------------------------------------------------------------------
  // Step 2: Select & Sync
  // ---------------------------------------------------------------------------

  const handleSelectAndSync = async () => {
    if (!scId || selectedNodeIds.size === 0) return;
    setSyncing(true);
    setSyncStatus("submitting");

    try {
      const resp = await apiClient.post(
        `/admin/source-connections/${scId}/browse-tree/select`,
        {
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
            `/source-connections/${scId}/jobs`
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
  // Step 3: Search (with optional search-as-user)
  // ---------------------------------------------------------------------------

  const handleSearch = async () => {
    if (!readable_id || !searchQuery) return;
    setSearching(true);

    try {
      const body = {
        query: searchQuery,
        source_connection_ids: scId ? [scId] : undefined,
        generate_answer: false,
        rerank: false,
      };

      let resp: Response;
      if (userPrincipal.trim()) {
        // Search as a specific user (admin endpoint with ACL filtering)
        const encodedPrincipal = encodeURIComponent(userPrincipal.trim());
        resp = await apiClient.post(
          `/admin/collections/${readable_id}/search/as-user?user_principal=${encodedPrincipal}&destination=vespa`,
          body
        );
      } else {
        resp = await apiClient.post(
          `/collections/${readable_id}/search`,
          body
        );
      }

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

  const selectedNodes = (): BrowseNode[] => {
    const all: BrowseNode[] = [];
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
          Browse Tree
        </h1>
      </div>

      <StepIndicator currentStep={step} />

      {/* ============================================================ */}
      {/* ACL Sync Status Banner */}
      {/* ============================================================ */}
      {(aclSyncing || aclSyncDone || aclSyncError) && (
        <div
          className={cn(
            "w-full rounded-lg border p-3 mb-4 flex items-center gap-3",
            aclSyncDone
              ? isDark ? "border-green-800 bg-green-900/20" : "border-green-200 bg-green-50"
              : aclSyncError
                ? isDark ? "border-red-800 bg-red-900/20" : "border-red-200 bg-red-50"
                : isDark ? "border-gray-800 bg-gray-800/50" : "border-gray-200 bg-gray-50"
          )}
        >
          {aclSyncing ? (
            <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
          ) : aclSyncDone ? (
            <CheckCircle2 className="w-4 h-4 text-green-500" />
          ) : (
            <XCircle className="w-4 h-4 text-red-500" />
          )}
          <div className="flex-1">
            <span className="text-sm font-medium">
              {aclSyncing ? "Syncing ACL data..." : aclSyncDone ? "ACL sync complete" : `ACL sync error: ${aclSyncError}`}
            </span>
          </div>
          {!aclSyncing && (
            <Button variant="ghost" size="sm" onClick={handleAclSync}>
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
              Re-sync ACL
            </Button>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* STEP 1: Browse Tree */}
      {/* ============================================================ */}
      {step === 1 && (
        <div
          className={cn(
            "w-full rounded-lg border p-6",
            isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          )}
        >
          <h2 className="text-lg font-semibold mb-4">
            Step 1: Browse Tree
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            {isFromCreationFlow
              ? "Your source connection is set up. Browse and select the content you want to sync."
              : "Select a source connection and browse its content tree. The tree is lazy-loaded directly from the source API."}
          </p>

          {/* SC selector — hidden when auto-set from URL */}
          {!isFromCreationFlow && (
            <div className="flex gap-3 mb-4">
              <div className="flex-1">
                <label className="text-sm font-medium text-foreground block mb-1">
                  Source Connection
                </label>
                <select
                  value={scId}
                  onChange={(e) => {
                    setScId(e.target.value);
                    setTreeLoaded(false);
                    setTreeNodes(new Map());
                    setExpandedNodes(new Set());
                    setSelectedNodeIds(new Set());
                    setVisibleCounts(new Map());
                    autoLoadTriggered.current = false;
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

              <div className="flex items-end">
                <Button
                  onClick={() => {
                    autoLoadTriggered.current = false;
                    loadTree(null);
                  }}
                  disabled={!scId || treeLoading}
                >
                  {treeLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-1" />
                  ) : null}
                  Load Tree
                </Button>
              </div>
            </div>
          )}

          {/* Manual ACL sync button (for non-creation-flow) */}
          {!isFromCreationFlow && scId && !aclSyncing && !aclSyncDone && (
            <div className="mb-4">
              <Button variant="outline" size="sm" onClick={handleAclSync}>
                <Shield className="w-3.5 h-3.5 mr-1" />
                Sync ACL
              </Button>
            </div>
          )}

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
                No nodes found. The source may not support browse tree.
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
      {/* STEP 2: Select & Sync */}
      {/* ============================================================ */}
      {step === 2 && (
        <div
          className={cn(
            "w-full rounded-lg border p-6",
            isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          )}
        >
          <h2 className="text-lg font-semibold mb-4">
            Step 2: Select Nodes & Trigger Sync
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            The selected nodes will be saved and a targeted sync will be
            triggered automatically.
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
            <Button variant="ghost" onClick={() => setStep(1)}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
            <Button onClick={() => setStep(3)} disabled={!syncDone}>
              Next
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* STEP 3: Search */}
      {/* ============================================================ */}
      {step === 3 && (
        <div
          className={cn(
            "w-full rounded-lg border p-6",
            isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          )}
        >
          <h2 className="text-lg font-semibold mb-4">Step 3: Search</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Search within the synced data. Optionally search as a specific user to verify access control filtering.
          </p>

          {/* Search-as-user input */}
          <div className="mb-3">
            <label className="text-xs font-medium text-muted-foreground block mb-1">
              <User className="w-3 h-3 inline mr-1" />
              Search as user (optional)
            </label>
            <Input
              value={userPrincipal}
              onChange={(e) => setUserPrincipal(e.target.value)}
              placeholder="e.g. user:sp_admin or user:hr_demo"
              className="text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Results filtered by this user's access permissions
            </p>
          </div>

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
                {userPrincipal.trim() && (
                  <span className="text-muted-foreground font-normal"> — filtered for {userPrincipal.trim()}</span>
                )}
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
            <Button variant="ghost" onClick={() => setStep(2)}>
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
