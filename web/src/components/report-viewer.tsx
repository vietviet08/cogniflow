"use client";

import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, History, RefreshCcw, Quote } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
    generateReport,
    getReport,
    listReports,
    getReportLineage,
} from "@/lib/api/client";
import type {
    ReportResult,
    ReportListItem,
    ReportLineage,
} from "@/lib/api/types";
import { getActiveProject } from "@/lib/project-store";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { PageWrapper } from "@/components/layout/page-wrapper";

export function ReportViewer() {
    const [activeProjectId, setActiveProjectId] = useState("");
    const [activeProjectName, setActiveProjectName] = useState("");
    const [query, setQuery] = useState("");
    const [reportType, setReportType] = useState<
        "research_brief" | "summary" | "comparison"
    >("research_brief");
    const [provider, setProvider] = useState("openai");

    const [busy, setBusy] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(false);

    const [report, setReport] = useState<ReportResult | null>(null);
    const [lineage, setLineage] = useState<ReportLineage | null>(null);
    const [history, setHistory] = useState<ReportListItem[]>([]);

    useEffect(() => {
        const active = getActiveProject();
        if (active) {
            setActiveProjectId(active.id);
            setActiveProjectName(active.name);
        }
    }, []);

    useEffect(() => {
        if (!activeProjectId) return;

        loadHistory();
    }, [activeProjectId]);

    async function loadHistory() {
        if (!activeProjectId) return;
        setLoadingHistory(true);
        try {
            const response = await listReports(activeProjectId);
            setHistory(response.data.items);
        } catch (error) {
            console.error("Failed to load history", error);
        } finally {
            setLoadingHistory(false);
        }
    }

    async function loadLineage(reportId: string) {
        try {
            const response = await getReportLineage(reportId);
            setLineage(response.data);
        } catch (error) {
            console.error("Failed to load lineage", error);
            setLineage(null);
        }
    }

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!activeProjectId) {
            toast.error("Create or select a project first.");
            return;
        }
        setBusy(true);
        setReport(null);
        setLineage(null);
        const toastId = toast.loading(
            `Generating ${reportType.replace("_", " ")} with ${provider}...`,
        );
        try {
            const response = await generateReport({
                projectId: activeProjectId,
                query,
                type: reportType,
                provider,
            });
            setReport(response.data);
            await loadLineage(response.data.report_id);
            toast.success(`Report generated successfully.`, { id: toastId });
            loadHistory();
        } catch {
            toast.error("Failed to generate report.", { id: toastId });
        } finally {
            setBusy(false);
        }
    }

    async function handleLoadReport(reportId: string) {
        setBusy(true);
        try {
            const response = await getReport(reportId);
            setReport(response.data);
            setReportType(response.data.type as any);
            setQuery("Loading from history..."); // Cannot reconstruct exactly from history easily
            await loadLineage(reportId);
            toast.success("Report loaded.");
        } catch {
            toast.error("Failed to load full report.");
        } finally {
            setBusy(false);
        }
    }

    return (
        <PageWrapper
            title="Reports"
            description={
                activeProjectName
                    ? `Reporting for: ${activeProjectName}`
                    : "Select a project to generate comprehensive markdown reports from verified insights."
            }
        >
            <div className="grid gap-6 lg:grid-cols-3">
                {/* Left Column: Form & History */}
                <div className="flex flex-col gap-6 lg:col-span-1">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">
                                Generate Report
                            </CardTitle>
                            <CardDescription>
                                Build a multi-source research report based on
                                retrieved and synthesized evidence.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form
                                onSubmit={handleSubmit}
                                className="flex flex-col gap-3"
                            >
                                <div className="grid gap-3 md:grid-cols-2">
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
                                            disabled={busy}
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
                                    <div className="flex flex-col gap-1.5">
                                        <Label htmlFor="report-type">
                                            Report Type
                                        </Label>
                                        <select
                                            id="report-type"
                                            value={reportType}
                                            onChange={(event) =>
                                                setReportType(
                                                    event.target.value as any,
                                                )
                                            }
                                            disabled={busy}
                                            className={
                                                "flex h-9 w-full rounded-md border border-input bg-transparent " +
                                                "px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none " +
                                                "focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                                            }
                                        >
                                            <option value="research_brief">
                                                Research Brief
                                            </option>
                                            <option value="summary">
                                                Summary
                                            </option>
                                            <option value="comparison">
                                                Comparison
                                            </option>
                                        </select>
                                    </div>
                                </div>
                                <div className="flex flex-col gap-1.5">
                                    <Label htmlFor="query-input">
                                        Topic / Request
                                    </Label>
                                    <Textarea
                                        id="query-input"
                                        required
                                        rows={4}
                                        value={query}
                                        onChange={(e) =>
                                            setQuery(e.target.value)
                                        }
                                        placeholder="E.g., Compare the security architectures described in these whitepapers."
                                        disabled={busy}
                                    />
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">
                                    This process runs insight synthesis first,
                                    then renders a full Markdown document with
                                    lineage tracking.
                                </p>
                                <Button
                                    type="submit"
                                    disabled={
                                        busy || !activeProjectId || !query
                                    }
                                    className="w-full gap-2 mt-2"
                                >
                                    {busy ? (
                                        <Spinner size="sm" />
                                    ) : (
                                        <FileText className="h-4 w-4" />
                                    )}
                                    {busy ? "Generating..." : "Generate Report"}
                                </Button>
                            </form>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between py-4">
                            <div className="flex items-center gap-2">
                                <History className="h-4 w-4 text-muted-foreground" />
                                <CardTitle className="text-base">
                                    History
                                </CardTitle>
                            </div>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={loadHistory}
                                disabled={loadingHistory || !activeProjectId}
                            >
                                <RefreshCcw className="h-3 w-3" />
                            </Button>
                        </CardHeader>
                        <Separator />
                        <CardContent className="p-0 max-h-[400px] overflow-auto">
                            {history.length === 0 ? (
                                <div className="p-6 text-center text-sm text-muted-foreground">
                                    No past reports found.
                                </div>
                            ) : (
                                <div className="flex flex-col">
                                    {history.map((item) => (
                                        <button
                                            key={item.report_id}
                                            onClick={() =>
                                                handleLoadReport(item.report_id)
                                            }
                                            disabled={busy}
                                            className="flex flex-col items-start gap-1 border-b p-4 text-left transition-colors hover:bg-muted/50 disabled:opacity-50"
                                        >
                                            <span className="line-clamp-2 text-sm font-medium">
                                                {item.title}
                                            </span>
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground mt-2">
                                                <span>
                                                    {new Date(
                                                        item.created_at,
                                                    ).toLocaleDateString()}
                                                </span>
                                                <span>•</span>
                                                <span className="capitalize">
                                                    {item.type.replace(
                                                        "_",
                                                        " ",
                                                    )}
                                                </span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Right Column: Viewer */}
                <div className="flex flex-col gap-6 lg:col-span-2">
                    {!report && !busy ? (
                        <Card className="flex h-[300px] items-center justify-center border-dashed">
                            <div className="flex flex-col items-center gap-2 text-muted-foreground">
                                <FileText className="h-8 w-8 opacity-20" />
                                <p>
                                    Generate a report to view the formatted
                                    Markdown output.
                                </p>
                            </div>
                        </Card>
                    ) : busy && !report ? (
                        <Card className="flex h-[300px] items-center justify-center">
                            <div className="flex flex-col items-center gap-4 text-muted-foreground">
                                <Spinner size="lg" />
                                <p>
                                    Synthesizing insights and drafting report...
                                </p>
                            </div>
                        </Card>
                    ) : report ? (
                        <>
                            <Card>
                                <CardHeader>
                                    <div className="flex items-center gap-2">
                                        <CardTitle className="text-lg">
                                            {report.title}
                                        </CardTitle>
                                        <Badge
                                            variant="secondary"
                                            className="ml-auto capitalize"
                                        >
                                            {report.type.replace("_", " ")}
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <Separator />
                                <CardContent
                                    className={
                                        "p-8 prose prose-sm max-w-none text-foreground " +
                                        "prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground " +
                                        "prose-li:text-foreground prose-blockquote:text-muted-foreground prose-a:text-primary " +
                                        "prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground"
                                    }
                                >
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {report.content}
                                    </ReactMarkdown>
                                </CardContent>
                            </Card>

                            {lineage && lineage.source_ids.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <div className="flex items-center gap-2">
                                            <Quote className="h-4 w-4 text-muted-foreground" />
                                            <CardTitle className="text-base">
                                                Document Lineage
                                            </CardTitle>
                                            <Badge
                                                variant="outline"
                                                className="ml-auto"
                                            >
                                                {lineage.source_ids.length}{" "}
                                                sources
                                            </Badge>
                                        </div>
                                        <CardDescription>
                                            This report was generated using
                                            verified chunks from{" "}
                                            {lineage.source_ids.length} indexed
                                            source(s).
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="p-0">
                                        <div className="grid gap-px bg-border">
                                            {lineage.source_ids.map(
                                                (sourceId) => (
                                                    <div
                                                        key={sourceId}
                                                        className="flex items-center justify-between bg-card px-6 py-4"
                                                    >
                                                        <p className="text-sm font-mono text-muted-foreground">
                                                            Source ID:{" "}
                                                            {sourceId}
                                                        </p>
                                                        <a
                                                            href={`/sources?id=${sourceId}`}
                                                            className="text-xs text-primary hover:underline"
                                                        >
                                                            View details
                                                        </a>
                                                    </div>
                                                ),
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    ) : null}
                </div>
            </div>
        </PageWrapper>
    );
}
