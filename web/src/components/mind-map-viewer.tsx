"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge as FlowEdge,
  type Node as FlowNode,
} from "@xyflow/react";
import {
  Copy,
  Download,
  Network,
  RefreshCcw,
  Workflow,
} from "lucide-react";
import { toast } from "sonner";

import { generateReport, getReport, listReports } from "@/lib/api/client";
import type {
  CitationData,
  MindMapEdgeData,
  MindMapNodeData,
  MindMapPayload,
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

const DEFAULT_MIND_MAP_QUERY =
  "Create a 2D mind map from all indexed documents in this project.";

type SelectedMindMapElement =
  | { type: "node"; data: MindMapNodeData }
  | { type: "edge"; data: MindMapEdgeData }
  | null;

type MindMapNodeFlowData = {
  label: string;
  item: MindMapNodeData;
};

type MindMapEdgeFlowData = {
  item: MindMapEdgeData;
};

function asMindMapPayload(
  payload: StructuredReportPayload | null | undefined,
): MindMapPayload | null {
  if (!payload || typeof payload !== "object") return null;
  if (!("overview" in payload) || !("nodes" in payload) || !("edges" in payload)) {
    return null;
  }
  const nodes = (payload as { nodes?: unknown }).nodes;
  const edges = (payload as { edges?: unknown }).edges;
  if (!Array.isArray(nodes) || !Array.isArray(edges)) return null;
  return payload as MindMapPayload;
}

function getNodeColor(type: MindMapNodeData["type"]) {
  if (type === "central") return "#2563eb";
  if (type === "topic") return "#059669";
  if (type === "subtopic") return "#7c3aed";
  if (type === "source") return "#d97706";
  return "#0891b2";
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

export function buildMindMapFlow(payload: MindMapPayload): {
  nodes: Array<FlowNode<MindMapNodeFlowData>>;
  edges: Array<FlowEdge<MindMapEdgeFlowData>>;
} {
  const validIds = new Set(payload.nodes.map((node) => node.id));

  if (payload.nodes.length === 0) {
    return { nodes: [], edges: [] };
  }

  // Map each child to its parent ID
  const parentMap = new Map<string, string>();

  // First pass: node.parent_id
  payload.nodes.forEach((node) => {
    if (node.parent_id && validIds.has(node.parent_id) && node.parent_id !== node.id) {
      parentMap.set(node.id, node.parent_id);
    }
  });

  // Second pass: parent_child edges
  payload.edges.forEach((edge) => {
    if (edge.type === "parent_child" && validIds.has(edge.source) && validIds.has(edge.target)) {
      if (!parentMap.has(edge.target) && edge.source !== edge.target) {
        parentMap.set(edge.target, edge.source);
      }
    }
  });

  // Find the primary root node
  let primaryRoot = payload.nodes.find(
    (n) => n.type === "central" || Math.max(0, Number(n.level) || 0) === 0
  );

  if (!primaryRoot) {
    primaryRoot = payload.nodes.find((n) => !parentMap.has(n.id));
  }

  if (!primaryRoot && payload.nodes.length > 0) {
    primaryRoot = payload.nodes[0];
  }

  // Detect cycle utility
  function isReachable(startId: string, targetId: string): boolean {
    const checked = new Set<string>();
    let curr: string | undefined = startId;
    while (curr) {
      if (curr === targetId) return true;
      if (checked.has(curr)) break;
      checked.add(curr);
      curr = parentMap.get(curr);
    }
    return false;
  }

  // Group children under parent
  const adjacencyList = new Map<string, string[]>();

  payload.nodes.forEach((node) => {
    if (!primaryRoot || node.id === primaryRoot.id) return;

    let pId = parentMap.get(node.id);
    if (!pId || !validIds.has(pId) || isReachable(pId, node.id)) {
      pId = primaryRoot.id;
    }

    const list = adjacencyList.get(pId) || [];
    list.push(node.id);
    adjacencyList.set(pId, list);
  });

  // Sort children by original index in the payload list to maintain stability
  const nodeIndexMap = new Map<string, number>();
  payload.nodes.forEach((node, i) => {
    nodeIndexMap.set(node.id, i);
  });

  adjacencyList.forEach((children) => {
    children.sort((a, b) => (nodeIndexMap.get(a) || 0) - (nodeIndexMap.get(b) || 0));
  });

  // Calculate coordinates using radial branching tree layout
  const positions = new Map<string, { x: number; y: number; level: number }>();
  const visited = new Set<string>();

  function layoutSubtree(
    nodeId: string,
    angle: number,
    sectorWidth: number,
    depth: number
  ) {
    if (visited.has(nodeId)) return;
    visited.add(nodeId);

    const radius = depth * 240;
    const x = depth === 0 ? 0 : Math.cos(angle) * radius * 1.35;
    const y = depth === 0 ? 0 : Math.sin(angle) * radius;

    positions.set(nodeId, { x, y, level: depth });

    const children = adjacencyList.get(nodeId) || [];
    const M = children.length;
    if (M > 0) {
      if (depth === 0) {
        // Root's children partition the full 2 * PI circle
        children.forEach((childId, i) => {
          const childAngle = (i * 2 * Math.PI) / M;
          const childSector = (2 * Math.PI) / M;
          layoutSubtree(childId, childAngle, childSector, 1);
        });
      } else {
        // Nested children share their parent's sector with a spacing margin
        const activeSector = sectorWidth * 0.85;
        children.forEach((childId, i) => {
          let childAngle: number;
          if (M === 1) {
            childAngle = angle;
          } else {
            childAngle = angle - activeSector / 2 + (i + 0.5) * (activeSector / M);
          }
          const childSector = sectorWidth / M;
          layoutSubtree(childId, childAngle, childSector, depth + 1);
        });
      }
    }
  }

  if (primaryRoot) {
    layoutSubtree(primaryRoot.id, 0, 2 * Math.PI, 0);
  }

  // Final check to handle any disconnected nodes
  payload.nodes.forEach((node) => {
    if (!positions.has(node.id)) {
      positions.set(node.id, { x: 0, y: 0, level: 1 });
    }
  });

  const positionedNodes = payload.nodes.map((node, index) => {
    const pos = positions.get(node.id) || { x: 0, y: 0, level: 1 };
    const x = pos.x;
    const y = pos.y;
    const color = getNodeColor(node.type);
    const width = node.type === "central" ? 190 : 170;
    return {
      id: node.id,
      type: "default",
      position: { x: x - width / 2, y: y - 28 },
      data: {
        label: node.label,
        item: node,
      },
      style: {
        width,
        minHeight: 56,
        borderRadius: 8,
        border: `1px solid ${color}`,
        color,
        background: "var(--color-background)",
        boxShadow: "0 8px 24px rgba(15, 23, 42, 0.10)",
        fontSize: 13,
        fontWeight: node.type === "central" ? 700 : 600,
        padding: 10,
      },
      zIndex: node.type === "central" ? 2 : 1,
      draggable: true,
      selectable: true,
      ariaLabel: `Mind map node ${index + 1}: ${node.label}`,
    } satisfies FlowNode<MindMapNodeFlowData>;
  });

  const positionedEdges = payload.edges
    .filter((edge) => validIds.has(edge.source) && validIds.has(edge.target))
    .map((edge) => {
      const color = edge.type === "parent_child" ? "#64748b" : "#2563eb";
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.type.replace("_", " "),
        data: { item: edge },
        type: "default", // smooth bezier curve layout fits radial branches perfectly
        animated: edge.type === "supports",
        markerEnd: { type: MarkerType.ArrowClosed, color },
        style: {
          stroke: color,
          strokeWidth: edge.type === "parent_child" ? 1.6 : 2,
        },
        labelStyle: {
          fill: "var(--color-muted-foreground)",
          fontSize: 11,
          fontWeight: 500,
        },
      } satisfies FlowEdge<MindMapEdgeFlowData>;
    });

  return { nodes: positionedNodes, edges: positionedEdges };
}

function DetailPanel({
  selected,
  payload,
}: {
  selected: SelectedMindMapElement;
  payload: MindMapPayload;
}) {
  if (!selected) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
        Select a node or relationship to view source-grounded details.
      </div>
    );
  }

  if (selected.type === "node") {
    const node = selected.data;
    const connectedEdges = payload.edges.filter(
      (edge) => edge.source === node.id || edge.target === node.id,
    );
    return (
      <div className="flex h-full flex-col">
        <CardHeader className="border-b bg-muted/20">
          <CardTitle className="text-lg">{node.label}</CardTitle>
          <div className="flex flex-wrap gap-2">
            <Badge variant={node.type === "central" ? "default" : "secondary"}>
              {node.type}
            </Badge>
            <Badge variant="outline">Level {node.level}</Badge>
          </div>
        </CardHeader>
        <div className="flex-1 overflow-y-auto p-5">
          <div className="flex flex-col gap-5">
            <div>
              <p className="text-xs font-medium uppercase text-muted-foreground">
                Summary
              </p>
              <p className="mt-2 text-sm leading-6 text-foreground/90">
                {node.summary || "No summary is attached to this node."}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-muted-foreground">
                Connected Relationships
              </p>
              {connectedEdges.length ? (
                <div className="mt-2 flex flex-col gap-2">
                  {connectedEdges.map((edge) => (
                    <div
                      key={edge.id}
                      className="rounded-md border border-border bg-muted/20 p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{edge.type.replace("_", " ")}</Badge>
                        <span className="text-xs text-muted-foreground">
                          {edge.source} to {edge.target}
                        </span>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-muted-foreground">
                        {edge.description}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  No connected relationships.
                </p>
              )}
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-muted-foreground">
                Sources
              </p>
              <div className="mt-2">
                <CitationList citations={node.citations} />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const edge = selected.data;
  return (
    <div className="flex h-full flex-col">
      <CardHeader className="border-b bg-muted/20">
        <CardTitle className="text-lg">Relationship</CardTitle>
        <Badge variant="secondary" className="w-fit">
          {edge.type.replace("_", " ")}
        </Badge>
      </CardHeader>
      <div className="flex-1 overflow-y-auto p-5">
        <div className="flex flex-col gap-5">
          <div>
            <p className="text-xs font-medium uppercase text-muted-foreground">
              Nodes
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge variant="outline">{edge.source}</Badge>
              <span className="text-xs text-muted-foreground">to</span>
              <Badge variant="outline">{edge.target}</Badge>
            </div>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-muted-foreground">
              Description
            </p>
            <p className="mt-2 text-sm leading-6 text-foreground/90">
              {edge.description}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-muted-foreground">
              Sources
            </p>
            <div className="mt-2">
              <CitationList citations={edge.citations} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function MindMapViewer() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [activeProjectRole, setActiveProjectRole] =
    useState<ProjectRole | null>(null);
  const [provider, setProvider] = useState("openai");
  const [query, setQuery] = useState(DEFAULT_MIND_MAP_QUERY);
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [report, setReport] = useState<ReportResult | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [selected, setSelected] = useState<SelectedMindMapElement>(null);

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
    () => asMindMapPayload(report?.structured_payload),
    [report],
  );
  const flow = useMemo(
    () => (payload ? buildMindMapFlow(payload) : { nodes: [], edges: [] }),
    [payload],
  );

  useEffect(() => {
    if (!activeProjectId) return;
    void loadHistory();
  }, [activeProjectId]);

  useEffect(() => {
    setSelected(null);
  }, [report?.report_id]);

  async function loadHistory() {
    if (!activeProjectId) return;
    setLoadingHistory(true);
    try {
      const response = await listReports(activeProjectId);
      setHistory(response.data.items.filter((item) => item.type === "mind_map"));
    } catch (error) {
      console.error("Failed to load mind map history", error);
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
      toast.error("Generating mind maps requires editor role or higher.");
      return;
    }
    setBusy(true);
    setReport(null);
    const toastId = toast.loading(`Generating mind map with ${provider}...`);
    try {
      const response = await generateReport({
        projectId: activeProjectId,
        query: query || DEFAULT_MIND_MAP_QUERY,
        type: "mind_map",
        provider,
      });
      setReport(response.data);
      toast.success("Mind map generated.", { id: toastId });
      void loadHistory();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to generate mind map.",
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
      toast.success("Mind map loaded.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to load mind map.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCopyJson() {
    if (!payload) return;
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    toast.success("Mind map JSON copied.");
  }

  async function handleCopyMarkdown() {
    if (!report) return;
    await navigator.clipboard.writeText(report.content);
    toast.success("Mind map markdown copied.");
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
        .replace(/^-|-$/g, "") || "mind-map"
    );
  }

  return (
    <PageWrapper
      title="Mind Map"
      description={
        activeProjectName
          ? `Generate a 2D source-grounded mind map for: ${activeProjectName}`
          : "Select a project to generate a mind map from indexed sources."
      }
    >
      {!canMutateProject && activeProjectId ? (
        <div className="rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          You have viewer access for this project. Mind map generation is
          disabled.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Workflow className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-base">Generate Mind Map</CardTitle>
              </div>
              <CardDescription>
                Uses all indexed chunks in the active project.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="mind-map-provider">Writer Model</Label>
                  <Select
                    value={provider}
                    onValueChange={setProvider}
                    disabled={busy || !canMutateProject}
                  >
                    <SelectTrigger id="mind-map-provider">
                      <SelectValue placeholder="Select provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="gemini">Gemini</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="mind-map-query">Prompt</Label>
                  <Textarea
                    id="mind-map-query"
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
                  {busy ? <Spinner size="sm" /> : <Workflow className="h-4 w-4" />}
                  {busy ? "Generating..." : "Generate Mind Map"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <div>
                <CardTitle className="text-base">History</CardTitle>
                <CardDescription>Previous mind maps.</CardDescription>
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
                  No mind maps yet.
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
                    Mind Map
                  </Badge>
                </div>
                <CardDescription>
                  {payload
                    ? `${payload.nodes.length} nodes and ${payload.edges.length} relationships generated from indexed evidence.`
                    : "Structured mind map payload is unavailable."}
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
                <p>Reading indexed chunks and generating a mind map...</p>
              </div>
            </Card>
          ) : payload ? (
            <div className="grid min-h-[720px] overflow-hidden rounded-lg border border-border bg-background xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="relative min-h-[520px]">
                <div className="absolute left-4 top-4 z-10 max-w-sm rounded-md border border-border bg-background/90 p-3 shadow-sm backdrop-blur">
                  <div className="flex items-center gap-2">
                    <Network className="h-4 w-4 text-primary" />
                    <p className="text-sm font-semibold">{payload.central_topic}</p>
                  </div>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
                    {payload.overview}
                  </p>
                </div>
                <ReactFlow
                  nodes={flow.nodes}
                  edges={flow.edges}
                  fitView
                  minZoom={0.2}
                  maxZoom={1.8}
                  onNodeClick={(_, node) =>
                    setSelected({
                      type: "node",
                      data: node.data.item,
                    })
                  }
                  onEdgeClick={(_, edge) =>
                    edge.data?.item
                      ? setSelected({ type: "edge", data: edge.data.item })
                      : null
                  }
                  onPaneClick={() => setSelected(null)}
                >
                  <Background />
                  <Controls />
                  <MiniMap
                    pannable
                    zoomable
                    nodeColor={(node) =>
                      getNodeColor((node.data as MindMapNodeFlowData).item.type)
                    }
                  />
                </ReactFlow>
              </div>
              <div className="border-t border-border bg-background xl:border-l xl:border-t-0">
                <DetailPanel selected={selected} payload={payload} />
              </div>
            </div>
          ) : (
            <Card className="flex h-[320px] items-center justify-center border-dashed">
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <Workflow className="h-8 w-8 opacity-20" />
                <p>Generate a 2D mind map from indexed source material.</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
