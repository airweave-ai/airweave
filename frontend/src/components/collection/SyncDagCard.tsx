import { Play } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import ReactFlow from 'reactflow';
import 'reactflow/dist/style.css';
import { SourceNode } from '@/components/sync/nodes/SourceNode';
import { TransformerNode } from '@/components/sync/nodes/TransformerNode';
import { DestinationNode } from '@/components/sync/nodes/DestinationNode';
import { EntityNode } from '@/components/sync/nodes/EntityNode';

// Define node types for ReactFlow
const nodeTypes = {
    sourceNode: SourceNode,
    transformerNode: TransformerNode,
    destinationNode: DestinationNode,
    entityNode: EntityNode
};

export interface SourceConnection {
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
    cron_schedule?: string;
    next_scheduled_run?: string;
}

export interface SyncDagCardProps {
    selectedConnection: SourceConnection;
    stableEntityDict: Record<string, number>;
    selectedEntity: string;
    setSelectedEntity: (entity: string) => void;
    nodes: any[];
    edges: any[];
    onNodesChange: any;
    onEdgesChange: any;
    reactFlowInstance: any;
    setReactFlowInstance: any;
    flowContainerRef: React.RefObject<HTMLDivElement>;
    entityData: {
        inserted: number;
        updated: number;
        deleted: number;
        kept: number;
        skipped: number;
    };
    total: number;
    onRunSync: () => void;
    isInitiatingSyncJob: boolean;
    isSyncJobRunning: boolean;
    isDark: boolean;
}

