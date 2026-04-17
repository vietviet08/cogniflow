"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Network, Layers, Cpu, RefreshCw, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

export interface KnowledgeNode {
  id: string;
  label: string;
  type: "concept" | "source" | "conflict" | "insight";
  weight: number; // 0–1, controls visual size
  connections: string[];
}

interface KnowledgePanelProps {
  nodes: KnowledgeNode[];
  activeNodeId?: string | null;
  onNodeClick?: (node: KnowledgeNode) => void;
  isLoading?: boolean;
  projectName?: string;
  stats?: {
    sources: number;
    chunks: number;
    sessions: number;
  };
}

const NODE_TYPE_CONFIG = {
  concept:  { color: "#6c63ff", glow: "rgba(108,99,255,0.5)",  label: "Concept"  },
  source:   { color: "#00d8ff", glow: "rgba(0,216,255,0.4)",   label: "Source"   },
  conflict: { color: "#ff6b35", glow: "rgba(255,107,53,0.5)",  label: "Conflict" },
  insight:  { color: "#10b981", glow: "rgba(16,185,129,0.4)",  label: "Insight"  },
};

// Particle animation for the pipeline visualization
function PipelineParticle({ delay }: { delay: number }) {
  return (
    <div
      className="absolute h-1 w-1 rounded-full bg-[#6c63ff] opacity-0"
      style={{
        animation: `cockpit-particle 3s ${delay}s infinite ease-in-out`,
        left: `${Math.random() * 80 + 10}%`,
        top: `${Math.random() * 80 + 10}%`,
      }}
    />
  );
}

