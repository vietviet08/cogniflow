"use client";

import { useMemo, useState, useCallback, useRef, useEffect } from "react";
import ForceGraph3D from "react-force-graph-3d";
import SpriteText from "three-spritetext";
import { useTheme } from "next-themes";
import * as THREE from "three";
import { Info, ChevronDown, ChevronUp } from "lucide-react";

import { NodeDetailPanel } from "./node-detail-panel";
import type { ConflictMeshPayload, MeshNodeData, MeshEdgeData } from "@/lib/api/types";

export default function MeshGraph3DClient({ payload }: { payload: ConflictMeshPayload }) {
    const { theme, systemTheme } = useTheme();
    const isDark = theme === "dark" || (theme === "system" && systemTheme === "dark");

    // Theme colors
    const bgColor = isDark ? "#09090b" : "#ffffff";
    const textColor = isDark ? "#ffffff" : "#09090b";
    const edgeColor = isDark ? "rgba(161, 161, 170, 0.25)" : "rgba(161, 161, 170, 0.45)"; // zinc-400
    const conflictColor = isDark ? "#ef4444" : "#dc2626"; // red-500 / red-600

    // Vibrant palette for nodes
    const nodePalette = [
        "#3b82f6", // blue
        "#8b5cf6", // violet
        "#ec4899", // pink
        "#10b981", // emerald
        "#f59e0b", // amber
        "#06b6d4"  // cyan
    ];

    const getNodeColor = useCallback((id: string) => {
        let hash = 0;
        for (let i = 0; i < (id || "").length; i++) hash = id.charCodeAt(i) + ((hash << 5) - hash);
        return nodePalette[Math.abs(hash) % nodePalette.length];
    }, []);

    const graphRef = useRef<any>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const [isInfoExpanded, setIsInfoExpanded] = useState(true);

    // Resize observer to keep the graph filling the container
    useEffect(() => {
        if (!containerRef.current) return;
        const observer = new ResizeObserver((entries) => {
            if (entries[0]) {
                const { width, height } = entries[0].contentRect;
                setDimensions({ width, height });
            }
        });
        observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, []);

    // Transform payload for ForceGraph
    const graphData = useMemo(() => {
        return {
            nodes: (payload.nodes || []).map(n => ({ ...n })),
            links: (payload.edges || []).map(e => ({ ...e, source: e.source, target: e.target }))
        };
    }, [payload]);

    const [selectedElement, setSelectedElement] = useState<
        | { type: "node"; data: MeshNodeData }
        | { type: "edge"; data: MeshEdgeData }
        | null
    >(null);

    const onNodeClick = useCallback((node: any) => {
        setSelectedElement({ type: "node", data: node as MeshNodeData });

        // Aim at node
        if (graphRef.current) {
            const distance = 150;
            const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
            graphRef.current.cameraPosition(
                { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
                node, // lookAt
                3000  // ms transition
            );
        }
    }, []);

    const onLinkClick = useCallback((link: any) => {
        setSelectedElement({ type: "edge", data: link as MeshEdgeData });
    }, []);

    const onBackgroundClick = useCallback(() => {
        setSelectedElement(null);
    }, []);

    return (
        <div className="flex h-[100%] w-full min-h-[500px]">
            <div ref={containerRef} className="flex-1 relative h-full border-r border-border min-w-0 bg-background overflow-hidden">
                <ForceGraph3D
                    ref={graphRef}
                    width={dimensions.width}
                    height={dimensions.height}
                    graphData={graphData}
                    backgroundColor={bgColor}
                    showNavInfo={false}
                    nodeThreeObject={(node: any) => {
                        const group = new THREE.Group();

                        // Node Sphere with Phong material for shiny 3D look
                        const geometry = new THREE.SphereGeometry(6, 16, 16);
                        const material = new THREE.MeshPhongMaterial({
                            color: getNodeColor(node.id),
                            transparent: true,
                            opacity: 0.85,
                            shininess: 80,
                            specular: new THREE.Color(0x444444)
                        });
                        const sphere = new THREE.Mesh(geometry, material);
                        group.add(sphere);

                        // Node Label
                        const sprite = new SpriteText(node.label || "Unknown");
                        sprite.color = textColor;
                        sprite.textHeight = 2; // A bit larger
                        sprite.fontWeight = "400"; // Semi-bold for cleaner look
                        sprite.fontFace = "Inter, system-ui, sans-serif"; // Modern crisp font
                        sprite.position.y = 12; // offset above the sphere

                        // Sleek badge background effect
                        sprite.backgroundColor = isDark ? "rgba(24, 24, 27, 0.85)" : "rgba(255, 255, 255, 0.85)";
                        sprite.padding = [2, 1] as any;
                        sprite.borderRadius = 3;
                        sprite.borderColor = getNodeColor(node.id);
                        sprite.borderWidth = 0.2;

                        group.add(sprite);

                        return group;
                    }}
                    linkColor={(link: any) => link.type === "contradicts" ? conflictColor : edgeColor}
                    linkWidth={(link: any) => link.type === "contradicts" ? 3 : 0.5}
                    linkDirectionalParticles={(link: any) => link.type === "contradicts" ? 8 : 2}
                    linkDirectionalParticleSpeed={(link: any) => link.type === "contradicts" ? 0.015 : 0.003}
                    linkDirectionalParticleWidth={(link: any) => link.type === "contradicts" ? 4 : 1.5}
                    linkDirectionalParticleColor={(link: any) => link.type === "contradicts" ? conflictColor : getNodeColor(link.source?.id || link.source)}
                    onNodeClick={onNodeClick}
                    onLinkClick={onLinkClick}
                    onBackgroundClick={onBackgroundClick}
                    enableNodeDrag={true}
                />

                {/* Floating Info Panel */}
                <div className="absolute top-4 left-4 pointer-events-auto">
                    <div className="bg-background/80 backdrop-blur-md rounded-lg border shadow-sm max-w-sm overflow-hidden transition-all duration-300">
                        {/* Header / Toggle */}
                        <div
                            className="p-3 bg-secondary/30 flex items-center justify-between cursor-pointer hover:bg-secondary/50 transition-colors"
                            onClick={() => setIsInfoExpanded(!isInfoExpanded)}
                        >
                            <h3 className="font-bold text-sm flex items-center gap-2 text-transparent bg-clip-text bg-gradient-to-r from-primary to-blue-500">
                                <Info className="w-4 h-4 text-primary" />
                                Knowledge Discovery 3D
                                <span className="text-[9px] bg-primary/10 text-foreground px-2 py-0.5 rounded-full border border-primary/20 ml-1">
                                    BETA
                                </span>
                            </h3>
                            {isInfoExpanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                        </div>

                        {/* Collapsible Content */}
                        {isInfoExpanded && (
                            <div className="p-4 pt-2 border-t border-border/50">
                                <p className="text-xs text-muted-foreground leading-relaxed">
                                    {payload.overview}
                                </p>
                                <p className="text-[10px] text-muted-foreground/60 mt-3 flex items-center gap-1.5">
                                    <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
                                    Red links signify contradictions. Rotate matrix to explore.
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Detail Panel */}
            <div className="w-[350px] shrink-0 h-full overflow-hidden bg-background">
                <NodeDetailPanel element={selectedElement} />
            </div>
        </div>
    );
}
