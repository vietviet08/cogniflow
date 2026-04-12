"use client";

import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, RefreshCcw, Network } from "lucide-react";

import { generateReport, getReport, listReports } from "@/lib/api/client";
import type {
    ConflictMeshPayload,
    ProjectRole,
    ReportListItem,
    ReportResult,
} from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject } from "@/lib/project-store";

import { PageWrapper } from "@/components/layout/page-wrapper";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import MeshGraph from "./mesh-graph";

export function MeshViewer() {
    const [activeProjectId, setActiveProjectId] = useState("");
    const [activeProjectName, setActiveProjectName] = useState("");
    const [activeProjectRole, setActiveProjectRole] = useState<ProjectRole | null>(null);
    const [query, setQuery] = useState("");
    const [provider, setProvider] = useState("openai");

    const [busy, setBusy] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(false);

    const [report, setReport] = useState<ReportResult | null>(null);
    const [history, setHistory] = useState<ReportListItem[]>([]);

    useEffect(() => {
        const active = getActiveProject();
        if (active) {
            setActiveProjectId(active.id);
            setActiveProjectName(active.name);
            setActiveProjectRole(active.role ?? "viewer");
        }
    }, []);

    const canMutateProject = canEditProject(activeProjectRole);

    useEffect(() => {
        if (!activeProjectId) return;
        void loadHistory();
    }, [activeProjectId]);

    async function loadHistory() {
        if (!activeProjectId) return;
        setLoadingHistory(true);
        try {
            const response = await listReports(activeProjectId);
            const meshReports = response.data.items.filter(item => item.type === "conflict_mesh");
            setHistory(meshReports);
        } catch (error) {
            console.error("Failed to load history", error);
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
            toast.error("Generating mesh requires editor role or higher.");
            return;
        }
        setBusy(true);
        setReport(null);
        const toastId = toast.loading(`Generating Knowledge Mesh with ${provider}...`);
        try {
            const response = await generateReport({
                projectId: activeProjectId,
                query,
                type: "conflict_mesh",
                provider,
            });
            setReport(response.data);
            toast.success("Mesh generated successfully.", { id: toastId });
            void loadHistory();
        } catch {
            toast.error("Failed to generate mesh.", { id: toastId });
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
            toast.success("Mesh loaded.");
        } catch {
            toast.error("Failed to load mesh.");
        } finally {
            setBusy(false);
        }
    }

    return (
        <PageWrapper
            title="Conflict Mesh"
            description={
                activeProjectName
                    ? `Interactive evidence graph for: ${activeProjectName}`
                    : "Select a project to visualize evidence conflicts and relationships."
            }
        >
            {!canMutateProject && activeProjectId ? (
                <div className="rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
                    You have viewer access for this project. Mesh generation is disabled.
                </div>
            ) : null}

            <div className="flex flex-col lg:flex-row gap-6 w-full">
                <div className="flex flex-col gap-6 lg:w-[320px] shrink-0">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg font-bold flex items-center gap-2">
                                <Network className="w-5 h-5 text-primary" />
                                Intelligence Mesh
                            </CardTitle>
                            <CardDescription>
                                Map out concepts, relationships, and contradictions from your evidence.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form
                                onSubmit={handleSubmit}
                                className="flex flex-col gap-3"
                            >
                                <div className="flex flex-col gap-1.5">
                                    <Label htmlFor="provider-select">
                                        Writer Model
                                    </Label>
                                    <select
                                        id="provider-select"
                                        value={provider}
                                        onChange={(event) =>
                                            setProvider(event.target.value)
                                        }
                                        disabled={busy || !canMutateProject}
                                        className={
                                            "flex h-9 w-full rounded-md border border-input bg-transparent " +
                                            "px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none " +
                                            "focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                                        }
                                    >
                                        <option value="openai">
                                            OpenAI
                                        </option>
                                        <option value="gemini">
                                            Gemini
                                        </option>
                                    </select>
                                </div>
                                <div className="flex flex-col gap-1.5 mt-2">
                                    <Label htmlFor="query-input">
                                        Focus Area
                                    </Label>
                                    <Textarea
                                        id="query-input"
                                        required
                                        rows={3}
                                        value={query}
                                        onChange={(event) => setQuery(event.target.value)}
                                        placeholder="E.g., Analyze the architectural decisions and list disagreements."
                                        disabled={busy || !canMutateProject}
                                    />
                                </div>
                                <Button type="submit" disabled={busy || !canMutateProject} className="mt-2 w-full">
                                    {busy ? "Generating..." : "Generate Mesh"}
                                </Button>
                            </form>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                            <div className="space-y-0.5">
                                <CardTitle className="text-base">History</CardTitle>
                                <CardDescription>Previous graphs</CardDescription>
                            </div>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => void loadHistory()}
                                disabled={loadingHistory || !activeProjectId}
                            >
                                <RefreshCcw className="h-4 w-4" />
                            </Button>
                        </CardHeader>
                        <CardContent>
                            {history.length === 0 ? (
                                <p className="text-sm text-muted-foreground">
                                    No generated meshes found.
                                </p>
                            ) : (
                                <ul className="flex flex-col gap-2">
                                    {history.map((item) => (
                                        <li key={item.report_id}>
                                            <button
                                                type="button"
                                                onClick={() => void handleLoadReport(item.report_id)}
                                                className="w-full text-left rounded-md px-3 py-2 text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
                                            >
                                                <div className="font-medium truncate">{item.title}</div>
                                                <div className="text-xs text-muted-foreground truncate">
                                                    {new Date(item.created_at).toLocaleString()}
                                                </div>
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </CardContent>
                    </Card>

                </div>

                <div className="lg:col-span-4 flex-1 flex flex-col">
                    {report?.structured_payload ? (
                        <div className="h-[82vh] min-h-[600px] border border-border rounded-xl overflow-hidden bg-background">
                            <MeshGraph payload={report.structured_payload as ConflictMeshPayload} />
                        </div>
                    ) : (
                        <Card className="flex h-full min-h-[400px] items-center justify-center text-center">
                            <CardContent>
                                <p className="text-sm text-muted-foreground">
                                    {busy ? "Generating Graph... This may take a minute." : "Generate or load a Mesh to view the interactive graph."}
                                </p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </PageWrapper>
    );
}
