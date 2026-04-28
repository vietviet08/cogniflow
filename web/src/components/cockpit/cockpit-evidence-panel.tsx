"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, ExternalLink, X, ChevronLeft, ChevronRight, BookOpen, Layers } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import { getSourceArtifactUrl } from "@/lib/api/client";
import { getStoredAuthToken } from "@/lib/auth-session";
import type { CitationData } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

interface CockpitEvidencePanelProps {
  citation: CitationData | null;
  onClose: () => void;
}

function buildHighlightTargets(quote?: string): string[] {
  if (!quote) return [];
  const compact = quote.replace(/\u2026/g, " ").replace(/\s+/g, " ").trim();
  if (!compact) return [];
  const fragments = compact
    .split(/[.!?]\s+/)
    .map((f) => f.trim())
    .filter((f) => f.length >= 12);
  const candidates = fragments.length > 0 ? fragments : [compact];
  return Array.from(new Set(candidates.map((f) => f.replace(/\s+/g, " ").trim().toLowerCase()).filter(Boolean))).slice(0, 6);
}

function applyHighlights(
  container: HTMLDivElement | null,
  targets: string[],
  key: string,
  shouldScroll: boolean
) {
  const layer = container?.querySelector(".react-pdf__Page__textContent");
  if (!(layer instanceof HTMLDivElement)) return;
  if (layer.dataset.evidenceKey === key) return;

  const spans = Array.from(layer.querySelectorAll("span"));
  let first: HTMLSpanElement | null = null;

  for (const span of spans) {
    if (!(span instanceof HTMLSpanElement)) continue;
    if (span.dataset.evidenceHL === "true") {
      span.dataset.evidenceHL = "false";
      span.style.backgroundColor = "";
      span.style.borderRadius = "";
      span.style.boxShadow = "";
    }
    const text = (span.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
    if (!text || text.length < 8) continue;
    const match = targets.some((t) => t.includes(text) || text.includes(t));
    if (!match) continue;
    span.dataset.evidenceHL = "true";
    span.style.backgroundColor = "rgba(108,99,255,0.35)";
    span.style.borderRadius = "0.2rem";
    span.style.boxShadow = "0 0 0 1px rgba(108,99,255,0.4)";
    if (!first) first = span;
  }

  layer.dataset.evidenceKey = key;
  if (first && shouldScroll) first.scrollIntoView({ block: "center", behavior: "auto" });
}

function useAuthenticatedPdfUrl(sourceId: string | undefined): {
  blobUrl: string | null;
  error: string | null;
} {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sourceId) return;
    let revoked = false;
    let objectUrl: string | null = null;

    async function load() {
      const token = getStoredAuthToken();
      const url = getSourceArtifactUrl(sourceId!);
      try {
        const res = await fetch(url, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) {
          setError(`Failed to load PDF (${res.status})`);
          return;
        }
        const blob = await res.blob();
        if (revoked) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
        setError(null);
      } catch (e) {
        if (!revoked) setError("Network error loading PDF");
      }
    }

    setBlobUrl(null);
    setError(null);
    load();

    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [sourceId]);

  return { blobUrl, error };
}

