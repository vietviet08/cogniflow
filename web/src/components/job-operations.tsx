"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Activity, AlertCircle, RotateCcw, Square, TimerReset } from "lucide-react";

import {
    cancelJob,
    getOpsSlo,
    listProjectJobs,
    listProjects,
    retryJob,
} from "@/lib/api/client";
import type { OpsSloData, ProjectRole } from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject, setActiveProject } from "@/lib/project-store";
import { useOrganization } from "@/components/organization-provider";

import { PageWrapper } from "@/components/layout/page-wrapper";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

const statusTone: Record<
    string,
    "default" | "secondary" | "destructive" | "outline"
> = {
    queued: "secondary",
    running: "default",
    completed: "default",
    failed: "destructive",
    dead_letter: "destructive",
    cancelled: "outline",
};

export function JobOperations() {
    const queryClient = useQueryClient();

    const [activeProjectId, setActiveProjectId] = useState("");
    const [activeProjectRole, setActiveProjectRole] =
        useState<ProjectRole | null>(null);
    const [busyAction, setBusyAction] = useState<string | null>(null);
    const { activeOrganization } = useOrganization();

    const { data: projectsData, isLoading: projectsLoading } = useQuery({
        queryKey: ["projects", activeOrganization?.id],
        queryFn: () => listProjects({ organizationId: activeOrganization?.id }),
    });

    const projects = projectsData?.data.items ?? [];

    useEffect(() => {
        if (!projects.length) {
            setActiveProjectId("");
            setActiveProjectRole(null);
            return;
        }

        const stored = getActiveProject();
        const preferred =
            projects.find((item) => item.id === stored?.id) ??
            projects[0] ??
            null;
        if (!preferred) {
            return;
        }

        setActiveProjectId(preferred.id);
        setActiveProjectRole(preferred.role);
        setActiveProject({
            id: preferred.id,
            organization_id: preferred.organization_id,
            name: preferred.name,
            description: preferred.description,
            role: preferred.role,
        });
    }, [projects]);

    const canMutateJobs = canEditProject(activeProjectRole);

    const {
        data: jobsData,
        isLoading: jobsLoading,
        isFetching: jobsFetching,
    } = useQuery({
        queryKey: ["project-jobs", activeProjectId],
        queryFn: () => listProjectJobs(activeProjectId),
        enabled: Boolean(activeProjectId),
        refetchInterval: 3000,
    });

    const jobs = jobsData?.data.items ?? [];

    const { data: opsData } = useQuery({
        queryKey: ["ops-slo"],
        queryFn: getOpsSlo,
        refetchInterval: 5000,
        retry: false,
    });

    const opsSlo = opsData?.data ?? null;

    const sortedJobs = useMemo(
        () =>
            [...jobs].sort((left, right) =>
                compareDates(right.started_at, left.started_at),
            ),
        [jobs],
    );

    async function handleCancel(jobId: string) {
        setBusyAction(`cancel:${jobId}`);
        const toastId = toast.loading("Requesting cancellation...");
        try {
            await cancelJob(jobId);
            await queryClient.invalidateQueries({
                queryKey: ["project-jobs", activeProjectId],
            });
            toast.success("Cancellation requested.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to cancel job.",
                {
                    id: toastId,
                },
            );
        } finally {
            setBusyAction(null);
        }
    }

    async function handleRetry(jobId: string) {
        setBusyAction(`retry:${jobId}`);
        const toastId = toast.loading("Queueing retry...");
        try {
            await retryJob(jobId);
            await queryClient.invalidateQueries({
                queryKey: ["project-jobs", activeProjectId],
            });
            toast.success("Job queued for retry.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : "Failed to retry job.",
                {
                    id: toastId,
                },
            );
        } finally {
            setBusyAction(null);
        }
    }

    function handleProjectChange(nextProjectId: string) {
        const project = projects.find((item) => item.id === nextProjectId);
        if (!project) {
            return;
        }
        setActiveProjectId(project.id);
        setActiveProjectRole(project.role);
        setActiveProject({
            id: project.id,
            organization_id: project.organization_id,
            name: project.name,
            description: project.description,
            role: project.role,
        });
    }

    let jobsContent;
    if (jobsLoading) {
        jobsContent = (
            <div className="flex items-center justify-center py-10">
                <Spinner />
            </div>
        );
    } else if (sortedJobs.length === 0) {
        jobsContent = (
            <Card>
                <CardContent className="pt-6 text-sm text-muted-foreground">
                    No jobs yet for this project.
                </CardContent>
            </Card>
        );
    } else {
        jobsContent = (
            <div className="grid gap-3">
                {sortedJobs.map((job) => {
                    const canCancel =
                        canMutateJobs &&
                        ["queued", "running"].includes(job.status);
                    const canRetry =
                        canMutateJobs &&
                        ["failed", "dead_letter", "cancelled"].includes(
                            job.status,
                        );
                    const isCancelling = busyAction === `cancel:${job.job_id}`;
                    const isRetrying = busyAction === `retry:${job.job_id}`;

                    return (
                        <Card key={job.job_id}>
                            <CardContent className="pt-6">
                                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                                    <div className="space-y-2">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <p className="text-sm font-semibold">
                                                {job.type}
                                            </p>
                                            <Badge
                                                variant={
                                                    statusTone[job.status] ??
                                                    "secondary"
                                                }
                                            >
                                                {formatStatus(job.status)}
                                            </Badge>
                                            <span className="text-xs text-muted-foreground">
                                                {job.job_id}
                                            </span>
                                        </div>

                                        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                                            <span>
                                                Queue:{" "}
                                                {job.queue_name ?? "default"}
                                            </span>
                                            <span>
                                                Attempts: {job.attempt_count}/
                                                {job.max_retries}
                                            </span>
                                            <span>
                                                Progress: {job.progress}%
                                            </span>
                                            <span>
                                                Started:{" "}
                                                {formatDate(job.started_at)}
                                            </span>
                                            <span>
                                                Finished:{" "}
                                                {formatDate(job.finished_at)}
                                            </span>
                                        </div>

                                        <div className="h-2 w-full max-w-xl overflow-hidden rounded-full bg-muted">
                                            <div
                                                className="h-full bg-primary transition-all"
                                                style={{
                                                    width: `${Math.max(0, Math.min(job.progress, 100))}%`,
                                                }}
                                            />
                                        </div>

                                        {job.error ? (
                                            <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
                                                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                                                <div>
                                                    <p className="font-semibold">
                                                        {job.error.code ??
                                                            "JOB_ERROR"}
                                                    </p>
                                                    <p>
                                                        {job.error.message ??
                                                            "Unknown worker failure."}
                                                    </p>
                                                </div>
                                            </div>
                                        ) : null}
                                    </div>

                                    <div className="flex gap-2">
                                        <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            disabled={
                                                !canCancel ||
                                                isCancelling ||
                                                isRetrying
                                            }
                                            onClick={() =>
                                                handleCancel(job.job_id)
                                            }
                                            className="gap-1"
                                        >
                                            <Square className="h-3.5 w-3.5" />
                                            {isCancelling
                                                ? "Cancelling..."
                                                : "Cancel"}
                                        </Button>
                                        <Button
                                            type="button"
                                            size="sm"
                                            disabled={
                                                !canRetry ||
                                                isRetrying ||
                                                isCancelling
                                            }
                                            onClick={() =>
                                                handleRetry(job.job_id)
                                            }
                                            className="gap-1"
                                        >
                                            <RotateCcw className="h-3.5 w-3.5" />
                                            {isRetrying
                                                ? "Retrying..."
                                                : "Retry"}
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>
        );
    }

    return (
        <PageWrapper
            title="Job Operations"
            description="Track processing status, inspect failures, and trigger cancel or retry actions."
        >
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Scope</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <Select
                        value={activeProjectId}
                        onValueChange={handleProjectChange}
                        disabled={projectsLoading || projects.length === 0}
                    >
                        <SelectTrigger className="h-10 min-w-[240px] bg-background">
                            <SelectValue
                                placeholder={
                                    projects.length === 0
                                        ? "No project available"
                                        : "Select project"
                                }
                            />
                        </SelectTrigger>
                        <SelectContent>
                            {projects.map((project) => (
                                <SelectItem key={project.id} value={project.id}>
                                    {project.name} ({project.role})
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <TimerReset className="h-4 w-4" />
                        {jobsFetching
                            ? "Refreshing jobs..."
                            : "Auto-refresh every 3s"}
                    </div>
                </CardContent>
            </Card>

            {opsSlo ? <OpsSloPanel snapshot={opsSlo} /> : null}

            {!canMutateJobs && activeProjectId ? (
                <Card>
                    <CardContent className="pt-6 text-sm text-muted-foreground">
                        This project is read-only for your role. Retry and
                        cancel require editor permission.
                    </CardContent>
                </Card>
            ) : null}

            {jobsContent}
        </PageWrapper>
    );
}

function OpsSloPanel({ snapshot }: { snapshot: OpsSloData }) {
    const queued = snapshot.jobs.status_counts.queued ?? 0;
    const running = snapshot.jobs.status_counts.running ?? 0;
    const completed = snapshot.jobs.status_counts.completed ?? 0;
    const failed =
        (snapshot.jobs.status_counts.failed ?? 0) +
        (snapshot.jobs.status_counts.dead_letter ?? 0);

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-muted-foreground" />
                        <CardTitle className="text-base">Operations SLO</CardTitle>
                    </div>
                    <Badge variant={getOpsStatusVariant(snapshot.status)}>
                        {snapshot.status}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-4">
                    <SloMetric label="Queued" value={queued} />
                    <SloMetric label="Running" value={running} />
                    <SloMetric label="Completed" value={completed} />
                    <SloMetric label="Failed" value={failed} />
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-md border p-3">
                        <p className="text-xs font-medium text-muted-foreground">
                            Queue Backlog
                        </p>
                        <div className="mt-2 space-y-2">
                            {snapshot.jobs.queue_counts.length === 0 ? (
                                <p className="text-sm text-muted-foreground">
                                    No active queue backlog.
                                </p>
                            ) : (
                                snapshot.jobs.queue_counts.map((queue) => (
                                    <div
                                        key={queue.queue_name}
                                        className="flex items-center justify-between gap-3 text-sm"
                                    >
                                        <span>{queue.queue_name}</span>
                                        <span className="font-mono text-muted-foreground">
                                            {queue.backlog}
                                        </span>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                    <div className="rounded-md border p-3">
                        <p className="text-xs font-medium text-muted-foreground">
                            Reliability
                        </p>
                        <div className="mt-2 grid gap-2 text-sm">
                            <span>
                                Failure rate:{" "}
                                {(snapshot.jobs.failure_rate * 100).toFixed(1)}%
                            </span>
                            <span>
                                Provider failures:{" "}
                                {snapshot.jobs.provider_failures}
                            </span>
                            <span>
                                Oldest queued:{" "}
                                {formatAge(snapshot.jobs.oldest_queued_age_seconds)}
                            </span>
                        </div>
                    </div>
                </div>

                {snapshot.alerts.length > 0 ? (
                    <div className="grid gap-2">
                        {snapshot.alerts.map((alert) => (
                            <div
                                key={`${alert.code}-${alert.target ?? "global"}`}
                                className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/5 p-3 text-sm"
                            >
                                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <p className="font-medium">{alert.code}</p>
                                        <Badge
                                            variant={
                                                alert.severity === "critical"
                                                    ? "destructive"
                                                    : "warning"
                                            }
                                        >
                                            {alert.severity}
                                        </Badge>
                                    </div>
                                    <p className="text-muted-foreground">
                                        {alert.message}
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : null}
            </CardContent>
        </Card>
    );
}

function SloMetric({ label, value }: { label: string; value: number }) {
    return (
        <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="text-2xl font-semibold">{value}</p>
        </div>
    );
}

function getOpsStatusVariant(status: OpsSloData["status"]) {
    if (status === "critical") return "destructive";
    if (status === "warning") return "warning";
    return "success";
}

function formatAge(value: number | null): string {
    if (value === null) {
        return "-";
    }
    if (value < 60) {
        return `${value}s`;
    }
    const minutes = Math.floor(value / 60);
    const seconds = value % 60;
    return `${minutes}m ${seconds}s`;
}

function formatStatus(status: string): string {
    return status.replaceAll("_", " ");
}

function formatDate(value: string | null): string {
    if (!value) {
        return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString();
}

function compareDates(left: string | null, right: string | null): number {
    const leftTime = left ? new Date(left).getTime() : 0;
    const rightTime = right ? new Date(right).getTime() : 0;
    return leftTime - rightTime;
}
