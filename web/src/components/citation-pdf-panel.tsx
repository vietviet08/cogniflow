"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { ChevronLeft, ChevronRight, ExternalLink, GripVertical, X } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";

import { getSourceArtifactUrl } from "@/lib/api/client";
import type { CitationData } from "@/lib/api/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function CitationPdfPanel({
  citation,
  width,
  onWidthChange,
  onClose,
}: {
  citation: CitationData;
  width: number;
  onWidthChange: (width: number) => void;
  onClose: () => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pageWrapperRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState(720);
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(citation.page_number || 1);
  const [textLayerVersion, setTextLayerVersion] = useState(0);

  const highlightTargets = useMemo(
    () => buildHighlightTargets(citation.quote),
    [citation.quote],
  );

  useEffect(() => {
    setPageNumber(citation.page_number || 1);
  }, [citation]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) {
        setContainerWidth(Math.floor(width));
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const layer = pageWrapperRef.current?.querySelector(
      ".react-pdf__Page__textContent",
    );
    if (!layer) {
      return;
    }

    const spans = Array.from(layer.querySelectorAll("span"));
    let firstHighlighted: HTMLSpanElement | null = null;

    for (const span of spans) {
      if (!(span instanceof HTMLSpanElement)) {
        continue;
      }
      if (span.dataset.notemeshHighlight === "true") {
        span.dataset.notemeshHighlight = "false";
        span.style.backgroundColor = "";
        span.style.borderRadius = "";
        span.style.boxShadow = "";
      }
      const text = normalizeText(span.textContent || "");
      if (!text || text.length < 8) {
        continue;
      }
      const isMatch = highlightTargets.some(
        (target) => target.includes(text) || text.includes(target),
      );
      if (!isMatch) {
        continue;
      }
      span.dataset.notemeshHighlight = "true";
      span.style.backgroundColor = "rgba(250, 204, 21, 0.45)";
      span.style.borderRadius = "0.2rem";
      span.style.boxShadow = "0 0 0 1px rgba(202, 138, 4, 0.25)";
      if (!firstHighlighted) {
        firstHighlighted = span;
      }
    }

    if (firstHighlighted) {
      firstHighlighted.scrollIntoView({
        block: "center",
        behavior: "smooth",
      });
    }
  }, [highlightTargets, pageNumber, textLayerVersion]);

  const artifactUrl = citation.source_id
    ? getSourceArtifactUrl(citation.source_id)
    : "";

  function handleResizeStart(event: ReactPointerEvent<HTMLDivElement>) {
    if (typeof window === "undefined" || window.innerWidth < 768) {
      return;
    }

    event.preventDefault();
    const pointerId = event.pointerId;
    event.currentTarget.setPointerCapture(pointerId);

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const viewportWidth = window.innerWidth;
      const nextWidth = clampPanelWidth(viewportWidth - moveEvent.clientX, viewportWidth);
      onWidthChange(nextWidth);
    };

    const stopResize = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopResize);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResize, { once: true });
  }

  return (
    <aside
      className="fixed bottom-0 right-0 top-0 z-40 flex w-full flex-col border-l border-border bg-background shadow-2xl md:w-[var(--citation-panel-width)]"
      style={{ "--citation-panel-width": `${width}px` } as CSSProperties}
    >
      <div
        role="separator"
        aria-label="Resize PDF preview"
        aria-orientation="vertical"
        className="absolute left-0 top-0 hidden h-full w-3 -translate-x-1/2 cursor-col-resize items-center justify-center md:flex"
        onPointerDown={handleResizeStart}
      >
        <div className="flex h-16 w-2 items-center justify-center rounded-full border border-border bg-background/95 shadow-sm">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      </div>
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">
            {citation.title || "PDF Viewer"}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant="outline">
              Page {citation.page_number || pageNumber || 1}
            </Badge>
            {citation.chunk_id ? (
              <Badge variant="secondary" className="font-mono text-[10px]">
                {citation.chunk_id.slice(0, 8)}
              </Badge>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {citation.url ? (
            <a
              href={citation.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center justify-center rounded-md border border-input px-3 text-sm shadow-sm transition-colors hover:bg-accent"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          ) : null}
          <Button type="button" variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex items-center justify-between border-b border-border px-4 py-2 text-sm text-muted-foreground">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setPageNumber((current) => Math.max(1, current - 1))}
          disabled={pageNumber <= 1}
          className="gap-1"
        >
          <ChevronLeft className="h-4 w-4" />
          Prev
        </Button>
        <span>
          Page {pageNumber}
          {numPages ? ` / ${numPages}` : ""}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() =>
            setPageNumber((current) =>
              numPages ? Math.min(numPages, current + 1) : current + 1,
            )
          }
          disabled={Boolean(numPages) && pageNumber >= numPages}
          className="gap-1"
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <div ref={containerRef} className="min-h-0 flex-1 overflow-auto bg-muted/20 p-4">
        <Document
          file={artifactUrl}
          loading={<div className="text-sm text-muted-foreground">Loading PDF...</div>}
          error={
            <div className="text-sm text-destructive">
              Failed to load this PDF artifact. Reprocess the source if needed.
            </div>
          }
          onLoadSuccess={({ numPages: loadedPages }) => {
            setNumPages(loadedPages);
            setPageNumber((current) => Math.min(Math.max(current, 1), loadedPages));
          }}
        >
          <div ref={pageWrapperRef}>
            <Page
              pageNumber={pageNumber}
              width={Math.max(containerWidth - 32, 280)}
              renderAnnotationLayer={false}
              renderTextLayer
              onRenderTextLayerSuccess={() =>
                setTextLayerVersion((current) => current + 1)
              }
            />
          </div>
        </Document>
        {citation.quote ? (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-950">
            <p className="font-medium">Highlighted evidence</p>
            <p className="mt-1 leading-5">{citation.quote}</p>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function buildHighlightTargets(quote?: string) {
  if (!quote) {
    return [];
  }

  const compact = quote.replace(/\u2026/g, " ").replace(/\s+/g, " ").trim();
  if (!compact) {
    return [];
  }

  const fragments = compact
    .split(/[.!?]\s+/)
    .map((fragment) => fragment.trim())
    .filter((fragment) => fragment.length >= 12);

  const candidates = fragments.length > 0 ? fragments : [compact];
  return Array.from(
    new Set(candidates.map((fragment) => normalizeText(fragment)).filter(Boolean)),
  ).slice(0, 6);
}

function normalizeText(value: string) {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

function clampPanelWidth(width: number, viewportWidth: number) {
  const minWidth = 380;
  const maxWidth = Math.max(520, Math.floor(viewportWidth * 0.72));
  return Math.min(Math.max(Math.floor(width), minWidth), maxWidth);
}