export function CockpitEvidencePanel({ citation, onClose }: CockpitEvidencePanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pageWrapperRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(400);
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);

  const targets = citation?.quote ? buildHighlightTargets(citation.quote) : [];
  const hlKey = `${citation?.chunk_id || citation?.citation_id || ""}:${pageNumber}:${targets.join("|")}`;

  const isPdf = citation?.source_type === "file" && Boolean(citation?.source_id);
  const { blobUrl: artifactUrl, error: pdfError } = useAuthenticatedPdfUrl(
    isPdf ? citation?.source_id : undefined,
  );

  useEffect(() => {
    if (citation?.page_number) setPageNumber(citation.page_number);
  }, [citation]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setContainerWidth(Math.floor(w));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const id = window.requestAnimationFrame(() => {
      applyHighlights(pageWrapperRef.current, targets, hlKey, false);
    });
    return () => window.cancelAnimationFrame(id);
  }, [hlKey]);

  if (!citation) {
    return (
      <div className="flex h-full flex-col bg-slate-50 dark:bg-[#0A0E1A] border-l border-slate-200 dark:border-white/5">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-white/5 shrink-0">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#00d8ff]/10 border border-[#00d8ff]/20">
            <Layers className="h-3.5 w-3.5 text-[#00d8ff]" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-800 dark:text-white/90 leading-none">Evidence Panel</p>
            <p className="text-[10px] text-slate-400 dark:text-white/30 mt-0.5">Citations appear here</p>
          </div>
        </div>

        {/* Empty state */}
        <div className="flex-1 flex flex-col items-center justify-center text-center px-6 gap-4">
          <div className="relative">
            <div className="absolute inset-0 rounded-full bg-[#00d8ff]/10 blur-xl" />
            <div className="relative h-12 w-12 rounded-2xl bg-[#00d8ff]/10 border border-[#00d8ff]/20 flex items-center justify-center">
              <BookOpen className="h-6 w-6 text-[#00d8ff]/50" />
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 dark:text-white/50">No evidence selected</p>
            <p className="text-[11px] text-slate-400 dark:text-white/25 mt-1 leading-relaxed">
              Click a citation tag in the chat to view the source document with highlights
            </p>
          </div>

          {/* Animated placeholder lines */}
          <div className="w-full space-y-2 opacity-20 mt-2">
            {[90, 70, 85, 60, 75].map((w, i) => (
              <div
                key={i}
                className="h-2 rounded-full bg-slate-300 dark:bg-white/20"
                style={{
                  width: `${w}%`,
                  animation: `cockpit-pulse 2s ${i * 0.3}s infinite ease-in-out`,
                }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }


  return (
    <div className="flex h-full flex-col bg-slate-50 dark:bg-[#0A0E1A] border-l border-slate-200 dark:border-white/5">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-white/5 shrink-0">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#00d8ff]/10 border border-[#00d8ff]/20 shrink-0">
          <FileText className="h-3.5 w-3.5 text-[#00d8ff]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-slate-800 dark:text-white/90 leading-none truncate">
            {citation.title || "Evidence Source"}
          </p>
          <div className="flex items-center gap-1.5 mt-0.5">
            {citation.page_number && (
              <Badge
                variant="outline"
                className="text-[9px] border-[#00d8ff]/30 text-[#00d8ff]/70 bg-[#00d8ff]/5 py-0 px-1.5 h-4"
              >
                p.{citation.page_number}
              </Badge>
            )}
            {citation.chunk_id && (
              <span className="font-mono text-[9px] text-slate-400 dark:text-white/25">
                {citation.chunk_id.slice(0, 6)}…
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {citation.url && (
            <a
              href={citation.url}
              target="_blank"
              rel="noreferrer"
              className="flex h-7 w-7 items-center justify-center rounded-md text-slate-400 dark:text-white/40 hover:text-slate-700 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-white/10 transition-colors"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-md text-slate-400 dark:text-white/40 hover:text-slate-700 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-white/10 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Quote highlight strip */}
      {citation.quote && (
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-white/5 shrink-0 bg-slate-100 dark:bg-[#6c63ff]/5">
          <p className="text-[10px] text-[#6c63ff]/70 font-medium mb-1 uppercase tracking-wide">
            Highlighted Evidence
          </p>
          <p className="text-xs text-slate-700 dark:text-white/60 leading-relaxed line-clamp-3">
            "{citation.quote}"
          </p>
        </div>
      )}

      {/* PDF navigation */}
      {isPdf && numPages > 1 && (
        <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-white/5 shrink-0">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            disabled={pageNumber <= 1}
            className="h-7 gap-1 text-xs text-slate-500 dark:text-white/50 hover:text-slate-800 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-white/10"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Prev
          </Button>
          <span className="text-xs text-slate-400 dark:text-white/40">
            {pageNumber} / {numPages}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setPageNumber((p) => Math.min(numPages, p + 1))}
            disabled={pageNumber >= numPages}
            className="h-7 gap-1 text-xs text-slate-500 dark:text-white/50 hover:text-slate-800 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-white/10"
          >
            Next
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Content */}
      <div ref={containerRef} className="flex-1 overflow-auto min-h-0 p-3">
        {isPdf ? (
          <>
            {pdfError && (
              <div className="text-xs text-red-400/70 p-4 text-center">
                {pdfError}
              </div>
            )}
            <Document
              file={artifactUrl ?? ""}
              loading={
                <div className="flex items-center justify-center h-32 text-xs text-slate-500 dark:text-white/30">
                  Loading document…
                </div>
              }
              error={
                <div className="text-xs text-red-400/70 p-4 text-center">
                  Failed to render artifact.
                </div>
              }
              onLoadSuccess={({ numPages: n }) => {
              setNumPages(n);
              setPageNumber((cur) => Math.min(Math.max(cur, 1), n));
            }}
          >
            <div ref={pageWrapperRef}>
              <Page
                pageNumber={pageNumber}
                width={Math.max(containerWidth - 24, 200)}
                renderAnnotationLayer={false}
                renderTextLayer
                onRenderTextLayerSuccess={() => {
                  applyHighlights(pageWrapperRef.current, targets, hlKey, true);
                }}
              />
            </div>
          </Document>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
            <ExternalLink className="h-8 w-8 text-slate-300 dark:text-white/20" />
            <p className="text-xs text-slate-500 dark:text-white/40">External source</p>
            {citation.url && (
              <a
                href={citation.url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-[#00d8ff]/70 hover:text-[#00d8ff] underline break-all"
              >
                {citation.url}
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
