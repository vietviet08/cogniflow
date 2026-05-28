"use client";

import { useMemo, useState, useCallback, useRef, useEffect } from "react";
import ForceGraph3D from "react-force-graph-3d";
import SpriteText from "three-spritetext";
import { useTheme } from "next-themes";
import * as THREE from "three";
import { Info, ChevronDown, ChevronUp, Maximize2, Minimize2 } from "lucide-react";

import { NodeDetailPanel } from "./node-detail-panel";
import type { ConflictMeshPayload, MeshNodeData, MeshEdgeData } from "@/lib/api/types";

export default function MeshGraph3DClient({ payload }: { payload: ConflictMeshPayload }) {
    const { theme, systemTheme } = useTheme();
    const isDark = theme === "dark" || (theme === "system" && systemTheme === "dark");

    // Theme colors
    const bgColor = isDark ? "#07111f" : "#f5fbff";
    const textColor = isDark ? "#ecfeff" : "#102033";
    const edgeColor = isDark ? "rgba(103, 232, 249, 0.22)" : "rgba(14, 165, 233, 0.28)";
    const conflictColor = isDark ? "#fb7185" : "#e11d48";

    // Vibrant palette for nodes
    const nodePalette = [
        "#22d3ee",
        "#8b5cf6",
        "#f472b6",
        "#34d399",
        "#facc15",
        "#38bdf8"
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
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [detailOpen, setDetailOpen] = useState(true);

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

    const graphShellClass = isFullscreen
        ? "fixed inset-0 z-50 flex h-screen w-screen bg-background"
        : "flex h-[100%] w-full min-h-[500px] overflow-hidden rounded-xl";

    return (
        <div className={graphShellClass}>
            <div ref={containerRef} className="relative h-full min-w-0 flex-1 overflow-hidden border-r border-border/70 bg-background">
                <div className="pointer-events-none absolute inset-0 z-10 bg-[radial-gradient(circle_at_18%_12%,color-mix(in_oklch,var(--color-primary)_18%,transparent),transparent_34%),radial-gradient(circle_at_85%_8%,color-mix(in_oklch,var(--color-accent)_18%,transparent),transparent_30%)]" />
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
                            opacity: 0.9,
                            shininess: 130,
                            emissive: new THREE.Color(getNodeColor(node.id)),
                            emissiveIntensity: isDark ? 0.16 : 0.08,
                            specular: new THREE.Color(0xb8f7ff)
                        });
                        const sphere = new THREE.Mesh(geometry, material);
                        group.add(sphere);

                        // Node Label
                        const sprite = new SpriteText(node.label || "Unknown");
                        sprite.color = textColor;
                        sprite.textHeight = 2; // A bit larger
                        sprite.fontWeight = "400"; // Semi-bold for cleaner look
                        sprite.fontFace = "Space Grotesk, Inter, system-ui, sans-serif";
                        sprite.position.y = 12; // offset above the sphere

                        // Sleek badge background effect
                        sprite.backgroundColor = isDark ? "rgba(8, 18, 34, 0.82)" : "rgba(245, 251, 255, 0.82)";
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

                <button
                    type="button"
                    onClick={() => setIsFullscreen((current) => !current)}
                    className="holo-surface absolute right-4 top-4 z-20 flex h-9 w-9 items-center justify-center rounded-lg text-foreground transition-colors hover:bg-accent/70"
                    aria-label={isFullscreen ? "Exit fullscreen mesh" : "Open fullscreen mesh"}
                    title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                >
                    {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                </button>

                {isFullscreen && (
                    <button
                        type="button"
                        onClick={() => setDetailOpen((current) => !current)}
                        className="holo-surface absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-full px-4 py-2 text-xs font-medium text-foreground transition-colors hover:bg-accent/70 lg:hidden"
                    >
                        <Info className="h-4 w-4" />
                        {detailOpen ? "Hide details" : "Show details"}
                    </button>
                )}

                {/* Floating Info Panel */}
                <div className="absolute top-4 left-4 pointer-events-auto">
                    <div className="holo-surface holo-edge max-w-sm overflow-hidden rounded-xl transition-all duration-300">
                        {/* Header / Toggle */}
                        <div
                            className="flex cursor-pointer items-center justify-between bg-secondary/30 p-3 transition-colors hover:bg-secondary/55"
                            onClick={() => setIsInfoExpanded(!isInfoExpanded)}
                        >
                            <h3 className="holo-text font-display flex items-center gap-2 text-sm font-bold">
                                <Info className="w-4 h-4 text-primary" />
                                Knowledge Discovery 3D
                                <span className="text-[9px] bg-primary/10 text-foreground px-2 py-0.5 rounded-full border border-primary/20 ml-1">
                                    HOLO
                                </span>
                            </h3>
                            {isInfoExpanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                        </div>

                        {/* Collapsible Content */}
                        {isInfoExpanded && (
                            <div className="border-t border-border/50 p-4 pt-2">
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
            <div
                className={
                    isFullscreen
                        ? `${detailOpen ? "translate-y-0" : "translate-y-full lg:translate-y-0"} holo-surface fixed inset-x-0 bottom-0 z-30 h-[42vh] overflow-hidden rounded-t-xl border-t border-border/70 bg-card/85 transition-transform lg:static lg:h-full lg:w-[360px] lg:shrink-0 lg:rounded-none lg:border-l lg:border-t-0`
                        : "holo-surface h-full w-[350px] shrink-0 overflow-hidden rounded-none bg-card/70"
                }
            >
                <NodeDetailPanel element={selectedElement} payload={payload} />
            </div>
        </div>
    );
}
