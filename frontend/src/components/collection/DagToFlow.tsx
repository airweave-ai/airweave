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
    if (dagNode.type === 'entity' && sourceName) {
        displayName = cleanEntityName(dagNode.name, sourceName);
    }

    // Generate shortName from name
    const shortName = displayName.toLowerCase().replace(/\s+/g, '');

    console.log(displayName)

    return {
        id: dagNode.id,
        data: {
            label: displayName,
            name: displayName,
            originalName: dagNode.name, // Store original name for reference
            shortName: shortName
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
    const sourceName = currentNode?.name || '';

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
    console.log(flowEdges)

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

    // if the dag contains a transformernode
    const transformerNode = flowNodes.find(node => node.type === 'transformerNode');
    if (transformerNode) {
        // replace the transformer node by ocr, chunker
        // how can I know the entity file type
        console.log(transformerNode)
        transformerNode.data = {
            label: 'Chunker',
            name: 'Chunker',
            shortName: 'chunker',
            model: 'chonkie'
        };
        console.log(transformerNode)
    }

    // Return the enriched graph
    return {
        nodes: [...flowNodes, embeddingNode],
        edges: [...filteredEdges, edgeToEmbedding, edgeFromEmbedding]
    };
}

export function cleanEntityName(entityName: string, sourceName: string): string {
    // Remove source name from beginning if it exists
    const nameWithoutSource = entityName.startsWith(sourceName)
        ? entityName.substring(sourceName.length)
        : entityName;

    // Remove 'Entity' suffix if present
    return nameWithoutSource.replace(/Entity$/, '');
}