export const SyncDagCard = ({
    selectedConnection,
    stableEntityDict,
    selectedEntity,
    setSelectedEntity,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    reactFlowInstance,
    setReactFlowInstance,
    flowContainerRef,
    entityData,
    total,
    onRunSync,
    isInitiatingSyncJob,
    isSyncJobRunning,
    isDark
}: SyncDagCardProps) => {
    return (
        <Card className={cn(
            "overflow-hidden border rounded-lg",
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
                            disabled={isInitiatingSyncJob || isSyncJobRunning}
                        >
                            <Play className="h-3.5 w-3.5" />
                            {isInitiatingSyncJob ? 'Starting...' : isSyncJobRunning ? 'Running...' : 'Run Sync'}
                        </Button>
                    </div>
                </div>

                <div className="flex flex-wrap gap-1.5 mt-3 mb-1 min-h-[2.25rem] transition-all">
                    {Object.keys(stableEntityDict).length > 0 ?
                        Object.keys(stableEntityDict)
                            .sort()
                            .map((key) => {
                                const isSelected = key === selectedEntity;

                                return (
                                    <Button
                                        key={key}
                                        variant="outline"
                                        className={cn(
                                            "flex items-center gap-1.5 h-7 py-0 px-2 text-[13px] min-w-[90px]",
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
                                        {key}
                                        <Badge
                                            variant="outline"
                                            className={cn(
                                                "ml-1 pointer-events-none text-[11px] px-1.5 font-normal h-5",
                                                isSelected
                                                    ? isDark
                                                        ? "bg-gray-600 text-gray-200 border-gray-500"
                                                        : "bg-blue-100 text-blue-700 border-blue-200"
                                                    : isDark
                                                        ? "bg-gray-700 text-gray-300 border-gray-600"
                                                        : "bg-gray-50 text-gray-600 border-gray-200"
                                            )}
                                        >
                                            {stableEntityDict[key]}
                                        </Badge>
                                    </Button>
                                );
                            })
                        : null
                    }
                </div>
            </CardHeader>
            <CardContent className="p-0 pb-0">
                <div
                    ref={flowContainerRef}
                    className="h-[320px] w-full overflow-hidden pointer-events-none [&_.react-flow__handle]:!cursor-default [&_*]:!cursor-default"
                    style={{ minHeight: '320px' }}
                >
                    <ReactFlow
                        key={selectedConnection.id || 'no-connection'}
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
                        proOptions={{ hideAttribution: true }}
                    />
                </div>

                <div className={cn(
                    "border-t w-full mx-auto my-2",
                    isDark ? "border-gray-700/50" : "border-gray-200"
                )} />

                <div className="px-3 pb-3 pt-1">
                    <h3 className={cn(
                        "text-base font-medium mb-4",
                        isDark ? "text-gray-200" : "text-gray-700"
                    )}>
                        Sync Progress
                    </h3>

                    <div className={cn(
                        "relative w-full h-3 rounded-md overflow-hidden mb-6",
                        isDark ? "bg-gray-700/50" : "bg-gray-100"
                    )}>
                        <div
                            className="absolute left-0 top-0 h-3 bg-green-500"
                            style={{ width: `${total > 0 ? (entityData.inserted / total) * 100 : 0}%` }}
                        />
                        <div
                            className="absolute top-0 h-3 bg-cyan-500"
                            style={{
                                left: `${total > 0 ? (entityData.inserted / total) * 100 : 0}%`,
                                width: `${total > 0 ? (entityData.updated / total) * 100 : 0}%`
                            }}
                        />
                        <div
                            className="absolute top-0 h-3 bg-primary"
                            style={{
                                left: `${total > 0 ? ((entityData.inserted + entityData.updated) / total) * 100 : 0}%`,
                                width: `${total > 0 ? (entityData.kept / total) * 100 : 0}%`
                            }}
                        />
                        <div
                            className="absolute top-0 h-3 bg-red-500"
                            style={{
                                left: `${total > 0 ? ((entityData.inserted + entityData.updated + entityData.kept) / total) * 100 : 0}%`,
                                width: `${total > 0 ? (entityData.deleted / total) * 100 : 0}%`
                            }}
                        />
                        <div
                            className="absolute top-0 h-3 bg-yellow-500"
                            style={{
                                left: `${total > 0 ? ((entityData.inserted + entityData.updated + entityData.kept + entityData.deleted) / total) * 100 : 0}%`,
                                width: `${total > 0 ? (entityData.skipped / total) * 100 : 0}%`
                            }}
                        />
                    </div>

                    <div className="grid grid-cols-5 gap-3 mt-5 min-h-[5rem]">
                        <div className={cn(
                            "rounded-md p-3 flex flex-col items-center",
                            isDark ? "bg-gray-700/30" : "bg-white border border-gray-100"
                        )}>
                            <div className="flex items-center space-x-1 mb-1">
                                <span className="w-3 h-3 block bg-green-500 rounded-full" />
                                <span className="text-xs font-medium">Inserted</span>
                            </div>
                            <span className="text-lg font-semibold">{entityData.inserted.toLocaleString()}</span>
                        </div>

                        <div className={cn(
                            "rounded-md p-3 flex flex-col items-center",
                            isDark ? "bg-gray-700/30" : "bg-white border border-gray-100"
                        )}>
                            <div className="flex items-center space-x-1 mb-1">
                                <span className="w-3 h-3 block bg-cyan-500 rounded-full" />
                                <span className="text-xs font-medium">Updated</span>
                            </div>
                            <span className="text-lg font-semibold">{entityData.updated.toLocaleString()}</span>
                        </div>

                        <div className={cn(
                            "rounded-md p-3 flex flex-col items-center",
                            isDark ? "bg-gray-700/30" : "bg-white border border-gray-100"
                        )}>
                            <div className="flex items-center space-x-1 mb-1">
                                <span className="w-3 h-3 block bg-primary rounded-full" />
                                <span className="text-xs font-medium">Kept</span>
                            </div>
                            <span className="text-lg font-semibold">{entityData.kept.toLocaleString()}</span>
                        </div>

                        <div className={cn(
                            "rounded-md p-3 flex flex-col items-center",
                            isDark ? "bg-gray-700/30" : "bg-white border border-gray-100"
                        )}>
                            <div className="flex items-center space-x-1 mb-1">
                                <span className="w-3 h-3 block bg-red-500 rounded-full" />
                                <span className="text-xs font-medium">Deleted</span>
                            </div>
                            <span className="text-lg font-semibold">{entityData.deleted.toLocaleString()}</span>
                        </div>

                        <div className={cn(
                            "rounded-md p-3 flex flex-col items-center",
                            isDark ? "bg-gray-700/30" : "bg-white border border-gray-100"
                        )}>
                            <div className="flex items-center space-x-1 mb-1">
                                <span className="w-3 h-3 block bg-yellow-500 rounded-full" />
                                <span className="text-xs font-medium">Skipped</span>
                            </div>
                            <span className="text-lg font-semibold">{entityData.skipped.toLocaleString()}</span>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
