import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { AlertCircle, RefreshCw, Pencil, Play, Clock, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
import { useTheme } from "@/lib/theme-provider";
import ReactFlow, {
    useNodesState,
    useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { SourceNode } from '@/components/sync/nodes/SourceNode';
import { TransformerNode } from '@/components/sync/nodes/TransformerNode';
import { DestinationNode } from '@/components/sync/nodes/DestinationNode';
import { EntityNode } from '@/components/sync/nodes/EntityNode';
import { Dag } from '@/components/sync/dag';
import {
    cleanEntityName,
    convertDagToFlowGraph
} from '@/components/collection/DagToFlow';
import { cn } from "@/lib/utils";
import { SyncErrorCard } from './SyncErrorCard';

const nodeTypes = {
    sourceNode: SourceNode,
    transformerNode: TransformerNode,
    destinationNode: DestinationNode,
    entityNode: EntityNode
};

// Source Connection interface - matches backend SourceConnection schema exactly
interface SourceConnection {
    id: string;
    name: string;
    description?: string;
    short_name: string;
    config_fields?: Record<string, any>;
    sync_id?: string;
    organization_id: string;
    created_at: string;
    modified_at: string;
    connection_id?: string;
    collection: string;
    created_by_email: string;
    modified_by_email: string;
    auth_fields?: Record<string, any> | string;
    status?: string;
    last_sync_job_status?: string;
    last_sync_job_id?: string;
    last_sync_job_started_at?: string;
    last_sync_job_completed_at?: string;
    last_sync_job_error?: string;
    cron_schedule?: string;
    next_scheduled_run?: string;
}

// Source Connection Job interface - matches backend SourceConnectionJob schema exactly
interface SourceConnectionJob {
    source_connection_id: string;
    id: string;
    organization_id: string;
    created_by_email: string;
    modified_by_email: string;
    created_at: string;
    modified_at: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelling' | 'cancelled';
    entities_inserted?: number;
    entities_updated?: number;
    entities_deleted?: number;
    entities_kept?: number;
    entities_skipped?: number;
    entities_encountered?: Record<string, number>;
    started_at?: string;
    completed_at?: string;
    failed_at?: string;
    error?: string;
}

interface SimplifiedSourceConnectionDetailViewProps {
    sourceConnectionId: string;
}

const SimplifiedSyncDagCard = ({
    sourceConnection,
    entityDict,
    selectedEntity,
    setSelectedEntity,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    reactFlowInstance,
    setReactFlowInstance,
    flowContainerRef,
    syncJobData,
    onRunSync,
    isInitiatingSyncJob,
    isDark
}: {
    sourceConnection: SourceConnection;
    entityDict: Record<string, number>;
    selectedEntity: string;
    setSelectedEntity: (entity: string) => void;
    nodes: any[];
    edges: any[];
    onNodesChange: any;
    onEdgesChange: any;
    reactFlowInstance: any;
    setReactFlowInstance: any;
    flowContainerRef: React.RefObject<HTMLDivElement>;
    syncJobData: {
        inserted: number;
        updated: number;
        deleted: number;
        kept: number;
        skipped: number;
        total: number;
    };
    onRunSync: () => void;
    isInitiatingSyncJob: boolean;
    isDark: boolean;
}) => {
    return (
        <div className="space-y-3">
            {/* Entity Graph Card with Entities Panel on the right */}
            <div className="flex gap-3">
                {/* Entity Graph Card */}
                <Card className={cn(
                    "overflow-hidden border rounded-lg flex-1",
                    isDark ? "border-gray-700/50 bg-gray-800/30" : "border-gray-200 bg-white shadow-sm"
                )}>
                    <CardHeader className="p-3">
                        <div className="flex justify-between items-center">
                            <h3 className={cn(
                                "text-base font-medium",
                                isDark ? "text-gray-200" : "text-gray-700"
                            )}>
                                Entity Graph
                            </h3>

                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className={cn(
                                        "h-8 gap-1.5 font-normal",
                                        isDark
                                            ? "bg-gray-700 border-gray-600 text-white"
                                            : "bg-white border-gray-200 text-gray-800 hover:bg-gray-50"
                                    )}
                                    onClick={onRunSync}
                                    disabled={isInitiatingSyncJob}
                                >
                                    <Play className="h-3.5 w-3.5" />
                                    {isInitiatingSyncJob ? 'Starting...' : 'Run Sync'}
                                </Button>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="p-3 pt-0">
                        <div
                            ref={flowContainerRef}
                            className="h-[200px] w-full overflow-hidden rounded-md"
                            style={{ minHeight: '200px' }}
                        >
                            <ReactFlow
                                key={sourceConnection.id || 'no-connection'}
                                nodes={nodes}
                                edges={edges}
                                onNodesChange={onNodesChange}
                                onEdgesChange={onEdgesChange}
                                nodeTypes={nodeTypes}
                                fitView
                                fitViewOptions={{
                                    padding: 0.3,
                                    minZoom: 0.1,
                                    maxZoom: 1.5,
                                    duration: 0
                                }}
                                onInit={setReactFlowInstance}
                                defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
                                style={{
                                    touchAction: 'none',
                                    cursor: 'default',
                                    background: isDark ? 'transparent' : '#ffffff'
                                }}
                                nodesDraggable={false}
                                nodesConnectable={false}
                                elementsSelectable={false}
                                zoomOnScroll={false}
                                panOnScroll={false}
                                panOnDrag={false}
                                zoomOnPinch={false}
                                zoomOnDoubleClick={false}
                                preventScrolling={true}
                                proOptions={{ hideAttribution: true }}
                            />
                        </div>
                    </CardContent>
                </Card>

                {/* Entity list - right side panel with same height as Entity Graph */}
                <div className={cn(
                    "w-[200px] flex-shrink-0 rounded-lg border flex flex-col h-[270px]",
                    isDark ? "border-gray-700/50 bg-gray-800/30" : "border-gray-200 bg-white shadow-sm"
                )}>
                    <div className={cn(
                        "p-3 border-b flex-shrink-0",
                        isDark ? "border-gray-700/50" : "border-gray-200"
                    )}>
                        <h3 className={cn(
                            "text-base font-medium",
                            isDark ? "text-gray-200" : "text-gray-700"
                        )}>
                            Entities
                        </h3>
                    </div>
                    <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-1.5 min-h-0">
                        {Object.keys(entityDict).length > 0 ?
                            Object.keys(entityDict)
                                .sort()
                                .map((key) => {
                                    const isSelected = key === selectedEntity;

                                    return (
                                        <Button
                                            key={key}
                                            variant="outline"
                                            className={cn(
                                                "w-full justify-between items-center gap-1.5 h-8 py-0 px-2 text-[13px] flex-shrink-0",
                                                isSelected
                                                    ? isDark
                                                        ? "bg-gray-700 border-gray-600 border-[1.5px] text-white"
                                                        : "bg-blue-50 border-blue-200 border-[1.5px] text-blue-700"
                                                    : isDark
                                                        ? "bg-gray-800/80 border-gray-700/60 text-gray-300"
                                                        : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"
                                            )}
                                            onClick={() => setSelectedEntity(key)}
                                        >
                                            <span className="truncate">{key}</span>
                                            <Badge
                                                variant="outline"
                                                className={cn(
                                                    "ml-1 pointer-events-none text-[11px] px-1.5 font-normal h-5 flex-shrink-0",
                                                    isSelected
                                                        ? isDark
                                                            ? "bg-gray-600 text-gray-200 border-gray-500"
                                                            : "bg-blue-100 text-blue-700 border-blue-200"
                                                        : isDark
                                                            ? "bg-gray-700 text-gray-300 border-gray-600"
                                                            : "bg-gray-50 text-gray-600 border-gray-200"
                                                )}
                                            >
                                                {entityDict[key]}
                                            </Badge>
                                        </Button>
                                    );
                                })
                            : <div className={cn(
                                "text-sm text-center py-4 flex-shrink-0",
                                isDark ? "text-gray-400" : "text-gray-500"
                            )}>
                                No entities found
                            </div>
                        }
                    </div>
                </div>
            </div>

            {/* Sync Progress - Compact Cards */}
            <div className="space-y-2">
                <div className="flex gap-2 flex-wrap">
                    <div className={cn(
                        "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[80px]",
                        isDark ? "bg-gray-700/30 border border-gray-600/50" : "bg-white border border-gray-100"
                    )}>
                        <div className="flex items-center gap-1">
                            <span className="w-2 h-2 block bg-green-500 rounded-full" />
                            <span className="text-[10px] uppercase tracking-wider font-medium opacity-60">Inserted</span>
                        </div>
                        <span className="text-sm font-semibold">{syncJobData.inserted.toLocaleString()}</span>
                    </div>

                    <div className={cn(
                        "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[80px]",
                        isDark ? "bg-gray-700/30 border border-gray-600/50" : "bg-white border border-gray-100"
                    )}>
                        <div className="flex items-center gap-1">
                            <span className="w-2 h-2 block bg-cyan-500 rounded-full" />
                            <span className="text-[10px] uppercase tracking-wider font-medium opacity-60">Updated</span>
                        </div>
                        <span className="text-sm font-semibold">{syncJobData.updated.toLocaleString()}</span>
                    </div>

                    <div className={cn(
                        "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[80px]",
                        isDark ? "bg-gray-700/30 border border-gray-600/50" : "bg-white border border-gray-100"
                    )}>
                        <div className="flex items-center gap-1">
                            <span className="w-2 h-2 block bg-primary rounded-full" />
                            <span className="text-[10px] uppercase tracking-wider font-medium opacity-60">Kept</span>
                        </div>
                        <span className="text-sm font-semibold">{syncJobData.kept.toLocaleString()}</span>
                    </div>

                    <div className={cn(
                        "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[80px]",
                        isDark ? "bg-gray-700/30 border border-gray-600/50" : "bg-white border border-gray-100"
                    )}>
                        <div className="flex items-center gap-1">
                            <span className="w-2 h-2 block bg-red-500 rounded-full" />
                            <span className="text-[10px] uppercase tracking-wider font-medium opacity-60">Deleted</span>
                        </div>
                        <span className="text-sm font-semibold">{syncJobData.deleted.toLocaleString()}</span>
                    </div>

                    <div className={cn(
                        "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[80px]",
                        isDark ? "bg-gray-700/30 border border-gray-600/50" : "bg-white border border-gray-100"
                    )}>
                        <div className="flex items-center gap-1">
                            <span className="w-2 h-2 block bg-yellow-500 rounded-full" />
                            <span className="text-[10px] uppercase tracking-wider font-medium opacity-60">Skipped</span>
                        </div>
                        <span className="text-sm font-semibold">{syncJobData.skipped.toLocaleString()}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

const SimplifiedSourceConnectionDetailView = ({
    sourceConnectionId
}: SimplifiedSourceConnectionDetailViewProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    const [sourceConnection, setSourceConnection] = useState<SourceConnection | null>(null);

    // CLEAR SEPARATION: Sync Job data (from /source-connections/{id}/jobs/{job_id})
    const [syncJob, setSyncJob] = useState<SourceConnectionJob | null>(null);

    // Loading and UI state
    const [isLoading, setIsLoading] = useState(true);
    const [isInitiatingSyncJob, setIsInitiatingSyncJob] = useState(false);

    // Entity processing and visualization state
    const [totalEntities, setTotalEntities] = useState<number>(0);
    const [totalRuntime, setTotalRuntime] = useState<number | null>(null);
    const [entityDict, setEntityDict] = useState<Record<string, number>>({});
    const [selectedEntity, setSelectedEntity] = useState<string>('');

    // Graph visualization state
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [reactFlowInstance, setReactFlowInstance] = useState(null);
    const [entityDags, setEntityDags] = useState<Dag[]>([]);
    const [selectedDag, setSelectedDag] = useState<Dag | null>(null);

    const flowContainerRef = useRef<HTMLDivElement>(null);

    // Sync job data processed for UI display
    const syncJobData = useMemo(() => {
        const inserted = syncJob?.entities_inserted || 0;
        const updated = syncJob?.entities_updated || 0;
        const deleted = syncJob?.entities_deleted || 0;
        const kept = syncJob?.entities_kept || 0;
        const skipped = syncJob?.entities_skipped || 0;
        const total = inserted + updated + kept + deleted + skipped;

        return { inserted, updated, deleted, kept, skipped, total };
    }, [syncJob]);

    // API CALL 1: Fetch Source Connection details (from /source-connections/{id})
    const fetchSourceConnection = async () => {
        try {
            console.log("Fetching source connection details...");
            const response = await apiClient.get(`/source-connections/${sourceConnectionId}`);

            if (response.ok) {
                const data = await response.json();
                console.log("Source connection data received:", data);
                setSourceConnection(data);
                return data;
            } else {
                console.error("Failed to load source connection details:", await response.text());
                return null;
            }
        } catch (err) {
            console.error("Error fetching source connection details:", err);
            return null;
        }
    };

    // API CALL 2: Fetch Sync Job details (from /source-connections/{id}/jobs/{job_id})
    const fetchSyncJob = async (connection: SourceConnection) => {
        if (!connection.last_sync_job_id) {
            console.log("No latest sync job ID found");
            setSyncJob(null);
            setTotalEntities(0);
            setTotalRuntime(null);
            // Still fetch entity DAGs even without job data if sync_id exists
            if (connection.sync_id) {
                await fetchEntityDags(connection.sync_id, connection);
            }
            return;
        }

        try {
            console.log("Fetching sync job details...");
            const response = await apiClient.get(`/source-connections/${connection.id}/jobs/${connection.last_sync_job_id}`);

            if (!response.ok) {
                console.error(`Failed to fetch job with ID ${connection.last_sync_job_id}, status: ${response.status}`);
                setSyncJob(null);
                setTotalEntities(0);
                setTotalRuntime(null);
                // Still fetch entity DAGs even when job fetch fails if sync_id exists
                if (connection.sync_id) {
                    await fetchEntityDags(connection.sync_id, connection);
                }
                return;
            }

            const jobData = await response.json();
            console.log("Sync job data received:", jobData);
            setSyncJob(jobData);

            // Calculate runtime for this job (using sync job timestamps)
            if (jobData.started_at && (jobData.completed_at || jobData.failed_at)) {
                const endTime = jobData.completed_at || jobData.failed_at;
                const runtime = new Date(endTime).getTime() - new Date(jobData.started_at).getTime();
                setTotalRuntime(runtime);
            }

            // Always fetch entity DAGs if we have sync_id (regardless of job data)
            if (connection.sync_id) {
                await fetchEntityDags(connection.sync_id, connection);
            }
        } catch (err) {
            console.error("Error fetching sync job:", err);
            setSyncJob(null);
            setTotalEntities(0);
            setTotalRuntime(null);
            // Still fetch entity DAGs even on error if sync_id exists
            if (connection.sync_id) {
                await fetchEntityDags(connection.sync_id, connection);
            }
        }
    };

    // API CALL 3: Fetch Entity DAGs (from /dag/sync/{sync_id}/entity_dags)
    const fetchEntityDags = async (syncId: string, connection: SourceConnection) => {
        try {
            console.log("Fetching entity DAGs for:", connection.short_name);
            const response = await apiClient.get(`/dag/sync/${syncId}/entity_dags`);

            if (!response.ok) {
                throw new Error('Failed to load entity DAGs');
            }

            const data = await response.json();
            setEntityDags(data);
            console.log('Entity DAGs loaded for', connection.short_name, ':', data);

            // Process DAGs with the passed connection data (not from state!)
            if (data.length > 0) {
                data.forEach(dag => {
                    dag.sourceShortName = connection.short_name;
                    const sourceNode = dag.nodes.find(node => node.type === 'source');
                    if (sourceNode) {
                        sourceNode.connection_id = connection.connection_id;
                    }
                });
            }
        } catch (error) {
            console.error('Error fetching entity DAGs:', error);
        }
    };

    // Main data loading function
    const loadAllData = async () => {
        setIsLoading(true);
        try {
            // Clear previous data to ensure clean state
            setEntityDags([]);
            setSelectedEntity('');
            setEntityDict({});
            setNodes([]);
            setEdges([]);

            // Step 1: Fetch source connection
            const connection = await fetchSourceConnection();

            // Step 2: If successful, fetch sync job
            if (connection) {
                await fetchSyncJob(connection);
            }
        } finally {
            setIsLoading(false);
        }
    };

    // API CALL 4: Run sync job (POST /source-connections/{id}/run)
    const handleRunSync = async () => {
        if (!sourceConnection?.id) {
            toast({
                title: "Error",
                description: "No source connection selected",
                variant: "destructive"
            });
            return;
        }

        try {
            setIsInitiatingSyncJob(true);
            console.log("Starting sync job...");
            const response = await apiClient.post(`/source-connections/${sourceConnection.id}/run`);

            if (!response.ok) {
                throw new Error("Failed to start sync job");
            }

            const newJob = await response.json();
            console.log("New sync job started:", newJob);
            setSyncJob(newJob);

            toast({
                title: "Success",
                description: "Sync job started successfully",
            });

            // Reload all data after a short delay to get updated status
            setTimeout(() => {
                loadAllData();
            }, 2000);

        } catch (error) {
            console.error("Error running sync:", error);
            toast({
                title: "Error",
                description: "Failed to start sync job",
                variant: "destructive"
            });
        } finally {
            setIsInitiatingSyncJob(false);
        }
    };

    // Helper function to extract entity names from DAGs
    const extractEntityNamesFromDags = useCallback((dags: Dag[], sourceName: string): Record<string, number> => {
        const entityDict: Record<string, number> = {};

        dags.forEach(dag => {
            // Extract the entity name from the DAG name
            if (dag.name) {
                // First remove " DAG" suffix if present
                const nameWithoutDagSuffix = dag.name.replace(/ DAG$/, '');
                // Then clean the entity name (removes source prefix and "Entity" suffix)
                const cleanedName = cleanEntityName(nameWithoutDagSuffix, sourceName);

                // Add to dictionary if we got a valid cleaned name
                if (cleanedName) {
                    entityDict[cleanedName] = 0; // Initialize with zero
                }
            }
        });

        console.log('Extracted entities from DAGs:', entityDict, 'source:', sourceName);
        return entityDict;
    }, []);

    // Entity dictionary processing (uses sync job data or DAG structure as fallback)
    const updateEntityDictionary = useCallback(() => {
        const entitiesEncountered = syncJob?.entities_encountered;

        // Get source name from entityDags
        const sourceName = entityDags[0]?.nodes
            ?.filter(node => node.type === 'source')
            ?.map(node => node.name)[0] || '';

        // If we have job data with actual entities_encountered data, use that
        if (entitiesEncountered && Object.keys(entitiesEncountered).length > 0 && entityDags.length > 0) {
            // Process the entities_encountered data with source name
            const cleanedDict = Object.entries(entitiesEncountered).reduce((acc, [key, value]) => {
                const cleanedName = cleanEntityName(key, sourceName);
                acc[cleanedName] = value as number;
                return acc;
            }, {} as Record<string, number>);

            console.log('Created cleaned entity dictionary from job data:', cleanedDict, 'with source name:', sourceName);

            if (Object.keys(cleanedDict).length > 0) {
                setEntityDict(cleanedDict);

                // Select first entity if none selected
                if (!selectedEntity) {
                    setSelectedEntity(Object.keys(cleanedDict)[0]);
                }
            }
        }
        // Fallback: If no job data (or empty entities_encountered) but we have DAGs, create entity dict with zero values
        else if (entityDags.length > 0) {
            const fallbackDict = extractEntityNamesFromDags(entityDags, sourceName);

            console.log('Created fallback entity dictionary from DAG structure:', fallbackDict, 'with source name:', sourceName);

            if (Object.keys(fallbackDict).length > 0) {
                setEntityDict(fallbackDict);

                // Select first entity if none selected
                if (!selectedEntity) {
                    setSelectedEntity(Object.keys(fallbackDict)[0]);
                }
            }
        }
    }, [syncJob?.entities_encountered, entityDags, selectedEntity, extractEntityNamesFromDags]);

    // Time formatting utilities
    const formatTotalRuntime = (ms: number) => {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    };

    const formatTimeSince = (dateStr: string) => {
        const now = new Date();
        const date = new Date(dateStr);
        const diffMs = now.getTime() - date.getTime();
        const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
        const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

        if (diffHrs > 24) {
            const days = Math.floor(diffHrs / 24);
            return `${days}d ago`;
        } else if (diffHrs > 0) {
            return `${diffHrs}h ${diffMins}m ago`;
        } else {
            return `${diffMins}m ago`;
        }
    };

    // Initial data loading
    useEffect(() => {
        loadAllData();
    }, [sourceConnectionId]);

    // Entity data processing (uses sync job data)
    useEffect(() => {
        const totalEntitiesCount = syncJobData.inserted + syncJobData.updated + syncJobData.kept + syncJobData.skipped - syncJobData.deleted;
        setTotalEntities(totalEntitiesCount);
    }, [syncJobData]);

    // Entity dictionary maintenance
    useEffect(() => {
        updateEntityDictionary();
    }, [updateEntityDictionary]);

    // Entity selection and DAG processing
    useEffect(() => {
        if (!selectedEntity || entityDags.length === 0) {
            setSelectedDag(null);
            return;
        }

        // Find DAG that matches the selected entity
        const exactMatch = entityDags.find(dag =>
            dag.name && dag.name.includes(selectedEntity + "Entity")
        );
        const matchingDag = exactMatch || entityDags.find(dag =>
            dag.name && dag.name.includes(selectedEntity)
        );

        if (matchingDag) {
            setSelectedDag(matchingDag);
            console.log(`Selected DAG for entity "${selectedEntity}":`, matchingDag);
        } else {
            console.warn(`No DAG found for entity "${selectedEntity}"`);
            setSelectedDag(null);
        }
    }, [selectedEntity, entityDags]);

    // DAG visualization
    useEffect(() => {
        convertDagToFlowGraph(selectedDag, setNodes, setEdges);
    }, [selectedDag, setNodes, setEdges]);

    // ReactFlow visualization adjustments
    useEffect(() => {
        if (reactFlowInstance) {
            reactFlowInstance.fitView({
                padding: 0.2,
                duration: 0
            });
        }
    }, [nodes, edges, reactFlowInstance]);

    // Handle resizing
    useEffect(() => {
        if (!reactFlowInstance || !flowContainerRef.current) return;

        const resizeObserver = new ResizeObserver(() => {
            setTimeout(() => {
                reactFlowInstance.fitView({
                    padding: 0.2,
                    duration: 0
                });
            }, 0);
        });

        resizeObserver.observe(flowContainerRef.current);

        return () => {
            if (flowContainerRef.current) {
                resizeObserver.unobserve(flowContainerRef.current);
            }
        };
    }, [reactFlowInstance]);

    if (!sourceConnection) {
        return (
            <div className="w-full py-6">
                <div className="flex items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2">Loading connection details...</span>
                </div>
            </div>
        );
    }

    return (
        <div className={cn(isDark ? "text-foreground" : "")}>
            <div className="py-2 space-y-3 mt-4">
                {/* Display appropriate card based on error status - FROM SYNC JOB */}
                {syncJob?.error ? (
                    <SyncErrorCard
                        error={syncJob.error}
                        onRunSync={handleRunSync}
                        isInitiatingSyncJob={isInitiatingSyncJob}
                        isSyncJobRunning={false}
                        isDark={isDark}
                    />
                ) : (
                    <div className="space-y-3">
                        {/* Status Dashboard - positioned above the cards */}
                        <div className="flex gap-2 flex-wrap">
                            {/* Entities Card - FROM SYNC JOB */}
                            <div className={cn(
                                "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[80px]",
                                isDark
                                    ? "bg-gray-800/60 border border-gray-700/50"
                                    : "bg-white border border-gray-100"
                            )}>
                                <div className="text-[10px] uppercase tracking-wider font-medium opacity-60">
                                    Entities
                                </div>
                                <div className="text-sm font-semibold">
                                    {totalEntities.toLocaleString()}
                                </div>
                            </div>

                            {/* Status Card - FROM SYNC JOB */}
                            <div className={cn(
                                "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[90px]",
                                isDark
                                    ? "bg-gray-800/60 border border-gray-700/50"
                                    : "bg-white border border-gray-100"
                            )}>
                                <div className="text-[10px] uppercase tracking-wider font-medium opacity-60">
                                    Status
                                </div>
                                <div className="text-sm font-medium flex items-center gap-1">
                                    <span className={`inline-flex h-2 w-2 rounded-full
                                        ${syncJob?.status === 'completed' ? 'bg-green-500' :
                                            syncJob?.status === 'failed' ? 'bg-red-500' :
                                                syncJob?.status === 'running' ? 'bg-blue-500 animate-pulse' :
                                                    syncJob?.status === 'cancelling' ? 'bg-amber-500 animate-pulse' :
                                                        syncJob?.status === 'cancelled' ? 'bg-gray-400' :
                                                            syncJob?.status === 'pending' ? 'bg-amber-500' :
                                                                'bg-gray-300'}`}
                                    />
                                    <span className="capitalize text-xs">
                                        {syncJob?.status || 'Not run'}
                                    </span>
                                </div>
                            </div>

                            {/* Runtime Card - FROM SYNC JOB */}
                            <div className={cn(
                                "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[80px]",
                                isDark
                                    ? "bg-gray-800/60 border border-gray-700/50"
                                    : "bg-white border border-gray-100"
                            )}>
                                <div className="text-[10px] uppercase tracking-wider font-medium opacity-60">
                                    Runtime
                                </div>
                                <div className="text-sm font-medium">
                                    {totalRuntime ? formatTotalRuntime(totalRuntime) : 'N/A'}
                                </div>
                            </div>

                            {/* Schedule Card - FROM SOURCE CONNECTION */}
                            <div className={cn(
                                "rounded-lg p-2 flex items-center gap-2 shadow-sm transition-all duration-200 h-8 min-w-[100px]",
                                isDark
                                    ? "bg-gray-800/60 border border-gray-700/50"
                                    : "bg-white border border-gray-100"
                            )}>
                                <div className="text-[10px] uppercase tracking-wider font-medium opacity-60">
                                    Schedule
                                </div>
                                <div className="flex items-center gap-1">
                                    <Clock className={cn(
                                        "w-3 h-3",
                                        isDark ? "text-gray-400" : "text-gray-500"
                                    )} />
                                    <div className="text-sm font-medium">
                                        {sourceConnection.cron_schedule ? 'Scheduled' : 'Manual'}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Entity Graph and Sync Progress Cards */}
                        <SimplifiedSyncDagCard
                            sourceConnection={sourceConnection}
                            entityDict={entityDict}
                            selectedEntity={selectedEntity}
                            setSelectedEntity={setSelectedEntity}
                            nodes={nodes}
                            edges={edges}
                            onNodesChange={onNodesChange}
                            onEdgesChange={onEdgesChange}
                            reactFlowInstance={reactFlowInstance}
                            setReactFlowInstance={setReactFlowInstance}
                            flowContainerRef={flowContainerRef}
                            syncJobData={syncJobData}
                            onRunSync={handleRunSync}
                            isInitiatingSyncJob={isInitiatingSyncJob}
                            isDark={isDark}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

export default SimplifiedSourceConnectionDetailView;
