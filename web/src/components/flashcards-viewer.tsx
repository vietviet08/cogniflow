"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  Layers,
  RefreshCcw,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

import {
  generateReport,
  getReport,
  listReports,
} from "@/lib/api/client";
import type {
  CitationData,
  FlashcardData,
  FlashcardsPayload,
  ProjectRole,
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

const DEFAULT_FLASHCARDS_QUERY =
  "Create flashcards from all indexed documents in this project.";

function asFlashcardsPayload(
  payload: StructuredReportPayload | null | undefined,
): FlashcardsPayload | null {
  if (!payload || typeof payload !== "object") return null;
  if (!("overview" in payload) || !("cards" in payload)) return null;
  const cards = (payload as { cards?: unknown }).cards;
  if (!Array.isArray(cards)) return null;
  return payload as FlashcardsPayload;
}

function getDifficultyVariant(difficulty: FlashcardData["difficulty"]) {
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

function FlashcardDeck({
  payload,
  selectedIndex,
  showBack,
  onSelect,
  onFlip,
  onNext,
  onPrevious,
}: {
  payload: FlashcardsPayload;
  selectedIndex: number;
  showBack: boolean;
  onSelect: (index: number) => void;
  onFlip: () => void;
  onNext: () => void;
  onPrevious: () => void;
}) {
  const selectedCard = payload.cards[selectedIndex];

  if (!selectedCard) {
    return (
      <Card className="flex h-[260px] items-center justify-center border-dashed">
        <p className="text-sm text-muted-foreground">
          This deck does not contain any flashcards.
        </p>
      </Card>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-base">
                Card {selectedIndex + 1} of {payload.cards.length}
              </CardTitle>
              <Badge variant={getDifficultyVariant(selectedCard.difficulty)}>
                {selectedCard.difficulty}
              </Badge>
              <div className="ml-auto flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={onPrevious}
                  disabled={payload.cards.length <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={onNext}
                  disabled={payload.cards.length <= 1}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <CardDescription>{payload.overview}</CardDescription>
          </CardHeader>
          <Separator />
          <CardContent className="flex min-h-[360px] flex-col justify-between gap-6 p-6">
            {/* 3D Flip Card Container */}
            <div 
              onClick={onFlip}
              className="perspective-1000 cursor-pointer w-full min-h-[260px] select-none group"
            >
              <div 
                className={cn(
                  "relative w-full h-full min-h-[260px] transition-transform duration-500 preserve-3d",
                  showBack ? "rotate-y-180" : ""
                )}
              >
                {/* Front Face */}
                <div className="absolute inset-0 w-full h-full backface-hidden rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between p-8 transition-all duration-300 group-hover:border-primary/30 group-hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline" className="text-[10px] font-semibold uppercase tracking-wider opacity-60 bg-background/50">Front</Badge>
                    <Sparkles className="h-4 w-4 text-primary opacity-45 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <div className="flex-1 flex items-center justify-center py-4">
                    <p className="text-lg font-semibold text-center leading-relaxed text-foreground max-h-full overflow-y-auto px-2">
                      {selectedCard.front}
                    </p>
                  </div>
                  <div className="text-[11px] text-center text-muted-foreground opacity-55 group-hover:opacity-90 transition-opacity">
                    Click to reveal definition
                  </div>
                </div>

                {/* Back Face */}
                <div className="absolute inset-0 w-full h-full backface-hidden rotate-y-180 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between p-8 transition-all duration-300 group-hover:border-primary/30 group-hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <Badge variant="secondary" className="text-[10px] font-semibold uppercase tracking-wider">Back</Badge>
                    <RotateCcw className="h-4 w-4 text-primary opacity-45" />
                  </div>
                  <div className="flex-1 flex flex-col justify-center py-2 overflow-y-auto px-2">
                    <p className="text-lg font-medium text-center leading-relaxed text-foreground">
                      {selectedCard.back}
                    </p>
                    {selectedCard.explanation && (
                      <div className="mt-3 pt-3 border-t border-border/50">
                        <p className="text-sm text-left leading-relaxed text-muted-foreground italic border-l-2 border-primary/30 pl-2">
                          {selectedCard.explanation}
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="text-[11px] text-center text-muted-foreground opacity-55">
                    Click to flip back
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={(e) => {
                  e.stopPropagation();
                  onFlip();
                }}
                className="gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                Flip
              </Button>
              {selectedCard.tags.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
            <CitationList citations={selectedCard.citations} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Deck</CardTitle>
          <CardDescription>
            Scan all generated cards and jump to any item.
          </CardDescription>
        </CardHeader>
        <Separator />
        <CardContent className="max-h-[520px] overflow-auto p-0">
          {payload.cards.map((card, index) => (
            <button
              key={card.id}
              type="button"
              onClick={() => onSelect(index)}
              className={
                "flex w-full flex-col items-start gap-2 border-b p-4 text-left transition-colors hover:bg-muted/50 " +
                (index === selectedIndex ? "bg-muted/60" : "")
              }
            >
              <div className="flex w-full items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {index + 1}
                </span>
                <Badge variant={getDifficultyVariant(card.difficulty)}>
                  {card.difficulty}
                </Badge>
              </div>
              <span className="line-clamp-2 text-sm font-medium">
                {card.front}
              </span>
              <span className="line-clamp-2 text-xs text-muted-foreground">
                {card.back}
              </span>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export function FlashcardsViewer() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [activeProjectRole, setActiveProjectRole] =
    useState<ProjectRole | null>(null);
  const [provider, setProvider] = useState("openai");
  const [query, setQuery] = useState(DEFAULT_FLASHCARDS_QUERY);
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [report, setReport] = useState<ReportResult | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [showBack, setShowBack] = useState(false);

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
    () => asFlashcardsPayload(report?.structured_payload),
    [report],
  );

  useEffect(() => {
    if (!activeProjectId) return;
    void loadHistory();
  }, [activeProjectId]);

  useEffect(() => {
    setSelectedIndex(0);
    setShowBack(false);
  }, [report?.report_id]);

  async function loadHistory() {
    if (!activeProjectId) return;
    setLoadingHistory(true);
    try {
      const response = await listReports(activeProjectId);
      setHistory(response.data.items.filter((item) => item.type === "flashcards"));
    } catch (error) {
      console.error("Failed to load flashcards history", error);
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
      toast.error("Generating flashcards requires editor role or higher.");
      return;
    }
    setBusy(true);
    setReport(null);
    const toastId = toast.loading(`Generating flashcards with ${provider}...`);
    try {
      const response = await generateReport({
        projectId: activeProjectId,
        query: query || DEFAULT_FLASHCARDS_QUERY,
        type: "flashcards",
        provider,
      });
      setReport(response.data);
      toast.success("Flashcards generated.", { id: toastId });
      void loadHistory();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to generate flashcards.",
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
      toast.success("Flashcards loaded.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to load flashcards.",
      );
    } finally {
      setBusy(false);
    }
  }

  function selectedNextIndex(offset: number) {
    if (!payload?.cards.length) return 0;
    return (selectedIndex + offset + payload.cards.length) % payload.cards.length;
  }

  function handleSelectCard(index: number) {
    setSelectedIndex(index);
    setShowBack(false);
  }

  async function handleCopyJson() {
    if (!payload) return;
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    toast.success("Flashcards JSON copied.");
  }

  async function handleCopyMarkdown() {
    if (!report) return;
    await navigator.clipboard.writeText(report.content);
    toast.success("Flashcards markdown copied.");
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
        .replace(/^-|-$/g, "") || "flashcards"
    );
  }

  return (
    <PageWrapper
      title="Flashcards"
      description={
        activeProjectName
          ? `Generate source-grounded study cards for: ${activeProjectName}`
          : "Select a project to generate flashcards from indexed sources."
      }
    >
      {!canMutateProject && activeProjectId ? (
        <div className="rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          You have viewer access for this project. Flashcard generation is
          disabled.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-base">Generate Deck</CardTitle>
              </div>
              <CardDescription>
                Uses all indexed chunks in the active project.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="flashcards-provider">Writer Model</Label>
                  <Select
                    value={provider}
                    onValueChange={setProvider}
                    disabled={busy || !canMutateProject}
                  >
                    <SelectTrigger id="flashcards-provider">
                      <SelectValue placeholder="Select provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="gemini">Gemini</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="flashcards-query">Prompt</Label>
                  <Textarea
                    id="flashcards-query"
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
                  {busy ? <Spinner size="sm" /> : <Layers className="h-4 w-4" />}
                  {busy ? "Generating..." : "Generate Flashcards"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <div>
                <CardTitle className="text-base">History</CardTitle>
                <CardDescription>Previous flashcard decks.</CardDescription>
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
                  No flashcard decks yet.
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
                    Flashcards
                  </Badge>
                </div>
                <CardDescription>
                  {payload
                    ? `${payload.cards.length} cards generated from indexed evidence.`
                    : "Structured flashcards payload is unavailable."}
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
                      downloadFile(
                        report.content,
                        `${exportBaseName()}.md`,
                        "text/markdown",
                      )
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
                <p>Reading indexed chunks and generating flashcards...</p>
              </div>
            </Card>
          ) : payload ? (
            <FlashcardDeck
              payload={payload}
              selectedIndex={selectedIndex}
              showBack={showBack}
              onSelect={handleSelectCard}
              onFlip={() => setShowBack((value) => !value)}
              onNext={() => {
                setSelectedIndex(selectedNextIndex(1));
                setShowBack(false);
              }}
              onPrevious={() => {
                setSelectedIndex(selectedNextIndex(-1));
                setShowBack(false);
              }}
            />
          ) : (
            <Card className="flex h-[320px] items-center justify-center border-dashed">
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <Layers className="h-8 w-8 opacity-20" />
                <p>Generate a deck to study the indexed source material.</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
