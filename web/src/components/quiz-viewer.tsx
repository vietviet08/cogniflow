"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  CircleHelp,
  Copy,
  Download,
  RefreshCcw,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import {
  createQuizAttempt,
  generateReport,
  getReport,
  listQuizAttempts,
  listReports,
} from "@/lib/api/client";
import type {
  CitationData,
  ProjectRole,
  QuizAttemptData,
  QuizPayload,
  QuizQuestionData,
  ReportListItem,
  ReportResult,
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

const DEFAULT_QUIZ_QUERY =
  "Create a quiz from all indexed documents in this project.";

function asQuizPayload(
  payload: StructuredReportPayload | null | undefined,
): QuizPayload | null {
  if (!payload || typeof payload !== "object") return null;
  if (!("overview" in payload) || !("questions" in payload)) return null;
  const questions = (payload as { questions?: unknown }).questions;
  if (!Array.isArray(questions)) return null;
  return payload as QuizPayload;
}

function getDifficultyVariant(difficulty: QuizQuestionData["difficulty"]) {
  if (difficulty === "hard") return "destructive";
  if (difficulty === "easy") return "secondary";
  return "warning";
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

function QuizResultSummary({
  attempt,
}: {
  attempt: QuizAttemptData;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-3">
          <CardTitle className="text-base">Score</CardTitle>
          <Badge variant={attempt.score_percent >= 70 ? "success" : "warning"}>
            {attempt.score_correct}/{attempt.score_total} correct
          </Badge>
          <Badge variant="outline">{attempt.score_percent}%</Badge>
        </div>
        <CardDescription>
          Saved {attempt.created_at ? new Date(attempt.created_at).toLocaleString() : "just now"}.
        </CardDescription>
      </CardHeader>
    </Card>
  );
}

function QuizAttemptsPanel({
  attempts,
  loading,
  onLoadAttempt,
}: {
  attempts: QuizAttemptData[];
  loading: boolean;
  onLoadAttempt: (attempt: QuizAttemptData) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Saved Attempts</CardTitle>
        <CardDescription>
          Compare this run with previous submitted answers.
        </CardDescription>
      </CardHeader>
      <Separator />
      <CardContent className="flex flex-col gap-2 p-4">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner size="sm" />
            Loading attempts...
          </div>
        ) : attempts.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No saved attempts for this quiz yet.
          </p>
        ) : (
          attempts.map((attempt) => (
            <button
              key={attempt.attempt_id}
              type="button"
              onClick={() => onLoadAttempt(attempt)}
              className="flex items-center gap-3 rounded-md border border-border bg-background px-3 py-2 text-left transition-colors hover:bg-muted/50"
            >
              <Badge variant={attempt.score_percent >= 70 ? "success" : "warning"}>
                {attempt.score_percent}%
              </Badge>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {attempt.score_correct}/{attempt.score_total} correct
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {attempt.created_at
                    ? new Date(attempt.created_at).toLocaleString()
                    : "Saved attempt"}
                </p>
              </div>
            </button>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function QuizQuestion({
  question,
  selectedOptionId,
  submitted,
  onSelect,
}: {
  question: QuizQuestionData;
  selectedOptionId?: string;
  submitted: boolean;
  onSelect: (optionId: string) => void;
}) {
  const isCorrect = selectedOptionId === question.correct_option_id;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            {question.type === "true_false" ? "True/False" : "Multiple choice"}
          </Badge>
          <Badge variant={getDifficultyVariant(question.difficulty)}>
            {question.difficulty}
          </Badge>
          {submitted ? (
            <Badge variant={isCorrect ? "success" : "destructive"}>
              {isCorrect ? "Correct" : "Incorrect"}
            </Badge>
          ) : null}
        </div>
        <CardTitle className="text-base leading-6">
          {question.question}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid gap-2">
          {question.options.map((option) => {
            const selected = selectedOptionId === option.id;
            const correct = submitted && option.id === question.correct_option_id;
            const wrongSelected = submitted && selected && !correct;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onSelect(option.id)}
                disabled={submitted}
                className={
                  "flex min-h-11 items-center gap-3 rounded-md border px-4 py-3 text-left text-sm transition-colors " +
                  (correct
                    ? "border-emerald-500 bg-emerald-500/10"
                    : wrongSelected
                      ? "border-destructive bg-destructive/10"
                      : selected
                        ? "border-primary bg-primary/10"
                        : "border-border bg-background hover:bg-muted/50")
                }
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border text-xs font-semibold uppercase">
                  {option.id}
                </span>
                <span className="flex-1">{option.text}</span>
                {correct ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : null}
                {wrongSelected ? <XCircle className="h-4 w-4 text-destructive" /> : null}
              </button>
            );
          })}
        </div>

        {submitted ? (
          <div className="rounded-md border border-border bg-muted/20 p-4">
            <p className="text-sm font-medium">Explanation</p>
            <p className="mt-2 text-sm text-muted-foreground">
              {question.explanation}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {question.tags.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
            <div className="mt-3">
              <CitationList citations={question.citations} />
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function QuizViewer() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [activeProjectRole, setActiveProjectRole] =
    useState<ProjectRole | null>(null);
  const [provider, setProvider] = useState("openai");
  const [query, setQuery] = useState(DEFAULT_QUIZ_QUERY);
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [report, setReport] = useState<ReportResult | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [savingAttempt, setSavingAttempt] = useState(false);
  const [loadingAttempts, setLoadingAttempts] = useState(false);
  const [attempts, setAttempts] = useState<QuizAttemptData[]>([]);
  const [activeAttempt, setActiveAttempt] = useState<QuizAttemptData | null>(null);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectName(active.name);
      setActiveProjectRole(active.role ?? "viewer");
    }
  }, []);

  const canMutateProject = canEditProject(activeProjectRole);
  const payload = useMemo(() => asQuizPayload(report?.structured_payload), [report]);

  useEffect(() => {
    if (!activeProjectId) return;
    void loadHistory();
  }, [activeProjectId]);

  useEffect(() => {
    setAnswers({});
    setSubmitted(false);
    setActiveAttempt(null);
    if (report?.report_id) {
      void loadAttempts(report.report_id);
    } else {
      setAttempts([]);
    }
  }, [report?.report_id]);

  async function loadHistory() {
    if (!activeProjectId) return;
    setLoadingHistory(true);
    try {
      const response = await listReports(activeProjectId);
      setHistory(response.data.items.filter((item) => item.type === "quiz"));
    } catch (error) {
      console.error("Failed to load quiz history", error);
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
      toast.error("Generating quizzes requires editor role or higher.");
      return;
    }
    setBusy(true);
    setReport(null);
    const toastId = toast.loading(`Generating quiz with ${provider}...`);
    try {
      const response = await generateReport({
        projectId: activeProjectId,
        query: query || DEFAULT_QUIZ_QUERY,
        type: "quiz",
        provider,
      });
      setReport(response.data);
      toast.success("Quiz generated.", { id: toastId });
      void loadHistory();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to generate quiz.",
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
      toast.success("Quiz loaded.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load quiz.");
    } finally {
      setBusy(false);
    }
  }

  async function loadAttempts(reportId: string) {
    setLoadingAttempts(true);
    try {
      const response = await listQuizAttempts(reportId);
      setAttempts(response.data.items);
    } catch (error) {
      console.error("Failed to load quiz attempts", error);
      setAttempts([]);
    } finally {
      setLoadingAttempts(false);
    }
  }

  async function handleQuizSubmit() {
    if (!payload || !report) return;
    const unanswered = payload.questions.filter((question) => !answers[question.id]);
    if (unanswered.length) {
      toast.error(`Answer ${unanswered.length} more question(s) before submitting.`);
      return;
    }
    setSavingAttempt(true);
    try {
      const response = await createQuizAttempt({
        reportId: report.report_id,
        answers,
      });
      setActiveAttempt(response.data);
      setAttempts((current) => [response.data, ...current]);
      setSubmitted(true);
      toast.success("Quiz submitted and saved.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to save quiz attempt.",
      );
    } finally {
      setSavingAttempt(false);
    }
  }

  function resetAttempt() {
    setAnswers({});
    setSubmitted(false);
    setActiveAttempt(null);
  }

  function loadSavedAttempt(attempt: QuizAttemptData) {
    setAnswers(attempt.answers);
    setActiveAttempt(attempt);
    setSubmitted(true);
    toast.success("Saved attempt loaded.");
  }

  async function handleCopyJson() {
    if (!payload) return;
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    toast.success("Quiz JSON copied.");
  }

  async function handleCopyMarkdown() {
    if (!report) return;
    await navigator.clipboard.writeText(report.content);
    toast.success("Quiz markdown copied.");
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
        .replace(/^-|-$/g, "") || "quiz"
    );
  }

  return (
    <PageWrapper
      title="Quiz"
      description={
        activeProjectName
          ? `Generate a source-grounded quiz for: ${activeProjectName}`
          : "Select a project to generate a quiz from indexed sources."
      }
    >
      {!canMutateProject && activeProjectId ? (
        <div className="rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          You have viewer access for this project. Quiz generation is disabled.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CircleHelp className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-base">Generate Quiz</CardTitle>
              </div>
              <CardDescription>
                Uses all indexed chunks in the active project.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="quiz-provider">Writer Model</Label>
                  <Select
                    value={provider}
                    onValueChange={setProvider}
                    disabled={busy || !canMutateProject}
                  >
                    <SelectTrigger id="quiz-provider">
                      <SelectValue placeholder="Select provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="gemini">Gemini</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="quiz-query">Prompt</Label>
                  <Textarea
                    id="quiz-query"
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
                  {busy ? <Spinner size="sm" /> : <CircleHelp className="h-4 w-4" />}
                  {busy ? "Generating..." : "Generate Quiz"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <div>
                <CardTitle className="text-base">History</CardTitle>
                <CardDescription>Previous quizzes.</CardDescription>
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
                  No quizzes yet.
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
                    Quiz
                  </Badge>
                </div>
                <CardDescription>
                  {payload
                    ? `${payload.questions.length} questions generated from indexed evidence.`
                    : "Structured quiz payload is unavailable."}
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
                <p>Reading indexed chunks and generating a quiz...</p>
              </div>
            </Card>
          ) : payload ? (
            <>
              {submitted && activeAttempt ? (
                <QuizResultSummary attempt={activeAttempt} />
              ) : null}
              <QuizAttemptsPanel
                attempts={attempts}
                loading={loadingAttempts}
                onLoadAttempt={loadSavedAttempt}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  onClick={() => void handleQuizSubmit()}
                  disabled={submitted || savingAttempt || !payload.questions.length}
                  className="gap-2"
                >
                  {savingAttempt ? <Spinner size="sm" /> : <CheckCircle2 className="h-4 w-4" />}
                  {savingAttempt ? "Saving..." : "Submit Quiz"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={resetAttempt}
                  className="gap-2"
                >
                  <RotateCcw className="h-4 w-4" />
                  Reset Attempt
                </Button>
              </div>
              <div className="flex flex-col gap-4">
                {payload.questions.map((question, index) => (
                  <div key={question.id} className="flex flex-col gap-2">
                    <div className="text-sm font-medium text-muted-foreground">
                      Question {index + 1}
                    </div>
                    <QuizQuestion
                      question={question}
                      selectedOptionId={answers[question.id]}
                      submitted={submitted}
                      onSelect={(optionId) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: optionId,
                        }))
                      }
                    />
                  </div>
                ))}
              </div>
            </>
          ) : (
            <Card className="flex h-[320px] items-center justify-center border-dashed">
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <CircleHelp className="h-8 w-8 opacity-20" />
                <p>Generate a quiz to test understanding of indexed sources.</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
