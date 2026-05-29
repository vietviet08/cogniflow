"use client";

import { useCitationViewer } from "@/components/citation-viewer-provider";
import { Badge } from "@/components/ui/badge";
import { CardHeader, CardTitle } from "@/components/ui/card";
import type {
  CitationData,
  ConflictMeshPayload,
  MeshEdgeData,
  MeshNodeData,
} from "@/lib/api/types";

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
    <div className="space-y-3 mt-2">
      {citations.map((citation, index) => {
        const label =
          citation.title ||
          citation.chunk_id ||
          citation.source_id ||
          `Source ${index + 1}`;

        return (
          <div
            key={`${citation.chunk_id}-${index}`}
            className="rounded-md border border-border bg-background p-3"
          >
            <button
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
              <Badge
                variant="outline"
                className="cursor-pointer hover:bg-muted text-xs"
              >
                {label}
              {citation.page_number ? ` · p.${citation.page_number}` : ""}
              </Badge>
            </button>
            {citation.quote ? (
              <p className="mt-2 text-xs leading-relaxed text-foreground/80">
                {citation.quote}
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

interface NodeDetailPanelProps {
  element:
    | { type: "node"; data: MeshNodeData }
    | { type: "edge"; data: MeshEdgeData }
    | null;
  payload: ConflictMeshPayload;
}

type ConnectedRelationship = {
  edge: MeshEdgeData;
  direction: "outgoing" | "incoming";
  relatedNode: MeshNodeData | null;
};

function getEndpointId(endpoint: unknown) {
  if (typeof endpoint === "string") {
    return endpoint;
  }

  const maybeNode = endpoint as { id?: string } | undefined;
  return maybeNode?.id ?? "";
}

function getConnectedRelationships(
  node: MeshNodeData,
  payload: ConflictMeshPayload,
): ConnectedRelationship[] {
  return (payload.edges || [])
    .map((edge) => {
      const sourceId = getEndpointId(edge.source);
      const targetId = getEndpointId(edge.target);
      if (sourceId !== node.id && targetId !== node.id) {
        return null;
      }

      const relatedNodeId = sourceId === node.id ? targetId : sourceId;
      return {
        edge,
        direction: sourceId === node.id ? "outgoing" : "incoming",
        relatedNode:
          (payload.nodes || []).find((candidate) => candidate.id === relatedNodeId) ||
          null,
      } satisfies ConnectedRelationship;
    })
    .filter((item): item is ConnectedRelationship => item !== null);
}

function getNodeCitations(
  node: MeshNodeData,
  payload: ConflictMeshPayload,
  relationships: ConnectedRelationship[],
) {
  const sourceId = node.id.startsWith("source-")
    ? node.id.replace(/^source-/, "")
    : null;

  const citations = [
    ...(node.citations || []),
    ...relationships.flatMap((item) => item.edge.citations || []),
    ...(sourceId
      ? (payload.edges || []).flatMap((edge) =>
          (edge.citations || []).filter(
            (citation) => citation.source_id === sourceId,
          ),
        )
      : []),
  ];

  const seen = new Set<string>();
  return citations.filter((citation, index) => {
    const key =
      citation.citation_id ||
      citation.chunk_id ||
      `${citation.source_id}-${citation.page_number ?? "unknown"}-${index}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function getEdgeEndpointLabel(
  payload: ConflictMeshPayload,
  endpoint: unknown,
) {
  const endpointId = getEndpointId(endpoint);
  const node = (payload.nodes || []).find((candidate) => candidate.id === endpointId);
  return node?.label || endpointId || "Unknown";
}

export function NodeDetailPanel({ element, payload }: NodeDetailPanelProps) {
  if (!element) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground p-8 text-center text-sm">
        Select a node or edge to view details.
      </div>
    );
  }

  if (element.type === "node") {
    const { data } = element;
    const relationships = getConnectedRelationships(data, payload);
    const citations = getNodeCitations(data, payload, relationships);
    const metadataEntries = data.metadata
      ? Object.entries(data.metadata).filter(([, value]) => value != null)
      : [];

    return (
      <div className="flex flex-col h-full">
        <CardHeader className="pb-3 border-b bg-muted/20">
          <CardTitle className="text-xl font-bold text-foreground">
            {data.label}
          </CardTitle>
          <Badge className="w-fit mt-1 shadow-sm" variant="secondary">
            {data.type}
          </Badge>
        </CardHeader>
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="space-y-6">
            <div>
              <h4 className="font-medium text-sm mb-2 text-muted-foreground">
                Node Details
              </h4>
              <dl className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-md bg-muted/30 px-3 py-2">
                  <dt className="text-muted-foreground">Relationships</dt>
                  <dd className="mt-1 font-medium text-foreground">
                    {relationships.length}
                  </dd>
                </div>
                <div className="rounded-md bg-muted/30 px-3 py-2">
                  <dt className="text-muted-foreground">Evidence Items</dt>
                  <dd className="mt-1 font-medium text-foreground">
                    {citations.length}
                  </dd>
                </div>
              </dl>
              <p className="mt-2 break-all text-[11px] text-muted-foreground">
                {data.id}
              </p>
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2 text-muted-foreground">
                Summary
              </h4>
              <p className="text-sm text-foreground/90 leading-relaxed border-l-2 border-primary/20 pl-4 py-1">
                {data.description ||
                  data.summary ||
                  (relationships.length > 0
                    ? `${data.label} appears in ${relationships.length} relationship${relationships.length === 1 ? "" : "s"} in this mesh.`
                    : "No relationship details are attached to this node yet.")}
              </p>
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2 text-muted-foreground">
                Connected Relationships
              </h4>
              {relationships.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No connected relationships found.
                </p>
              ) : (
                <div className="space-y-3">
                  {relationships.map(({ edge, direction, relatedNode }) => (
                    <div
                      key={edge.id}
                      className="rounded-md border border-border bg-muted/20 p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="text-[10px]">
                          {direction === "outgoing" ? "to" : "from"}
                        </Badge>
                        <span className="text-sm font-medium">
                          {relatedNode?.label || "Unknown node"}
                        </span>
                        <Badge variant="secondary" className="text-[10px]">
                          {edge.type.replace("_", " ")}
                        </Badge>
                      </div>
                      {edge.description ? (
                        <p className="mt-2 text-xs leading-relaxed text-foreground/80">
                          {edge.description}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2 text-muted-foreground">
                Evidence
              </h4>
              <CitationList citations={citations} />
            </div>

            {metadataEntries.length > 0 ? (
              <div>
                <h4 className="font-medium text-sm mb-2 text-muted-foreground">
                  Metadata
                </h4>
                <dl className="space-y-2 text-xs">
                  {metadataEntries.map(([key, value]) => (
                    <div key={key} className="rounded-md bg-muted/30 px-3 py-2">
                      <dt className="font-medium text-foreground">{key}</dt>
                      <dd className="mt-1 text-muted-foreground break-words">
                        {typeof value === "object"
                          ? JSON.stringify(value)
                          : String(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  const { data } = element;
  const isContradiction = data.type === "contradicts";

  return (
    <div className="flex flex-col h-full">
      <CardHeader className="pb-3 border-b bg-muted/20">
        <CardTitle className="text-xl font-bold text-foreground">
          Relationship
        </CardTitle>
        <Badge
          className="w-fit mt-1 shadow-sm"
          variant={isContradiction ? "destructive" : "secondary"}
        >
          {data.type.replace("_", " ")}
        </Badge>
      </CardHeader>
      <div className="flex-1 p-6 overflow-y-auto">
        <div className="space-y-6">
          <div>
            <h4 className="font-medium text-sm mb-2 text-muted-foreground">
              Connected Nodes
            </h4>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">
                {getEdgeEndpointLabel(payload, data.source)}
              </Badge>
              <span className="text-xs text-muted-foreground">to</span>
              <Badge variant="outline">
                {getEdgeEndpointLabel(payload, data.target)}
              </Badge>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-sm mb-2 text-muted-foreground">
              Description
            </h4>
            <p className="text-sm text-foreground/90 leading-relaxed border-l-2 border-primary/20 pl-4 py-1">
              {data.description}
            </p>
          </div>

          <div>
            <h4 className="font-medium text-sm mb-2 text-muted-foreground">
              Evidence
            </h4>
            <CitationList citations={data.citations || []} />
          </div>
        </div>
      </div>
    </div>
  );
}
