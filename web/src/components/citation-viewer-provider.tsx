"use client";

import { createContext, useContext, useMemo, useState, type CSSProperties } from "react";
import dynamic from "next/dynamic";

import type { CitationData } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const CitationPdfPanel = dynamic(
  () =>
    import("@/components/citation-pdf-panel").then(
      (module) => module.CitationPdfPanel,
    ),
  {
    ssr: false,
  },
);

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

export function CitationViewerProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [activeCitation, setActiveCitation] = useState<CitationData | null>(null);
  const [panelWidth, setPanelWidth] = useState(640);

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
          activeCitation ? "md:pr-[var(--citation-panel-width)]" : "",
        )}
        style={
          activeCitation
            ? ({ "--citation-panel-width": `${panelWidth}px` } as CSSProperties)
            : undefined
        }
      >
        {children}
      </div>
      {activeCitation && canOpenPdfCitation(activeCitation) ? (
        <CitationPdfPanel
          citation={activeCitation}
          width={panelWidth}
          onWidthChange={setPanelWidth}
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
