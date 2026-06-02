"use client";

import {
  ChangeEvent,
  Dispatch,
  FormEvent,
  ReactNode,
  RefObject,
  SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { Command as CmdkCommand } from "cmdk";
import { useTheme } from "next-themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Group as ResizablePanelGroup,
  Panel as ResizablePanel,
  Separator as ResizableHandle,
} from "react-resizable-panels";
import {
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Copy,
  ExternalLink,
  FileText,
  FolderOpen,
  Layers,
  Link2,
  LogOut,
  MessageSquare,
  Mic,
  Moon,
  Pause,
  Play,
  PanelBottomOpen,
  Plus,
  RefreshCcw,
  RotateCcw,
  Search,
  Send,
  Settings,
  Share2,
  Sparkles,
  Sun,
  Upload,
  Volume2,
  VolumeX,
  Workflow,
  X,
} from "lucide-react";
import { toast } from "sonner";

import {
  createChatSession,
  generateReport,
  getReport,
  ingestSourceUrl,
  listProjectJobs,
  listChatMessages,
  listChatSessions,
  listReports,
  listSources,
  processSources,
  sendChatMessage,
  browseGoogleDriveItems,
  importProjectIntegrationSource,
  listProjectIntegrations,
  updateChatMessage,
  uploadSourceFile,
  createApiUrl,
} from "@/lib/api/client";
import { getStoredAuthToken } from "@/lib/auth-session";
import type {
  ChatMessageData,
  CitationData,
  GoogleDriveBrowseItemData,
  IntegrationConnectionData,
  JobStatusData,
  ProjectRole,
  QuizQuestionData,
  ReportListItem,
  ReportResult,
  ReportType,
  SourceListItemData,
  StructuredReportPayload,
} from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject, type StoredProject } from "@/lib/project-store";
import { cn } from "@/lib/utils";

import { useAuth } from "@/components/auth-provider";
import { useCitationViewer } from "@/components/citation-viewer-provider";
import { WebSourceDiscovery } from "@/components/web-source-discovery";
import MeshGraph from "@/components/mesh/mesh-graph";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import { buildMindMapFlow } from "@/components/mind-map-viewer";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

type WorkspaceTab = "sources" | "research" | "studio";
type SourceTool = "add" | "web" | "drive";

type StudioRequest = {
  query: string;
  type: ReportType;
  nonce: number;
};

type WorkspaceActions = {
  focusAsk?: () => void;
  newChat?: () => void;
  uploadSource?: () => void;
  processSelectedSources?: () => void;
  refreshSources?: () => void;
  refreshArtifacts?: () => void;
  generateArtifact?: (type: ReportType) => void;
};

const REPORT_TYPES: Array<{
  value: ReportType;
  label: string;
  icon: typeof FileText;
}> = [
  { value: "research_brief", label: "Research brief", icon: FileText },
  { value: "summary", label: "Summary", icon: BookOpen },
  { value: "comparison", label: "Comparison", icon: Search },
  { value: "flashcards", label: "Flashcards", icon: Layers },
  { value: "quiz", label: "Quiz", icon: CircleHelp },
  { value: "study_guide", label: "Study guide", icon: BookOpen },
  { value: "mind_map", label: "Mind map", icon: Workflow },
  { value: "conflict_mesh", label: "Conflict mesh", icon: Share2 },
  { value: "podcast", label: "AI Podcast", icon: Mic },
];

const REPORT_LABELS = Object.fromEntries(
  REPORT_TYPES.map((type) => [type.value, type.label]),
) as Record<ReportType, string>;

const fadeUp = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 8 },
};

const noMotion = {
  initial: { opacity: 1, y: 0, scale: 1, x: 0 },
  animate: { opacity: 1, y: 0, scale: 1, x: 0 },
  exit: { opacity: 1, y: 0, scale: 1, x: 0 },
};

const SUPPORTED_FILE_ACCEPT = [
  ".pdf",
  ".txt",
  ".md",
  ".csv",
  ".json",
  ".html",
  ".htm",
  ".xml",
  ".docx",
  ".pptx",
  ".xlsx",
  "application/pdf",
  "text/plain",
  "text/csv",
  "application/json",
  "text/html",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
].join(",");

function formatDate(value: string | null | undefined) {
  if (!value) return "No date";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function getSourceStatusVariant(status: string) {
  if (status === "processed" || status === "completed") return "success";
  if (status === "failed") return "destructive";
  if (status === "queued" || status === "processing") return "warning";
  return "outline";
}

function getReportIcon(type: ReportType) {
  return REPORT_TYPES.find((item) => item.value === type)?.icon ?? FileText;
}

function getArtifactFullViewerRoute(type: ReportType) {
  if (type === "flashcards") return "/flashcards";
  if (type === "quiz") return "/quiz";
  if (type === "study_guide") return "/study-guide";
  if (type === "mind_map") return "/mind-map";
  if (type === "conflict_mesh") return "/mesh";
  return "/reports";
}

function describeStructuredPayload(
  payload: StructuredReportPayload | null | undefined,
) {
  if (!payload || typeof payload !== "object") {
    return "No structured payload.";
  }
  if ("cards" in payload && Array.isArray(payload.cards)) {
    return `${payload.cards.length} flashcards generated.`;
  }
  if ("questions" in payload && Array.isArray(payload.questions)) {
    return `${payload.questions.length} quiz questions generated.`;
  }
  if ("sections" in payload && Array.isArray(payload.sections)) {
    return `${payload.sections.length} study sections generated.`;
  }
  if ("nodes" in payload && Array.isArray(payload.nodes)) {
    return `${payload.nodes.length} nodes mapped.`;
  }
  if ("items" in payload && Array.isArray(payload.items)) {
    return `${payload.items.length} structured items generated.`;
  }
  if ("summary" in payload && typeof payload.summary === "string") {
    return payload.summary;
  }
  if ("overview" in payload && typeof payload.overview === "string") {
    return payload.overview;
  }
  return "Structured artifact ready.";
}

function CitationChips({
  citations,
  onCitationHover,
}: {
  citations: CitationData[];
  onCitationHover?: (sourceId: string | null) => void;
}) {
  const { openCitation } = useCitationViewer();

  if (!citations.length) return null;

  function open(citation: CitationData) {
    if (citation.source_type === "file" && citation.source_id) {
      openCitation(citation);
      return;
    }
    if (citation.url) {
      window.open(citation.url, "_blank", "noopener,noreferrer");
    }
  }

  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {citations.slice(0, 8).map((citation, index) => (
        <button
          key={`${citation.chunk_id}-${index}`}
          type="button"
          onMouseEnter={() => onCitationHover?.(citation.source_id || null)}
          onMouseLeave={() => onCitationHover?.(null)}
          onFocus={() => onCitationHover?.(citation.source_id || null)}
          onBlur={() => onCitationHover?.(null)}
          onClick={() => open(citation)}
          className="group inline-flex"
        >
          <Badge
            variant="outline"
            className="max-w-52 cursor-pointer gap-1 truncate border-primary/20 bg-primary/5 text-[10px] text-primary group-hover:bg-primary/10"
          >
            <span className="truncate">
              {citation.title || citation.chunk_id || `Source ${index + 1}`}
            </span>
            {citation.page_number ? (
              <span>p.{citation.page_number}</span>
            ) : null}
          </Badge>
        </button>
      ))}
    </div>
  );
}

