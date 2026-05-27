"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  CalendarDays,
  Copy,
  Download,
  FileText,
  HelpCircle,
  Lightbulb,
  RefreshCcw,
} from "lucide-react";
import { toast } from "sonner";

import { generateReport, getReport, listReports } from "@/lib/api/client";
import type {
  CitationData,
  ProjectRole,
  ReportListItem,
  ReportResult,
  StructuredReportPayload,
  StudyGuidePayload,
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

const DEFAULT_STUDY_GUIDE_QUERY =
  "Create a study guide from all indexed documents in this project.";

type StudyGuideView = "overview" | "sections" | "concepts" | "timeline" | "review";

const studyGuideViews: Array<{
  id: StudyGuideView;
  label: string;
  icon: typeof BookOpen;
}> = [
  { id: "overview", label: "Overview", icon: FileText },
  { id: "sections", label: "Sections", icon: BookOpen },
  { id: "concepts", label: "Concepts", icon: Lightbulb },
  { id: "timeline", label: "Timeline", icon: CalendarDays },
  { id: "review", label: "Review", icon: HelpCircle },
];

function asStudyGuidePayload(
  payload: StructuredReportPayload | null | undefined,
): StudyGuidePayload | null {
  if (!payload || typeof payload !== "object") return null;
  if (!("overview" in payload) || !("sections" in payload)) return null;
  const sections = (payload as { sections?: unknown }).sections;
  const keyConcepts = (payload as { key_concepts?: unknown }).key_concepts;
  const timeline = (payload as { timeline?: unknown }).timeline;
  const reviewQuestions = (payload as { review_questions?: unknown }).review_questions;
  if (
    !Array.isArray(sections) ||
    !Array.isArray(keyConcepts) ||
    !Array.isArray(timeline) ||
    !Array.isArray(reviewQuestions)
  ) {
    return null;
  }
  return payload as StudyGuidePayload;
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
              {citation.page_number ? ` - p.${citation.page_number}` : ""}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <Card className="flex h-[220px] items-center justify-center border-dashed">
      <p className="text-sm text-muted-foreground">{message}</p>
    </Card>
  );
}

