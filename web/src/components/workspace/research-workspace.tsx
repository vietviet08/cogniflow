"use client";

import {
  ChangeEvent,
  Dispatch,
  FormEvent,
  ReactNode,
  RefObject,
  SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { Command as CmdkCommand } from "cmdk";
import { useTheme } from "next-themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
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
  CircleHelp,
  Copy,
  ExternalLink,
  FileText,
  FolderOpen,
  Layers,
  Link2,
  LogOut,
  MessageSquare,
  Moon,
  Plus,
  RefreshCcw,
  Search,
  Send,
  Settings,
  Share2,
  Sparkles,
  Sun,
  Upload,
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
  updateChatMessage,
  uploadSourceFile,
} from "@/lib/api/client";
import type {
  ChatMessageData,
  CitationData,
  JobStatusData,
  ProjectRole,
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
];

const REPORT_LABELS = Object.fromEntries(
  REPORT_TYPES.map((type) => [type.value, type.label]),
) as Record<ReportType, string>;

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

function describeStructuredPayload(payload: StructuredReportPayload | null | undefined) {
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
            {citation.page_number ? <span>p.{citation.page_number}</span> : null}
          </Badge>
        </button>
      ))}
    </div>
  );
}

export function ResearchWorkspace() {
  const [activeProject, setActiveProjectState] = useState<StoredProject | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("research");
  const [studioRequest, setStudioRequest] = useState<StudioRequest | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<ReportResult | null>(null);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);
  const [commandOpen, setCommandOpen] = useState(false);
  const workspaceActionsRef = useRef<WorkspaceActions>({});

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

  const canMutate = canEditProject(activeProject.role as ProjectRole | undefined);

  function requestArtifact(query: string, type: ReportType) {
    setStudioRequest({ query, type, nonce: Date.now() });
    setActiveTab("studio");
  }

  function openArtifact(artifact: ReportResult) {
    setSelectedArtifact(artifact);
    setActiveTab("research");
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
    <div className="flex h-screen min-h-0 flex-col bg-background">
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

      <div className="border-b border-border bg-card/60 px-3 py-2 lg:hidden">
        <div className="grid grid-cols-3 gap-1 rounded-lg bg-muted p-1">
          {(["sources", "research", "studio"] as WorkspaceTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={cn(
                "rounded-md px-2 py-1.5 text-xs font-medium capitalize transition-colors",
                activeTab === tab
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

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
              selectedArtifact={selectedArtifact}
              selectedSourceIds={selectedSourceIds}
              onClearSourceScope={clearSourceScope}
              onCloseArtifact={() => setSelectedArtifact(null)}
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
              selectedArtifactId={selectedArtifact?.report_id ?? null}
              onOpenArtifact={openArtifact}
              registerActions={registerWorkspaceActions}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      <div className="min-h-0 flex-1 lg:hidden">
        {activeTab === "sources" ? (
          <KnowledgeSourcesPanel
            activeProject={activeProject}
            canMutate={canMutate}
            selectedSourceIds={selectedSourceIds}
            setSelectedSourceIds={setSelectedSourceIds}
            highlightedSourceId={highlightedSourceId}
            registerActions={registerWorkspaceActions}
          />
        ) : null}
        {activeTab === "research" ? (
          <ResearchCanvasPanel
            activeProject={activeProject}
            canMutate={canMutate}
            selectedArtifact={selectedArtifact}
            selectedSourceIds={selectedSourceIds}
            onClearSourceScope={clearSourceScope}
            onCloseArtifact={() => setSelectedArtifact(null)}
            onRequestArtifact={requestArtifact}
            onCitationHover={setHighlightedSourceId}
            registerActions={registerWorkspaceActions}
          />
        ) : null}
        {activeTab === "studio" ? (
          <StudioOutputsPanel
            activeProject={activeProject}
            canMutate={canMutate}
            request={studioRequest}
            selectedArtifactId={selectedArtifact?.report_id ?? null}
            onOpenArtifact={openArtifact}
            registerActions={registerWorkspaceActions}
          />
        ) : null}
      </div>
    </div>
  );
}

function WorkspaceResizeHandle() {
  return (
    <ResizableHandle className="group flex w-3 cursor-col-resize items-center justify-center bg-background transition-colors hover:bg-primary/5">
      <div className="h-12 w-1 rounded-full bg-border transition-colors group-hover:bg-primary/60" />
    </ResizableHandle>
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
    <div className="fixed inset-0 z-50 bg-background/60 p-4 backdrop-blur-sm" onClick={() => onOpenChange(false)}>
      <div className="mx-auto mt-20 max-w-xl" onClick={(event) => event.stopPropagation()}>
        <CmdkCommand className="overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-xl">
          <div className="flex items-center gap-2 border-b border-border px-3">
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
                  "flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm outline-none data-[selected=true]:bg-accent",
                  command.disabled && "cursor-not-allowed opacity-40",
                )}
              >
                <span>{command.label}</span>
                <span className="text-xs text-muted-foreground">{command.hint}</span>
              </CmdkCommand.Item>
            ))}
          </CmdkCommand.List>
        </CmdkCommand>
      </div>
    </div>
  );
}

