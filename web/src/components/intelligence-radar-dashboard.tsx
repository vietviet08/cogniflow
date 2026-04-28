"use client";

import { FormEvent, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
    Activity,
    Bell,
    CheckCircle2,
    FileText,
    Gauge,
    Plus,
    Radar,
    Send,
    ShieldCheck,
    type LucideIcon,
} from "lucide-react";

import {
    acknowledgeIntelligenceEvent,
    createIntelligenceAction,
    createIntelligenceOutput,
    createIntelligenceSource,
    getIntelligenceRoiDashboard,
    getIntelligenceTodayDigest,
    listIntelligenceActions,
    listIntelligenceApprovals,
    listIntelligenceEvents,
    listIntelligenceOutputs,
    listIntelligenceSources,
    requestIntelligenceApproval,
    reviewIntelligenceApproval,
    triggerIntelligenceScan,
} from "@/lib/api/client";
import type {
    IntelligenceEventData,
    IntelligenceSeverity,
} from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject } from "@/lib/project-store";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

const EMPTY_SELECT_VALUE = "__none__";
const OUTPUT_TYPES = [
    "battlecard",
    "talking_points",
    "response_plan",
    "outreach_draft",
] as const;

function severityVariant(severity: IntelligenceSeverity) {
    if (severity === "high") return "destructive";
    if (severity === "medium") return "warning";
    return "secondary";
}

