"use client";

import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  ClipboardList,
  Copy,
  Download,
  FileText,
  History,
  Quote,
  RefreshCcw,
  ShieldAlert,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  generateReport,
  getReport,
  getReportLineage,
  listReports,
  updateActionItemStatus,
} from "@/lib/api/client";
import type {
  ActionItemData,
  ActionItemsPayload,
  CitationData,
  ExecutiveBriefPayload,
  ReportLineage,
  ReportListItem,
  ReportResult,
  ReportType,
  ProjectRole,
  RiskAnalysisPayload,
  RiskItemData,
  StructuredReportPayload,
} from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject } from "@/lib/project-store";

import { useCitationViewer } from "@/components/citation-viewer-provider";
import { PageWrapper } from "@/components/layout/page-wrapper";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

const REPORT_TYPE_OPTIONS: Array<{
  value: ReportType;
  label: string;
  description: string;
}> = [
  {
    value: "action_items",
    label: "Action Items",
    description: "Extract concrete follow-ups, owners, and due date hints.",
  },
  {
    value: "risk_analysis",
    label: "Risk Analysis",
    description: "Highlight risk areas, impact, and recommended mitigation.",
  },
  {
    value: "executive_brief",
    label: "Executive Brief",
    description: "Summarize the situation, decisions needed, and next steps.",
  },
  {
    value: "research_brief",
    label: "Research Brief",
    description: "Long-form evidence-backed markdown brief.",
  },
  {
    value: "summary",
    label: "Summary",
    description: "Short markdown overview of main themes.",
  },
  {
    value: "comparison",
    label: "Comparison",
    description: "Side-by-side comparison across the indexed evidence.",
  },
];

const REPORT_TYPE_LABELS: Record<ReportType, string> = Object.fromEntries(
  REPORT_TYPE_OPTIONS.map((option) => [option.value, option.label]),
) as Record<ReportType, string>;

const ACTIONABLE_REPORT_TYPES = new Set<ReportType>([
  "action_items",
  "risk_analysis",
  "executive_brief",
]);

function getReportTypeLabel(type: ReportType) {
  return REPORT_TYPE_LABELS[type] ?? type.replace("_", " ");
}

function getReportTypeDescription(type: ReportType) {
  return (
    REPORT_TYPE_OPTIONS.find((option) => option.value === type)?.description ??
    "Generate a source-grounded report."
  );
}

function asActionItemsPayload(
  payload: StructuredReportPayload | null | undefined,
): ActionItemsPayload | null {
  if (!payload || typeof payload !== "object") return null;
  if (!("overview" in payload) || !("items" in payload)) return null;
  return payload as ActionItemsPayload;
}

function asRiskAnalysisPayload(
  payload: StructuredReportPayload | null | undefined,
): RiskAnalysisPayload | null {
  if (!payload || typeof payload !== "object") return null;
  if (!("overview" in payload) || !("items" in payload)) return null;
  return payload as RiskAnalysisPayload;
}

function asExecutiveBriefPayload(
  payload: StructuredReportPayload | null | undefined,
): ExecutiveBriefPayload | null {
  if (!payload || typeof payload !== "object") return null;
  if (!("summary" in payload)) return null;
  return payload as ExecutiveBriefPayload;
}

function getPriorityVariant(priority: ActionItemData["priority"]) {
  if (priority === "high") return "destructive";
  if (priority === "low") return "secondary";
  return "warning";
}

function getRiskVariant(severity: RiskItemData["severity"]) {
  if (severity === "high") return "destructive";
  if (severity === "low") return "secondary";
  return "warning";
}

function getStatusVariant(status: string) {
  if (status === "done" || status === "accepted") return "success";
  if (status === "needs_review") return "warning";
  return "outline";
}