function WorkspaceEmptyState() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-md rounded-lg border border-dashed border-border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <BrainCircuit className="h-6 w-6" />
        </div>
        <h1 className="text-xl font-semibold text-foreground">Select a project first</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          The research workspace is scoped to one active project so sources,
          chat, and studio artifacts stay connected.
        </p>
        <Link href="/projects" className={cn(buttonVariants(), "mt-6")}>
          <FolderOpen className="h-4 w-4" />
          Open projects
        </Link>
      </div>
    </div>
  );
}

function WorkspaceTopBar({ activeProject }: { activeProject: StoredProject }) {
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const isDark = theme === "dark";

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card/90 px-4 backdrop-blur">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <BrainCircuit className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-foreground">NoteMesh Workspace</p>
            {activeProject.role ? (
              <Badge variant="secondary" className="hidden text-[10px] capitalize sm:inline-flex">
                {activeProject.role}
              </Badge>
            ) : null}
          </div>
          <p className="truncate text-xs text-muted-foreground">{activeProject.name}</p>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <Link
          href="/projects"
          className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}
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
        <Button type="button" variant="ghost" size="icon" onClick={logout} title="Log out">
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
    <section className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border bg-card/60 px-4 py-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-foreground">{title}</h2>
            <p className="truncate text-xs text-muted-foreground">{description}</p>
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

  const {
    data,
    isLoading,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["workspace-sources", activeProject.id],
    queryFn: () => listSources(activeProject.id),
  });

  const sources = data?.data.items ?? [];
  const indexedCount = sources.filter((source) => source.indexing?.is_indexed).length;
  const { data: jobsData } = useQuery({
    queryKey: ["workspace-processing-jobs", activeProject.id],
    queryFn: () => listProjectJobs(activeProject.id),
    enabled: processingActive,
    refetchInterval: processingActive ? 2000 : false,
  });
  const processingJobs = (jobsData?.data.items ?? []).filter(
    (job) =>
      job.type === "processing" &&
      ["queued", "running"].includes(job.status),
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
    await queryClient.invalidateQueries({ queryKey: ["workspace-sources", activeProject.id] });
  }

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
    const toastId = toast.loading(`Uploading ${files.length} source${files.length > 1 ? "s" : ""}...`);
    try {
      for (const file of files) {
        await uploadSourceFile({ projectId: activeProject.id, file });
      }
      toast.success("Sources uploaded.", { id: toastId });
      await refreshSources();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed.", { id: toastId });
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
      toast.error(error instanceof Error ? error.message : "Could not add source.", { id: toastId });
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
      toast.error(error instanceof Error ? error.message : "Processing failed.", { id: toastId });
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
        <Button type="button" variant="ghost" size="icon" onClick={() => void refetch()}>
          {isFetching ? <Spinner className="h-4 w-4" /> : <RefreshCcw className="h-4 w-4" />}
        </Button>
      }
    >
      <div className="space-y-4 p-4">
        <div className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold text-foreground">Add source</p>
              <p className="text-[11px] text-muted-foreground">PDF, DOCX, URL, arXiv and web pages.</p>
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
              placeholder="https://example.com/research"
              disabled={!canMutate || busy}
              className="h-8 text-xs"
            />
            <Button type="submit" size="icon" disabled={!canMutate || busy || !url.trim()}>
              <Link2 className="h-4 w-4" />
            </Button>
          </form>
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
            <p className="mt-3 text-sm font-medium text-foreground">No sources yet</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Add a file or URL to build the project knowledge base.
            </p>
          </div>
        )}
      </div>
    </PanelFrame>
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
      ? Math.round(jobs.reduce((sum, job) => sum + job.progress, 0) / activeJobs)
      : 5;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-primary/20 bg-primary/5 p-3"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-foreground">Indexing sources</p>
          <p className="text-[11px] text-muted-foreground">
            {activeJobs ? `${activeJobs} processing job${activeJobs > 1 ? "s" : ""} active` : "Waiting for job status..."}
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
        "rounded-lg border bg-card p-3 transition-colors",
        selected ? "border-primary/50 bg-primary/5" : "border-border hover:border-primary/25",
        highlighted && "border-warning bg-warning/10 shadow-sm",
      )}
    >
      <div className="flex items-start gap-3">
        <Checkbox checked={selected} onCheckedChange={onToggle} className="mt-1" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-xs font-semibold text-foreground">{source.file_name}</p>
            <Badge variant={getSourceStatusVariant(source.status)} className="text-[10px]">
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
              <Badge variant="secondary" className="text-[10px]">Not indexed</Badge>
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
          <p className="mt-2 text-[11px] text-muted-foreground">{formatDate(source.created_at)}</p>
        </div>
      </div>
    </motion.div>
  );
}