export function IntelligenceRadarDashboard() {
    const queryClient = useQueryClient();
    const activeProject = getActiveProject();
    const projectId = activeProject?.id ?? "";
    const projectRole = activeProject?.role;
    const canMutate = canEditProject(projectRole);

    const [sourceName, setSourceName] = useState("");
    const [sourceUrl, setSourceUrl] = useState("");
    const [category, setCategory] = useState("competitor");
    const [defaultOwner, setDefaultOwner] = useState("");
    const [pollInterval, setPollInterval] = useState(1440);
    const [scanThreshold, setScanThreshold] =
        useState<IntelligenceSeverity>("medium");
    const [selectedEventId, setSelectedEventId] = useState("");
    const [outputType, setOutputType] =
        useState<(typeof OUTPUT_TYPES)[number]>("battlecard");
    const [outputContext, setOutputContext] = useState("");
    const [busyAction, setBusyAction] = useState<string | null>(null);

    const sourcesQuery = useQuery({
        queryKey: ["intelligence-sources", projectId],
        queryFn: () => listIntelligenceSources(projectId),
        enabled: Boolean(projectId),
    });
    const eventsQuery = useQuery({
        queryKey: ["intelligence-events", projectId, 24],
        queryFn: () =>
            listIntelligenceEvents({ projectId, sinceHours: 24 }),
        enabled: Boolean(projectId),
    });
    const digestQuery = useQuery({
        queryKey: ["intelligence-digest", projectId],
        queryFn: () => getIntelligenceTodayDigest(projectId),
        enabled: Boolean(projectId),
    });
    const roiQuery = useQuery({
        queryKey: ["intelligence-roi", projectId],
        queryFn: () => getIntelligenceRoiDashboard({ projectId }),
        enabled: Boolean(projectId),
    });
    const outputsQuery = useQuery({
        queryKey: ["intelligence-outputs", projectId],
        queryFn: () => listIntelligenceOutputs(projectId),
        enabled: Boolean(projectId),
    });
    const approvalsQuery = useQuery({
        queryKey: ["intelligence-approvals", projectId],
        queryFn: () => listIntelligenceApprovals({ projectId }),
        enabled: Boolean(projectId),
    });
    const actionsQuery = useQuery({
        queryKey: ["intelligence-actions", projectId],
        queryFn: () => listIntelligenceActions({ projectId }),
        enabled: Boolean(projectId),
    });

    const sources = sourcesQuery.data?.data.items ?? [];
    const events = eventsQuery.data?.data.items ?? [];
    const digest = digestQuery.data?.data;
    const roi = roiQuery.data?.data;
    const outputs = outputsQuery.data?.data.items ?? [];
    const approvals = approvalsQuery.data?.data.items ?? [];
    const actions = actionsQuery.data?.data.items ?? [];

    const selectedEvent = useMemo(
        () => events.find((event) => event.event_id === selectedEventId),
        [events, selectedEventId],
    );
    const pendingApprovals = approvals.filter(
        (approval) => approval.status === "pending",
    );

    async function reloadDashboard() {
        await Promise.all([
            queryClient.invalidateQueries({
                queryKey: ["intelligence-sources", projectId],
            }),
            queryClient.invalidateQueries({
                queryKey: ["intelligence-events", projectId],
            }),
            queryClient.invalidateQueries({
                queryKey: ["intelligence-digest", projectId],
            }),
            queryClient.invalidateQueries({
                queryKey: ["intelligence-roi", projectId],
            }),
            queryClient.invalidateQueries({
                queryKey: ["intelligence-outputs", projectId],
            }),
            queryClient.invalidateQueries({
                queryKey: ["intelligence-approvals", projectId],
            }),
            queryClient.invalidateQueries({
                queryKey: ["intelligence-actions", projectId],
            }),
        ]);
    }

    async function handleCreateSource(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!projectId || !canMutate) return;
        setBusyAction("create-source");
        const toastId = toast.loading("Creating radar source...");
        try {
            await createIntelligenceSource({
                projectId,
                name: sourceName,
                sourceUrl,
                category,
                defaultOwner: defaultOwner || undefined,
                pollIntervalMinutes: pollInterval,
                isActive: true,
            });
            setSourceName("");
            setSourceUrl("");
            setDefaultOwner("");
            await reloadDashboard();
            toast.success("Radar source created.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to create radar source.",
                { id: toastId },
            );
        } finally {
            setBusyAction(null);
        }
    }

    async function handleScan() {
        if (!projectId || !canMutate) return;
        setBusyAction("scan");
        const toastId = toast.loading("Scanning intelligence sources...");
        try {
            const response = await triggerIntelligenceScan({
                projectId,
                mode: "sync",
                alertThreshold: scanThreshold,
            });
            await reloadDashboard();
            if ("checked_sources" in response.data) {
                toast.success(
                    `Scan complete: ${response.data.events_created} events, ${response.data.alerts_triggered} alerts.`,
                    { id: toastId },
                );
            } else {
                toast.success("Scan job queued.", { id: toastId });
            }
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : "Scan failed.",
                { id: toastId },
            );
        } finally {
            setBusyAction(null);
        }
    }

    async function handleAcknowledge(eventId: string) {
        if (!canMutate) return;
        setBusyAction(`ack:${eventId}`);
        try {
            await acknowledgeIntelligenceEvent({ projectId, eventId });
            await reloadDashboard();
            toast.success("Event acknowledged.");
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to acknowledge event.",
            );
        } finally {
            setBusyAction(null);
        }
    }

    async function handleCreateAction(eventRow: IntelligenceEventData) {
        if (!canMutate) return;
        setBusyAction(`action:${eventRow.event_id}`);
        try {
            await createIntelligenceAction({
                projectId,
                eventId: eventRow.event_id,
                title: eventRow.title,
                description: eventRow.summary,
                priority: eventRow.severity,
            });
            await reloadDashboard();
            toast.success("Action created from event.");
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : "Failed to create action.",
            );
        } finally {
            setBusyAction(null);
        }
    }

    async function handleCreateOutput() {
        if (!projectId || !canMutate) return;
        setBusyAction("create-output");
        const toastId = toast.loading("Creating GTM output...");
        try {
            const response = await createIntelligenceOutput({
                projectId,
                eventId: selectedEvent?.event_id,
                outputType,
                context: outputContext,
            });
            await requestIntelligenceApproval({
                projectId,
                targetType: "gtm_output",
                targetId: response.data.output_id,
            });
            setOutputContext("");
            await reloadDashboard();
            toast.success("Output created and sent for approval.", {
                id: toastId,
            });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to create output.",
                { id: toastId },
            );
        } finally {
            setBusyAction(null);
        }
    }

    async function handleReviewApproval(
        approvalId: string,
        status: "approved" | "rejected",
    ) {
        if (!canMutate) return;
        setBusyAction(`approval:${approvalId}`);
        try {
            await reviewIntelligenceApproval({
                projectId,
                approvalId,
                status,
            });
            await reloadDashboard();
            toast.success(`Approval ${status}.`);
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to review approval.",
            );
        } finally {
            setBusyAction(null);
        }
    }

    return (
        <PageWrapper
            title="Intelligence Radar"
            description={
                activeProject
                    ? `Monitor changes, triage alerts, and produce GTM outputs for ${activeProject.name}.`
                    : "Select a project to run the intelligence workflow."
            }
        >
            <div className="grid gap-4 md:grid-cols-4">
                <MetricCard
                    icon={Radar}
                    label="Sources"
                    value={sources.length}
                    helper={`${sources.filter((source) => source.is_active).length} active`}
                />
                <MetricCard
                    icon={Bell}
                    label="Events today"
                    value={digest?.summary.events_total ?? 0}
                    helper={`${digest?.summary.high ?? 0} high severity`}
                />
                <MetricCard
                    icon={CheckCircle2}
                    label="Action closure"
                    value={`${Math.round((roi?.action_completion_rate ?? 0) * 100)}%`}
                    helper={`${roi?.actions_completed ?? 0}/${roi?.actions_total ?? 0} done`}
                />
                <MetricCard
                    icon={FileText}
                    label="Outputs"
                    value={roi?.outputs_generated ?? outputs.length}
                    helper={`${pendingApprovals.length} pending approvals`}
                />
            </div>

            <div className="grid gap-6 xl:grid-cols-[minmax(280px,360px)_1fr]">
                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base">
                                <Plus className="h-4 w-4" />
                                Add Source
                            </CardTitle>
                            <CardDescription>
                                Track competitor, policy, pricing, review, or news pages.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form className="space-y-3" onSubmit={handleCreateSource}>
                                <div className="space-y-1">
                                    <Label htmlFor="radar-source-name">Name</Label>
                                    <Input
                                        id="radar-source-name"
                                        value={sourceName}
                                        onChange={(event) =>
                                            setSourceName(event.target.value)
                                        }
                                        placeholder="Competitor pricing"
                                        required
                                        disabled={!canMutate}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label htmlFor="radar-source-url">URL</Label>
                                    <Input
                                        id="radar-source-url"
                                        type="url"
                                        value={sourceUrl}
                                        onChange={(event) =>
                                            setSourceUrl(event.target.value)
                                        }
                                        placeholder="https://example.com/pricing"
                                        required
                                        disabled={!canMutate}
                                    />
                                </div>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <div className="space-y-1">
                                        <Label>Category</Label>
                                        <Select
                                            value={category}
                                            onValueChange={setCategory}
                                            disabled={!canMutate}
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="competitor">
                                                    competitor
                                                </SelectItem>
                                                <SelectItem value="pricing">
                                                    pricing
                                                </SelectItem>
                                                <SelectItem value="policy">
                                                    policy
                                                </SelectItem>
                                                <SelectItem value="review">
                                                    review
                                                </SelectItem>
                                                <SelectItem value="news">
                                                    news
                                                </SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-1">
                                        <Label htmlFor="radar-interval">
                                            Poll minutes
                                        </Label>
                                        <Input
                                            id="radar-interval"
                                            type="number"
                                            min={5}
                                            value={pollInterval}
                                            onChange={(event) =>
                                                setPollInterval(
                                                    Number(event.target.value) || 1440,
                                                )
                                            }
                                            disabled={!canMutate}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-1">
                                    <Label htmlFor="radar-owner">
                                        Default owner
                                    </Label>
                                    <Input
                                        id="radar-owner"
                                        value={defaultOwner}
                                        onChange={(event) =>
                                            setDefaultOwner(event.target.value)
                                        }
                                        placeholder="Growth PM"
                                        disabled={!canMutate}
                                    />
                                </div>
                                <Button
                                    type="submit"
                                    className="w-full gap-2"
                                    disabled={
                                        !projectId ||
                                        !canMutate ||
                                        busyAction === "create-source"
                                    }
                                >
                                    {busyAction === "create-source" ? (
                                        <Spinner size="sm" />
                                    ) : (
                                        <Plus className="h-4 w-4" />
                                    )}
                                    Add source
                                </Button>
                            </form>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base">
                                <Activity className="h-4 w-4" />
                                Scan Control
                            </CardTitle>
                            <CardDescription>
                                Run a sync scan and create threshold-based alerts.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <Select
                                value={scanThreshold}
                                onValueChange={(value) =>
                                    setScanThreshold(value as IntelligenceSeverity)
                                }
                                disabled={!canMutate}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="low">low</SelectItem>
                                    <SelectItem value="medium">medium</SelectItem>
                                    <SelectItem value="high">high</SelectItem>
                                </SelectContent>
                            </Select>
                            <Button
                                className="w-full gap-2"
                                onClick={handleScan}
                                disabled={
                                    !projectId ||
                                    !canMutate ||
                                    busyAction === "scan" ||
                                    sources.length === 0
                                }
                            >
                                {busyAction === "scan" ? (
                                    <Spinner size="sm" />
                                ) : (
                                    <Radar className="h-4 w-4" />
                                )}
                                Run scan
                            </Button>
                        </CardContent>
                    </Card>
                </div>

                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <CardTitle className="flex items-center gap-2 text-base">
                                        <Bell className="h-4 w-4" />
                                        Recent Events
                                    </CardTitle>
                                    <CardDescription>
                                        Last 24 hours of detected changes and alert signals.
                                    </CardDescription>
                                </div>
                                {eventsQuery.isLoading ? <Spinner size="sm" /> : null}
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {events.length === 0 ? (
                                <p className="text-sm text-muted-foreground">
                                    No recent events. Add a source and run a scan.
                                </p>
                            ) : (
                                events.slice(0, 8).map((eventRow) => (
                                    <div
                                        key={eventRow.event_id}
                                        className="rounded-md border border-border p-3"
                                    >
                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                            <div className="min-w-0 flex-1">
                                                <div className="mb-2 flex flex-wrap items-center gap-2">
                                                    <Badge
                                                        variant={severityVariant(
                                                            eventRow.severity,
                                                        )}
                                                    >
                                                        {eventRow.severity}
                                                    </Badge>
                                                    <Badge variant="outline">
                                                        {eventRow.event_type}
                                                    </Badge>
                                                    {eventRow.acknowledged_at ? (
                                                        <Badge variant="secondary">
                                                            acknowledged
                                                        </Badge>
                                                    ) : null}
                                                </div>
                                                <p className="font-medium">
                                                    {eventRow.title}
                                                </p>
                                                <p className="mt-1 text-sm text-muted-foreground">
                                                    {eventRow.summary}
                                                </p>
                                            </div>
                                            <div className="flex shrink-0 flex-wrap gap-2">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="gap-1"
                                                    disabled={
                                                        !canMutate ||
                                                        Boolean(
                                                            eventRow.acknowledged_at,
                                                        ) ||
                                                        busyAction ===
                                                            `ack:${eventRow.event_id}`
                                                    }
                                                    onClick={() =>
                                                        handleAcknowledge(
                                                            eventRow.event_id,
                                                        )
                                                    }
                                                >
                                                    <CheckCircle2 className="h-3.5 w-3.5" />
                                                    Ack
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    className="gap-1"
                                                    disabled={
                                                        !canMutate ||
                                                        busyAction ===
                                                            `action:${eventRow.event_id}`
                                                    }
                                                    onClick={() =>
                                                        handleCreateAction(eventRow)
                                                    }
                                                >
                                                    <Send className="h-3.5 w-3.5" />
                                                    Action
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </CardContent>
                    </Card>

                    <div className="grid gap-6 lg:grid-cols-2">
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-base">
                                    <FileText className="h-4 w-4" />
                                    GTM Output
                                </CardTitle>
                                <CardDescription>
                                    Generate battlecards, talking points, and response plans.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <Select
                                    value={selectedEventId || EMPTY_SELECT_VALUE}
                                    onValueChange={(value) =>
                                        setSelectedEventId(
                                            value === EMPTY_SELECT_VALUE ? "" : value,
                                        )
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value={EMPTY_SELECT_VALUE}>
                                            No event context
                                        </SelectItem>
                                        {events.map((eventRow) => (
                                            <SelectItem
                                                key={eventRow.event_id}
                                                value={eventRow.event_id}
                                            >
                                                {eventRow.title}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Select
                                    value={outputType}
                                    onValueChange={(value) =>
                                        setOutputType(
                                            value as (typeof OUTPUT_TYPES)[number],
                                        )
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {OUTPUT_TYPES.map((type) => (
                                            <SelectItem key={type} value={type}>
                                                {type}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Textarea
                                    value={outputContext}
                                    onChange={(event) =>
                                        setOutputContext(event.target.value)
                                    }
                                    rows={4}
                                    placeholder="Add positioning notes, target segment, or sales context."
                                />
                                <Button
                                    className="w-full gap-2"
                                    disabled={
                                        !projectId ||
                                        !canMutate ||
                                        busyAction === "create-output"
                                    }
                                    onClick={handleCreateOutput}
                                >
                                    {busyAction === "create-output" ? (
                                        <Spinner size="sm" />
                                    ) : (
                                        <ShieldCheck className="h-4 w-4" />
                                    )}
                                    Create and request approval
                                </Button>
                                <div className="space-y-2">
                                    {outputs.slice(0, 3).map((output) => (
                                        <div
                                            key={output.output_id}
                                            className="rounded-md border p-2 text-sm"
                                        >
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline">
                                                    {output.output_type}
                                                </Badge>
                                                <Badge variant="secondary">
                                                    {output.status}
                                                </Badge>
                                            </div>
                                            <p className="mt-1 font-medium">
                                                {output.title}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-base">
                                    <Gauge className="h-4 w-4" />
                                    Workflow Health
                                </CardTitle>
                                <CardDescription>
                                    ROI and approval status for the pilot workflow.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="grid grid-cols-2 gap-3 text-sm">
                                    <HealthStat
                                        label="Events"
                                        value={roi?.events_total ?? 0}
                                    />
                                    <HealthStat
                                        label="High severity"
                                        value={roi?.high_events ?? 0}
                                    />
                                    <HealthStat
                                        label="Actions"
                                        value={actions.length}
                                    />
                                    <HealthStat
                                        label="Acknowledged"
                                        value={`${Math.round((roi?.acknowledged_rate ?? 0) * 100)}%`}
                                    />
                                </div>
                                <div className="space-y-2">
                                    {pendingApprovals.length === 0 ? (
                                        <p className="text-sm text-muted-foreground">
                                            No pending approvals.
                                        </p>
                                    ) : (
                                        pendingApprovals.slice(0, 4).map((approval) => (
                                            <div
                                                key={approval.approval_id}
                                                className="rounded-md border p-2"
                                            >
                                                <div className="mb-2 flex items-center justify-between gap-2">
                                                    <Badge variant="warning">
                                                        pending
                                                    </Badge>
                                                    <span className="truncate text-xs text-muted-foreground">
                                                        {approval.target_type}
                                                    </span>
                                                </div>
                                                <div className="flex gap-2">
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        disabled={
                                                            busyAction ===
                                                            `approval:${approval.approval_id}`
                                                        }
                                                        onClick={() =>
                                                            handleReviewApproval(
                                                                approval.approval_id,
                                                                "rejected",
                                                            )
                                                        }
                                                    >
                                                        Reject
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        disabled={
                                                            busyAction ===
                                                            `approval:${approval.approval_id}`
                                                        }
                                                        onClick={() =>
                                                            handleReviewApproval(
                                                                approval.approval_id,
                                                                "approved",
                                                            )
                                                        }
                                                    >
                                                        Approve
                                                    </Button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </PageWrapper>
    );
}

function MetricCard({
    icon: Icon,
    label,
    value,
    helper,
}: {
    icon: LucideIcon;
    label: string;
    value: string | number;
    helper: string;
}) {
    return (
        <Card>
            <CardContent className="flex items-center gap-3 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                    <Icon className="h-4 w-4" />
                </div>
                <div>
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="text-xl font-semibold">{value}</p>
                    <p className="text-xs text-muted-foreground">{helper}</p>
                </div>
            </CardContent>
        </Card>
    );
}

function HealthStat({
    label,
    value,
}: {
    label: string;
    value: string | number;
}) {
    return (
        <div className="rounded-md border border-border p-3">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="mt-1 text-lg font-semibold">{value}</p>
        </div>
    );
}
