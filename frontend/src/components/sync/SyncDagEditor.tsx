import { useCallback, useEffect, useState, useRef } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  Node,
  NodeTypes,
  addEdge,
  useEdgesState,
  useNodesState,
  Panel,
  Connection,
  ConnectionMode,
  Position,
  useReactFlow,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import { useToast } from "@/components/ui/use-toast";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { LayoutGrid, Save } from "lucide-react";
import { SourceNode } from "./nodes/SourceNode";
import { DestinationNode } from "./nodes/DestinationNode";
import { EntityNode } from "./nodes/EntityNode";
import { ButtonEdge } from "./edges/ButtonEdge";
import { BlankEdge } from "./edges/BlankEdge";
import { NonPlussableEdge } from "./edges/NonPlussableEdge";
import dagre from "dagre";
import {
  Dag,
  FlowNode,
  FlowEdge,
  toFlowNodes,
  toFlowEdges,
  toDagNodes,
  toDagEdges,
} from "@/components/sync/dag";
import { TransformerNode } from "./nodes/TransformerNode";
import { v4 as uuidv4 } from 'uuid';

// Define custom node types
const nodeTypes: NodeTypes = {
  source: SourceNode,
  destination: DestinationNode,
  entity: EntityNode,
  transformer: TransformerNode,
};

const edgeTypes = {
  button: ButtonEdge,
  blank: BlankEdge,
  nonplussable: NonPlussableEdge,
};

interface SyncDagEditorProps {
  syncId: string;
  initialDag?: Dag;
  onSave?: () => void;
}

const nodeWidth = 200;
const nodeHeight = 50;

// Add these helper functions at the top level
const analyzeGraphStructure = (nodes: FlowNode[], edges: FlowEdge[]) => {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: 'LR' });

  // Add all nodes and edges to the graph
  nodes.forEach(node => graph.setNode(node.id, {}));
  edges.forEach(edge => graph.setEdge(edge.source, edge.target));

  // Calculate the basic layout to get rank information
  dagre.layout(graph);

  // Get all nodes with their ranks
  const nodeRanks = new Map<number, string[]>();
  nodes.forEach(node => {
    const rank = graph.node(node.id).x;
    if (!nodeRanks.has(rank)) {
      nodeRanks.set(rank, []);
    }
    nodeRanks.get(rank)?.push(node.id);
  });

  // Sort ranks and count columns
  const uniqueRanks = Array.from(nodeRanks.keys()).sort((a, b) => a - b);
  const columnCount = uniqueRanks.length;

  // Analyze column density (nodes per column)
  const columnDensities = uniqueRanks.map(rank => nodeRanks.get(rank)?.length || 0);
  const maxNodesInColumn = Math.max(...columnDensities);
  const avgNodesInColumn = columnDensities.reduce((sum, count) => sum + count, 0) / columnCount;

  return {
    columnCount,
    maxNodesInColumn,
    avgNodesInColumn,
    columnDensities,
  };
};

const calculateLayoutParameters = (graphStructure: ReturnType<typeof analyzeGraphStructure>) => {
  const { columnCount, maxNodesInColumn, avgNodesInColumn } = graphStructure;

  // Increase base values for more spread
  const baseRankSep = 120;  // Increased from 120
  const baseNodeSep = 80;

  // Calculate scaling factors based on graph complexity
  const rankSepScaleFactor = Math.max(0.7, Math.min(1, 3 / columnCount));  // Increased minimum from 0.5
  const nodeSepScaleFactor = Math.max(0.6, Math.min(1, 3 / maxNodesInColumn));

  // Calculate adjusted values
  const ranksep = Math.round(baseRankSep * rankSepScaleFactor);
  const nodesep = Math.round(baseNodeSep * nodeSepScaleFactor);

  // Calculate edge weights based on graph density
  const denseGraph = avgNodesInColumn > 2 || columnCount > 4;
  const blankEdgeWeight = denseGraph ? 6 : 4;
  const buttonEdgeWeight = denseGraph ? 2 : 1;

  return {
    ranksep,
    nodesep,
    blankEdgeWeight,
    buttonEdgeWeight,
    marginx: 0,
    marginy: 0,
  };
};