function ResearchCanvasPanel({
  activeProject,
  canMutate,
  selectedArtifact,
  selectedSourceIds,
  onClearSourceScope,
  onCloseArtifact,
  onRequestArtifact,
  onCitationHover,
  registerActions,
}: {
  activeProject: StoredProject;
  canMutate: boolean;
  selectedArtifact: ReportResult | null;
  selectedSourceIds: Set<string>;
  onClearSourceScope: () => void;
  onCloseArtifact: () => void;
  onRequestArtifact: (query: string, type: ReportType) => void;
  onCitationHover: (sourceId: string | null) => void;
  registerActions: (actions: Partial<WorkspaceActions>) => void;
}) {
  const queryClient = useQueryClient();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [optimisticMessage, setOptimisticMessage] = useState<string | null>(null);
  const [assistantStage, setAssistantStage] = useState("Retrieving evidence");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const askInputRef = useRef<HTMLTextAreaElement>(null);

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
    const stages = ["Retrieving evidence", "Ranking citations", "Drafting answer"];
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
        onCloseArtifact();
        askInputRef.current?.focus();
      },
      newChat: () => {
        onCloseArtifact();
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
        const title = content.length > 42 ? `${content.slice(0, 42)}...` : content;
        const session = await createChatSession({ projectId: activeProject.id, title });
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
        filters: scopedSourceIds.length ? { source_ids: scopedSourceIds } : undefined,
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

  async function handleMessageAction(messageId: string, patch: { isBookmarked?: boolean; rating?: number }) {
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
        selectedArtifact ? (
          <Button type="button" variant="ghost" size="sm" onClick={onCloseArtifact}>
            <MessageSquare className="h-4 w-4" />
            Chat
          </Button>
        ) : (
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
        )
      }
    >
      {selectedArtifact ? (
        <ArtifactCanvas
          report={selectedArtifact}
          onRequestArtifact={onRequestArtifact}
          onCitationHover={onCitationHover}
        />
      ) : (
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
              {sending ? (
                <AssistantSkeleton stage={assistantStage} />
              ) : null}
              <div ref={messagesEndRef} />
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-8">
              <div className="max-w-lg text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <MessageSquare className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-foreground">Start with a research question</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Ask across indexed sources, then turn strong answers into reports,
                  flashcards, or a mind map without leaving the workspace.
                </p>
              </div>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="shrink-0 border-t border-border bg-card/80 p-3">
          <div className="flex gap-2">
            <Textarea
              ref={askInputRef}
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Ask about the selected research project..."
              className="min-h-11 resize-none text-sm"
              disabled={!canMutate || sending}
            />
            <Button type="submit" size="icon" disabled={!canMutate || sending || !inputValue.trim()}>
              {sending ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
        </form>
      </div>
      )}
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
  onMessageAction: (messageId: string, patch: { isBookmarked?: boolean; rating?: number }) => void;
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
        "rounded-lg border p-4",
        isAssistant
          ? "border-primary/15 bg-card shadow-sm"
          : "ml-auto max-w-[88%] border-border bg-muted/60",
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-lg",
              isAssistant ? "bg-primary/10 text-primary" : "bg-secondary text-secondary-foreground",
            )}
          >
            {isAssistant ? <BrainCircuit className="h-4 w-4" /> : <MessageSquare className="h-4 w-4" />}
          </div>
          <span className="text-xs font-semibold capitalize text-foreground">{message.role}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button type="button" variant="ghost" size="icon" className="h-7 w-7" onClick={copyMessage}>
            <Copy className="h-3.5 w-3.5" />
          </Button>
          {isAssistant ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() =>
                onMessageAction(message.id, { isBookmarked: !message.is_bookmarked })
              }
            >
              <BookOpen className={cn("h-3.5 w-3.5", message.is_bookmarked && "text-primary")} />
            </Button>
          ) : null}
        </div>
      </div>

      <div className="prose prose-sm max-w-none dark:prose-invert">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      </div>
      <CitationChips citations={message.citations ?? []} onCitationHover={onCitationHover} />

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
        <Button type="button" variant="ghost" size="sm" className="h-6 px-2" onClick={onClear}>
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
  const Icon = getReportIcon(report.type);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b border-border bg-card/30 px-5 py-4">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start justify-between gap-4"
        >
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Icon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="truncate text-lg font-semibold text-foreground">
                  {report.title}
                </h3>
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
              <p className="mt-1 text-xs text-muted-foreground">
                {formatDate(report.created_at)} · Run {report.run_id?.slice(0, 8) ?? "n/a"}
              </p>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                {report.query}
              </p>
            </div>
          </div>
          <Link
            href={getArtifactFullViewerRoute(report.type)}
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "shrink-0")}
          >
            <ExternalLink className="h-4 w-4" />
            Full viewer
          </Link>
        </motion.div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <motion.div
          key={report.report_id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-auto max-w-5xl space-y-5"
        >
          <ArtifactStructuredView report={report} />
          <CitationChips citations={report.citations ?? []} onCitationHover={onCitationHover} />

          <div className="rounded-lg border border-border bg-card p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">Branch from this artifact</p>
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
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

function ArtifactStructuredView({ report }: { report: ReportResult }) {
  const payload = report.structured_payload;

  if (report.content) {
    return (
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.content}</ReactMarkdown>
        </div>
      </div>
    );
  }

  if (!payload || typeof payload !== "object") {
    return (
      <div className="rounded-lg border border-dashed border-border p-8 text-center">
        <FileText className="mx-auto h-9 w-9 text-muted-foreground" />
        <p className="mt-3 text-sm font-medium text-foreground">Artifact has no preview payload</p>
      </div>
    );
  }

  if ("cards" in payload && Array.isArray(payload.cards)) {
    return (
      <ArtifactSection title="Flashcards" description={describeStructuredPayload(payload)}>
        <div className="grid gap-3 md:grid-cols-2">
          {payload.cards.map((card, index) => {
            const item = card as Record<string, unknown>;
            return (
              <ArtifactItemCard key={String(item.id ?? index)}>
                <p className="text-xs font-semibold text-primary">
                  {String(item.front ?? `Card ${index + 1}`)}
                </p>
                <p className="mt-2 text-sm leading-6 text-foreground">
                  {String(item.back ?? "")}
                </p>
                {item.explanation ? (
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
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

  if ("questions" in payload && Array.isArray(payload.questions)) {
    return (
      <ArtifactSection title="Quiz" description={describeStructuredPayload(payload)}>
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
      <ArtifactSection title="Study Guide" description={describeStructuredPayload(payload)}>
        <div className="space-y-3">
          {payload.sections.map((section, index) => {
            const item = section as Record<string, unknown>;
            const points = Array.isArray(item.key_points) ? item.key_points : [];
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
    const nodes = payload.nodes as Array<Record<string, unknown>>;
    const edges = "edges" in payload && Array.isArray(payload.edges) ? payload.edges : [];
    return (
      <ArtifactSection title={report.type === "mind_map" ? "Mind Map" : "Mesh"} description={describeStructuredPayload(payload)}>
        <div className="grid gap-3 md:grid-cols-[1fr_0.85fr]">
          <div className="rounded-lg border border-border bg-muted/30 p-4">
            <p className="mb-3 text-xs font-semibold uppercase text-muted-foreground">Nodes</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {nodes.slice(0, 18).map((node, index) => (
                <div key={String(node.id ?? index)} className="rounded-md border border-border bg-card p-3">
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
            <p className="text-xs font-semibold uppercase text-muted-foreground">Relationships</p>
            <p className="mt-2 text-3xl font-semibold text-foreground">{edges.length}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Open the full viewer for interactive 2D/3D exploration.
            </p>
          </div>
        </div>
      </ArtifactSection>
    );
  }

  return (
    <ArtifactSection title={REPORT_LABELS[report.type] ?? "Artifact"} description={describeStructuredPayload(payload)}>
      <pre className="max-h-[520px] overflow-auto rounded-lg bg-muted p-4 text-xs text-muted-foreground">
        {JSON.stringify(payload, null, 2)}
      </pre>
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
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
      </div>
      {children}
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
  selectedArtifactId,
  onOpenArtifact,
  registerActions,
}: {
  activeProject: StoredProject;
  canMutate: boolean;
  request: StudioRequest | null;
  selectedArtifactId: string | null;
  onOpenArtifact: (artifact: ReportResult) => void;
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
      generateArtifact: (reportType: ReportType) => void generateArtifact(query || "Create a source-grounded artifact from this project.", reportType),
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
    const toastId = toast.loading(`Generating ${REPORT_LABELS[nextType] ?? nextType}...`);
    try {
      const result = await generateReport({
        projectId: activeProject.id,
        query: cleanQuery,
        type: nextType,
        provider: "openai",
      });
      onOpenArtifact(result.data);
      toast.success("Artifact generated.", { id: toastId });
      await queryClient.invalidateQueries({ queryKey: ["workspace-reports", activeProject.id] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Artifact generation failed.", { id: toastId });
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
      toast.error(error instanceof Error ? error.message : "Could not open report.");
    } finally {
      setLoadingReportId(null);
    }
  }

  return (
    <PanelFrame
      title="Studio Outputs"
      description={`${reports.length} generated artifacts`}
      icon={Sparkles}
      action={
        <Button type="button" variant="ghost" size="icon" onClick={() => void refetch()}>
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
              <p className="text-xs font-semibold text-foreground">Create artifact</p>
              <p className="text-[11px] text-muted-foreground">Generate from indexed evidence.</p>
            </div>
            <Badge variant="secondary" className="text-[10px]">OpenAI</Badge>
          </div>
          <div className="mt-3 space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Type</Label>
              <Select value={type} onValueChange={(value) => setType(value as ReportType)}>
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
              {generating ? <Spinner className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
              Generate
            </Button>
          </div>
        </form>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-foreground">Recent artifacts</p>
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
              <p className="mt-2 text-sm font-medium text-foreground">No artifacts yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Generate a report, quiz, study guide, or map from the canvas.
              </p>
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
        "w-full rounded-lg border bg-card p-3 text-left transition-colors hover:border-primary/30",
        selected ? "border-primary/50 bg-primary/5" : "border-border",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          {loading ? <Spinner className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-semibold text-foreground">{report.title}</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <Badge variant="outline" className="text-[10px]">
              {REPORT_LABELS[report.type] ?? report.type}
            </Badge>
            <Badge variant={report.status === "completed" ? "success" : "secondary"} className="text-[10px]">
              {report.status}
            </Badge>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">{formatDate(report.created_at)}</p>
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
      className="rounded-lg border border-primary/20 bg-primary/5 p-3"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-background text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-foreground">Generating {REPORT_LABELS[type] ?? type}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">Retrieving evidence and drafting artifact...</p>
          <div className="mt-3 space-y-1.5">
            <div className="h-2 w-4/5 animate-pulse rounded-full bg-primary/20" />
            <div className="h-2 w-2/3 animate-pulse rounded-full bg-primary/20" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
