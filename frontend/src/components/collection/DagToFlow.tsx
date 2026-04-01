import { MarkerType } from 'reactflow';

export function dagNodeToFlowNode(dagNode, xPosition, sourceName = '') {
    // Map node type to ReactFlow node type
    const nodeTypeMap = {
        'source': 'sourceNode',
        'entity': 'entityNode',
        'transformer': 'transformerNode',
        'destination': 'destinationNode'
    };

    // Generate proper display name
    let displayName = dagNode.name;

    // Clean entity names if it's an entity node
    // Also check if the name ends with "Entity" to identify entity nodes
    if ((dagNode.type === 'entity' || dagNode.name?.endsWith('Entity')) && sourceName) {
        displayName = cleanEntityName(dagNode.name, sourceName);
    }

    // Use sourceName directly for source nodes, otherwise generate shortName from displayName
    const shortName = dagNode.type === 'source' ? sourceName : displayName.toLowerCase().replace(/\s+/g, '');

    return {
        id: dagNode.id,
        data: {
            label: displayName,
            name: displayName,
            originalName: dagNode.name, // Store original name for reference
            shortName: shortName,
            connection_id: dagNode.connection_id
        },
        position: { x: xPosition, y: 0 },
        type: nodeTypeMap[dagNode.type] || 'default',
        draggable: false
    };
}


export function dagEdgeToFlowEdge(dagEdge, isFirstEdge = false) {
    // Create a unique ID using source and target IDs
    const uniqueId = `edge-${dagEdge.from_node_id}-to-${dagEdge.to_node_id}`;

    return {
        id: uniqueId,
        source: dagEdge.from_node_id,
        target: dagEdge.to_node_id,
        // Only add arrow marker if it's not the first edge
        markerEnd: isFirstEdge ? undefined : {
            type: MarkerType.Arrow,
            width: 20,
            height: 20,
        },
        type: 'straight',
    };
}


export function convertDagToFlowGraph(dag, setNodes, setEdges) {
    if (!dag || !dag.edges || !dag.nodes) return;

    const flowNodes = []
    const flowEdges = []
    let xPosition = 0

    // Find the source node
    let currentNode = dag.nodes.find(node => node.type === 'source')
    // Use dag.sourceShortName if available, otherwise use node name
    const sourceName = dag.sourceShortName || currentNode?.name || '';

    // Process each node until we reach the end or a destination
    let isFirstEdge = true;
    while (currentNode && currentNode.type !== 'destination') {
        // Add current node to results
        flowNodes.push(dagNodeToFlowNode(currentNode, xPosition, sourceName));

        // Find the edge connecting from current node
        const nextEdge = dag.edges.find(edge => edge.from_node_id === currentNode.id);
        if (!nextEdge) break; // Exit if no more edges

        // Add edge to results with flag for first edge
        flowEdges.push(dagEdgeToFlowEdge(nextEdge, isFirstEdge));
        isFirstEdge = false;  // Set to false after first edge

        // Get the next node
        currentNode = dag.nodes.find(node => node.id === nextEdge.to_node_id);
        xPosition += 100;
    }

    // Add destination node if found
    if (currentNode && currentNode.type === 'destination') {
        flowNodes.push(dagNodeToFlowNode(currentNode, xPosition, sourceName));
    } else {
        console.error('Error: No destination node found in the DAG');
        return;
    }

    // Enrich the flow graph by adding an embedding node
    const enrichedGraph = enrichFlowGraphVisualization(flowNodes, flowEdges);

    if (enrichedGraph) {
        // Update the ReactFlow states with the enriched graph
        setNodes(enrichedGraph.nodes);
        setEdges(enrichedGraph.edges);
    } else {
        // Fallback to original graph if enrichment fails
        setNodes(flowNodes);
        setEdges(flowEdges);
    }
}


export function enrichFlowGraphVisualization(flowNodes, flowEdges) {
    // Safety checks for required nodes
    const destinationNode = flowNodes.find(node => node.type === 'destinationNode');
    const edgeToDestination = flowEdges.find(edge => edge.target === destinationNode.id);

    const nodeBeforeDestinationId = edgeToDestination.source;
    const nodeBeforeDestination = flowNodes.find(node => node.id === nodeBeforeDestinationId);

    // Filter out the direct edge to destination
    const filteredEdges = flowEdges.filter(edge => edge.id !== edgeToDestination.id);

    // Position the embedding node between the entity and destination
    const embeddingNodeXPosition = nodeBeforeDestination.position.x + 100;
    destinationNode.position.x = embeddingNodeXPosition + 100;

    // Create the embedding model node
    const embeddingNode = {
        id: 'embedding-node',
        data: {
            label: 'Embedding Model',
            name: 'Embedding Model',
            shortName: 'embedding',
            model: 'openai' // TODO: this should be determined dynamically
        },
        position: { x: embeddingNodeXPosition, y: 0 },
        type: 'transformerNode',
        draggable: false,
    };

    // Create edge from entity to embedding model
    const edgeToEmbedding = {
        id: `e-${nodeBeforeDestinationId}-${embeddingNode.id}`,
        source: nodeBeforeDestinationId,
        target: embeddingNode.id,
        markerEnd: {
            type: MarkerType.Arrow,
            width: 20,
            height: 20,
        },
        type: 'straight'
    };

    // Create edge from embedding model to destination
    const edgeFromEmbedding = {
        id: `e-${embeddingNode.id}-${destinationNode.id}`,
        source: embeddingNode.id,
        target: destinationNode.id,
        markerEnd: {
            type: MarkerType.Arrow,
            width: 20,
            height: 20,
        },
        type: 'straight'
    };

    // Update transformer node labels for better display names
    const transformerNodes = flowNodes.filter(node => node.type === 'transformerNode');
    transformerNodes.forEach(transformerNode => {
        const originalName = transformerNode.data.originalName || transformerNode.data.name;

        // Map transformer names to better display names
        if (originalName === 'Web Fetcher') {
            transformerNode.data.label = 'Crawler';
            transformerNode.data.name = 'Crawler';
            transformerNode.data.shortName = 'crawler';
            transformerNode.data.model = 'firecrawl';
        } else if (originalName === 'File Chunker') {
            transformerNode.data.label = 'Chunker';
            transformerNode.data.name = 'Chunker';
            transformerNode.data.shortName = 'chunker';
            transformerNode.data.model = 'chonkie';
        }
        // Keep other transformers as they are
    });

    // Return the enriched graph
    return {
        nodes: [...flowNodes, embeddingNode],
        edges: [...filteredEdges, edgeToEmbedding, edgeFromEmbedding]
    };
}

export function cleanEntityName(entityName: string, sourceName: string): string {
    // Remove source name from beginning if it exists (case-insensitive)
    const sourceNameLower = sourceName.toLowerCase();
    const entityNameLower = entityName.toLowerCase();

    let nameWithoutSource = entityName;
    if (entityNameLower.startsWith(sourceNameLower)) {
        nameWithoutSource = entityName.substring(sourceName.length);
    }

    // Remove 'Entity' suffix if present
    return nameWithoutSource.replace(/Entity$/, '');
}