export function ResearchWorkspace() {
  const [activeProject, setActiveProjectState] = useState<StoredProject | null>(
    null,
  );
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("research");
  const [studioRequest, setStudioRequest] = useState<StudioRequest | null>(
    null,
  );
  const [selectedArtifact, setSelectedArtifact] = useState<ReportResult | null>(
    null,
  );
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(
    new Set(),
  );
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(
    null,
  );
  const [commandOpen, setCommandOpen] = useState(false);
  const workspaceActionsRef = useRef<WorkspaceActions>({});
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    setActiveProjectState(getActiveProject());
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  if (!activeProject) {
    return <WorkspaceEmptyState />;
  }

  const canMutate = canEditProject(
    activeProject.role as ProjectRole | undefined,
  );

  function requestArtifact(query: string, type: ReportType) {
    setStudioRequest({ query, type, nonce: Date.now() });
    setActiveTab("studio");
  }

  function openArtifact(artifact: ReportResult) {
    setSelectedArtifact(artifact);
    setActiveTab("studio");
  }

  function registerWorkspaceActions(actions: Partial<WorkspaceActions>) {
    workspaceActionsRef.current = {
      ...workspaceActionsRef.current,
      ...actions,
    };
  }

  function clearSourceScope() {
    setSelectedSourceIds(new Set());
  }

  return (
    <div className="flex h-screen min-h-0 flex-col bg-transparent">
      <WorkspaceTopBar activeProject={activeProject} />
      <WorkspaceCommandPalette
        open={commandOpen}
        onOpenChange={setCommandOpen}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        canMutate={canMutate}
        selectedSourceCount={selectedSourceIds.size}
        actionsRef={workspaceActionsRef}
      />

      <div className="hidden min-h-0 flex-1 lg:block">
        <ResizablePanelGroup orientation="horizontal" className="h-full">
          <ResizablePanel
            id="workspace-sources"
            defaultSize="25%"
            minSize="18%"
            maxSize="34%"
          >
            <KnowledgeSourcesPanel
              activeProject={activeProject}
              canMutate={canMutate}
              selectedSourceIds={selectedSourceIds}
              setSelectedSourceIds={setSelectedSourceIds}
              highlightedSourceId={highlightedSourceId}
              registerActions={registerWorkspaceActions}
            />
          </ResizablePanel>
          <WorkspaceResizeHandle />
          <ResizablePanel
            id="workspace-research"
            defaultSize="47%"
            minSize="34%"
            maxSize="60%"
          >
            <ResearchCanvasPanel
              activeProject={activeProject}
              canMutate={canMutate}
              selectedSourceIds={selectedSourceIds}
              onClearSourceScope={clearSourceScope}
              onRequestArtifact={requestArtifact}
              onCitationHover={setHighlightedSourceId}
              registerActions={registerWorkspaceActions}
            />
          </ResizablePanel>
          <WorkspaceResizeHandle />
          <ResizablePanel
            id="workspace-studio"
            defaultSize="28%"
            minSize="22%"
            maxSize="38%"
          >
            <StudioOutputsPanel
              activeProject={activeProject}
              canMutate={canMutate}
              request={studioRequest}
              selectedArtifact={selectedArtifact}
              selectedArtifactId={selectedArtifact?.report_id ?? null}
              onOpenArtifact={openArtifact}
              onCloseArtifact={() => setSelectedArtifact(null)}
              onRequestArtifact={requestArtifact}
              onCitationHover={setHighlightedSourceId}
              registerActions={registerWorkspaceActions}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden pb-16 lg:hidden">
        <AnimatePresence mode="wait">
          {activeTab === "research" ? (
            <motion.div
              key="mobile-research"
              {...(reduceMotion ? noMotion : fadeUp)}
              className="h-full"
            >
              <ResearchCanvasPanel
                activeProject={activeProject}
                canMutate={canMutate}
                selectedSourceIds={selectedSourceIds}
                onClearSourceScope={clearSourceScope}
                onRequestArtifact={requestArtifact}
                onCitationHover={setHighlightedSourceId}
                registerActions={registerWorkspaceActions}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>

        <AnimatePresence>
          {activeTab === "sources" ? (
            <MobileWorkspaceDrawer
              key="mobile-sources"
              title="Sources"
              reduceMotion={reduceMotion}
              onClose={() => setActiveTab("research")}
            >
              <KnowledgeSourcesPanel
                activeProject={activeProject}
                canMutate={canMutate}
                selectedSourceIds={selectedSourceIds}
                setSelectedSourceIds={setSelectedSourceIds}
                highlightedSourceId={highlightedSourceId}
                registerActions={registerWorkspaceActions}
              />
            </MobileWorkspaceDrawer>
          ) : null}
          {activeTab === "studio" ? (
            <MobileWorkspaceDrawer
              key="mobile-studio"
              title="Studio"
              reduceMotion={reduceMotion}
              onClose={() => setActiveTab("research")}
            >
              <StudioOutputsPanel
                activeProject={activeProject}
                canMutate={canMutate}
                request={studioRequest}
                selectedArtifact={selectedArtifact}
                selectedArtifactId={selectedArtifact?.report_id ?? null}
                onOpenArtifact={openArtifact}
                onCloseArtifact={() => setSelectedArtifact(null)}
                onRequestArtifact={requestArtifact}
                onCitationHover={setHighlightedSourceId}
                registerActions={registerWorkspaceActions}
              />
            </MobileWorkspaceDrawer>
          ) : null}
        </AnimatePresence>

        <MobileWorkspaceTabs
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onCommand={() => setCommandOpen(true)}
        />
      </div>
    </div>
  );
}

function WorkspaceResizeHandle() {
  return (
    <ResizableHandle className="group flex w-3 cursor-col-resize items-center justify-center bg-transparent transition-colors hover:bg-primary/5">
      <div className="h-12 w-1 rounded-full bg-border transition-colors group-hover:bg-primary/50" />
    </ResizableHandle>
  );
}

function MobileWorkspaceDrawer({
  title,
  reduceMotion,
  onClose,
  children,
}: {
  title: string;
  reduceMotion: boolean | null;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <motion.div
      className="holo-surface absolute inset-0 z-30 flex flex-col bg-background/95 backdrop-blur-xl"
      initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 32 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 32 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-border/70 bg-card/65 px-4">
        <div className="flex items-center gap-2">
          <PanelBottomOpen className="h-4 w-4 text-primary" />
          <p className="text-sm font-semibold text-foreground">{title}</p>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden pb-14">{children}</div>
    </motion.div>
  );
}

function MobileWorkspaceTabs({
  activeTab,
  setActiveTab,
  onCommand,
}: {
  activeTab: WorkspaceTab;
  setActiveTab: (tab: WorkspaceTab) => void;
  onCommand: () => void;
}) {
  const tabs: Array<{
    value: WorkspaceTab;
    label: string;
    icon: typeof Layers;
  }> = [
    { value: "sources", label: "Sources", icon: Layers },
    { value: "research", label: "Research", icon: MessageSquare },
    { value: "studio", label: "Studio", icon: Sparkles },
  ];

  return (
    <div className="holo-surface fixed inset-x-0 bottom-0 z-40 border-t border-border/70 bg-card/90 px-3 py-2 backdrop-blur-xl lg:hidden">
      <div className="grid grid-cols-4 gap-1">
        {tabs.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            onClick={() => setActiveTab(value)}
            className={cn(
              "flex flex-col items-center gap-1 rounded-lg px-2 py-1.5 text-[11px] font-medium transition-colors",
              activeTab === value
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
        <button
          type="button"
          onClick={onCommand}
          className="flex flex-col items-center gap-1 rounded-lg px-2 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent/70 hover:text-foreground"
        >
          <Search className="h-4 w-4" />
          Commands
        </button>
      </div>
    </div>
  );
}

function WorkspaceCommandPalette({
  open,
  onOpenChange,
  activeTab,
  setActiveTab,
  canMutate,
  selectedSourceCount,
  actionsRef,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activeTab: WorkspaceTab;
  setActiveTab: (tab: WorkspaceTab) => void;
  canMutate: boolean;
  selectedSourceCount: number;
  actionsRef: RefObject<WorkspaceActions>;
}) {
  const reduceMotion = useReducedMotion();
  if (!open) return null;

  function run(action: () => void, disabled = false) {
    if (disabled) return;
    action();
    onOpenChange(false);
  }

  const commands = [
    {
      label: "Focus ask box",
      hint: "Research",
      action: () => actionsRef.current?.focusAsk?.(),
    },
    {
      label: "Start new chat",
      hint: "Research",
      disabled: !canMutate,
      action: () => actionsRef.current?.newChat?.(),
    },
    {
      label: "Upload source",
      hint: "Sources",
      disabled: !canMutate,
      action: () => actionsRef.current?.uploadSource?.(),
    },
    {
      label: `Process selected sources (${selectedSourceCount})`,
      hint: "Sources",
      disabled: !canMutate || selectedSourceCount === 0,
      action: () => actionsRef.current?.processSelectedSources?.(),
    },
    {
      label: "Generate research brief",
      hint: "Studio",
      disabled: !canMutate,
      action: () => actionsRef.current?.generateArtifact?.("research_brief"),
    },
    {
      label: "Generate flashcards",
      hint: "Studio",
      disabled: !canMutate,
      action: () => actionsRef.current?.generateArtifact?.("flashcards"),
    },
    {
      label: "Generate mind map",
      hint: "Studio",
      disabled: !canMutate,
      action: () => actionsRef.current?.generateArtifact?.("mind_map"),
    },
    {
      label: "Refresh sources",
      hint: "Sources",
      action: () => actionsRef.current?.refreshSources?.(),
    },
    {
      label: "Refresh artifacts",
      hint: "Studio",
      action: () => actionsRef.current?.refreshArtifacts?.(),
    },
    {
      label: "Switch to Sources",
      hint: activeTab === "sources" ? "Current" : "Panel",
      action: () => setActiveTab("sources"),
    },
    {
      label: "Switch to Research",
      hint: activeTab === "research" ? "Current" : "Panel",
      action: () => setActiveTab("research"),
    },
    {
      label: "Switch to Studio",
      hint: activeTab === "studio" ? "Current" : "Panel",
      action: () => setActiveTab("studio"),
    },
  ];

  return (
    <motion.div
      className="fixed inset-0 z-50 bg-background/60 p-4 backdrop-blur-md"
      onClick={() => onOpenChange(false)}
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
    >
      <motion.div
        className="mx-auto mt-20 max-w-xl"
        onClick={(event) => event.stopPropagation()}
        initial={
          reduceMotion ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.96 }
        }
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.16 }}
      >
        <CmdkCommand className="holo-surface overflow-hidden rounded-xl text-popover-foreground shadow-2xl">
          <div className="flex items-center gap-2 border-b border-border/70 px-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <CmdkCommand.Input
              autoFocus
              placeholder="Run a workspace command..."
              className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <CmdkCommand.List className="max-h-80 overflow-y-auto p-2">
            <CmdkCommand.Empty className="px-3 py-8 text-center text-sm text-muted-foreground">
              No commands found.
            </CmdkCommand.Empty>
            {commands.map((command) => (
              <CmdkCommand.Item
                key={command.label}
                value={command.label}
                disabled={command.disabled}
                onSelect={() => run(command.action, command.disabled)}
                className={cn(
                  "flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm outline-none data-[selected=true]:bg-primary/10 data-[selected=true]:text-primary",
                  command.disabled && "cursor-not-allowed opacity-40",
                )}
              >
                <span>{command.label}</span>
                <span className="text-xs text-muted-foreground">
                  {command.hint}
                </span>
              </CmdkCommand.Item>
            ))}
          </CmdkCommand.List>
        </CmdkCommand>
      </motion.div>
    </motion.div>
  );
}

function WorkspaceEmptyState() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-transparent p-6">
      <div className="holo-surface holo-edge w-full max-w-lg rounded-xl p-8 text-center shadow-xl">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary shadow-sm">
          <BrainCircuit className="h-6 w-6" />
        </div>
        <h1 className="holo-text font-display text-xl font-semibold">
          Select a project first
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          The research workspace is scoped to one active project so sources,
          chat, and studio artifacts stay connected.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
          <Link href="/projects" className={buttonVariants()}>
            <FolderOpen className="h-4 w-4" />
            Create/select project
          </Link>
          <Link
            href="/projects"
            className={buttonVariants({ variant: "outline" })}
          >
            Open projects
          </Link>
        </div>
      </div>
    </div>
  );
}

function WorkspaceTopBar({ activeProject }: { activeProject: StoredProject }) {
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const isDark = theme === "dark";

  return (
    <header className="holo-surface flex h-14 shrink-0 items-center justify-between rounded-none border-x-0 border-t-0 border-border/70 bg-card/80 px-4 backdrop-blur-xl">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary text-primary-foreground shadow-sm">
          <BrainCircuit className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="holo-text font-display truncate text-sm font-semibold">
              NoteMesh Workspace
            </p>
            {activeProject.role ? (
              <Badge
                variant="secondary"
                className="hidden text-[10px] capitalize sm:inline-flex"
              >
                {activeProject.role}
              </Badge>
            ) : null}
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {activeProject.name}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <Link
          href="/projects"
          className={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "hidden sm:inline-flex",
          )}
        >
          <FolderOpen className="h-4 w-4" />
          Projects
        </Link>
        <Link
          href="/settings"
          className={buttonVariants({ variant: "ghost", size: "icon" })}
          title="Settings"
        >
          <Settings className="h-4 w-4" />
        </Link>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          title="Toggle theme"
        >
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <div className="hidden max-w-36 truncate px-2 text-xs text-muted-foreground md:block">
          {user?.display_name ?? user?.email}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={logout}
          title="Log out"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}