function StudyGuideContent({
  payload,
  activeView,
}: {
  payload: StudyGuidePayload;
  activeView: StudyGuideView;
}) {
  if (activeView === "overview") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Overview</CardTitle>
          <CardDescription>
            A compact map of the generated guide.
          </CardDescription>
        </CardHeader>
        <Separator />
        <CardContent className="flex flex-col gap-6 p-6">
          <p className="text-sm leading-6 text-muted-foreground">
            {payload.overview}
          </p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-md border border-border bg-muted/20 p-4">
              <p className="text-2xl font-semibold">{payload.sections.length}</p>
              <p className="text-xs text-muted-foreground">Sections</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-4">
              <p className="text-2xl font-semibold">{payload.key_concepts.length}</p>
              <p className="text-xs text-muted-foreground">Key concepts</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-4">
              <p className="text-2xl font-semibold">{payload.timeline.length}</p>
              <p className="text-xs text-muted-foreground">Timeline items</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-4">
              <p className="text-2xl font-semibold">
                {payload.review_questions.length}
              </p>
              <p className="text-xs text-muted-foreground">Review questions</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (activeView === "sections") {
    if (!payload.sections.length) {
      return <EmptyPanel message="No sections were generated." />;
    }
    return (
      <div className="flex flex-col gap-4">
        {payload.sections.map((section, index) => (
          <Card key={section.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">Section {index + 1}</Badge>
                <CardTitle className="text-base">{section.title}</CardTitle>
              </div>
              <CardDescription>{section.summary}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {section.key_points.length ? (
                <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
                  {section.key_points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
              ) : null}
              <CitationList citations={section.citations} />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (activeView === "concepts") {
    if (!payload.key_concepts.length) {
      return <EmptyPanel message="No key concepts were generated." />;
    }
    return (
      <div className="grid gap-4 xl:grid-cols-2">
        {payload.key_concepts.map((concept) => (
          <Card key={concept.id}>
            <CardHeader>
              <CardTitle className="text-base">{concept.term}</CardTitle>
              <CardDescription>{concept.definition}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="rounded-md border border-border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase text-muted-foreground">
                  Importance
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {concept.importance}
                </p>
              </div>
              <CitationList citations={concept.citations} />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (activeView === "timeline") {
    if (!payload.timeline.length) {
      return (
        <EmptyPanel message="No timeline items were found in the indexed evidence." />
      );
    }
    return (
      <div className="flex flex-col gap-4">
        {payload.timeline.map((item, index) => (
          <Card key={item.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{index + 1}</Badge>
                <CardTitle className="text-base">{item.label}</CardTitle>
              </div>
              <CardDescription>{item.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <CitationList citations={item.citations} />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (!payload.review_questions.length) {
    return <EmptyPanel message="No review questions were generated." />;
  }
  return (
    <div className="flex flex-col gap-4">
      {payload.review_questions.map((question, index) => (
        <Card key={question.id}>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Question {index + 1}</Badge>
              <CardTitle className="text-base leading-6">
                {question.question}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="rounded-md border border-border bg-muted/20 p-4">
              <p className="text-xs font-medium uppercase text-muted-foreground">
                Suggested Answer
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                {question.answer}
              </p>
            </div>
            <CitationList citations={question.citations} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function StudyGuideViewer() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [activeProjectRole, setActiveProjectRole] =
    useState<ProjectRole | null>(null);
  const [provider, setProvider] = useState("openai");
  const [query, setQuery] = useState(DEFAULT_STUDY_GUIDE_QUERY);
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [report, setReport] = useState<ReportResult | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [activeView, setActiveView] = useState<StudyGuideView>("overview");

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectName(active.name);
      setActiveProjectRole(active.role ?? "viewer");
    }
  }, []);

  const canMutateProject = canEditProject(activeProjectRole);
  const payload = useMemo(
    () => asStudyGuidePayload(report?.structured_payload),
    [report],
  );

  useEffect(() => {
    if (!activeProjectId) return;
    void loadHistory();
  }, [activeProjectId]);

  useEffect(() => {
    setActiveView("overview");
  }, [report?.report_id]);

  async function loadHistory() {
    if (!activeProjectId) return;
    setLoadingHistory(true);
    try {
      const response = await listReports(activeProjectId);
      setHistory(response.data.items.filter((item) => item.type === "study_guide"));
    } catch (error) {
      console.error("Failed to load study guide history", error);
    } finally {
      setLoadingHistory(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProjectId) {
      toast.error("Create or select a project first.");
      return;
    }
    if (!canMutateProject) {
      toast.error("Generating study guides requires editor role or higher.");
      return;
    }
    setBusy(true);
    setReport(null);
    const toastId = toast.loading(`Generating study guide with ${provider}...`);
    try {
      const response = await generateReport({
        projectId: activeProjectId,
        query: query || DEFAULT_STUDY_GUIDE_QUERY,
        type: "study_guide",
        provider,
      });
      setReport(response.data);
      toast.success("Study guide generated.", { id: toastId });
      void loadHistory();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to generate study guide.",
        { id: toastId },
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadReport(reportId: string) {
    setBusy(true);
    try {
      const response = await getReport(reportId);
      setReport(response.data);
      setQuery(response.data.query);
      toast.success("Study guide loaded.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to load study guide.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCopyJson() {
    if (!payload) return;
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    toast.success("Study guide JSON copied.");
  }

  async function handleCopyMarkdown() {
    if (!report) return;
    await navigator.clipboard.writeText(report.content);
    toast.success("Study guide markdown copied.");
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

  function exportBaseName() {
    return (
      report?.title
        ?.toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "study-guide"
    );
  }

  return (
    <PageWrapper
      title="Study Guide"
      description={
        activeProjectName
          ? `Generate a source-grounded study guide for: ${activeProjectName}`
          : "Select a project to generate a study guide from indexed sources."
      }
    >
      {!canMutateProject && activeProjectId ? (
        <div className="rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          You have viewer access for this project. Study guide generation is
          disabled.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-base">Generate Guide</CardTitle>
              </div>
              <CardDescription>
                Uses all indexed chunks in the active project.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="study-guide-provider">Writer Model</Label>
                  <Select
                    value={provider}
                    onValueChange={setProvider}
                    disabled={busy || !canMutateProject}
                  >
                    <SelectTrigger id="study-guide-provider">
                      <SelectValue placeholder="Select provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="gemini">Gemini</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="study-guide-query">Prompt</Label>
                  <Textarea
                    id="study-guide-query"
                    rows={4}
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    disabled={busy || !canMutateProject}
                  />
                </div>
                <Button
                  type="submit"
                  disabled={busy || !activeProjectId || !canMutateProject}
                  className="gap-2"
                >
                  {busy ? <Spinner size="sm" /> : <BookOpen className="h-4 w-4" />}
                  {busy ? "Generating..." : "Generate Study Guide"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <div>
                <CardTitle className="text-base">History</CardTitle>
                <CardDescription>Previous study guides.</CardDescription>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => void loadHistory()}
                disabled={loadingHistory || !activeProjectId}
              >
                <RefreshCcw className="h-3.5 w-3.5" />
              </Button>
            </CardHeader>
            <Separator />
            <CardContent className="max-h-[420px] overflow-auto p-0">
              {history.length === 0 ? (
                <div className="p-6 text-center text-sm text-muted-foreground">
                  No study guides yet.
                </div>
              ) : (
                history.map((item) => (
                  <button
                    key={item.report_id}
                    type="button"
                    onClick={() => void handleLoadReport(item.report_id)}
                    disabled={busy}
                    className="flex w-full flex-col items-start gap-1 border-b p-4 text-left transition-colors hover:bg-muted/50 disabled:opacity-50"
                  >
                    <span className="line-clamp-2 text-sm font-medium">
                      {item.title}
                    </span>
                    <span className="line-clamp-2 text-xs text-muted-foreground">
                      {item.query}
                    </span>
                    <span className="mt-1 text-xs text-muted-foreground">
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          {report ? (
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle className="text-lg">{report.title}</CardTitle>
                  <Badge variant="success" className="ml-auto">
                    Study Guide
                  </Badge>
                </div>
                <CardDescription>
                  {payload
                    ? `${payload.sections.length} sections, ${payload.key_concepts.length} concepts, ${payload.review_questions.length} review questions.`
                    : "Structured study guide payload is unavailable."}
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
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void handleCopyJson()}
                    disabled={!payload}
                    className="gap-2"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    Copy JSON
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      report &&
                      downloadFile(report.content, `${exportBaseName()}.md`, "text/markdown")
                    }
                    className="gap-2"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export .md
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      payload &&
                      downloadFile(
                        JSON.stringify(payload, null, 2),
                        `${exportBaseName()}.json`,
                        "application/json",
                      )
                    }
                    disabled={!payload}
                    className="gap-2"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export .json
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ) : null}

          {busy && !report ? (
            <Card className="flex h-[320px] items-center justify-center">
              <div className="flex flex-col items-center gap-4 text-muted-foreground">
                <Spinner size="lg" />
                <p>Reading indexed chunks and generating a study guide...</p>
              </div>
            </Card>
          ) : payload ? (
            <>
              <div className="flex flex-wrap gap-2">
                {studyGuideViews.map(({ id, label, icon: Icon }) => (
                  <Button
                    key={id}
                    type="button"
                    variant={activeView === id ? "default" : "outline"}
                    size="sm"
                    onClick={() => setActiveView(id)}
                    className="gap-2"
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </Button>
                ))}
              </div>
              <StudyGuideContent payload={payload} activeView={activeView} />
            </>
          ) : (
            <Card className="flex h-[320px] items-center justify-center border-dashed">
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <BookOpen className="h-8 w-8 opacity-20" />
                <p>Generate a guide to study the indexed source material.</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
