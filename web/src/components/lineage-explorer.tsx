"use client";

import type { ReactNode } from "react";
import {
  Braces,
  FileText,
  GitBranch,
  Quote,
  Search,
} from "lucide-react";

import type { CitationData, LineagePayload } from "@/lib/api/types";

import { useCitationViewer } from "@/components/citation-viewer-provider";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

interface LineageExplorerProps {
  lineage: LineagePayload;
}

export function LineageExplorer({ lineage }: LineageExplorerProps) {
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

  return (
    <div className="rounded-lg border bg-card">
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-base font-semibold">Lineage Explorer</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            Audit path from generated output to runs, insights, sources,
            documents, chunks, and citations.
          </p>
        </div>
        <Badge variant="outline">{lineage.summary.citation_count} citations</Badge>
      </div>

      <Separator />

      <div className="grid gap-px bg-border sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="Runs" value={lineage.summary.run_count} />
        <Metric label="Insights" value={lineage.summary.insight_count} />
        <Metric label="Sources" value={lineage.summary.source_count} />
        <Metric label="Documents" value={lineage.summary.document_count} />
        <Metric label="Chunks" value={lineage.summary.chunk_count} />
        <Metric label="Citations" value={lineage.summary.citation_count} />
      </div>

      <div className="grid gap-6 p-5 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-5">
          <SectionTitle icon={<Braces className="h-4 w-4" />} title="Runs" />
          {lineage.runs.length === 0 ? (
            <EmptyState label="No run metadata attached." />
          ) : (
            <div className="space-y-3">
              {lineage.runs.map((run) => (
                <div key={run.run_id} className="rounded-md border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{run.run_type}</Badge>
                    <span className="font-mono text-xs text-muted-foreground">
                      {run.run_id}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-muted-foreground">
                    <KeyValue label="Model" value={run.model_id ?? "n/a"} />
                    <KeyValue label="Prompt" value={run.prompt_hash ?? "n/a"} />
                    <KeyValue label="Config" value={run.config_hash ?? "n/a"} />
                    <KeyValue
                      label="Retrieval"
                      value={formatRetrieval(run.retrieval_config)}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          <SectionTitle icon={<Search className="h-4 w-4" />} title="Insights" />
          {lineage.insights.length === 0 ? (
            <EmptyState label="No insight nodes attached." />
          ) : (
            <div className="space-y-3">
              {lineage.insights.map((insight) => (
                <div key={insight.insight_id} className="rounded-md border p-3">
                  <p className="line-clamp-2 text-sm font-medium">
                    {insight.query}
                  </p>
                  <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">
                    {insight.summary || "No summary"}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant="outline">{insight.provider ?? "provider"}</Badge>
                    <Badge variant="outline">{insight.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-5">
          <SectionTitle icon={<FileText className="h-4 w-4" />} title="Sources" />
          {lineage.sources.length === 0 ? (
            <EmptyState label="No source graph attached." />
          ) : (
            <div className="space-y-3">
              {lineage.sources.map((source) => (
                <div key={source.source_id} className="rounded-md border">
                  <div className="flex flex-col gap-2 p-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-sm font-medium">{source.title}</p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {source.source_id}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Badge variant="secondary">{source.type}</Badge>
                      <Badge variant="outline">{source.status}</Badge>
                    </div>
                  </div>
                  <Separator />
                  <div className="space-y-3 p-3">
                    {source.documents.map((document) => (
                      <div key={document.document_id} className="rounded-md bg-muted/40 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="line-clamp-1 text-sm font-medium">
                            {document.title}
                          </p>
                          <span className="text-xs text-muted-foreground">
                            {document.token_count} tokens
                          </span>
                        </div>
                        <div className="mt-3 space-y-2">
                          {document.chunks.map((chunk) => (
                            <div key={chunk.chunk_id} className="rounded border bg-card p-2">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-mono text-xs text-muted-foreground">
                                  Chunk {chunk.chunk_index}
                                </span>
                                <Badge variant="outline">
                                  {chunk.citation_count} refs
                                </Badge>
                              </div>
                              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                                {chunk.preview}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          <SectionTitle icon={<Quote className="h-4 w-4" />} title="Citations" />
          {lineage.citations.length === 0 ? (
            <EmptyState label="No citations attached." />
          ) : (
            <div className="grid gap-2">
              {lineage.citations.map((citation, index) => (
                <button
                  key={`${citation.citation_id}-${index}`}
                  type="button"
                  onClick={() => handleCitationClick(citation)}
                  className="rounded-md border p-3 text-left transition hover:bg-muted/50"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="line-clamp-1 text-sm font-medium">
                      {citation.title || "Untitled citation"}
                    </p>
                    <Badge variant="outline">#{index + 1}</Badge>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                    {citation.quote || citation.chunk_id}
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}

function SectionTitle({
  icon,
  title,
}: {
  icon: ReactNode;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2 text-sm font-semibold">
      <span className="text-muted-foreground">{icon}</span>
      {title}
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[72px_1fr] gap-2">
      <span>{label}</span>
      <span className="truncate font-mono text-foreground/80">{value}</span>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
      {label}
    </div>
  );
}

function formatRetrieval(config: Record<string, unknown>) {
  const mode = typeof config.mode === "string" ? config.mode : "n/a";
  const reranker = typeof config.reranker === "string" ? config.reranker : null;
  return reranker ? `${mode} / ${reranker}` : mode;
}