const getLayoutedElements = (nodes: FlowNode[], edges: FlowEdge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Analyze graph structure and get optimal layout parameters
  const graphStructure = analyzeGraphStructure(nodes, edges);
  const layoutParams = calculateLayoutParameters(graphStructure);

  dagreGraph.setGraph({
    rankdir: 'LR',
    nodesep: layoutParams.nodesep,
    ranksep: layoutParams.ranksep,
    align: 'DL',
    marginx: layoutParams.marginx,
    marginy: layoutParams.marginy,
  });

  // Add nodes to dagre
  nodes.forEach((node) => {
    // Use consistent 80x80 dimensions for layout calculations
    const nodeWidth = 80;  // Consistent width for layout
    const nodeHeight = 80; // Consistent height for layout
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  // Add edges to dagre with specific weights and constraints
  edges.forEach((edge) => {
    const sourceNode = nodes.find(n => n.id === edge.source);
    const targetNode = nodes.find(n => n.id === edge.target);

    if (sourceNode && targetNode) {
      // For blank edges (source to entity, transformer to entity)
      if (edge.type === 'blank') {
        dagreGraph.setEdge(edge.source, edge.target, {
          weight: layoutParams.blankEdgeWeight,
          minlen: 2  // Increased from 1
        });
      }
      // For button edges
      else {
        // If target is a transformer, give more space
        if (targetNode.type === 'transformer') {
          dagreGraph.setEdge(edge.source, edge.target, {
            weight: layoutParams.buttonEdgeWeight,
            minlen: Math.min(3, graphStructure.columnCount > 4 ? 2 : 3)  // Increased spacing
          });
        }
        // If source is an entity going to destination
        else if (sourceNode.type === 'entity' && targetNode.type === 'destination') {
          dagreGraph.setEdge(edge.source, edge.target, {
            weight: layoutParams.buttonEdgeWeight,
            minlen: Math.min(3, graphStructure.columnCount > 4 ? 2 : 3)  // Increased spacing
          });
        }
        // Default button edge
        else {
          dagreGraph.setEdge(edge.source, edge.target, {
            weight: layoutParams.buttonEdgeWeight,
            minlen: Math.min(3, graphStructure.columnCount > 4 ? 2 : 3)  // Increased spacing
          });
        }
      }
    }
  });

  // Calculate layout
  dagre.layout(dagreGraph);

  // Rest of the positioning code...
  const positions = new Map();
  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    positions.set(node.id, {
      x: nodeWithPosition.x,
      y: nodeWithPosition.y
    });
  });

  // For source and destination nodes, calculate the center position based on their connected nodes
  const layoutedNodes = nodes.map((node) => {
    const pos = positions.get(node.id);
    let finalY = pos.y;

    if (node.type === 'source') {
      // Find all nodes this source connects to
      const targetNodes = edges
        .filter(edge => edge.source === node.id)
        .map(edge => positions.get(edge.target)?.y)
        .filter(y => y !== undefined);

      if (targetNodes.length > 0) {
        finalY = targetNodes.reduce((sum, y) => sum + y, 0) / targetNodes.length;
      }
    } else if (node.type === 'destination') {
      // Find all nodes that connect to this destination
      const sourceNodes = edges
        .filter(edge => edge.target === node.id)
        .map(edge => positions.get(edge.source)?.y)
        .filter(y => y !== undefined);

      if (sourceNodes.length > 0) {
        finalY = sourceNodes.reduce((sum, y) => sum + y, 0) / sourceNodes.length;
      }
    }

    return {
      ...node,
      targetPosition: 'left',
      sourcePosition: 'right',
      position: {
        x: pos.x - nodeWidth / 2,
        y: finalY - nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

// Helper to determine edge type based on connection
const getEdgeType = (sourceNode: FlowNode, targetNode: FlowNode): 'button' | 'blank' | 'nonplussable' => {
  // Sources to entities and transformers to entities use blank edges
  if (
    (sourceNode.type === 'source' && targetNode.type === 'entity') ||
    (sourceNode.type === 'transformer' && targetNode.type === 'entity')
  ) {
    return 'blank';
  }

  // File entities to transformers use nonplussable edges
  if (sourceNode.type === 'entity' && targetNode.type === 'transformer') {
    // Check if the source is a file entity by looking for common file entity naming patterns
    const fileEntityPatterns = ['File', 'PDF', 'Document', 'Attachment'];
    const isFileEntity = fileEntityPatterns.some(pattern =>
      sourceNode.data.name.includes(pattern)
    );

    if (isFileEntity) {
      return 'nonplussable';
    }
  }

  // All other connections use button edges
  return 'button';
};

const SyncDagEditorInner = ({ syncId, initialDag, onSave }: SyncDagEditorProps) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();
  const { fitView, addNodes, addEdges } = useReactFlow();
  const isInitialLoad = useRef(true);

  const applyLayout = useCallback(() => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(nodes as FlowNode[], edges as FlowEdge[]);
    setNodes([...layoutedNodes]);
    setEdges([...layoutedEdges]);
    fitView({ padding: 0.2 });
  }, [nodes, edges, setNodes, setEdges, fitView]);

  // Apply layout when nodes or edges change (except during initial load)
  useEffect(() => {
    if (!isInitialLoad.current && nodes.length > 0) {
      const timeoutId = setTimeout(() => {
        applyLayout();
      }, 50);
      return () => clearTimeout(timeoutId);
    }
  }, [nodes.length, edges.length]);

  // Load initial DAG
  useEffect(() => {
    const loadDag = async () => {
      try {
        isInitialLoad.current = true;

        // If we have initial DAG data, use it
        if (initialDag) {
          const flowNodes = toFlowNodes(initialDag.nodes);
          const initialEdges = initialDag.edges.map(edge => {
            const sourceNode = flowNodes.find(n => n.id === edge.from_node_id);
            const targetNode = flowNodes.find(n => n.id === edge.to_node_id);
            const edgeType = sourceNode && targetNode ? getEdgeType(sourceNode, targetNode) : 'button';
            return {
              source: edge.from_node_id,
              target: edge.to_node_id,
              type: edgeType,
              id: edge.id
            };
          });

          setNodes(flowNodes as Node[]);
          setEdges(initialEdges as Edge[]);

          // Apply initial layout
          const { nodes: layoutedNodes } = getLayoutedElements(flowNodes, initialEdges);
          setNodes([...layoutedNodes] as Node[]);

          fitView({ padding: 0.2 });
          return;
        }

        // Otherwise fetch from API
        const resp = await apiClient.get(`/sync/${syncId}/dag`);
        if (!resp.ok) throw new Error("Failed to load DAG");
        const data: Dag = await resp.json();

        const flowNodes = toFlowNodes(data.nodes);
        const initialEdges = data.edges.map(edge => {
          const sourceNode = flowNodes.find(n => n.id === edge.from_node_id);
          const targetNode = flowNodes.find(n => n.id === edge.to_node_id);
          const edgeType = sourceNode && targetNode ? getEdgeType(sourceNode, targetNode) : 'button';
          return {
            source: edge.from_node_id,
            target: edge.to_node_id,
            type: edgeType,
            id: edge.id
          };
        });

        setNodes(flowNodes as Node[]);
        setEdges(initialEdges as Edge[]);

        // Apply initial layout
        const { nodes: layoutedNodes } = getLayoutedElements(flowNodes, initialEdges);
        setNodes([...layoutedNodes] as Node[]);

        fitView({ padding: 0.2 });
      } catch (err: any) {
        toast({
          variant: "destructive",
          title: "Failed to load DAG",
          description: err.message || String(err),
        });
      } finally {
        isInitialLoad.current = false;
      }
    };

    loadDag();
  }, [initialDag, syncId, setNodes, setEdges, toast, fitView]);

  const onConnect = useCallback(
    (params: Connection) => {
      const sourceNode = nodes.find(n => n.id === params.source);
      const targetNode = nodes.find(n => n.id === params.target);

      if (sourceNode && targetNode) {
        // Prevent entity to entity connections
        if (sourceNode.type === 'entity' && targetNode.type === 'entity') {
          return;
        }

        // Set the appropriate edge type
        const edgeType = getEdgeType(sourceNode as FlowNode, targetNode as FlowNode);
        setEdges((eds) => addEdge({ ...params, type: edgeType }, eds));
      }
    },
    [nodes, setEdges]
  );

  // Add this new function to handle transformer creation
  const handleTransformerAdd = useCallback((
    transformerId: string,
    transformerName: string,
    sourceNodeId: string,
    targetNodeId: string,
    sourceEdge: Edge
  ) => {
    // Disable layout updates temporarily
    isInitialLoad.current = true;

    // Create transformer node
    const transformerNode: Node = {
      id: uuidv4(),
      type: 'transformer',
      data: {
        name: transformerName,
        transformer_id: transformerId,
      },
      position: { x: 0, y: 0 }, // Will be set by layout
    };

    // Create chunk nodes
    const chunk1: Node = {
      id: uuidv4(),
      type: 'entity',
      data: {
        name: 'Entity 1',
      },
      position: { x: 0, y: 0 }, // Will be set by layout
    };

    const chunk2: Node = {
      id: uuidv4(),
      type: 'entity',
      data: {
        name: 'Entity 2',
      },
      position: { x: 0, y: 0 }, // Will be set by layout
    };

    // Create new edges with appropriate types
    const newEdges: Edge[] = [
      // Edge from source to transformer (button type)
      {
        id: uuidv4(),
        source: sourceNodeId,
        target: transformerNode.id,
        type: 'button',
      },
      // Edges from transformer to entities (blank type)
      {
        id: uuidv4(),
        source: transformerNode.id,
        target: chunk1.id,
        type: 'blank',
      },
      {
        id: uuidv4(),
        source: transformerNode.id,
        target: chunk2.id,
        type: 'blank',
      },
      // Edges from entities to target (button type)
      {
        id: uuidv4(),
        source: chunk1.id,
        target: targetNodeId,
        type: 'button',
      },
      {
        id: uuidv4(),
        source: chunk2.id,
        target: targetNodeId,
        type: 'button',
      },
    ];

    // Update all state at once
    const updatedEdges = edges.filter(e => e.id !== sourceEdge.id).concat(newEdges);
    const updatedNodes = [...nodes, transformerNode, chunk1, chunk2];

    // Calculate new layout
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      updatedNodes as FlowNode[],
      updatedEdges as FlowEdge[]
    );

    // Apply all updates at once
    setNodes([...layoutedNodes] as Node[]);
    setEdges([...layoutedEdges] as Edge[]);

    // Re-enable layout updates and fit view
    setTimeout(() => {
      isInitialLoad.current = false;
      fitView({ padding: 0.2 });
    }, 50);
  }, [nodes, edges, setNodes, setEdges, fitView]);

  // Handle saving the DAG
  const handleSave = async () => {
    setIsLoading(true);
    try {
      const dagData: Dag = {
        id: initialDag?.id || '',
        name: initialDag?.name || "DAG from UI",
        description: initialDag?.description || "Created via DAG editor",
        sync_id: syncId,
        nodes: toDagNodes(nodes),
        edges: toDagEdges(edges),
      };

      const resp = await apiClient.put(`/dag/sync/${syncId}/dag`, null, dagData);
      if (!resp.ok) throw new Error("Failed to save DAG");

      toast({
        title: "DAG saved successfully",
      });

      onSave?.();
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Failed to save DAG",
        description: err.message || String(err),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full space-y-2">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-semibold">Sync DAG Editor</h3>
        <span className="bg-yellow-500/10 text-yellow-500 text-xs px-2 py-1 rounded-full">Beta</span>
      </div>
      <div className="w-full h-[800px] relative border rounded-lg bg-background group">
        <div className="absolute inset-0 z-50 bg-black/5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="bg-popover text-popover-foreground p-4 rounded-lg shadow-lg max-w-md text-center">
            <p>The DAG editor is coming soon! Contact us if you want to try it early.</p>
          </div>
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges.map(edge => ({
            ...edge,
            data: { onTransformerAdd: handleTransformerAdd }
          }))}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          className="bg-background rounded-lg pointer-events-none"
          defaultEdgeOptions={{
            type: 'button',
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls />
          <Panel position="top-right" className="flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={applyLayout}
              disabled
            >
              <LayoutGrid className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSave}
            >
              <Save className="w-4 h-4" />
            </Button>
          </Panel>
        </ReactFlow>
      </div>
    </div>
  );
};

export const SyncDagEditor = (props: SyncDagEditorProps) => (
  <ReactFlowProvider>
    <SyncDagEditorInner {...props} />
  </ReactFlowProvider>
);