function PanelFrame({
  title,
  description,
  icon: Icon,
  action,
  children,
}: {
  title: string;
  description: string;
  icon: typeof Search;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex h-full min-h-0 flex-col bg-transparent">
      <div className="holo-surface flex shrink-0 items-start justify-between gap-3 rounded-none border-x-0 border-t-0 border-border/70 bg-card/60 px-4 py-3 backdrop-blur-xl">
        <div className="flex min-w-0 items-start gap-2.5">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary dark:bg-primary/15">
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h2 className="font-display truncate text-sm font-semibold text-foreground">
              {title}
            </h2>
            <p className="truncate text-xs text-muted-foreground">
              {description}
            </p>
          </div>
        </div>
        {action}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </section>
  );
}

function KnowledgeSourcesPanel({
  activeProject,
  canMutate,
  selectedSourceIds,
  setSelectedSourceIds,
  highlightedSourceId,
  registerActions,
}: {
  activeProject: StoredProject;
  canMutate: boolean;
  selectedSourceIds: Set<string>;
  setSelectedSourceIds: Dispatch<SetStateAction<Set<string>>>;
  highlightedSourceId: string | null;
  registerActions: (actions: Partial<WorkspaceActions>) => void;
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [processingActive, setProcessingActive] = useState(false);
  const [sourceTool, setSourceTool] = useState<SourceTool>("add");
  const [driveFolderPath, setDriveFolderPath] = useState<
    Array<{ id: string; name: string }>
  >([{ id: "root", name: "My Drive" }]);
  const [driveSearch, setDriveSearch] = useState("");
  const [driveItems, setDriveItems] = useState<GoogleDriveBrowseItemData[]>([]);
  const [driveLoading, setDriveLoading] = useState(false);
  const [driveImportingId, setDriveImportingId] = useState<string | null>(null);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["workspace-sources", activeProject.id],
    queryFn: () => listSources(activeProject.id),
  });

  const sources = data?.data.items ?? [];
  const indexedCount = sources.filter(
    (source) => source.indexing?.is_indexed,
  ).length;
  const sourceUrls = new Set(
    sources
      .map((source) => source.file_name)
      .filter(
        (item) => item.startsWith("http://") || item.startsWith("https://"),
      ),
  );
  const { data: jobsData } = useQuery({
    queryKey: ["workspace-processing-jobs", activeProject.id],
    queryFn: () => listProjectJobs(activeProject.id),
    enabled: processingActive,
    refetchInterval: processingActive ? 2000 : false,
  });
  const processingJobs = (jobsData?.data.items ?? []).filter(
    (job) =>
      job.type === "processing" && ["queued", "running"].includes(job.status),
  );
  const { data: integrationsData, refetch: refetchIntegrations } = useQuery({
    queryKey: ["workspace-integrations", activeProject.id],
    queryFn: () => listProjectIntegrations(activeProject.id),
    enabled: sourceTool === "drive",
  });
  const googleDriveIntegration = integrationsData?.data.items.find(
    (integration) => integration.provider === "google_drive",
  );

  useEffect(() => {
    if (processingActive && jobsData && processingJobs.length === 0) {
      setProcessingActive(false);
      void refreshSources();
    }
  }, [jobsData, processingActive, processingJobs.length]);

  function toggleSelected(sourceId: string) {
    setSelectedSourceIds((current) => {
      const next = new Set(current);
      if (next.has(sourceId)) {
        next.delete(sourceId);
      } else {
        next.add(sourceId);
      }
      return next;
    });
  }

  async function refreshSources() {
    await queryClient.invalidateQueries({
      queryKey: ["workspace-sources", activeProject.id],
    });
  }

  async function loadDriveItems(
    folderId = driveFolderPath.at(-1)?.id ?? "root",
    query = driveSearch,
  ) {
    setDriveLoading(true);
    try {
      const response = await browseGoogleDriveItems({
        projectId: activeProject.id,
        folderId,
        query: query.trim() || undefined,
        pageSize: 50,
      });
      setDriveItems(response.data.items);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to browse Google Drive.",
      );
      setDriveItems([]);
    } finally {
      setDriveLoading(false);
    }
  }

  async function openDriveFolder(item: GoogleDriveBrowseItemData) {
    const nextPath = [...driveFolderPath, { id: item.id, name: item.name }];
    setDriveFolderPath(nextPath);
    await loadDriveItems(item.id, driveSearch);
  }

  async function goBackDriveFolder() {
    if (driveFolderPath.length <= 1) return;
    const nextPath = driveFolderPath.slice(0, -1);
    const folder = nextPath.at(-1);
    if (!folder) return;
    setDriveFolderPath(nextPath);
    await loadDriveItems(folder.id, driveSearch);
  }

  async function handleDriveSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await loadDriveItems(driveFolderPath.at(-1)?.id ?? "root", driveSearch);
  }

  async function importDriveFile(item: GoogleDriveBrowseItemData) {
    if (!canMutate) {
      toast.error("This action requires editor role or higher.");
      return;
    }
    setDriveImportingId(item.id);
    const toastId = toast.loading(`Importing ${item.name}...`);
    try {
      await importProjectIntegrationSource({
        projectId: activeProject.id,
        provider: "google_drive",
        itemReference: item.id,
      });
      toast.success(
        "Google Drive source imported. Run processing to index it.",
        { id: toastId },
      );
      await refreshSources();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to import Drive file.",
        { id: toastId },
      );
    } finally {
      setDriveImportingId(null);
    }
  }

  useEffect(() => {
    if (sourceTool !== "drive" || !googleDriveIntegration?.configured) {
      return;
    }
    void loadDriveItems("root", "");
  }, [sourceTool, googleDriveIntegration?.configured]);

  useEffect(() => {
    registerActions({
      uploadSource: () => fileInputRef.current?.click(),
      processSelectedSources: () => void handleProcessSelected(),
      refreshSources: () => void refreshSources(),
    });
  });

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) return;
    setBusy(true);
    const toastId = toast.loading(
      `Uploading ${files.length} source${files.length > 1 ? "s" : ""}...`,
    );
    try {
      for (const file of files) {
        await uploadSourceFile({ projectId: activeProject.id, file });
      }
      toast.success("Sources uploaded.", { id: toastId });
      await refreshSources();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed.", {
        id: toastId,
      });
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    const toastId = toast.loading("Adding web source...");
    try {
      await ingestSourceUrl({ projectId: activeProject.id, url: url.trim() });
      setUrl("");
      toast.success("Web source added.", { id: toastId });
      await refreshSources();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not add source.",
        { id: toastId },
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleProcessSelected() {
    const sourceIds = Array.from(selectedSourceIds);
    if (!sourceIds.length) {
      toast.error("Select at least one source to process.");
      return;
    }
    setBusy(true);
    const toastId = toast.loading("Indexing selected sources...");
    try {
      await processSources({ projectId: activeProject.id, sourceIds });
      setProcessingActive(true);
      toast.success("Processing job started.", { id: toastId });
      await refreshSources();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Processing failed.",
        { id: toastId },
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <PanelFrame
      title="Knowledge Sources"
      description={`${sources.length} sources, ${indexedCount} indexed`}
      icon={Layers}
      action={
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => void refetch()}
        >
          {isFetching ? (
            <Spinner className="h-4 w-4" />
          ) : (
            <RefreshCcw className="h-4 w-4" />
          )}
        </Button>
      }
    >
      <div className="space-y-4 p-4">
        <div className="rounded-lg border border-border bg-card p-3">
          <div className="mb-3 grid grid-cols-3 gap-1 rounded-lg bg-muted/45 p-1">
            {(
              [
                { value: "add", label: "Add", icon: Upload },
                { value: "web", label: "Web", icon: Search },
                { value: "drive", label: "Drive", icon: FolderOpen },
              ] as Array<{
                value: SourceTool;
                label: string;
                icon: typeof Upload;
              }>
            ).map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setSourceTool(value)}
                className={cn(
                  "flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-medium transition-colors",
                  sourceTool === value
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          {sourceTool === "add" ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-foreground">
                    Add source
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    PDF, DOCX, URL, arXiv and web pages.
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  disabled={!canMutate || busy}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-3.5 w-3.5" />
                  Upload
                </Button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={SUPPORTED_FILE_ACCEPT}
                className="hidden"
                onChange={handleUpload}
              />
              <form onSubmit={handleUrlSubmit} className="mt-3 flex gap-2">
                <Input
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://example.com/research or arXiv URL"
                  disabled={!canMutate || busy}
                  className="h-8 text-xs"
                />
                <Button
                  type="submit"
                  size="icon"
                  disabled={!canMutate || busy || !url.trim()}
                >
                  <Link2 className="h-4 w-4" />
                </Button>
              </form>
            </>
          ) : null}

          {sourceTool === "web" ? (
            <div className="max-h-[560px] min-h-[360px] overflow-hidden">
              <WebSourceDiscovery
                projectId={activeProject.id}
                canMutate={canMutate}
                addedUrls={sourceUrls}
                onSourceAdded={() => void refreshSources()}
                compact
              />
            </div>
          ) : null}

          {sourceTool === "drive" ? (
            <GoogleDriveSourceTool
              integration={googleDriveIntegration}
              canMutate={canMutate}
              driveItems={driveItems}
              driveFolderPath={driveFolderPath}
              driveSearch={driveSearch}
              driveLoading={driveLoading}
              driveImportingId={driveImportingId}
              onRefreshIntegration={() => void refetchIntegrations()}
              onSearchChange={setDriveSearch}
              onSearch={handleDriveSearch}
              onBack={() => void goBackDriveFolder()}
              onOpenFolder={(item) => void openDriveFolder(item)}
              onImport={(item) => void importDriveFile(item)}
              onReload={() => void loadDriveItems()}
            />
          ) : null}
        </div>

        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            {selectedSourceIds.size} selected
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!canMutate || busy || selectedSourceIds.size === 0}
            onClick={() => void handleProcessSelected()}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Process
          </Button>
        </div>

        {processingActive ? (
          <SourceProcessingProgress jobs={processingJobs} />
        ) : null}

        {isLoading ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner />
          </div>
        ) : sources.length ? (
          <div className="space-y-2">
            {sources.map((source) => (
              <SourceRow
                key={source.id}
                source={source}
                selected={selectedSourceIds.has(source.id)}
                highlighted={highlightedSourceId === source.id}
                onToggle={() => toggleSelected(source.id)}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border p-6 text-center">
            <DatabaseIcon />
            <p className="mt-3 text-sm font-medium text-foreground">
              No sources yet
            </p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Add a file or URL to build the project knowledge base.
            </p>
            <div className="mt-4 flex flex-col justify-center gap-2 sm:flex-row">
              <Button
                type="button"
                size="sm"
                disabled={!canMutate || busy}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-3.5 w-3.5" />
                Upload file
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!canMutate || busy}
                onClick={() => setUrl("https://")}
              >
                <Link2 className="h-3.5 w-3.5" />
                Add URL
              </Button>
            </div>
          </div>
        )}
      </div>
    </PanelFrame>
  );
}

function GoogleDriveSourceTool({
  integration,
  canMutate,
  driveItems,
  driveFolderPath,
  driveSearch,
  driveLoading,
  driveImportingId,
  onRefreshIntegration,
  onSearchChange,
  onSearch,
  onBack,
  onOpenFolder,
  onImport,
  onReload,
}: {
  integration?: IntegrationConnectionData;
  canMutate: boolean;
  driveItems: GoogleDriveBrowseItemData[];
  driveFolderPath: Array<{ id: string; name: string }>;
  driveSearch: string;
  driveLoading: boolean;
  driveImportingId: string | null;
  onRefreshIntegration: () => void;
  onSearchChange: (value: string) => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onBack: () => void;
  onOpenFolder: (item: GoogleDriveBrowseItemData) => void;
  onImport: (item: GoogleDriveBrowseItemData) => void;
  onReload: () => void;
}) {
  if (!integration) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4 text-center">
        <Spinner className="mx-auto h-5 w-5" />
        <p className="mt-2 text-xs text-muted-foreground">
          Loading Google Drive integration...
        </p>
      </div>
    );
  }

  if (!integration.configured) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4 text-center">
        <FolderOpen className="mx-auto h-7 w-7 text-muted-foreground" />
        <p className="mt-2 text-sm font-medium text-foreground">
          Google Drive is not connected
        </p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          Connect Google Drive from the Sources page, then import Docs, Sheets,
          Slides, PDFs, and Office files here.
        </p>
        <div className="mt-4 flex justify-center gap-2">
          <Link href="/sources" className={buttonVariants({ size: "sm" })}>
            Connect Drive
            <ExternalLink className="h-3.5 w-3.5" />
          </Link>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onRefreshIntegration}
          >
            Refresh
          </Button>
        </div>
      </div>
    );
  }

  const currentFolder = driveFolderPath.at(-1)?.name ?? "My Drive";

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-foreground">
            Google Drive
          </p>
          <p className="truncate text-[11px] text-muted-foreground">
            {integration.account_label || integration.display_name}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onReload}
          disabled={driveLoading}
        >
          {driveLoading ? (
            <Spinner className="h-3.5 w-3.5" />
          ) : (
            <RefreshCcw className="h-3.5 w-3.5" />
          )}
          Reload
        </Button>
      </div>

      <form onSubmit={onSearch} className="flex gap-2">
        <Input
          value={driveSearch}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={`Search in ${currentFolder}`}
          className="h-8 text-xs"
        />
        <Button type="submit" size="icon" disabled={driveLoading}>
          <Search className="h-4 w-4" />
        </Button>
      </form>

      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={onBack}
          disabled={driveFolderPath.length <= 1 || driveLoading}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="truncate">
          {driveFolderPath.map((item) => item.name).join(" / ")}
        </span>
      </div>

      {driveLoading ? (
        <div className="flex h-32 items-center justify-center">
          <Spinner />
        </div>
      ) : driveItems.length ? (
        <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
          {driveItems.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-2 rounded-lg border border-border/70 bg-background/40 p-2"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                {item.is_folder ? (
                  <FolderOpen className="h-3.5 w-3.5" />
                ) : (
                  <FileText className="h-3.5 w-3.5" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium text-foreground">
                  {item.name}
                </p>
                <p className="truncate text-[10px] text-muted-foreground">
                  {item.is_folder ? "Folder" : item.mime_type}
                </p>
              </div>
              {item.is_folder ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onOpenFolder(item)}
                >
                  Open
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  disabled={
                    !canMutate ||
                    !item.is_supported_import ||
                    driveImportingId === item.id
                  }
                  onClick={() => onImport(item)}
                >
                  {driveImportingId === item.id ? (
                    <Spinner className="h-3.5 w-3.5" />
                  ) : (
                    <Plus className="h-3.5 w-3.5" />
                  )}
                  Import
                </Button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-4 text-center">
          <p className="text-xs text-muted-foreground">No Drive items found.</p>
        </div>
      )}
    </div>
  );
}

