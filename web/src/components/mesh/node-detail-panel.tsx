"use client";

import { useCitationViewer } from "@/components/citation-viewer-provider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CitationData, MeshEdgeData, MeshNodeData } from "@/lib/api/types";

function CitationList({ citations }: { citations: CitationData[] }) {
    const { openCitation } = useCitationViewer();

    if (!citations || citations.length === 0) {
        return (
            <p className="text-xs text-muted-foreground mt-2">
                No source links attached.
            </p>
        );
    }

    return (
        <div className="flex flex-wrap gap-2 mt-2">
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
                        onClick={() => {
                            if (citation.source_type === "file" && citation.source_id) {
                                openCitation(citation);
                            } else if (citation.url) {
                                window.open(citation.url, "_blank", "noopener,noreferrer");
                            }
                        }}
                        className="inline-flex"
                    >
                        <Badge variant="outline" className="cursor-pointer hover:bg-muted text-xs">
                            {label}
                            {citation.page_number ? ` · p.${citation.page_number}` : ""}
                        </Badge>
                    </button>
                );
            })}
        </div>
    );
}

interface NodeDetailPanelProps {
    element: { type: "node"; data: MeshNodeData } | { type: "edge"; data: MeshEdgeData } | null;
}

export function NodeDetailPanel({ element }: NodeDetailPanelProps) {
    if (!element) {
        return (
            <div className="flex items-center justify-center h-full text-muted-foreground p-8 text-center text-sm">
                Select a node or edge to view details.
            </div>
        );
    }

    if (element.type === "node") {
        const { data } = element;
        return (
            <div className="flex flex-col h-full">
                <CardHeader className="pb-3 border-b">
                    <CardTitle className="text-lg">Concept: {data.label}</CardTitle>
                    <Badge className="w-fit" variant="secondary">{data.type}</Badge>
                </CardHeader>
                <div className="flex-1 p-6 overflow-y-auto">
                    <div className="space-y-4">
                        <p className="text-sm text-foreground/80">
                            Select an edge connected to this node to see how it relates or conflicts with other concepts in the documents.
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    const { data } = element;
    const isContradiction = data.type === "contradicts";

    return (
        <div className="flex flex-col h-full">
            <CardHeader className="pb-3 border-b">
                <CardTitle className="text-lg">Relationship</CardTitle>
                <Badge className="w-fit" variant={isContradiction ? "destructive" : "secondary"}>
                    {data.type.replace('_', ' ')}
                </Badge>
            </CardHeader>
            <div className="flex-1 p-6 overflow-y-auto">
                <div className="space-y-6">
                    <div>
                        <h4 className="font-medium text-sm mb-2 text-muted-foreground">Description</h4>
                        <p className="text-sm text-foreground/90 leading-relaxed border-l-2 border-primary/20 pl-4 py-1">
                            {data.description}
                        </p>
                    </div>
                    
                    <div>
                        <h4 className="font-medium text-sm mb-2 text-muted-foreground">Evidence</h4>
                        <CitationList citations={data.citations || []} />
                    </div>
                </div>
            </div>
        </div>
    );
}
