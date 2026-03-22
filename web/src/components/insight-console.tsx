"use client";

import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import {
    Send,
    BookOpen,
    Quote,
    ExternalLink,
    History,
    RefreshCcw,
} from "lucide-react";

import { generateInsight, getInsight, listInsights } from "@/lib/api/client";
import type { InsightResult, InsightListItem } from "@/lib/api/types";
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

export function InsightConsole() {
    const [activeProjectId, setActiveProjectId] = useState("");
    const [activeProjectName, setActiveProjectName] = useState("");
    const [query, setQuery] = useState("");
    const [provider, setProvider] = useState("openai");

    const [busy, setBusy] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(false);

    const [insight, setInsight] = useState<InsightResult | null>(null);
    const [history, setHistory] = useState<InsightListItem[]>([]);

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
            const response = await listInsights(activeProjectId);
            setHistory(response.data.items);
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
        setBusy(true);
        setInsight(null);
        const toastId = toast.loading(
            `Synthesizing evidence with ${provider}...`,
        );
        try {
            const response = await generateInsight({
                projectId: activeProjectId,
                query,
                provider,
                maxSources: 20,
            });
            setInsight(response.data);
            toast.success(`Synthesis completed successfully.`, { id: toastId });
            loadHistory();
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to generate insight.",
                { id: toastId },
            );
        } finally {
            setBusy(false);
        }
    }

    async function handleLoadInsight(insightId: string) {
        setBusy(true);
        try {
            const response = await getInsight(insightId);
            setInsight(response.data);
            setQuery(response.data.query);
            toast.success("Insight loaded.");
        } catch {
            toast.error("Failed to load full insight.");
        } finally {
            setBusy(false);
        }
    }

    return (
        <PageWrapper
            title="Insights"
            description={
                activeProjectName
                    ? `Analysis for: ${activeProjectName}`
                    : "Select a project to synthesize multi-document evidence into thematic findings."
            }
        >
            <div className="grid gap-6 lg:grid-cols-3">
                {/* Left Column: Form & History */}
                <div className="flex flex-col gap-6 lg:col-span-1">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">
                                Generate Insight
                            </CardTitle>
                            <CardDescription>
                                Ask a broad research question to extract themes
                                and findings across many documents.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form
                                onSubmit={handleSubmit}
                                className="flex flex-col gap-3"
                            >
                                <div className="flex flex-col gap-1.5">
                                    <Label htmlFor="provider-select">
                                        Synthesizer Provider
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
                                        <option value="openai">OpenAI</option>
                                        <option value="gemini">Gemini</option>
                                    </select>
                                </div>
                                <div className="flex flex-col gap-1.5">
                                    <Label htmlFor="query-input">
                                        Research Question
                                    </Label>
                                    <Textarea
                                        id="query-input"
                                        required
                                        rows={4}
                                        value={query}
                                        onChange={(e) =>
                                            setQuery(e.target.value)
                                        }
                                        placeholder="E.g., What are the common challenges mentioned in the user interviews?"
                                        disabled={busy}
                                    />
                                </div>
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
                                        <Send className="h-4 w-4" />
                                    )}
                                    {busy ? "Synthesizing..." : "Analyze"}
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
                                    No past insights found.
                                </div>
                            ) : (
                                <div className="flex flex-col">
                                    {history.map((item) => (
                                        <button
                                            key={item.insight_id}
                                            onClick={() =>
                                                handleLoadInsight(
                                                    item.insight_id,
                                                )
                                            }
                                            disabled={busy}
                                            className="flex flex-col items-start gap-1 border-b p-4 text-left transition-colors hover:bg-muted/50 disabled:opacity-50"
                                        >
                                            <span className="line-clamp-2 text-sm font-medium">
                                                {item.query}
                                            </span>
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                <span>
                                                    {new Date(
                                                        item.created_at,
                                                    ).toLocaleDateString()}
                                                </span>
                                                <span>•</span>
                                                <span className="capitalize">
                                                    {item.provider}
                                                </span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Right Column: Results */}
                <div className="flex flex-col gap-6 lg:col-span-2">
                    {!insight && !busy ? (
                        <Card className="flex h-[300px] items-center justify-center border-dashed">
                            <div className="flex flex-col items-center gap-2 text-muted-foreground">
                                <BookOpen className="h-8 w-8 opacity-20" />
                                <p>
                                    Run an analysis or select one from history
                                    to view findings.
                                </p>
                            </div>
                        </Card>
                    ) : busy && !insight ? (
                        <Card className="flex h-[300px] items-center justify-center">
                            <div className="flex flex-col items-center gap-4 text-muted-foreground">
                                <Spinner size="lg" />
                                <p>
                                    Gathering evidence and synthesizing
                                    insights...
                                </p>
                            </div>
                        </Card>
                    ) : insight ? (
                        <>
                            <Card>
                                <CardHeader>
                                    <div className="flex items-center gap-2">
                                        <CardTitle className="text-lg">
                                            Synthesis Overview
                                        </CardTitle>
                                        <Badge
                                            variant="secondary"
                                            className="ml-auto capitalize"
                                        >
                                            {insight.provider}
                                        </Badge>
                                    </div>
                                    <CardDescription className="text-primary font-medium mt-2">
                                        {insight.summary}
                                    </CardDescription>
                                </CardHeader>
                                <Separator />
                                <CardContent className="p-6">
                                    {insight.findings.length === 0 ? (
                                        <p className="text-sm text-muted-foreground italic">
                                            No specific findings were extracted.
                                        </p>
                                    ) : (
                                        <div className="flex flex-col gap-6">
                                            {insight.findings.map(
                                                (finding, idx) => (
                                                    <div
                                                        key={idx}
                                                        className="flex flex-col gap-2"
                                                    >
                                                        <h4 className="text-base font-semibold">
                                                            {finding.theme}
                                                        </h4>
                                                        <ul className="list-inside list-disc space-y-1">
                                                            {finding.points.map(
                                                                (pt, i) => (
                                                                    <li
                                                                        key={i}
                                                                        className="text-sm text-foreground/80 leading-relaxed"
                                                                    >
                                                                        {pt}
                                                                    </li>
                                                                ),
                                                            )}
                                                        </ul>
                                                    </div>
                                                ),
                                            )}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            {insight.citations.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <div className="flex items-center gap-2">
                                            <Quote className="h-4 w-4 text-muted-foreground" />
                                            <CardTitle className="text-base">
                                                Evidence Citations
                                            </CardTitle>
                                            <Badge
                                                variant="outline"
                                                className="ml-auto"
                                            >
                                                {insight.citations.length}
                                            </Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="p-0">
                                        <div className="grid gap-px bg-border">
                                            {insight.citations.map(
                                                (citation, index) => (
                                                    <div
                                                        key={`${citation.chunk_id}-${index}`}
                                                        className="flex flex-col gap-1 bg-card px-6 py-4"
                                                    >
                                                        <p className="text-sm font-medium">
                                                            {citation.title ||
                                                                "Unknown Document"}
                                                        </p>
                                                        <p
                                                            className="text-xs font-mono text-muted-foreground truncate"
                                                            title={
                                                                citation.chunk_id
                                                            }
                                                        >
                                                            ID:{" "}
                                                            {citation.chunk_id}
                                                        </p>
                                                        {citation.url && (
                                                            <a
                                                                href={
                                                                    citation.url
                                                                }
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                className="mt-1 flex items-center gap-1 text-xs text-primary hover:underline"
                                                            >
                                                                <ExternalLink className="h-3 w-3" />
                                                                View Source
                                                            </a>
                                                        )}
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