function DatabaseIcon() {
  return (
    <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
      <Layers className="h-5 w-5" />
    </div>
  );
}

function SourceProcessingProgress({ jobs }: { jobs: JobStatusData[] }) {
  const activeJobs = jobs.length;
  const averageProgress =
    activeJobs > 0
      ? Math.round(
          jobs.reduce((sum, job) => sum + job.progress, 0) / activeJobs,
        )
      : 5;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-primary/20 bg-primary/5 p-3"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-foreground">
            Indexing sources
          </p>
          <p className="text-[11px] text-muted-foreground">
            {activeJobs
              ? `${activeJobs} processing job${activeJobs > 1 ? "s" : ""} active`
              : "Waiting for job status..."}
          </p>
        </div>
        <Spinner className="h-4 w-4 text-primary" />
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-background">
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={{ width: "8%" }}
          animate={{ width: `${Math.max(averageProgress, 8)}%` }}
        />
      </div>
    </motion.div>
  );
}

function SourceRow({
  source,
  selected,
  highlighted,
  onToggle,
}: {
  source: SourceListItemData;
  selected: boolean;
  highlighted: boolean;
  onToggle: () => void;
}) {
  const trust = source.quality?.trust_score;
  const freshness = source.quality?.freshness_score;

  return (
    <motion.div
      layout
      whileHover={{ y: -1 }}
      className={cn(
        "holo-edge rounded-lg border bg-card/68 p-3 backdrop-blur transition-colors",
        selected
          ? "border-primary/50 bg-primary/10 dark:bg-primary/10"
          : "border-border/70 hover:border-primary/25",
        highlighted &&
          "border-warning bg-warning/10 shadow-sm dark:bg-warning/15",
      )}
    >
      <div className="flex items-start gap-3">
        <Checkbox
          checked={selected}
          onCheckedChange={onToggle}
          className="mt-1"
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-xs font-semibold text-foreground">
              {source.file_name}
            </p>
            <Badge
              variant={getSourceStatusVariant(source.status)}
              className="text-[10px]"
            >
              {source.status}
            </Badge>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="outline" className="text-[10px]">
              {source.type}
            </Badge>
            {source.indexing?.is_indexed ? (
              <Badge variant="success" className="gap-1 text-[10px]">
                <CheckCircle2 className="h-3 w-3" />
                {source.indexing.chunk_count} chunks
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-[10px]">
                Not indexed
              </Badge>
            )}
            {typeof trust === "number" ? (
              <Badge variant="outline" className="text-[10px]">
                Trust {Math.round(trust * 100)}%
              </Badge>
            ) : null}
            {typeof freshness === "number" ? (
              <Badge variant="outline" className="text-[10px]">
                Fresh {Math.round(freshness * 100)}%
              </Badge>
            ) : null}
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {formatDate(source.created_at)}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

function ResearchCanvasPanel({
  activeProject,
  canMutate,
  selectedSourceIds,
  onClearSourceScope,
  onRequestArtifact,
  onCitationHover,
  registerActions,
}: {
  activeProject: StoredProject;
  canMutate: boolean;
  selectedSourceIds: Set<string>;
  onClearSourceScope: () => void;
  onRequestArtifact: (query: string, type: ReportType) => void;
  onCitationHover: (sourceId: string | null) => void;
  registerActions: (actions: Partial<WorkspaceActions>) => void;
}) {
  const queryClient = useQueryClient();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [optimisticMessage, setOptimisticMessage] = useState<string | null>(
    null,
  );
  const [assistantStage, setAssistantStage] = useState("Retrieving evidence");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const askInputRef = useRef<HTMLTextAreaElement>(null);
  const suggestedPrompts = [
    "Summarize the strongest evidence in this project.",
    "What are the open risks or contradictions?",
    "Create a study plan from the indexed sources.",
  ];

  const { data: sessionsData, isLoading: loadingSessions } = useQuery({
    queryKey: ["workspace-chat-sessions", activeProject.id],
    queryFn: () => listChatSessions(activeProject.id),
  });
  const sessions = sessionsData?.data.items ?? [];

  const { data: messagesData, isLoading: loadingMessages } = useQuery({
    queryKey: ["workspace-chat-messages", activeSessionId],
    queryFn: () => listChatMessages(activeSessionId!),
    enabled: !!activeSessionId,
  });
  const messages = messagesData?.data.items ?? [];

  useEffect(() => {
    if (!activeSessionId && sessions.length > 0 && !loadingSessions) {
      setActiveSessionId(sessions[0].id);
    }
  }, [activeSessionId, sessions, loadingSessions]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sending, optimisticMessage]);

  useEffect(() => {
    if (!sending) return;
    const stages = [
      "Retrieving evidence",
      "Ranking citations",
      "Drafting answer",
    ];
    let index = 0;
    setAssistantStage(stages[index]);
    const interval = window.setInterval(() => {
      index = (index + 1) % stages.length;
      setAssistantStage(stages[index]);
    }, 1400);
    return () => window.clearInterval(interval);
  }, [sending]);

  useEffect(() => {
    registerActions({
      focusAsk: () => {
        askInputRef.current?.focus();
      },
      newChat: () => {
        setActiveSessionId(null);
      },
    });
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = inputValue.trim();
    if (!content || sending) return;
    if (!canMutate) {
      toast.error("Sending messages requires editor role or higher.");
      return;
    }

    setInputValue("");
    setOptimisticMessage(content);
    setSending(true);
    let sessionId = activeSessionId;
    const scopedSourceIds = Array.from(selectedSourceIds);

    try {
      if (!sessionId) {
        const title =
          content.length > 42 ? `${content.slice(0, 42)}...` : content;
        const session = await createChatSession({
          projectId: activeProject.id,
          title,
        });
        sessionId = session.data.id;
        setActiveSessionId(sessionId);
        await queryClient.invalidateQueries({
          queryKey: ["workspace-chat-sessions", activeProject.id],
        });
      }

      await sendChatMessage({
        sessionId,
        content,
        provider: "openai",
        topK: 5,
        filters: scopedSourceIds.length
          ? { source_ids: scopedSourceIds }
          : undefined,
      });
      await queryClient.invalidateQueries({
        queryKey: ["workspace-chat-messages", sessionId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["workspace-chat-sessions", activeProject.id],
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Message failed.");
    } finally {
      setSending(false);
      setOptimisticMessage(null);
    }
  }

  async function handleMessageAction(
    messageId: string,
    patch: { isBookmarked?: boolean; rating?: number },
  ) {
    try {
      await updateChatMessage({ messageId, ...patch });
      await queryClient.invalidateQueries({
        queryKey: ["workspace-chat-messages", activeSessionId],
      });
    } catch {
      toast.error("Could not update message.");
    }
  }

  return (
    <PanelFrame
      title="Research Canvas"
      description="Ask, verify citations, and branch answers into artifacts"
      icon={MessageSquare}
      action={
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setActiveSessionId(null)}
          disabled={!canMutate}
        >
          <Plus className="h-4 w-4" />
          New
        </Button>
      }
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b border-border bg-card/30 px-4 py-2">
          <div className="flex gap-2 overflow-x-auto">
            {sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => setActiveSessionId(session.id)}
                className={cn(
                  "max-w-44 shrink-0 truncate rounded-md border px-3 py-1.5 text-xs transition-colors",
                  activeSessionId === session.id
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border bg-background text-muted-foreground hover:text-foreground",
                )}
              >
                {session.title || "Untitled chat"}
              </button>
            ))}
          </div>
          <SourceScopeBar
            selectedCount={selectedSourceIds.size}
            onClear={onClearSourceScope}
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {loadingMessages || loadingSessions ? (
            <div className="flex h-full items-center justify-center">
              <Spinner />
            </div>
          ) : messages.length ? (
            <div className="space-y-4">
              {messages.map((message) => (
                <ChatMessageCard
                  key={message.id}
                  message={message}
                  onRequestArtifact={onRequestArtifact}
                  onMessageAction={handleMessageAction}
                  onCitationHover={onCitationHover}
                />
              ))}
              {optimisticMessage ? (
                <OptimisticChatBubble content={optimisticMessage} />
              ) : null}
              {sending ? <AssistantSkeleton stage={assistantStage} /> : null}
              <div ref={messagesEndRef} />
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-8">
              <div className="max-w-lg text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <MessageSquare className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-foreground">
                  Start with a research question
                </h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Ask across indexed sources, then turn strong answers into
                  reports, flashcards, or a mind map without leaving the
                  workspace.
                </p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {suggestedPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => setInputValue(prompt)}
                      className="rounded-full border border-border/70 bg-card/60 px-3 py-1.5 text-xs text-muted-foreground backdrop-blur transition-colors hover:border-primary/30 hover:bg-primary/10 hover:text-foreground"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <form
          onSubmit={handleSubmit}
          className="holo-surface shrink-0 rounded-none border-x-0 border-b-0 border-t border-border/70 bg-card/78 p-3 pb-20 lg:pb-3"
        >
          <div className="flex items-center gap-2">
            <Textarea
              ref={askInputRef}
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Ask about the selected research project..."
              className="min-h-11 resize-none text-sm"
              disabled={!canMutate || sending}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!canMutate || sending || !inputValue.trim()}
            >
              {sending ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </form>
      </div>
    </PanelFrame>
  );
}

function ChatMessageCard({
  message,
  onRequestArtifact,
  onMessageAction,
  onCitationHover,
}: {
  message: ChatMessageData;
  onRequestArtifact: (query: string, type: ReportType) => void;
  onMessageAction: (
    messageId: string,
    patch: { isBookmarked?: boolean; rating?: number },
  ) => void;
  onCitationHover: (sourceId: string | null) => void;
}) {
  const isAssistant = message.role === "assistant";

  async function copyMessage() {
    await navigator.clipboard.writeText(message.content);
    toast.success("Copied message.");
  }

  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "holo-edge rounded-lg border p-4 backdrop-blur",
        isAssistant
          ? "border-primary/20 bg-card/82 shadow-sm dark:bg-card/80"
          : "ml-auto max-w-[88%] border-border/70 bg-muted/55 dark:bg-muted/40",
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-lg",
              isAssistant
                ? "border border-primary/20 bg-primary/15 text-primary"
                : "bg-secondary text-secondary-foreground",
            )}
          >
            {isAssistant ? (
              <BrainCircuit className="h-4 w-4" />
            ) : (
              <MessageSquare className="h-4 w-4" />
            )}
          </div>
          <span className="text-xs font-semibold capitalize text-foreground">
            {message.role}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={copyMessage}
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
          {isAssistant ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() =>
                onMessageAction(message.id, {
                  isBookmarked: !message.is_bookmarked,
                })
              }
            >
              <BookOpen
                className={cn(
                  "h-3.5 w-3.5",
                  message.is_bookmarked && "text-primary",
                )}
              />
            </Button>
          ) : null}
        </div>
      </div>

      <div className="prose prose-sm max-w-none dark:prose-invert">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {message.content}
        </ReactMarkdown>
      </div>
      <CitationChips
        citations={message.citations ?? []}
        onCitationHover={onCitationHover}
      />

      {isAssistant ? (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onRequestArtifact(message.content, "research_brief")}
          >
            <FileText className="h-3.5 w-3.5" />
            Research brief
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onRequestArtifact(message.content, "flashcards")}
          >
            <Layers className="h-3.5 w-3.5" />
            Flashcards
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onRequestArtifact(message.content, "mind_map")}
          >
            <Workflow className="h-3.5 w-3.5" />
            Mind map
          </Button>
        </div>
      ) : null}
    </motion.article>
  );
}