function CitationList({ citations }: { citations: CitationData[] }) {
  const { openCitation } = useCitationViewer();

  function handleCitationClick(citation: CitationData) {
    if (citation.source_type === "file" && citation.source_id) {
      openCitation(citation);
      return;
    }
    if (citation.url) {
      window.open(citation.url, "_blank", "noopener,noreferrer");
    }
  }

  if (!citations.length) {
    return (
      <p className="text-xs text-muted-foreground">No source links attached.</p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {citations.map((citation, index) => {
        const label =
          citation.title ||
          citation.chunk_id ||
          citation.source_id ||
          `Source ${index + 1}`;

        return (
          <button
            key={`${citation.chunk_id}-${index}`}
            type="button"
            onClick={() => handleCitationClick(citation)}
            className="inline-flex"
          >
            <Badge variant="outline" className="cursor-pointer">
              {label}
              {citation.page_number ? ` · p.${citation.page_number}` : ""}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}

function ActionItemsView({
  payload,
  updatingItemId,
  canMutateProject,
  onStatusChange,
}: {
  payload: ActionItemsPayload;
  updatingItemId: string | null;
  canMutateProject: boolean;
  onStatusChange: (
    itemId: string,
    status: ActionItemData["status"],
  ) => Promise<void>;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <ClipboardList className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Action Items</CardTitle>
          <Badge variant="outline" className="ml-auto">
            {payload.items.length} items
          </Badge>
        </div>
        <CardDescription>{payload.overview}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {payload.items.map((item, index) => (
          <div
            key={item.id}
            className="rounded-xl border border-border bg-muted/20 p-4"
          >
            <div className="flex flex-wrap items-start gap-2">
              <h4 className="text-sm font-semibold">
                {index + 1}. {item.title}
              </h4>
              <Badge variant={getPriorityVariant(item.priority)}>
                {item.priority}
              </Badge>
              <Select
                value={item.status}
                onValueChange={(value) =>
                  void onStatusChange(
                    item.id,
                    value as ActionItemData["status"],
                  )
                }
                disabled={updatingItemId === item.id || !canMutateProject}
              >
                <SelectTrigger className="h-7 w-[136px] bg-background px-2 text-xs shadow-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="needs_review">Needs review</SelectItem>
                  <SelectItem value="done">Done</SelectItem>
                </SelectContent>
              </Select>
              <Badge variant={getStatusVariant(item.status)}>
                {updatingItemId === item.id
                  ? "saving..."
                  : item.status.replace("_", " ")}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-foreground/80">
              {item.description}
            </p>
            <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
              <div>Owner: {item.owner_suggested || "Unassigned"}</div>
              <div>Due: {item.due_date_suggested || "Not specified"}</div>
            </div>
            <div className="mt-3">
              <CitationList citations={item.citations} />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function RiskAnalysisView({ payload }: { payload: RiskAnalysisPayload }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Risk Register</CardTitle>
          <Badge variant="outline" className="ml-auto">
            {payload.items.length} risks
          </Badge>
        </div>
        <CardDescription>{payload.overview}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {payload.items.map((item, index) => (
          <div
            key={item.id}
            className="rounded-xl border border-border bg-muted/20 p-4"
          >
            <div className="flex flex-wrap items-start gap-2">
              <h4 className="text-sm font-semibold">
                {index + 1}. {item.title}
              </h4>
              <Badge variant={getRiskVariant(item.severity)}>
                {item.severity}
              </Badge>
              <Badge variant={getStatusVariant(item.status)}>
                {item.status.replace("_", " ")}
              </Badge>
            </div>
            <p className="mt-3 text-sm">
              <span className="font-medium">Why it matters:</span>{" "}
              {item.why_it_matters}
            </p>
            <p className="mt-2 text-sm">
              <span className="font-medium">Recommended action:</span>{" "}
              {item.recommended_action}
            </p>
            <div className="mt-3">
              <CitationList citations={item.citations} />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function ExecutiveBriefView({ payload }: { payload: ExecutiveBriefPayload }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Executive Brief</CardTitle>
        </div>
        <CardDescription>{payload.summary}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-3">
        <div className="rounded-xl border border-border bg-muted/20 p-4">
          <h4 className="text-sm font-semibold">Key Points</h4>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-foreground/80">
            {payload.key_points.map((point, index) => (
              <li key={`${point}-${index}`}>{point}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-border bg-muted/20 p-4">
          <h4 className="text-sm font-semibold">Decisions Needed</h4>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-foreground/80">
            {payload.decisions_needed.map((point, index) => (
              <li key={`${point}-${index}`}>{point}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-border bg-muted/20 p-4">
          <h4 className="text-sm font-semibold">Next Steps</h4>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-foreground/80">
            {payload.next_steps.map((point, index) => (
              <li key={`${point}-${index}`}>{point}</li>
            ))}
          </ul>
        </div>
        <div className="md:col-span-3">
          <CitationList citations={payload.citations} />
        </div>
      </CardContent>
    </Card>
  );
}

function MarkdownPreview({
  title,
  content,
}: {
  title: string;
  content: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>
          Markdown export preview for reuse and sharing.
        </CardDescription>
      </CardHeader>
      <Separator />
      <CardContent
        className={
          "p-8 prose prose-sm max-w-none text-foreground " +
          "prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground " +
          "prose-li:text-foreground prose-blockquote:text-muted-foreground prose-a:text-primary " +
          "prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground"
        }
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </CardContent>
    </Card>
  );
}

function StructuredReportView({
  report,
  updatingItemId,
  canMutateProject,
  onActionItemStatusChange,
}: {
  report: ReportResult;
  updatingItemId: string | null;
  canMutateProject: boolean;
  onActionItemStatusChange: (
    itemId: string,
    status: ActionItemData["status"],
  ) => Promise<void>;
}) {
  if (report.type === "action_items") {
    const payload = asActionItemsPayload(report.structured_payload);
    if (payload) {
      return (
        <>
          <ActionItemsView
            payload={payload}
            updatingItemId={updatingItemId}
            canMutateProject={canMutateProject}
            onStatusChange={onActionItemStatusChange}
          />
          <MarkdownPreview title="Markdown Export" content={report.content} />
        </>
      );
    }
  }

  if (report.type === "risk_analysis") {
    const payload = asRiskAnalysisPayload(report.structured_payload);
    if (payload) {
      return (
        <>
          <RiskAnalysisView payload={payload} />
          <MarkdownPreview title="Markdown Export" content={report.content} />
        </>
      );
    }
  }

  if (report.type === "executive_brief") {
    const payload = asExecutiveBriefPayload(report.structured_payload);
    if (payload) {
      return (
        <>
          <ExecutiveBriefView payload={payload} />
          <MarkdownPreview title="Markdown Export" content={report.content} />
        </>
      );
    }
  }

  return <MarkdownPreview title={report.title} content={report.content} />;
}

export function ReportViewer() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [activeProjectRole, setActiveProjectRole] =
    useState<ProjectRole | null>(null);
  const [query, setQuery] = useState("");
  const [reportType, setReportType] = useState<ReportType>("action_items");
  const [provider, setProvider] = useState("openai");

  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [updatingItemId, setUpdatingItemId] = useState<string | null>(null);

  const [report, setReport] = useState<ReportResult | null>(null);
  const [lineage, setLineage] = useState<ReportLineage | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectName(active.name);
      setActiveProjectRole(active.role ?? "viewer");
    }
  }, []);

  const canMutateProject = canEditProject(activeProjectRole);

  useEffect(() => {
    if (!activeProjectId) return;
    void loadHistory();
  }, [activeProjectId]);

  async function loadHistory() {
    if (!activeProjectId) return;
    setLoadingHistory(true);
    try {
      const response = await listReports(activeProjectId);
      setHistory(response.data.items);
    } catch (error) {
      console.error("Failed to load history", error);
    } finally {
      setLoadingHistory(false);
    }
  }

  async function loadLineage(reportId: string) {
    try {
      const response = await getReportLineage(reportId);
      setLineage(response.data);
    } catch (error) {
      console.error("Failed to load lineage", error);
      setLineage(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProjectId) {
      toast.error("Create or select a project first.");
      return;
    }
    if (!canMutateProject) {
      toast.error("Generating reports requires editor role or higher.");
      return;
    }
    setBusy(true);
    setReport(null);
    setLineage(null);
    const toastId = toast.loading(
      `Generating ${getReportTypeLabel(reportType)} with ${provider}...`,
    );
    try {
      const response = await generateReport({
        projectId: activeProjectId,
        query,
        type: reportType,
        provider,
      });
      setReport(response.data);
      await loadLineage(response.data.report_id);
      toast.success("Output generated successfully.", { id: toastId });
      void loadHistory();
    } catch {
      toast.error("Failed to generate output.", { id: toastId });
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadReport(reportId: string) {
    setBusy(true);
    try {
      const response = await getReport(reportId);
      setReport(response.data);
      setReportType(response.data.type);
      setQuery(response.data.query);
      await loadLineage(reportId);
      toast.success("Output loaded.");
    } catch {
      toast.error("Failed to load full output.");
    } finally {
      setBusy(false);
    }
  }

  async function handleActionItemStatusChange(
    itemId: string,
    status: ActionItemData["status"],
  ) {
    if (!report) return;
    if (!canMutateProject) {
      toast.error("Updating action items requires editor role or higher.");
      return;
    }
    setUpdatingItemId(itemId);
    try {
      const response = await updateActionItemStatus({
        reportId: report.report_id,
        itemId,
        status,
      });
      setReport(response.data);
      toast.success("Action item status updated.");
      void loadHistory();
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to update action item status.",
      );
    } finally {
      setUpdatingItemId(null);
    }
  }

  async function handleCopyMarkdown() {
    if (!report) return;
    await navigator.clipboard.writeText(report.content);
    toast.success("Markdown copied.");
  }

  async function handleCopyJson() {
    if (!report?.structured_payload) {
      toast.error("This output does not have structured JSON.");
      return;
    }
    await navigator.clipboard.writeText(
      JSON.stringify(report.structured_payload, null, 2),
    );
    toast.success("Structured JSON copied.");
  }

  function downloadFile(content: string, filename: string, type: string) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function buildExportFilename(extension: "md" | "json") {
    const base =
      report?.title
        ?.toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "report";
    return `${base}.${extension}`;
  }

  function handleExportMarkdown() {
    if (!report) return;
    downloadFile(report.content, buildExportFilename("md"), "text/markdown");
    toast.success("Markdown exported.");
  }

  function handleExportJson() {
    if (!report?.structured_payload) {
      toast.error("This output does not have structured JSON.");
      return;
    }
    downloadFile(
      JSON.stringify(report.structured_payload, null, 2),
      buildExportFilename("json"),
      "application/json",
    );
    toast.success("Structured JSON exported.");
  }

  const selectedTypeDescription = getReportTypeDescription(reportType);
  const isActionableType = ACTIONABLE_REPORT_TYPES.has(reportType);

  return (
    <PageWrapper
      title="Reports"
      description={
        activeProjectName
          ? `Generate action-focused outputs for: ${activeProjectName}`
          : "Select a project to turn indexed evidence into briefs, risks, and action items."
      }
    >
      {!canMutateProject && activeProjectId ? (
        <div className="rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          You have viewer access for this project. Report generation and action
          item updates are disabled.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Generate Output</CardTitle>
              <CardDescription>
                Build a practical deliverable from verified project evidence.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="provider-select">Writer Model</Label>
                    <Select
                      value={provider}
                      onValueChange={setProvider}
                      disabled={busy || !canMutateProject}
                    >
                      <SelectTrigger id="provider-select">
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="gemini">Gemini</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="report-type">Output Template</Label>
                    <Select
                      value={reportType}
                      onValueChange={(value) =>
                        setReportType(value as ReportType)
                      }
                      disabled={busy || !canMutateProject}
                    >
                      <SelectTrigger id="report-type">
                        <SelectValue placeholder="Select template" />
                      </SelectTrigger>
                      <SelectContent>
                        {REPORT_TYPE_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-sm">
                  <p className="font-medium">
                    {getReportTypeLabel(reportType)}
                  </p>
                  <p className="text-muted-foreground">
                    {selectedTypeDescription}
                  </p>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="query-input">Topic / Request</Label>
                  <Textarea
                    id="query-input"
                    required
                    rows={4}
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={
                      isActionableType
                        ? "E.g., Identify the main follow-ups and owners implied by these product requirement docs."
                        : "E.g., Compare the security architectures described in these whitepapers."
                    }
                    disabled={busy || !canMutateProject}
                  />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {isActionableType
                    ? "This template returns structured output with source-grounded citations."
                    : "This template renders a markdown document from synthesized evidence."}
                </p>
                <Button
                  type="submit"
                  disabled={
                    busy || !activeProjectId || !query || !canMutateProject
                  }
                  title={canMutateProject ? undefined : "Requires editor role"}
                  className="mt-2 w-full gap-2"
                >
                  {busy ? (
                    <Spinner size="sm" />
                  ) : (
                    <FileText className="h-4 w-4" />
                  )}
                  {busy ? "Generating..." : "Generate Output"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-base">History</CardTitle>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => void loadHistory()}
                disabled={loadingHistory || !activeProjectId}
              >
                <RefreshCcw className="h-3 w-3" />
              </Button>
            </CardHeader>
            <Separator />
            <CardContent className="max-h-[400px] overflow-auto p-0">
              {history.length === 0 ? (
                <div className="p-6 text-center text-sm text-muted-foreground">
                  No past outputs found.
                </div>
              ) : (
                <div className="flex flex-col">
                  {history.map((item) => (
                    <button
                      key={item.report_id}
                      onClick={() => void handleLoadReport(item.report_id)}
                      disabled={busy}
                      className="flex flex-col items-start gap-1 border-b p-4 text-left transition-colors hover:bg-muted/50 disabled:opacity-50"
                    >
                      <span className="line-clamp-2 text-sm font-medium">
                        {item.title}
                      </span>
                      <span className="line-clamp-2 text-xs text-muted-foreground">
                        {item.query}
                      </span>
                      <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                        <span>
                          {new Date(item.created_at).toLocaleDateString()}
                        </span>
                        <span>•</span>
                        <span>{getReportTypeLabel(item.type)}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-6 lg:col-span-2">
          {!report && !busy ? (
            <Card className="flex h-[300px] items-center justify-center border-dashed">
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <FileText className="h-8 w-8 opacity-20" />
                <p>
                  Generate an output to view actionable results or markdown.
                </p>
              </div>
            </Card>
          ) : busy && !report ? (
            <Card className="flex h-[300px] items-center justify-center">
              <div className="flex flex-col items-center gap-4 text-muted-foreground">
                <Spinner size="lg" />
                <p>Synthesizing evidence and building output...</p>
              </div>
            </Card>
          ) : report ? (
            <>
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-lg">{report.title}</CardTitle>
                    <Badge
                      variant={
                        ACTIONABLE_REPORT_TYPES.has(report.type)
                          ? "success"
                          : "secondary"
                      }
                      className="ml-auto"
                    >
                      {getReportTypeLabel(report.type)}
                    </Badge>
                  </div>
                  <CardDescription>
                    {getReportTypeDescription(report.type)}
                  </CardDescription>
                  <div className="flex flex-wrap gap-2 pt-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void handleCopyMarkdown()}
                      className="gap-2"
                    >
                      <Copy className="h-3.5 w-3.5" />
                      Copy Markdown
                    </Button>
                    {report.structured_payload ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void handleCopyJson()}
                        className="gap-2"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        Copy JSON
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleExportMarkdown}
                      className="gap-2"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Export .md
                    </Button>
                    {report.structured_payload ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleExportJson}
                        className="gap-2"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Export .json
                      </Button>
                    ) : null}
                  </div>
                </CardHeader>
              </Card>

              <StructuredReportView
                report={report}
                updatingItemId={updatingItemId}
                canMutateProject={canMutateProject}
                onActionItemStatusChange={handleActionItemStatusChange}
              />

              {lineage && lineage.source_ids.length > 0 && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Quote className="h-4 w-4 text-muted-foreground" />
                      <CardTitle className="text-base">
                        Document Lineage
                      </CardTitle>
                      <Badge variant="outline" className="ml-auto">
                        {lineage.source_ids.length} sources
                      </Badge>
                    </div>
                    <CardDescription>
                      This output was generated from verified chunks across{" "}
                      {lineage.source_ids.length} indexed source(s).
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="grid gap-px bg-border">
                      {lineage.source_ids.map((sourceId) => (
                        <div
                          key={sourceId}
                          className="flex items-center justify-between bg-card px-6 py-4"
                        >
                          <p className="text-sm font-mono text-muted-foreground">
                            Source ID: {sourceId}
                          </p>
                          <a
                            href={`/sources?id=${sourceId}`}
                            className="text-xs text-primary hover:underline"
                          >
                            View details
                          </a>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : null}
        </div>
      </div>
    </PageWrapper>
  );
}
