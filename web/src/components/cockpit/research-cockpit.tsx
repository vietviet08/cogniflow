"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Telescope, LayoutPanelLeft, Info } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { listSources, listChatSessions } from "@/lib/api/client";
import { getActiveProject } from "@/lib/project-store";
import type { ProjectRole, CitationData } from "@/lib/api/types";

import { CockpitKnowledgePanel, type KnowledgeNode } from "./cockpit-knowledge-panel";
import { CockpitChatPanel } from "./cockpit-chat-panel";
import { CockpitEvidencePanel } from "./cockpit-evidence-panel";

// Resizable divider
function PanelDivider({
  onDrag,
  className,
}: {
  onDrag: (delta: number) => void;
  className?: string;
}) {
  const dragStartX = useRef<number | null>(null);

  function handleMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    dragStartX.current = e.clientX;

    function onMove(ev: MouseEvent) {
      if (dragStartX.current === null) return;
      onDrag(ev.clientX - dragStartX.current);
      dragStartX.current = ev.clientX;
    }
    function onUp() {
      dragStartX.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  return (
    <div
      className={`relative flex-shrink-0 w-1 cursor-col-resize group select-none ${className}`}
      onMouseDown={handleMouseDown}
      role="separator"
      aria-orientation="vertical"
    >
      <div className="absolute inset-y-0 -left-1 -right-1 flex items-center justify-center">
        <div className="h-8 w-[3px] rounded-full bg-slate-200 dark:bg-white/10 group-hover:bg-[#6c63ff]/60 transition-colors" />
      </div>
    </div>
  );
}

// Example: build knowledge nodes from chat messages (could be real later)
function buildDemoNodes(concepts: KnowledgeNode[]): KnowledgeNode[] {
  return concepts.slice(0, 20);
}

export function ResearchCockpit() {
  const [projectId, setProjectId] = useState("");
  const [projectName, setProjectName] = useState("");
  const [projectRole, setProjectRole] = useState<ProjectRole | null>(null);
  const [activeCitation, setActiveCitation] = useState<CitationData | null>(null);
  const [knowledgeNodes, setKnowledgeNodes] = useState<KnowledgeNode[]>([]);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [showTip, setShowTip] = useState(true);

  // Panel widths (in px). Use fractions of viewport.
  const containerRef = useRef<HTMLDivElement>(null);
  const [leftW, setLeftW] = useState(240);
  const [rightW, setRightW] = useState(320);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setProjectId(active.id);
      setProjectName(active.name);
      setProjectRole(active.role ?? "viewer");
    }
  }, []);

  // Stats from API
  const { data: sourcesData } = useQuery({
    queryKey: ["sources", projectId],
    queryFn: () => listSources(projectId),
    enabled: !!projectId,
  });
  const { data: sessionsData } = useQuery({
    queryKey: ["chat_sessions", projectId],
    queryFn: () => listChatSessions(projectId),
    enabled: !!projectId,
  });

  const sources = sourcesData?.data?.items || [];
  const sessions = sessionsData?.data?.items || [];

  const handleConceptsExtracted = useCallback((nodes: KnowledgeNode[]) => {
    setKnowledgeNodes((prev) => {
      // Merge without duplicate ids
      const existingIds = new Set(prev.map((n) => n.id));
      const fresh = nodes.filter((n) => !existingIds.has(n.id));
      return buildDemoNodes([...prev, ...fresh]);
    });
  }, []);

  const handleCitationActivated = useCallback((citation: CitationData) => {
    setActiveCitation(citation);
  }, []);

  // Min/max panel widths
  const MIN_LEFT = 180;
  const MAX_LEFT = 360;
  const MIN_RIGHT = 240;
  const MAX_RIGHT = 500;

  function onDragLeft(delta: number) {
    setLeftW((w) => Math.max(MIN_LEFT, Math.min(MAX_LEFT, w + delta)));
  }
  function onDragRight(delta: number) {
    setRightW((w) => Math.max(MIN_RIGHT, Math.min(MAX_RIGHT, w - delta)));
  }

  if (!projectId) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-[#0A0E1A]">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[#6c63ff]/10 border border-[#6c63ff]/20">
            <Telescope className="h-8 w-8 text-[#6c63ff]" />
          </div>
          <h2 className="text-lg font-semibold text-slate-800 dark:text-white/80">No Active Project</h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-white/40">
            Select a project in the Projects section to launch the Research Cockpit.
          </p>
          <a
            href="/projects"
            className="mt-4 inline-flex items-center rounded-xl px-4 py-2 text-sm font-medium bg-[#6c63ff] text-white hover:bg-[#6c63ff]/90 transition-colors"
          >
            Go to Projects
          </a>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex h-screen overflow-hidden bg-slate-50 dark:bg-[#0A0E1A] relative"
      style={{ fontFamily: "'Inter', 'Sora', system-ui, sans-serif" }}
    >
      {/* ── CSS Keyframes ───────────────────────────────────────── */}
      <style>{`
        @keyframes cockpit-particle {
          0%, 100% { opacity: 0; transform: translateY(0) scale(0.8); }
          50%       { opacity: 0.8; transform: translateY(-12px) scale(1.2); }
        }
        @keyframes cockpit-bounce {
          0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
          40%            { transform: scale(1); opacity: 1; }
        }
        @keyframes cockpit-pulse {
          0%, 100% { opacity: 0.2; }
          50%       { opacity: 0.5; }
        }
        /* Hide scrollbar on session list */
        .scrollbar-none::-webkit-scrollbar { display: none; }
        .scrollbar-none { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>

      {/* ── Top banner ────────────────────────────────────────── */}
      <div className="absolute top-0 left-0 right-0 z-30 h-10 flex items-center justify-between px-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/90 dark:bg-[#0A0E1A]/90 backdrop-blur-sm">
        <div className="flex items-center gap-2.5">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[#6c63ff]/20 border border-[#6c63ff]/30">
            <Telescope className="h-3.5 w-3.5 text-[#6c63ff]" />
          </div>
          <span className="text-xs font-bold text-slate-800 dark:text-white/80 tracking-wide">RESEARCH COCKPIT</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#6c63ff]/15 border border-[#6c63ff]/25 text-[#6c63ff]/80">
            BETA
          </span>
          <span className="hidden sm:block text-slate-300 dark:text-white/20 mx-1">·</span>
          <span className="hidden sm:block text-xs text-slate-500 dark:text-white/40 truncate max-w-[200px]">
            {projectName}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <LayoutPanelLeft className="h-3.5 w-3.5 text-slate-400 dark:text-white/30" />
          <span className="text-[10px] text-slate-400 dark:text-white/30 hidden sm:block">3-panel mode</span>
        </div>
      </div>

      {/* ── Onboarding tip ────────────────────────────────────── */}
      {showTip && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 rounded-xl px-4 py-2.5 bg-white dark:bg-[#161b27] border border-slate-200 dark:border-white/10 shadow-2xl max-w-sm">
          <Info className="h-4 w-4 text-[#00d8ff] shrink-0" />
          <p className="text-xs text-slate-600 dark:text-white/60">
            Click citation tags{" "}
            <span className="text-[#00d8ff]">[1]</span> in the chat to view evidence in this panel
          </p>
          <button
            type="button"
            onClick={() => setShowTip(false)}
            className="ml-2 text-slate-400 dark:text-white/30 hover:text-slate-600 dark:hover:text-white/60"
          >
            ✕
          </button>
        </div>
      )}

      {/* ── 3-Panel layout ────────────────────────────────────── */}
      <div className="flex w-full mt-10 overflow-hidden">

        {/* LEFT: Knowledge Map */}
        <div
          className="flex-shrink-0 overflow-hidden"
          style={{ width: leftW }}
        >
          <CockpitKnowledgePanel
            nodes={knowledgeNodes}
            activeNodeId={activeNodeId}
            onNodeClick={(node) =>
              setActiveNodeId((prev) => (prev === node.id ? null : node.id))
            }
            projectName={projectName}
            stats={{
              sources: sources.length,
              chunks: 0,
              sessions: sessions.length,
            }}
          />
        </div>

        <PanelDivider onDrag={onDragLeft} />

        {/* CENTER: Chat */}
        <div className="flex-1 min-w-0 overflow-hidden">
          <CockpitChatPanel
            projectId={projectId}
            projectRole={projectRole}
            onConceptsExtracted={handleConceptsExtracted}
            onCitationActivated={handleCitationActivated}
          />
        </div>

        <PanelDivider onDrag={onDragRight} />

        {/* RIGHT: Evidence */}
        <div
          className="flex-shrink-0 overflow-hidden"
          style={{ width: rightW }}
        >
          <CockpitEvidencePanel
            citation={activeCitation}
            onClose={() => setActiveCitation(null)}
          />
        </div>
      </div>
    </div>
  );
}