function SourceScopeBar({
  selectedCount,
  onClear,
}: {
  selectedCount: number;
  onClear: () => void;
}) {
  return (
    <div className="mt-2 flex items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Layers className="h-3.5 w-3.5" />
        <span>
          {selectedCount > 0
            ? `Scoped to ${selectedCount} selected source${selectedCount > 1 ? "s" : ""}`
            : "Using all indexed sources"}
        </span>
      </div>
      {selectedCount > 0 ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-6 px-2"
          onClick={onClear}
        >
          <X className="h-3.5 w-3.5" />
          Clear
        </Button>
      ) : null}
    </div>
  );
}

function OptimisticChatBubble({ content }: { content: string }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="ml-auto max-w-[88%] rounded-lg border border-border bg-muted/60 p-4"
    >
      <div className="mb-2 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
          <MessageSquare className="h-4 w-4" />
        </div>
        <span className="text-xs font-semibold text-foreground">user</span>
      </div>
      <p className="text-sm leading-6 text-foreground">{content}</p>
    </motion.article>
  );
}

function AssistantSkeleton({ stage }: { stage: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-primary/15 bg-card p-4 shadow-sm"
    >
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="h-4 w-4 text-primary" />
        {stage}...
      </div>
      <div className="mt-4 space-y-2">
        <div className="h-3 w-3/4 animate-pulse rounded-full bg-muted" />
        <div className="h-3 w-11/12 animate-pulse rounded-full bg-muted" />
        <div className="h-3 w-2/3 animate-pulse rounded-full bg-muted" />
      </div>
    </motion.div>
  );
}

function ArtifactCanvas({
  report,
  onRequestArtifact,
  onCitationHover,
}: {
  report: ReportResult;
  onRequestArtifact: (query: string, type: ReportType) => void;
  onCitationHover: (sourceId: string | null) => void;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <motion.div
          key={report.report_id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-auto max-w-5xl space-y-5"
        >
          {report.type === "quiz" ? (
            <QuizAttemptView
              report={report}
              onCitationHover={onCitationHover}
            />
          ) : (
            <ArtifactStructuredView report={report} />
          )}
          <CitationChips
            citations={report.citations ?? []}
            onCitationHover={onCitationHover}
          />

          <div className="rounded-lg border border-border bg-card p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">
                  Branch from this artifact
                </p>
                <p className="text-xs text-muted-foreground">
                  Reuse the artifact query to create another study output.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onRequestArtifact(report.query, "summary")}
              >
                <BookOpen className="h-3.5 w-3.5" />
                Summary
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onRequestArtifact(report.query, "quiz")}
              >
                <CircleHelp className="h-3.5 w-3.5" />
                Quiz
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onRequestArtifact(report.query, "study_guide")}
              >
                <BookOpen className="h-3.5 w-3.5" />
                Study guide
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onRequestArtifact(report.query, "conflict_mesh")}
              >
                <Share2 className="h-3.5 w-3.5" />
                Mesh
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onRequestArtifact(report.query, "podcast")}
              >
                <Mic className="h-3.5 w-3.5" />
                Podcast
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