export function CockpitKnowledgePanel({
  nodes,
  activeNodeId,
  onNodeClick,
  isLoading = false,
  projectName,
  stats,
}: KnowledgePanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Canvas-based mini force graph
  const nodePositions = useRef<Map<string, { x: number; y: number; vx: number; vy: number }>>(new Map());

  const initPositions = useCallback((canvasWidth: number, canvasHeight: number) => {
    nodes.forEach((node) => {
      if (!nodePositions.current.has(node.id)) {
        nodePositions.current.set(node.id, {
          x: Math.random() * (canvasWidth - 80) + 40,
          y: Math.random() * (canvasHeight - 80) + 40,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5,
        });
      }
    });
    // Remove stale nodes
    const nodeIds = new Set(nodes.map((n) => n.id));
    nodePositions.current.forEach((_, id) => {
      if (!nodeIds.has(id)) nodePositions.current.delete(id);
    });
  }, [nodes]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = canvas.offsetWidth;
    let height = canvas.offsetHeight;
    canvas.width = width;
    canvas.height = height;

    initPositions(width, height);

    const REPULSION = 2500;
    const SPRING_LEN = 120;
    const SPRING_K = 0.015;
    const DAMPING = 0.88;
    const CENTER_PULL = 0.003;

    function tick() {
      if (!ctx || !canvas) return;
      width = canvas.offsetWidth;
      height = canvas.offsetHeight;
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        initPositions(width, height);
      }

      ctx.clearRect(0, 0, width, height);

      const positions = nodePositions.current;
      const nodeList = nodes;

      // Apply forces
      for (const nodeA of nodeList) {
        const posA = positions.get(nodeA.id);
        if (!posA) continue;

        // Center gravity
        posA.vx += (width / 2 - posA.x) * CENTER_PULL;
        posA.vy += (height / 2 - posA.y) * CENTER_PULL;

        for (const nodeB of nodeList) {
          if (nodeA.id === nodeB.id) continue;
          const posB = positions.get(nodeB.id);
          if (!posB) continue;
          const dx = posA.x - posB.x;
          const dy = posA.y - posB.y;
          const dist2 = dx * dx + dy * dy + 1;
          const force = REPULSION / dist2;
          posA.vx += (dx / Math.sqrt(dist2)) * force;
          posA.vy += (dy / Math.sqrt(dist2)) * force;
        }

        // Spring forces for connections
        for (const connId of nodeA.connections) {
          const posB = positions.get(connId);
          if (!posB) continue;
          const dx = posB.x - posA.x;
          const dy = posB.y - posA.y;
          const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
          const force = (dist - SPRING_LEN) * SPRING_K;
          posA.vx += (dx / dist) * force;
          posA.vy += (dy / dist) * force;
        }

        posA.vx *= DAMPING;
        posA.vy *= DAMPING;
        posA.x = Math.max(24, Math.min(width - 24, posA.x + posA.vx));
        posA.y = Math.max(24, Math.min(height - 24, posA.y + posA.vy));
      }

      // Draw edges
      for (const node of nodeList) {
        const posA = positions.get(node.id);
        if (!posA) continue;
        for (const connId of node.connections) {
          const posB = positions.get(connId);
          if (!posB) continue;
          const cfg = NODE_TYPE_CONFIG[node.type];
          ctx.beginPath();
          ctx.strokeStyle = cfg.color + "33"; // 20% opacity
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 5]);
          ctx.moveTo(posA.x, posA.y);
          ctx.lineTo(posB.x, posB.y);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      // Draw nodes
      for (const node of nodeList) {
        const pos = positions.get(node.id);
        if (!pos) continue;
        const cfg = NODE_TYPE_CONFIG[node.type];
        const r = 7 + node.weight * 10;
        const isActive = node.id === activeNodeId;
        const isHovered = node.id === hoveredNodeId;

        // Glow
        if (isActive || isHovered) {
          const grd = ctx.createRadialGradient(pos.x, pos.y, r * 0.5, pos.x, pos.y, r * 2.5);
          grd.addColorStop(0, cfg.glow);
          grd.addColorStop(1, "transparent");
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, r * 2.5, 0, Math.PI * 2);
          ctx.fillStyle = grd;
          ctx.fill();
        }

        // Node circle
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
        ctx.fillStyle = cfg.color + (isActive ? "ff" : "bb");
        ctx.fill();
        ctx.strokeStyle = isActive ? "#fff" : cfg.color;
        ctx.lineWidth = isActive ? 2 : 1;
        ctx.stroke();

        // Label
        if (isHovered || isActive || nodes.length <= 12) {
          const maxLen = 12;
          const label = node.label.length > maxLen ? node.label.slice(0, maxLen) + "…" : node.label;
          ctx.font = "500 9px Inter, system-ui, sans-serif";
          ctx.fillStyle = "#e2e8f0";
          ctx.textAlign = "center";
          ctx.fillText(label, pos.x, pos.y + r + 10);
        }
      }

      animFrameRef.current = requestAnimationFrame(tick);
    }

    animFrameRef.current = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [nodes, activeNodeId, hoveredNodeId, initPositions]);

  // Handle mouse interaction on canvas
  function handleCanvasMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    let found: string | null = null;
    nodePositions.current.forEach((pos, id) => {
      const node = nodes.find((n) => n.id === id);
      if (!node) return;
      const r = 7 + node.weight * 10;
      const dx = mx - pos.x;
      const dy = my - pos.y;
      if (dx * dx + dy * dy < (r + 4) * (r + 4)) found = id;
    });
    setHoveredNodeId(found);
  }

  function handleCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    nodePositions.current.forEach((pos, id) => {
      const node = nodes.find((n) => n.id === id);
      if (!node) return;
      const r = 7 + node.weight * 10;
      const dx = mx - pos.x;
      const dy = my - pos.y;
      if (dx * dx + dy * dy < (r + 4) * (r + 4)) {
        onNodeClick?.(node);
      }
    });
  }

  const typeCounts = nodes.reduce<Record<string, number>>((acc, n) => {
    acc[n.type] = (acc[n.type] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex h-full flex-col bg-[#0A0E1A] border-r border-white/5">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#6c63ff]/20 border border-[#6c63ff]/30">
            <Network className="h-3.5 w-3.5 text-[#6c63ff]" />
          </div>
          <div>
            <p className="text-xs font-semibold text-white/90 leading-none">Knowledge Map</p>
            <p className="text-[10px] text-white/40 mt-0.5 leading-none truncate max-w-[100px]">
              {projectName || "No project"}
            </p>
          </div>
        </div>
        {isLoading && (
          <RefreshCw className="h-3.5 w-3.5 text-[#6c63ff] animate-spin" />
        )}
      </div>

      {/* Graph Canvas */}
      <div className="relative flex-1 min-h-0 overflow-hidden">
        {nodes.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6">
            <div className="relative mb-4">
              {/* Animated rings */}
              <div className="absolute inset-0 rounded-full border border-[#6c63ff]/20 animate-ping" />
              <div
                className="absolute inset-[-8px] rounded-full border border-[#6c63ff]/10 animate-ping"
                style={{ animationDelay: "0.5s" }}
              />
              <div className="relative h-10 w-10 rounded-full bg-[#6c63ff]/10 border border-[#6c63ff]/30 flex items-center justify-center">
                <Cpu className="h-5 w-5 text-[#6c63ff]/70" />
              </div>
            </div>
            <p className="text-xs text-white/40 leading-relaxed">
              Start a conversation to build your knowledge map
            </p>
            {/* Particle shimmer */}
            <div className="relative w-full h-24 mt-4 overflow-hidden opacity-30">
              {Array.from({ length: 8 }).map((_, i) => (
                <PipelineParticle key={i} delay={i * 0.4} />
              ))}
            </div>
          </div>
        ) : (
          <canvas
            ref={canvasRef}
            className="h-full w-full cursor-pointer"
            onMouseMove={handleCanvasMouseMove}
            onClick={handleCanvasClick}
            onMouseLeave={() => setHoveredNodeId(null)}
          />
        )}
      </div>

      {/* Type Legend */}
      <div className="shrink-0 border-t border-white/5 px-3 py-2.5">
        <div className="grid grid-cols-2 gap-1">
          {(Object.entries(NODE_TYPE_CONFIG) as [keyof typeof NODE_TYPE_CONFIG, typeof NODE_TYPE_CONFIG[keyof typeof NODE_TYPE_CONFIG]][]).map(
            ([type, cfg]) => (
              <div key={type} className="flex items-center gap-1.5">
                <div
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: cfg.color }}
                />
                <span className="text-[10px] text-white/40">
                  {cfg.label}
                  {typeCounts[type] ? (
                    <span className="ml-1 text-white/60">{typeCounts[type]}</span>
                  ) : null}
                </span>
              </div>
            )
          )}
        </div>
      </div>

      {/* Stats strip */}
      {stats && (
        <div className="shrink-0 border-t border-white/5 px-3 py-2 flex justify-between">
          {[
            { label: "Sources", value: stats.sources, icon: Layers },
            { label: "Chunks", value: stats.chunks, icon: Cpu },
            { label: "Chats", value: stats.sessions, icon: Zap },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="flex flex-col items-center gap-0.5">
              <Icon className="h-3 w-3 text-white/30" />
              <span className="text-[11px] font-semibold text-white/70">{value}</span>
              <span className="text-[9px] text-white/30">{label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
