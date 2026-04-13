"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bot, Download, GitBranchPlus, Plus } from "lucide-react";

import {
    breakDownIntelligenceEvent,
    createIntelligenceAction,
    createShareLink,
    exportIntelligenceActions,
    listIntelligenceActions,
    listIntelligenceEvents,
    listOrganizationMembers,
    listShareLinks,
    revokeShareLink,
    updateIntelligenceAction,
} from "@/lib/api/client";
import type { IntelligenceActionData } from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject } from "@/lib/project-store";

import { useOrganization } from "@/components/organization-provider";
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
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

interface TaskNode extends IntelligenceActionData {
    children: TaskNode[];
}

function downloadJsonFile(data: unknown, filename: string) {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

export function IntelligenceTaskManager() {
    const queryClient = useQueryClient();
    const { activeOrganization } = useOrganization();

    const activeProject = getActiveProject();
    const projectId = activeProject?.id ?? "";
    const projectRole = activeProject?.role;
    const canMutate = canEditProject(projectRole);

    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [eventId, setEventId] = useState("");
    const [creating, setCreating] = useState(false);
    const [shareExpiryHours, setShareExpiryHours] = useState(72);

    const { data: actionsData, isLoading: actionsLoading } = useQuery({
        queryKey: ["intelligence-actions", projectId],
        queryFn: () => listIntelligenceActions({ projectId }),
        enabled: Boolean(projectId),
    });

    const { data: eventsData } = useQuery({
        queryKey: ["intelligence-events", projectId],
        queryFn: () => listIntelligenceEvents({ projectId, sinceHours: 168 }),
        enabled: Boolean(projectId),
    });

    const { data: membersData } = useQuery({
        queryKey: ["org-members", activeOrganization?.id],
        queryFn: () => listOrganizationMembers(activeOrganization!.id),
        enabled: Boolean(activeOrganization?.id),
    });

    const { data: shareLinksData } = useQuery({
        queryKey: ["share-links", projectId],
        queryFn: () => listShareLinks(projectId),
        enabled: Boolean(projectId),
    });

    const actions = actionsData?.data.items ?? [];
    const events = eventsData?.data.items ?? [];
    const members = membersData?.data.items ?? [];
    const shareLinks = shareLinksData?.data.items ?? [];

    const taskTree = useMemo(() => {
        const map = new Map<string, TaskNode>();
        for (const action of actions) {
            map.set(action.action_id, { ...action, children: [] });
        }

        const roots: TaskNode[] = [];
        for (const node of map.values()) {
            if (node.parent_action_id && map.has(node.parent_action_id)) {
                const parent = map.get(node.parent_action_id);
                if (parent) {
                    parent.children.push(node);
                } else {
                    roots.push(node);
                }
            } else {
                roots.push(node);
            }
        }

        const sortFn = (a: TaskNode, b: TaskNode) => {
            const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
            const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
            return bTime - aTime;
        };

        function sortChildren(node: TaskNode) {
            node.children.sort(sortFn);
            node.children.forEach(sortChildren);
        }

        roots.sort(sortFn);
        roots.forEach(sortChildren);
        return roots;
    }, [actions]);

    async function reloadActions() {
        await queryClient.invalidateQueries({
            queryKey: ["intelligence-actions", projectId],
        });
    }

    async function handleCreateTask(event: { preventDefault: () => void }) {
        event.preventDefault();
        if (!projectId) {
            toast.error("Select a project first.");
            return;
        }
        if (!canMutate) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        setCreating(true);
        const toastId = toast.loading("Creating task...");
        try {
            await createIntelligenceAction({
                projectId,
                title,
                description,
                eventId: eventId || undefined,
                priority: "medium",
            });
            setTitle("");
            setDescription("");
            setEventId("");
            await reloadActions();
            toast.success("Task created.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to create task.",
                { id: toastId },
            );
        } finally {
            setCreating(false);
        }
    }

    async function handleBreakdown(targetEventId: string) {
        if (!canMutate) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        const toastId = toast.loading("Generating AI task breakdown...");
        try {
            await breakDownIntelligenceEvent({
                projectId,
                eventId: targetEventId,
            });
            await reloadActions();
            toast.success("AI breakdown completed.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to break down event.",
                { id: toastId },
            );
        }
    }

    async function handleAddSubtask(parentActionId: string) {
        if (!canMutate) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        const subtaskTitle = prompt("Sub-task title");
        if (!subtaskTitle) return;

        const toastId = toast.loading("Creating sub-task...");
        try {
            await createIntelligenceAction({
                projectId,
                title: subtaskTitle,
                description: "Generated as a sub-task",
                parentActionId,
                priority: "medium",
            });
            await reloadActions();
            toast.success("Sub-task created.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to create sub-task.",
                { id: toastId },
            );
        }
    }

    async function handleStatusChange(
        actionId: string,
        status: IntelligenceActionData["status"],
    ) {
        try {
            await updateIntelligenceAction({ projectId, actionId, status });
            await reloadActions();
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to update status.",
            );
        }
    }

    async function handleAssign(actionId: string, assignedUserId: string) {
        try {
            await updateIntelligenceAction({
                projectId,
                actionId,
                assignedUserId: assignedUserId || undefined,
                owner: members.find((m) => m.user_id === assignedUserId)
                    ?.display_name,
            });
            await reloadActions();
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to assign member.",
            );
        }
    }

    async function handleExportJson() {
        try {
            const response = await exportIntelligenceActions({
                projectId,
                format: "json",
            });
            downloadJsonFile(
                response.data.items,
                `intelligence-actions-${projectId}.json`,
            );
            toast.success("Task export completed.");
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to export actions.",
            );
        }
    }

    async function handleCreateShareLink() {
        if (!canMutate) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        const toastId = toast.loading("Creating share link...");
        try {
            await createShareLink({
                projectId,
                targetType: "actions",
                expiresInHours: shareExpiryHours,
            });
            await queryClient.invalidateQueries({
                queryKey: ["share-links", projectId],
            });
            toast.success("Share link created.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to create share link.",
                { id: toastId },
            );
        }
    }

    async function handleRevokeShareLink(linkId: string) {
        const toastId = toast.loading("Revoking share link...");
        try {
            await revokeShareLink({ projectId, linkId });
            await queryClient.invalidateQueries({
                queryKey: ["share-links", projectId],
            });
            toast.success("Share link revoked.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to revoke link.",
                { id: toastId },
            );
        }
    }

    function renderNode(node: TaskNode, depth: number) {
        return (
            <div key={node.action_id} className="space-y-2">
                <div
                    className="rounded-md border p-3"
                    style={{ marginLeft: `${depth * 16}px` }}
                >
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                        <p className="font-medium">{node.title}</p>
                        <Badge variant="secondary">{node.status}</Badge>
                        <Badge variant="outline">{node.priority}</Badge>
                        {node.owner ? <Badge>{node.owner}</Badge> : null}
                    </div>
                    <p className="mb-3 text-sm text-muted-foreground">
                        {node.description}
                    </p>

                    <div className="flex flex-wrap items-center gap-2">
                        <select
                            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                            value={node.status}
                            onChange={(e) =>
                                handleStatusChange(
                                    node.action_id,
                                    e.target
                                        .value as IntelligenceActionData["status"],
                                )
                            }
                            disabled={!canMutate}
                        >
                            <option value="open">open</option>
                            <option value="in_progress">in_progress</option>
                            <option value="done">done</option>
                            <option value="escalated">escalated</option>
                        </select>

                        <select
                            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                            value={node.assigned_user_id ?? ""}
                            onChange={(e) =>
                                handleAssign(node.action_id, e.target.value)
                            }
                            disabled={!canMutate}
                        >
                            <option value="">Unassigned</option>
                            {members.map((member) => (
                                <option
                                    key={member.user_id}
                                    value={member.user_id}
                                >
                                    {member.display_name} ({member.role})
                                </option>
                            ))}
                        </select>

                        <Button
                            size="sm"
                            variant="outline"
                            className="h-8 gap-1 text-xs"
                            onClick={() => handleAddSubtask(node.action_id)}
                            disabled={!canMutate}
                        >
                            <GitBranchPlus className="h-3.5 w-3.5" />
                            Sub-task
                        </Button>
                    </div>
                </div>
                {node.children.map((child) => renderNode(child, depth + 1))}
            </div>
        );
    }

    return (
        <PageWrapper
            title="Action Tasks"
            description={
                activeProject
                    ? `Break task, assign owners, and track execution for project ${activeProject.name}.`
                    : "Select a project to manage intelligence tasks."
            }
        >
            <div className="grid gap-6 lg:grid-cols-3">
                <div className="space-y-6 lg:col-span-1">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">
                                Create Task
                            </CardTitle>
                            <CardDescription>
                                Create a top-level action or attach it to a
                                detected event.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form
                                onSubmit={handleCreateTask}
                                className="space-y-3"
                            >
                                <div className="space-y-1">
                                    <Label>Title</Label>
                                    <Input
                                        value={title}
                                        onChange={(e) =>
                                            setTitle(e.target.value)
                                        }
                                        required
                                        disabled={!canMutate || creating}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label>Description</Label>
                                    <Textarea
                                        value={description}
                                        onChange={(e) =>
                                            setDescription(e.target.value)
                                        }
                                        rows={3}
                                        disabled={!canMutate || creating}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label>Related Event (optional)</Label>
                                    <select
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                                        value={eventId}
                                        onChange={(e) =>
                                            setEventId(e.target.value)
                                        }
                                        disabled={!canMutate || creating}
                                    >
                                        <option value="">No event</option>
                                        {events.map((eventRow) => (
                                            <option
                                                key={eventRow.event_id}
                                                value={eventRow.event_id}
                                            >
                                                {eventRow.title}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <Button
                                    type="submit"
                                    className="w-full gap-2"
                                    disabled={
                                        !canMutate || creating || !projectId
                                    }
                                >
                                    {creating ? (
                                        <Spinner size="sm" />
                                    ) : (
                                        <Plus className="h-4 w-4" />
                                    )}
                                    {creating ? "Creating..." : "Create Task"}
                                </Button>
                            </form>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">
                                Automation
                            </CardTitle>
                            <CardDescription>
                                Generate sub-task checklist from a radar event.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            {events.slice(0, 5).map((eventRow) => (
                                <Button
                                    key={eventRow.event_id}
                                    variant="outline"
                                    size="sm"
                                    className="w-full justify-start gap-2"
                                    onClick={() =>
                                        handleBreakdown(eventRow.event_id)
                                    }
                                    disabled={!canMutate}
                                >
                                    <Bot className="h-3.5 w-3.5" />
                                    <span className="truncate">
                                        {eventRow.title}
                                    </span>
                                </Button>
                            ))}
                            {events.length === 0 ? (
                                <p className="text-xs text-muted-foreground">
                                    No recent event available.
                                </p>
                            ) : null}
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Share</CardTitle>
                            <CardDescription>
                                Create read-only public links for task board
                                export.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="space-y-1">
                                <Label>Expiry (hours)</Label>
                                <Input
                                    type="number"
                                    min={1}
                                    value={shareExpiryHours}
                                    onChange={(e) =>
                                        setShareExpiryHours(
                                            Number(e.target.value) || 72,
                                        )
                                    }
                                    disabled={!canMutate}
                                />
                            </div>
                            <Button
                                className="w-full"
                                onClick={handleCreateShareLink}
                                disabled={!canMutate || !projectId}
                            >
                                Create Share Link
                            </Button>

                            <div className="space-y-2">
                                {shareLinks.slice(0, 5).map((link) => (
                                    <div
                                        key={link.link_id}
                                        className="rounded-md border p-2 text-xs"
                                    >
                                        <p className="truncate text-muted-foreground">
                                            {link.url_path}
                                        </p>
                                        <div className="mt-2 flex items-center justify-between">
                                            <Badge
                                                variant={
                                                    link.is_revoked
                                                        ? "secondary"
                                                        : "default"
                                                }
                                            >
                                                {link.is_revoked
                                                    ? "revoked"
                                                    : "active"}
                                            </Badge>
                                            {link.is_revoked ? null : (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() =>
                                                        handleRevokeShareLink(
                                                            link.link_id,
                                                        )
                                                    }
                                                >
                                                    Revoke
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                ))}
                                {shareLinks.length === 0 ? (
                                    <p className="text-xs text-muted-foreground">
                                        No share links created yet.
                                    </p>
                                ) : null}
                            </div>
                        </CardContent>
                    </Card>
                </div>

                <div className="lg:col-span-2">
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <CardTitle className="text-base">
                                        Task Tree
                                    </CardTitle>
                                    <CardDescription>
                                        Hierarchical view of action and sub-task
                                        assignments.
                                    </CardDescription>
                                </div>
                                <Button
                                    variant="secondary"
                                    size="sm"
                                    className="gap-2"
                                    onClick={handleExportJson}
                                    disabled={!projectId}
                                >
                                    <Download className="h-3.5 w-3.5" />
                                    Export JSON
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {(() => {
                                let content: ReactNode;
                                if (actionsLoading) {
                                    content = (
                                        <div className="flex justify-center py-6">
                                            <Spinner />
                                        </div>
                                    );
                                } else if (taskTree.length === 0) {
                                    content = (
                                        <p className="text-sm text-muted-foreground">
                                            No tasks yet. Create one to start
                                            tracking execution.
                                        </p>
                                    );
                                } else {
                                    content = taskTree.map((node) =>
                                        renderNode(node, 0),
                                    );
                                }
                                return content;
                            })()}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </PageWrapper>
    );
}