function ArtifactStructuredView({ report }: { report: ReportResult }) {
  const payload = report.structured_payload;

  if (payload && typeof payload === "object") {
    if ("dialogue" in payload && Array.isArray(payload.dialogue)) {
      return (
        <ArtifactSection
          title="AI Podcast"
          description={describeStructuredPayload(payload)}
        >
          <WorkspacePodcastPlayer report={report} dialogue={payload.dialogue} />
        </ArtifactSection>
      );
    }

    if ("cards" in payload && Array.isArray(payload.cards)) {
      return (
        <ArtifactSection
          title="Flashcards"
          description={describeStructuredPayload(payload)}
        >
          <WorkspaceFlashcardDeck cards={payload.cards} />
        </ArtifactSection>
      );
    }

    if ("questions" in payload && Array.isArray(payload.questions)) {
      return (
        <ArtifactSection
          title="Quiz"
          description={describeStructuredPayload(payload)}
        >
          <div className="space-y-3">
            {payload.questions.map((question, index) => {
              const item = question as Record<string, unknown>;
              const options = Array.isArray(item.options) ? item.options : [];
              return (
                <ArtifactItemCard key={String(item.id ?? index)}>
                  <p className="text-sm font-semibold text-foreground">
                    {index + 1}. {String(item.question ?? "Untitled question")}
                  </p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {options.map((option, optionIndex) => {
                      const optionItem = option as Record<string, unknown>;
                      return (
                        <div
                          key={String(optionItem.id ?? optionIndex)}
                          className="rounded-md border border-border bg-background px-3 py-2 text-xs"
                        >
                          <span className="font-semibold">
                            {String(optionItem.id ?? optionIndex + 1)}.
                          </span>{" "}
                          {String(optionItem.text ?? "")}
                        </div>
                      );
                    })}
                  </div>
                  {item.explanation ? (
                    <p className="mt-3 text-xs leading-5 text-muted-foreground">
                      {String(item.explanation)}
                    </p>
                  ) : null}
                </ArtifactItemCard>
              );
            })}
          </div>
        </ArtifactSection>
      );
    }

    if ("sections" in payload && Array.isArray(payload.sections)) {
      return (
        <ArtifactSection
          title="Study Guide"
          description={describeStructuredPayload(payload)}
        >
          <div className="space-y-3">
            {payload.sections.map((section, index) => {
              const item = section as Record<string, unknown>;
              const points = Array.isArray(item.key_points)
                ? item.key_points
                : [];
              return (
                <ArtifactItemCard key={String(item.id ?? index)}>
                  <p className="text-sm font-semibold text-foreground">
                    {String(item.title ?? `Section ${index + 1}`)}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {String(item.summary ?? "")}
                  </p>
                  {points.length ? (
                    <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-5 text-muted-foreground">
                      {points.map((point, pointIndex) => (
                        <li key={pointIndex}>{String(point)}</li>
                      ))}
                    </ul>
                  ) : null}
                </ArtifactItemCard>
              );
            })}
          </div>
        </ArtifactSection>
      );
    }

    if ("nodes" in payload && Array.isArray(payload.nodes)) {
      if (report.type === "conflict_mesh") {
        return (
          <ArtifactSection
            title="Conflict Mesh Graph"
            description={describeStructuredPayload(payload)}
          >
            <div className="h-[380px] w-full border border-border rounded-xl overflow-hidden bg-background">
              <MeshGraph payload={payload as any} compact={true} />
            </div>
          </ArtifactSection>
        );
      }

      if (report.type === "mind_map") {
        return (
          <ArtifactSection
            title="Mind Map Graph"
            description={describeStructuredPayload(payload)}
          >
            <WorkspaceMindMap payload={payload} />
          </ArtifactSection>
        );
      }

      const nodes = payload.nodes as Array<Record<string, unknown>>;
      const edges =
        "edges" in payload && Array.isArray(payload.edges) ? payload.edges : [];
      return (
        <ArtifactSection
          title="Mesh"
          description={describeStructuredPayload(payload)}
        >
          <div className="grid gap-3 md:grid-cols-[1fr_0.85fr]">
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <p className="mb-3 text-xs font-semibold uppercase text-muted-foreground">
                Nodes
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {nodes.slice(0, 18).map((node, index) => (
                  <div
                    key={String(node.id ?? index)}
                    className="rounded-md border border-border bg-card p-3"
                  >
                    <p className="truncate text-xs font-semibold text-foreground">
                      {String(node.label ?? `Node ${index + 1}`)}
                    </p>
                    <p className="mt-1 line-clamp-3 text-[11px] leading-5 text-muted-foreground">
                      {String(node.summary ?? node.description ?? "")}
                    </p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs font-semibold uppercase text-muted-foreground">
                Relationships
              </p>
              <p className="mt-2 text-3xl font-semibold text-foreground">
                {edges.length}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Open the full viewer for interactive 2D/3D exploration.
              </p>
            </div>
          </div>
        </ArtifactSection>
      );
    }

    return (
      <ArtifactSection
        title={REPORT_LABELS[report.type] ?? "Artifact"}
        description={describeStructuredPayload(payload)}
      >
        <pre className="max-h-[520px] overflow-auto rounded-lg bg-muted p-4 text-xs text-muted-foreground">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </ArtifactSection>
    );
  }

  if (report.content) {
    return (
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {report.content}
          </ReactMarkdown>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-dashed border-border p-8 text-center">
      <FileText className="mx-auto h-9 w-9 text-muted-foreground" />
      <p className="mt-3 text-sm font-medium text-foreground">
        Artifact has no preview payload
      </p>
    </div>
  );
}

function QuizAttemptView({
  report,
  onCitationHover,
}: {
  report: ReportResult;
  onCitationHover: (sourceId: string | null) => void;
}) {
  const payload = report.structured_payload;
  const questions =
    payload &&
    typeof payload === "object" &&
    "questions" in payload &&
    Array.isArray(payload.questions)
      ? (payload.questions as QuizQuestionData[])
      : [];
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    setCurrentIndex(0);
    setAnswers({});
    setSubmitted(false);
  }, [report.report_id]);

  if (!questions.length) {
    return <ArtifactStructuredView report={report} />;
  }

  const currentQuestion =
    questions[Math.min(currentIndex, questions.length - 1)];
  const selectedOptionId = answers[currentQuestion.id];
  const answeredCount = questions.filter(
    (question) => answers[question.id],
  ).length;
  const score = questions.reduce(
    (total, question) =>
      total + (answers[question.id] === question.correct_option_id ? 1 : 0),
    0,
  );
  const scorePercent = Math.round((score / questions.length) * 100);
  const progressPercent = Math.round(
    ((currentIndex + 1) / questions.length) * 100,
  );

  function selectAnswer(optionId: string) {
    if (submitted) return;
    setAnswers((current) => ({
      ...current,
      [currentQuestion.id]: optionId,
    }));
  }

  function goNext() {
    if (!selectedOptionId) return;
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((index) => index + 1);
      return;
    }
    setSubmitted(true);
  }

  function resetAttempt() {
    setCurrentIndex(0);
    setAnswers({});
    setSubmitted(false);
  }

  if (submitted) {
    return (
      <ArtifactSection
        title="Quiz results"
        description={`${score} of ${questions.length} correct`}
      >
        <div className="rounded-lg border border-primary/20 bg-primary/10 p-4">
          <p className="text-xs font-semibold uppercase text-primary">Score</p>
          <p className="mt-2 text-4xl font-semibold text-foreground">
            {scorePercent}%
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {score} correct answers out of {questions.length}.
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-4"
            onClick={resetAttempt}
          >
            Retry quiz
          </Button>
        </div>

        <div className="mt-4 space-y-3">
          {questions.map((question, index) => {
            const selected = question.options.find(
              (option) => option.id === answers[question.id],
            );
            const correct = question.options.find(
              (option) => option.id === question.correct_option_id,
            );
            const isCorrect = selected?.id === question.correct_option_id;

            return (
              <div
                key={question.id}
                className="rounded-lg border border-border bg-background p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold leading-6 text-foreground">
                    {index + 1}. {question.question}
                  </p>
                  <Badge
                    variant={isCorrect ? "success" : "destructive"}
                    className="shrink-0 text-[10px]"
                  >
                    {isCorrect ? "Correct" : "Review"}
                  </Badge>
                </div>
                <div className="mt-3 space-y-2 text-xs leading-5">
                  <p className="text-muted-foreground">
                    Your answer:{" "}
                    <span
                      className={cn(
                        "font-semibold",
                        isCorrect ? "text-foreground" : "text-destructive",
                      )}
                    >
                      {selected?.text ?? "No answer"}
                    </span>
                  </p>
                  {!isCorrect ? (
                    <p className="text-muted-foreground">
                      Correct answer:{" "}
                      <span className="font-semibold text-foreground">
                        {correct?.text ?? "Unknown"}
                      </span>
                    </p>
                  ) : null}
                  {question.explanation ? (
                    <p className="rounded-md border border-border bg-card p-3 text-muted-foreground">
                      {question.explanation}
                    </p>
                  ) : null}
                </div>
                <CitationChips
                  citations={question.citations ?? []}
                  onCitationHover={onCitationHover}
                />
              </div>
            );
          })}
        </div>
      </ArtifactSection>
    );
  }

  return (
    <ArtifactSection
      title="Quiz"
      description={`Answer ${questions.length} questions, then submit for a score.`}
    >
      <div className="mb-4">
        <div className="flex items-center justify-between gap-3">
          <Badge variant="secondary" className="text-[10px]">
            Question {currentIndex + 1} of {questions.length}
          </Badge>
          <span className="text-[11px] text-muted-foreground">
            {answeredCount} answered
          </span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      <div className="rounded-lg border border-border bg-background p-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline" className="text-[10px]">
            {currentQuestion.type === "true_false"
              ? "True/False"
              : "Multiple choice"}
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            {currentQuestion.difficulty}
          </Badge>
        </div>
        <p className="mt-3 text-base font-semibold leading-7 text-foreground">
          {currentQuestion.question}
        </p>

        <div className="mt-4 space-y-2">
          {currentQuestion.options.map((option, optionIndex) => {
            const selected = selectedOptionId === option.id;

            return (
              <button
                key={option.id}
                type="button"
                onClick={() => selectAnswer(option.id)}
                className={cn(
                  "flex w-full items-start gap-3 rounded-lg border p-3 text-left text-sm transition-colors",
                  selected
                    ? "border-primary/50 bg-primary/10 text-foreground"
                    : "border-border bg-card hover:border-primary/30 hover:bg-primary/5",
                )}
              >
                <span
                  className={cn(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                    selected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground",
                  )}
                >
                  {String.fromCharCode(65 + optionIndex)}
                </span>
                <span className="leading-6">{option.text}</span>
              </button>
            );
          })}
        </div>

        <CitationChips
          citations={currentQuestion.citations ?? []}
          onCitationHover={onCitationHover}
        />
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setCurrentIndex((index) => Math.max(index - 1, 0))}
          disabled={currentIndex === 0}
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={goNext}
          disabled={!selectedOptionId}
        >
          {currentIndex === questions.length - 1 ? "Submit" : "Next"}
        </Button>
      </div>
    </ArtifactSection>
  );
}

function ArtifactSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="mb-4">
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          {description}
        </p>
      </div>
      {children}
    </div>
  );
}

function getDifficultyVariant(difficulty: string) {
  if (difficulty === "hard") return "destructive";
  if (difficulty === "easy") return "secondary";
  return "warning";
}

