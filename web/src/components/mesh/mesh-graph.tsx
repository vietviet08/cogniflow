"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import {
    ReactFlow,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    Node,
    Edge,
    Panel,
    BackgroundVariant
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { NodeDetailPanel } from "./node-detail-panel";
import type { ConflictMeshPayload, MeshNodeData, MeshEdgeData } from "@/lib/api/types";

function getLayoutedElements(nodesData: MeshNodeData[], edgesData: MeshEdgeData[]) {
    const radius = Math.max(200, nodesData.length * 30);
    const centerX = 300;
    const centerY = 300;

    const nodes: Node[] = nodesData.map((n, i) => {
        const angle = (i / nodesData.length) * 2 * Math.PI;
        return {
            id: n.id,
            position: {
                x: centerX + radius * Math.cos(angle),
                y: centerY + radius * Math.sin(angle),
            },
            data: { label: n.label, fullNode: n },
            style: {
                background: "hsl(var(--background))",
                color: "hsl(var(--foreground))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
                padding: "10px",
                fontSize: "13px",
                fontWeight: 500,
                boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                minWidth: "120px",
                textAlign: "center",
                transition: "all 0.2s ease"
            }
        };
    });

    const edges: Edge[] = edgesData.map((e) => {
        const isContradiction = e.type === "contradicts";
        return {
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.type.replace('_', ' '),
            animated: isContradiction,
            data: { fullEdge: e },
            style: {
                stroke: isContradiction ? "hsl(var(--destructive))" : "hsl(var(--muted-foreground))",
                strokeWidth: isContradiction ? 2 : 1.5,
                transition: "all 0.2s ease"
            },
            labelStyle: {
                fill: isContradiction ? "hsl(var(--destructive))" : "hsl(var(--foreground))",
                fontSize: 11,
                fontWeight: isContradiction ? 600 : 400,
            },
            labelBgStyle: {
                fill: "hsl(var(--background))",
                fillOpacity: 0.9,
            },
            markerEnd: {
                type: MarkerType.ArrowClosed,
                color: isContradiction ? "hsl(var(--destructive))" : "hsl(var(--muted-foreground))",
            },
        };
    });

    return { nodes, edges };
}

export default function MeshGraph({ payload }: { payload: ConflictMeshPayload }) {
    const { nodes: initialNodes, edges: initialEdges } = useMemo(
        () => getLayoutedElements(payload.nodes || [], payload.edges || []),
        [payload]
    );

    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

    useEffect(() => {
        const { nodes: newNodes, edges: newEdges } = getLayoutedElements(payload.nodes || [], payload.edges || []);
        setNodes(newNodes);
        setEdges(newEdges);
        setSelectedElement(null);
    }, [payload]);

    const [selectedElement, setSelectedElement] = useState<
        | { type: "node"; data: MeshNodeData }
        | { type: "edge"; data: MeshEdgeData }
        | null
    >(null);

    const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
        setSelectedElement({ type: "node", data: node.data.fullNode as MeshNodeData });
    }, []);

    const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
        setSelectedElement({ type: "edge", data: edge.data?.fullEdge as MeshEdgeData });
    }, []);

    const onPaneClick = useCallback(() => {
        setSelectedElement(null);
    }, []);

    return (
        <div className="flex h-[100%] w-full min-h-[500px]">
            <div className="flex-1 relative h-full border-r border-border min-w-0">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeClick={onNodeClick}
                    onEdgeClick={onEdgeClick}
                    onPaneClick={onPaneClick}
                    fitView
                    fitViewOptions={{ padding: 0.2, maxZoom: 1.5 }}
                >
                    <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
                    <Controls />
                    <Panel position="top-left" className="bg-background/90 backdrop-blur-sm p-4 rounded-lg border shadow-sm max-w-xs">
                        <h3 className="font-semibold text-sm mb-1">Knowledge Mesh</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">{payload.overview}</p>
                    </Panel>
                </ReactFlow>
            </div>
            <div className="w-[350px] shrink-0 h-full overflow-hidden bg-background">
                <NodeDetailPanel element={selectedElement} />
            </div>
        </div>
    );
}
