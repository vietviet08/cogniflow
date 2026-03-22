"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ChevronLeft, ChevronRight, ExternalLink, X } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";

import { getSourceArtifactUrl } from "@/lib/api/client";
import type { CitationData } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

type CitationViewerContextValue = {
  activeCitation: CitationData | null;
  openCitation: (citation: CitationData) => void;
  closeCitation: () => void;
};

const CitationViewerContext = createContext<CitationViewerContextValue | null>(
  null,
);

function canOpenPdfCitation(citation: CitationData) {
  return citation.source_type === "file" && Boolean(citation.source_id);
}

function CitationViewerPanel({
  citation,
  onClose,
}: {
  citation: CitationData;
  onClose: () => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState(720);
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(citation.page_number || 1);

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

  const artifactUrl = citation.source_id
    ? getSourceArtifactUrl(citation.source_id)
    : "";

  return (
    <aside
      className={
        "fixed bottom-0 right-0 top-0 z-40 flex w-full flex-col border-l border-border bg-background shadow-2xl " +
        "md:w-[calc((100vw-15rem)/2)]"
      }
    >
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
              className={
                "inline-flex h-9 items-center justify-center rounded-md border border-input px-3 text-sm shadow-sm transition-colors hover:bg-accent"
              }
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
          <Page
            pageNumber={pageNumber}
            width={Math.max(containerWidth - 32, 280)}
            renderAnnotationLayer={false}
            renderTextLayer={false}
          />
        </Document>
      </div>
    </aside>
  );
}

export function CitationViewerProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [activeCitation, setActiveCitation] = useState<CitationData | null>(null);

  const value = useMemo(
    () => ({
      activeCitation,
      openCitation: (citation: CitationData) => setActiveCitation(citation),
      closeCitation: () => setActiveCitation(null),
    }),
    [activeCitation],
  );

  return (
    <CitationViewerContext.Provider value={value}>
      <div
        className={cn(
          "min-h-full transition-[padding] duration-200",
          activeCitation ? "md:pr-[calc((100vw-15rem)/2)]" : "",
        )}
      >
        {children}
      </div>
      {activeCitation && canOpenPdfCitation(activeCitation) ? (
        <CitationViewerPanel
          citation={activeCitation}
          onClose={() => setActiveCitation(null)}
        />
      ) : null}
    </CitationViewerContext.Provider>
  );
}

export function useCitationViewer() {
  const context = useContext(CitationViewerContext);
  if (!context) {
    throw new Error("useCitationViewer must be used within CitationViewerProvider");
  }
  return context;
}