function WorkspaceFlashcardDeck({ cards }: { cards: any[] }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  if (!cards.length) return null;

  const currentCard = cards[currentIndex] as Record<string, any>;
  const progressPercent = Math.round(((currentIndex + 1) / cards.length) * 100);

  const handleNext = () => {
    setIsFlipped(false);
    setTimeout(() => {
      setCurrentIndex((prev) => (prev + 1) % cards.length);
    }, 150);
  };

  const handlePrev = () => {
    setIsFlipped(false);
    setTimeout(() => {
      setCurrentIndex((prev) => (prev - 1 + cards.length) % cards.length);
    }, 150);
  };

  const handleCardClick = () => {
    setIsFlipped((prev) => !prev);
  };

  const tags = Array.isArray(currentCard.tags) ? currentCard.tags : [];

  return (
    <div className="flex flex-col gap-4">
      {/* Progress Indicator */}
      <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
        <div className="flex flex-col">
          <span className="font-semibold text-foreground">
            Card {currentIndex + 1} of {cards.length}
          </span>
          <span className="text-[10px]">{progressPercent}% completed</span>
        </div>
        <Link
          href="/flashcards"
          className={cn(
            buttonVariants({ variant: "outline", size: "sm" }),
            "h-7 gap-1 px-2.5 text-[11px] shrink-0",
          )}
        >
          <ExternalLink className="h-3 w-3" />
          Full viewer
        </Link>
      </div>
      <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
        <div
          className="h-full bg-primary transition-all duration-300 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* 3D Flip Card Container */}
      <div
        onClick={handleCardClick}
        className="perspective-1000 cursor-pointer w-full aspect-[4/3] min-h-[220px] select-none group"
      >
        <div
          className={cn(
            "relative w-full h-full transition-transform duration-500 preserve-3d",
            isFlipped ? "rotate-y-180" : "",
          )}
        >
          {/* Front Face */}
          <div className="absolute inset-0 w-full h-full backface-hidden rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between p-6 transition-all duration-300 group-hover:border-primary/30 group-hover:shadow-md">
            <div className="flex items-center justify-between">
              <Badge
                variant="outline"
                className="text-[9px] font-semibold uppercase tracking-wider opacity-60 bg-background/50"
              >
                Front
              </Badge>
              <Sparkles className="h-3.5 w-3.5 text-primary opacity-40 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="flex-1 flex items-center justify-center py-4">
              <p className="text-sm font-semibold text-center leading-relaxed text-foreground max-h-full overflow-y-auto px-2">
                {String(currentCard.front ?? `Card ${currentIndex + 1}`)}
              </p>
            </div>
            <div className="text-[10px] text-center text-muted-foreground opacity-50 group-hover:opacity-80 transition-opacity">
              Click to reveal back
            </div>
          </div>

          {/* Back Face */}
          <div className="absolute inset-0 w-full h-full backface-hidden rotate-y-180 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between p-6 transition-all duration-300 group-hover:border-primary/30 group-hover:shadow-md">
            <div className="flex items-center justify-between">
              <Badge
                variant="secondary"
                className="text-[9px] font-semibold uppercase tracking-wider"
              >
                Back
              </Badge>
              <RotateCcw className="h-3.5 w-3.5 text-primary opacity-40" />
            </div>
            <div className="flex-1 flex flex-col justify-center py-2 overflow-y-auto px-2">
              <p className="text-sm font-medium text-center leading-relaxed text-foreground">
                {String(currentCard.back ?? "")}
              </p>
              {currentCard.explanation && (
                <div className="mt-3 pt-3 border-t border-border/50">
                  <p className="text-xs text-left leading-relaxed text-muted-foreground italic border-l-2 border-primary/30 pl-2">
                    {String(currentCard.explanation)}
                  </p>
                </div>
              )}
            </div>
            <div className="text-[10px] text-center text-muted-foreground opacity-50">
              Click to flip back
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Controls */}
      <div className="flex items-center justify-between mt-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            handlePrev();
          }}
          className="h-8 gap-1 text-xs"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Prev
        </Button>

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            setIsFlipped((prev) => !prev);
          }}
          className="h-8 text-[11px] text-muted-foreground gap-1 hover:text-foreground"
        >
          <RotateCcw className="h-3 w-3" />
          Flip
        </Button>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            handleNext();
          }}
          className="h-8 gap-1 text-xs"
        >
          Next
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Tags and difficulty info if available */}
      {(currentCard.difficulty || tags.length > 0) && (
        <div className="flex flex-wrap gap-1.5 items-center bg-muted/20 p-2 rounded-lg border border-border/40">
          {currentCard.difficulty && (
            <Badge
              variant={getDifficultyVariant(String(currentCard.difficulty))}
              className="text-[9px] h-5 py-0"
            >
              {String(currentCard.difficulty)}
            </Badge>
          )}
          {tags.map((tag: any, idx: number) => (
            <Badge
              key={idx}
              variant="outline"
              className="text-[9px] h-5 py-0 bg-background/50"
            >
              {String(tag)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function WorkspacePodcastPlayer({
  report,
  dialogue,
}: {
  report: any;
  dialogue: any[];
}) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [isMuted, setIsMuted] = useState(false);
  const [isPreparingAudio, setIsPreparingAudio] = useState(false);
  const [serverAudioUrl, setServerAudioUrl] = useState<string | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const token = getStoredAuthToken();
  const audioUrl = useMemo(() => {
    const base = createApiUrl(`/reports/${report.report_id}/podcast-audio`);
    return token ? `${base}?token=${encodeURIComponent(token)}` : base;
  }, [report.report_id, token]);

  useEffect(() => {
    let objectUrl: string | null = null;
    const controller = new AbortController();

    setIsPreparingAudio(true);
    setServerAudioUrl(null);
    setAudioError(null);

    fetch(audioUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal: controller.signal,
    })
      .then(async (response) => {
        const contentType = response.headers.get("content-type") ?? "";
        if (!response.ok || !contentType.toLowerCase().startsWith("audio/")) {
          const body = await response.json().catch(() => null);
          const message =
            body?.error?.message ??
            "Failed to generate podcast audio with edge-tts.";
          setAudioError(message);
          return;
        }
        const blob = await response.blob();
        if (blob.size < 128 || !blob.type.toLowerCase().startsWith("audio/")) {
          setAudioError("Podcast endpoint returned an invalid audio file.");
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setServerAudioUrl(objectUrl);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setAudioError("Failed to load podcast audio from edge-tts.");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsPreparingAudio(false);
        }
      });

    return () => {
      controller.abort();
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [audioUrl, token]);

  useEffect(() => {
    if (!serverAudioUrl) {
      audioRef.current = null;
      return;
    }

    const audio = new Audio(serverAudioUrl);
    audioRef.current = audio;
    audio.preload = "metadata";
    audio.volume = isMuted ? 0 : volume;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
    const handleDurationChange = () => {
      if (Number.isFinite(audio.duration)) {
        setDuration(audio.duration);
      }
    };
    const handleEnded = () => {
      setIsPlaying(false);
      setCurrentTime(0);
    };
    const handleAudioError = () => {
      setIsPlaying(false);
      setAudioError("Podcast audio stream failed.");
    };

    audio.addEventListener("play", handlePlay);
    audio.addEventListener("pause", handlePause);
    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("durationchange", handleDurationChange);
    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("error", handleAudioError);

    return () => {
      audio.pause();
      audio.removeEventListener("play", handlePlay);
      audio.removeEventListener("pause", handlePause);
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("durationchange", handleDurationChange);
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("error", handleAudioError);
      audioRef.current = null;
    };
  }, [serverAudioUrl]);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume;
    }
  }, [volume, isMuted]);

  const togglePlay = () => {
    if (!audioRef.current) {
      toast.error(audioError ?? "Podcast audio is not ready.");
      return;
    }

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch((err) => {
        console.error(err);
        setAudioError("Podcast audio stream failed.");
        toast.error("Podcast audio stream failed.");
      });
    }
  };

  const handleSeek = (e: ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setCurrentTime(val);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
    }
  };

  const handleVolumeChange = (e: ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    if (val > 0) {
      setIsMuted(false);
    }
  };

  const toggleMute = () => {
    setIsMuted((prev) => !prev);
  };

  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs === Infinity) return "00:00";
    const minutes = Math.floor(secs / 60);
    const seconds = Math.floor(secs % 60);
    return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Audio Player Card */}
      <div className="relative overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-primary/5 via-background to-secondary/5 p-4 shadow-sm">
        {/* Abstract background waves */}
        <div className="absolute right-0 top-0 -mr-6 -mt-6 h-24 w-24 rounded-full bg-primary/10 blur-2xl" />
        <div className="absolute bottom-0 left-0 -ml-6 -mb-6 h-20 w-20 rounded-full bg-secondary/15 blur-2xl" />

        <div className="relative flex flex-col gap-3">
          {/* Header Info */}
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <Mic className={cn("h-5 w-5", isPlaying && "animate-pulse")} />
            </div>
            <div className="min-w-0">
              <h4 className="truncate text-sm font-semibold text-foreground">
                AI Research Podcast
              </h4>
              <p className="truncate text-xs text-muted-foreground">
                Host A & Host B discuss findings
              </p>
            </div>
            {isPlaying && (
              <div className="ml-auto flex items-center gap-0.5 h-3">
                <span className="w-0.5 h-3 bg-primary rounded-full animate-pulse" />
                <span className="w-0.5 h-2 bg-primary rounded-full animate-pulse [animation-delay:0.2s]" />
                <span className="w-0.5 h-3.5 bg-primary rounded-full animate-pulse [animation-delay:0.4s]" />
                <span className="w-0.5 h-1.5 bg-primary rounded-full animate-pulse [animation-delay:0.1s]" />
              </div>
            )}
          </div>

          {/* Slider and Time */}
          <div className="flex flex-col gap-1 mt-1">
            <input
              type="range"
              min={0}
              max={duration || 100}
              value={currentTime}
              onChange={handleSeek}
              className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-secondary accent-primary focus:outline-none"
              style={{
                background: `linear-gradient(to right, var(--color-primary) 0%, var(--color-primary) ${
                  duration ? (currentTime / duration) * 100 : 0
                }%, var(--color-secondary) ${
                  duration ? (currentTime / duration) * 100 : 0
                }%, var(--color-secondary) 100%)`,
              }}
            />
            <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* Controls Bar */}
          <div className="flex items-center justify-between mt-1">
            {/* Volume Control */}
            <div className="flex items-center gap-1.5 w-24">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={toggleMute}
                className="h-7 w-7 text-muted-foreground hover:text-foreground shrink-0"
              >
                {isMuted || volume === 0 ? (
                  <VolumeX className="h-4 w-4" />
                ) : (
                  <Volume2 className="h-4 w-4" />
                )}
              </Button>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={isMuted ? 0 : volume}
                onChange={handleVolumeChange}
                className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-secondary accent-muted-foreground focus:outline-none"
              />
            </div>

            {/* Play Button */}
            <Button
              type="button"
              size="icon"
              onClick={togglePlay}
              disabled={isPreparingAudio || !serverAudioUrl}
              className="h-9 w-9 rounded-full bg-primary hover:bg-primary/95 text-primary-foreground shadow-md shadow-primary/20 active:scale-95 transition-transform shrink-0"
            >
              {isPreparingAudio ? (
                <Spinner className="h-4 w-4" />
              ) : isPlaying ? (
                <Pause className="h-4.5 w-4.5 fill-current" />
              ) : (
                <Play className="h-4.5 w-4.5 fill-current ml-0.5" />
              )}
            </Button>

            <div className="w-24 flex justify-end">
              <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-semibold">
                Edge-TTS
              </span>
            </div>
          </div>

          {audioError && (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {audioError}
            </p>
          )}
        </div>
      </div>

      {/* Timeline Transcript */}
      <div className="max-h-[300px] overflow-y-auto space-y-3 pr-1 scrollbar-thin">
        {dialogue.map((turn, index) => {
          const isHostA = turn.speaker === "Host A";
          return (
            <div
              key={index}
              className={cn(
                "flex flex-col gap-1 max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed border shadow-[0_2px_8px_rgba(0,0,0,0.02)]",
                isHostA
                  ? "bg-card border-border/80 rounded-tl-none mr-auto"
                  : "bg-primary/5 border-primary/10 rounded-tr-none ml-auto",
              )}
            >
              <div className="flex items-center gap-1.5 font-bold mb-1">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    isHostA ? "bg-primary" : "bg-purple-500",
                  )}
                />
                <span className="text-foreground">{turn.speaker}</span>
              </div>
              <p className="text-muted-foreground">{turn.text}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WorkspaceMindMap({ payload }: { payload: any }) {
  const flow = useMemo(() => buildMindMapFlow(payload), [payload]);

  return (
    <div className="h-[380px] w-full border border-border rounded-xl bg-background overflow-hidden relative">
      <ReactFlow
        nodes={flow.nodes}
        edges={flow.edges}
        fitView
        minZoom={0.1}
        maxZoom={1.5}
        nodesConnectable={false}
        nodesDraggable={true}
        elementsSelectable={true}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
      <div className="absolute left-3 top-3 z-10 rounded-md border border-border/80 bg-background/90 px-2 py-1 text-[10px] font-semibold shadow-sm backdrop-blur">
        Drag nodes to reorganize
      </div>
    </div>
  );
}

function ArtifactItemCard({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-background p-4 shadow-sm">
      {children}
    </div>
  );
}

function StudioOutputsPanel({
  activeProject,
  canMutate,
  request,
  selectedArtifact,
  selectedArtifactId,
  onOpenArtifact,
  onCloseArtifact,
  onRequestArtifact,
  onCitationHover,
  registerActions,
}: {
  activeProject: StoredProject;
  canMutate: boolean;
  request: StudioRequest | null;
  selectedArtifact: ReportResult | null;
  selectedArtifactId: string | null;
  onOpenArtifact: (artifact: ReportResult) => void;
  onCloseArtifact: () => void;
  onRequestArtifact: (query: string, type: ReportType) => void;
  onCitationHover: (sourceId: string | null) => void;
  registerActions: (actions: Partial<WorkspaceActions>) => void;
}) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [type, setType] = useState<ReportType>("research_brief");
  const [generating, setGenerating] = useState(false);
  const [loadingReportId, setLoadingReportId] = useState<string | null>(null);
  const lastRequestNonce = useRef<number | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["workspace-reports", activeProject.id],
    queryFn: () => listReports(activeProject.id),
  });
  const reports = data?.data.items ?? [];

  useEffect(() => {
    if (!request || lastRequestNonce.current === request.nonce) return;
    lastRequestNonce.current = request.nonce;
    setQuery(request.query);
    setType(request.type);
    void generateArtifact(request.query, request.type);
  }, [request]);

  useEffect(() => {
    registerActions({
      refreshArtifacts: () => void refetch(),
      generateArtifact: (reportType: ReportType) =>
        void generateArtifact(
          query || "Create a source-grounded artifact from this project.",
          reportType,
        ),
    });
  });

  async function generateArtifact(nextQuery = query, nextType = type) {
    const cleanQuery = nextQuery.trim();
    if (!cleanQuery || generating) return;
    if (!canMutate) {
      toast.error("Generating artifacts requires editor role or higher.");
      return;
    }
    setGenerating(true);
    const toastId = toast.loading(
      `Generating ${REPORT_LABELS[nextType] ?? nextType}...`,
    );
    try {
      const result = await generateReport({
        projectId: activeProject.id,
        query: cleanQuery,
        type: nextType,
        provider: "openai",
      });
      onOpenArtifact(result.data);
      toast.success("Artifact generated.", { id: toastId });
      await queryClient.invalidateQueries({
        queryKey: ["workspace-reports", activeProject.id],
      });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Artifact generation failed.",
        { id: toastId },
      );
    } finally {
      setGenerating(false);
    }
  }

  async function openReport(report: ReportListItem) {
    setLoadingReportId(report.report_id);
    try {
      const response = await getReport(report.report_id);
      onOpenArtifact(response.data);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not open report.",
      );
    } finally {
      setLoadingReportId(null);
    }
  }

  if (selectedArtifact) {
    const Icon = getReportIcon(selectedArtifact.type);

    return (
      <PanelFrame
        title="Artifact Detail"
        description={
          REPORT_LABELS[selectedArtifact.type] ?? selectedArtifact.type
        }
        icon={Icon}
        action={
          <div className="flex items-center gap-1.5">
            <Link
              href={getArtifactFullViewerRoute(selectedArtifact.type)}
              className={cn(
                buttonVariants({ variant: "outline", size: "sm" }),
                "h-7 gap-1 px-2.5 text-[11px] shrink-0 bg-background/50 hover:bg-accent",
              )}
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Full
            </Link>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onCloseArtifact}
              className="h-7 px-2"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Back
            </Button>
          </div>
        }
      >
        <ArtifactCanvas
          report={selectedArtifact}
          onRequestArtifact={onRequestArtifact}
          onCitationHover={onCitationHover}
        />
      </PanelFrame>
    );
  }

  return (
    <PanelFrame
      title="Studio Outputs"
      description={`${reports.length} generated artifacts`}
      icon={Sparkles}
      action={
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => void refetch()}
        >
          <RefreshCcw className="h-4 w-4" />
        </Button>
      }
    >
      <div className="space-y-4 p-4">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void generateArtifact();
          }}
          className="rounded-lg border border-border bg-card p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold text-foreground">
                Create artifact
              </p>
              <p className="text-[11px] text-muted-foreground">
                Generate from indexed evidence.
              </p>
            </div>
            <Badge variant="secondary" className="text-[10px]">
              OpenAI
            </Badge>
          </div>
          <div className="mt-3 space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Type</Label>
              <Select
                value={type}
                onValueChange={(value) => setType(value as ReportType)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REPORT_TYPES.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="What should the studio create?"
              className="min-h-24 resize-none text-xs"
              disabled={!canMutate || generating}
            />
            <Button
              type="submit"
              size="sm"
              className="w-full"
              disabled={!canMutate || generating || !query.trim()}
            >
              {generating ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Generate
            </Button>
          </div>
        </form>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-foreground">
              Recent artifacts
            </p>
          </div>
          {isLoading ? (
            <div className="flex h-28 items-center justify-center">
              <Spinner />
            </div>
          ) : reports.length || generating ? (
            <>
              {generating ? <ArtifactSkeletonCard type={type} /> : null}
              {reports.map((report) => (
                <ArtifactCard
                  key={report.report_id}
                  report={report}
                  selected={selectedArtifactId === report.report_id}
                  loading={loadingReportId === report.report_id}
                  onOpen={() => void openReport(report)}
                />
              ))}
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-5 text-center">
              <FileText className="mx-auto h-8 w-8 text-muted-foreground" />
              <p className="mt-2 text-sm font-medium text-foreground">
                No artifacts yet
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Generate a report, quiz, study guide, or map from the canvas.
              </p>
              <div className="mt-4 grid gap-2">
                {(
                  ["research_brief", "flashcards", "mind_map"] as ReportType[]
                ).map((templateType) => {
                  const Icon = getReportIcon(templateType);
                  return (
                    <button
                      key={templateType}
                      type="button"
                      onClick={() => {
                        setType(templateType);
                        setQuery(
                          "Create a source-grounded artifact from this project.",
                        );
                      }}
                      className="flex items-center gap-2 rounded-lg border border-border/70 bg-card/60 px-3 py-2 text-left text-xs backdrop-blur transition-colors hover:border-primary/30 hover:bg-primary/10"
                    >
                      <Icon className="h-4 w-4 text-primary" />
                      {REPORT_LABELS[templateType]}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </PanelFrame>
  );
}

function ArtifactCard({
  report,
  selected,
  loading,
  onOpen,
}: {
  report: ReportListItem;
  selected: boolean;
  loading: boolean;
  onOpen: () => void;
}) {
  const Icon = getReportIcon(report.type);

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={onOpen}
      className={cn(
        "holo-edge w-full rounded-lg border bg-card/78 p-3 text-left backdrop-blur transition-colors hover:border-primary/30 dark:bg-card/75",
        selected
          ? "border-primary/50 bg-primary/10 dark:bg-primary/10"
          : "border-border/70",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/70 bg-muted/60 text-muted-foreground">
          {loading ? (
            <Spinner className="h-4 w-4" />
          ) : (
            <Icon className="h-4 w-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-semibold text-foreground">
            {report.title}
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <Badge variant="outline" className="text-[10px]">
              {REPORT_LABELS[report.type] ?? report.type}
            </Badge>
            <Badge
              variant={report.status === "completed" ? "success" : "secondary"}
              className="text-[10px]"
            >
              {report.status}
            </Badge>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {formatDate(report.created_at)}
          </p>
        </div>
      </div>
    </motion.button>
  );
}

function ArtifactSkeletonCard({ type }: { type: ReportType }) {
  const Icon = getReportIcon(type);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="holo-edge rounded-lg border border-primary/20 bg-primary/10 p-3 shadow-sm"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-background text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-foreground">
            Generating {REPORT_LABELS[type] ?? type}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Retrieving evidence and drafting artifact...
          </p>
          <div className="mt-3 space-y-1.5">
            <div className="h-2 w-4/5 animate-pulse rounded-full bg-primary/20" />
            <div className="h-2 w-2/3 animate-pulse rounded-full bg-primary/20" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
