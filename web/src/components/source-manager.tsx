"use client";

import { FormEvent, useEffect, useState, useMemo } from "react";
import { toast } from "sonner";
import {
    Upload,
    Link2,
    Trash2,
    FileText,
    Folder,
    Globe,
    PlugZap,
    FolderSymlink,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
    deleteProjectIntegrationConnection,
    ingestSourceUrl,
    importProjectIntegrationSource,
    listProjectIntegrations,
    processSources,
    saveProjectIntegrationConnection,
    uploadSourceFile,
    listSources,
    deleteSources,
    startProjectIntegrationOAuth,
    browseGoogleDriveItems,
} from "@/lib/api/client";
import type {
    GoogleDriveBrowseItemData,
    IntegrationConnectionData,
    ProjectRole,
} from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject } from "@/lib/project-store";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { Checkbox } from "@/components/ui/checkbox";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

export function SourceManager() {
    const GOOGLE_DRIVE_FOLDER_PREFIX = "folder:";

    const queryClient = useQueryClient();
    const [activeProjectId, setActiveProjectId] = useState("");
    const [activeProjectName, setActiveProjectName] = useState("");
    const [activeProjectRole, setActiveProjectRole] =
        useState<ProjectRole | null>(null);
    const [url, setUrl] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [busy, setBusy] = useState(false);
    const [integrationBusy, setIntegrationBusy] = useState<string | null>(null);
    const [integrationDrafts, setIntegrationDrafts] = useState<
        Record<
            string,
            {
                accountLabel: string;
                accessToken: string;
                baseUrl: string;
                itemReference: string;
            }
        >
    >({});

    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [drivePickerOpen, setDrivePickerOpen] = useState(false);
    const [drivePickerLoading, setDrivePickerLoading] = useState(false);
    const [drivePickerItems, setDrivePickerItems] = useState<
        GoogleDriveBrowseItemData[]
    >([]);
    const [drivePickerPath, setDrivePickerPath] = useState<
        Array<{ id: string; name: string }>
    >([{ id: "root", name: "My Drive" }]);
    const [drivePickerSearch, setDrivePickerSearch] = useState("");
    const [drivePickerIntegration, setDrivePickerIntegration] =
        useState<IntegrationConnectionData | null>(null);

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
        if (typeof window === "undefined") {
            return;
        }

        const params = new URLSearchParams(window.location.search);
        const provider = params.get("integration");
        const status = params.get("status");
        const message = params.get("message");
        if (!provider || !status) {
            return;
        }

        if (status === "connected") {
            toast.success(`${provider.replace("_", " ")} connected.`);
        } else if (status === "error") {
            toast.error(message || "Integration connection failed.");
        }

        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.delete("integration");
        nextUrl.searchParams.delete("status");
        nextUrl.searchParams.delete("message");
        window.history.replaceState({}, "", nextUrl.toString());
    }, []);

    const {
        data: sourcesData,
        isLoading,
        refetch,
    } = useQuery({
        queryKey: ["sources", activeProjectId],
        queryFn: () => listSources(activeProjectId),
        enabled: !!activeProjectId,
        refetchInterval: 5000, // Poll every 5s to update processing status
    });

    const sources = useMemo(() => sourcesData?.data.items || [], [sourcesData]);

    const {
        data: integrationsData,
        isLoading: loadingIntegrations,
        refetch: refetchIntegrations,
    } = useQuery({
        queryKey: ["integrations", activeProjectId],
        queryFn: () => listProjectIntegrations(activeProjectId),
        enabled: !!activeProjectId,
    });

    const integrations = useMemo(
        () => integrationsData?.data.items || [],
        [integrationsData],
    );

    useEffect(() => {
        if (!integrations.length) {
            return;
        }
        setIntegrationDrafts((current) => {
            const next = { ...current };
            for (const integration of integrations) {
                const existing = next[integration.provider];
                next[integration.provider] = {
                    accountLabel:
                        existing?.accountLabel ??
                        integration.account_label ??
                        "",
                    accessToken: existing?.accessToken ?? "",
                    baseUrl: existing?.baseUrl ?? integration.base_url ?? "",
                    itemReference: existing?.itemReference ?? "",
                };
            }
            return next;
        });
    }, [integrations]);

    function updateIntegrationDraft(
        provider: string,
        field: "accountLabel" | "accessToken" | "baseUrl" | "itemReference",
        value: string,
    ) {
        setIntegrationDrafts((current) => ({
            ...current,
            [provider]: {
                accountLabel: current[provider]?.accountLabel ?? "",
                accessToken: current[provider]?.accessToken ?? "",
                baseUrl: current[provider]?.baseUrl ?? "",
                itemReference: current[provider]?.itemReference ?? "",
                [field]: value,
            },
        }));
    }

    async function loadDrivePickerItems(folderId: string, query?: string) {
        if (!activeProjectId) {
            return;
        }
        setDrivePickerLoading(true);
        try {
            const response = await browseGoogleDriveItems({
                projectId: activeProjectId,
                folderId,
                query,
                pageSize: 100,
            });
            setDrivePickerItems(response.data.items);
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to browse Google Drive.",
            );
        } finally {
            setDrivePickerLoading(false);
        }
    }

    async function handleOpenGoogleDrivePicker(
        integration: IntegrationConnectionData,
    ) {
        if (!activeProjectId) {
            return;
        }
        setDrivePickerIntegration(integration);
        setDrivePickerOpen(true);
        setDrivePickerSearch("");
        setDrivePickerPath([{ id: "root", name: "My Drive" }]);
        await loadDrivePickerItems("root");
    }

    async function handleOpenDriveFolder(item: GoogleDriveBrowseItemData) {
        const nextPath = [...drivePickerPath, { id: item.id, name: item.name }];
        setDrivePickerPath(nextPath);
        await loadDrivePickerItems(item.id, drivePickerSearch);
    }

    async function handleDrivePickerBack() {
        if (drivePickerPath.length <= 1) {
            return;
        }
        const nextPath = drivePickerPath.slice(0, -1);
        const targetFolder = nextPath.at(-1);
        if (!targetFolder) {
            return;
        }
        setDrivePickerPath(nextPath);
        await loadDrivePickerItems(targetFolder.id, drivePickerSearch);
    }

    async function handleDrivePickerSearchSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {
        event.preventDefault();
        const currentFolder = drivePickerPath.at(-1);
        if (!currentFolder) {
            return;
        }
        await loadDrivePickerItems(currentFolder.id, drivePickerSearch);
    }

    function handleSelectDriveFile(item: GoogleDriveBrowseItemData) {
        if (!drivePickerIntegration) {
            return;
        }
        updateIntegrationDraft(
            drivePickerIntegration.provider,
            "itemReference",
            item.id,
        );
        setDrivePickerOpen(false);
        toast.success(`Selected file: ${item.name}`);
    }

    function handleSelectDriveFolder(item: GoogleDriveBrowseItemData) {
        if (!drivePickerIntegration) {
            return;
        }
        updateIntegrationDraft(
            drivePickerIntegration.provider,
            "itemReference",
            `${GOOGLE_DRIVE_FOLDER_PREFIX}${item.id}`,
        );
        setDrivePickerOpen(false);
        toast.success(`Selected folder: ${item.name}`);
    }

    async function resolveGoogleDriveFolderImportTargets(
        folderId: string,
    ): Promise<string[]> {
        if (!activeProjectId) {
            return [];
        }

        const queue: string[] = [folderId];
        const targets: string[] = [];
        const seenFolders = new Set<string>();
        const maxItems = 100;

        while (queue.length > 0 && targets.length < maxItems) {
            const currentFolder = queue.shift();
            if (!currentFolder || seenFolders.has(currentFolder)) {
                continue;
            }
            seenFolders.add(currentFolder);

            let pageToken: string | undefined;
            do {
                const response = await browseGoogleDriveItems({
                    projectId: activeProjectId,
                    folderId: currentFolder,
                    pageToken,
                    pageSize: 100,
                });

                for (const item of response.data.items) {
                    if (item.is_folder) {
                        queue.push(item.id);
                    } else if (item.is_supported_import) {
                        targets.push(item.id);
                        if (targets.length >= maxItems) {
                            break;
                        }
                    }
                }

                pageToken = response.data.next_page_token || undefined;
            } while (pageToken && targets.length < maxItems);
        }

        return targets;
    }

    async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canMutateProject) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        if (!activeProjectId) {
            toast.error("Create or select a project first.");
            return;
        }
        setBusy(true);
        const toastId = toast.loading("Ingesting remote source...");
        try {
            await ingestSourceUrl({ projectId: activeProjectId, url });
            setUrl("");
            await refetch();
            toast.success(`Source ingested. Run processing to index it.`, {
                id: toastId,
            });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to ingest URL.",
                { id: toastId },
            );
        } finally {
            setBusy(false);
        }
    }

    async function handleFileSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canMutateProject) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        if (!activeProjectId) {
            toast.error("Create or select a project first.");
            return;
        }
        if (!file) {
            toast.error("Select a PDF file first.");
            return;
        }
        setBusy(true);
        const toastId = toast.loading("Uploading file...");
        try {
            await uploadSourceFile({ projectId: activeProjectId, file });
            setFile(null);
            await refetch();
            toast.success("File uploaded. Run processing to index it.", {
                id: toastId,
            });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to upload file.",
                { id: toastId },
            );
        } finally {
            setBusy(false);
        }
    }

    async function handleProcessAll() {
        if (!canMutateProject) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        if (!activeProjectId) {
            toast.error("Create or select a project first.");
            return;
        }
        if (sources.length === 0) {
            toast.error("Ingest at least one source before processing.");
            return;
        }
        setBusy(true);
        const toastId = toast.loading("Processing sources...");
        try {
            const response = await processSources({
                projectId: activeProjectId,
                sourceIds: sources.map((s: any) => s.id),
            });
            toast.success(
                `Processing queued. Job ID: ${response.data.job_id}. Progress will update automatically.`,
                { id: toastId },
            );
            await refetch();
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to start processing.",
                { id: toastId },
            );
        } finally {
            setBusy(false);
        }
    }

    async function handleDeleteSelected() {
        if (!canMutateProject) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        if (selectedIds.size === 0) return;
        if (
            !confirm(
                `Are you sure you want to delete ${selectedIds.size} source(s)?`,
            )
        )
            return;

        setBusy(true);
        const toastId = toast.loading("Deleting sources...");
        try {
            await deleteSources(Array.from(selectedIds));
            setSelectedIds(new Set());
            await queryClient.invalidateQueries({
                queryKey: ["sources", activeProjectId],
            });
            await queryClient.invalidateQueries({ queryKey: ["projects"] });
            toast.success("Sources deleted.", { id: toastId });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : "Failed to delete sources.",
                { id: toastId },
            );
        } finally {
            setBusy(false);
        }
    }

    function toggleSelectAll() {
        if (selectedIds.size === sources.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(sources.map((s) => s.id)));
        }
    }

    function toggleSelectOne(id: string) {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) newSet.delete(id);
        else newSet.add(id);
        setSelectedIds(newSet);
    }

    async function handleSaveIntegration(
        integration: IntegrationConnectionData,
    ) {
        if (!canMutateProject) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        if (!activeProjectId) return;
        const draft = integrationDrafts[integration.provider] ?? {
            accountLabel: "",
            accessToken: "",
            baseUrl: "",
            itemReference: "",
        };

        if (!integration.configured && !draft.accessToken.trim()) {
            toast.error(
                "Enter an access token before connecting this integration.",
            );
            return;
        }

        setIntegrationBusy(`${integration.provider}:connect`);
        const toastId = toast.loading(
            `Saving ${integration.display_name} connection...`,
        );
        try {
            await saveProjectIntegrationConnection({
                projectId: activeProjectId,
                provider: integration.provider,
                accessToken: draft.accessToken.trim() || undefined,
                accountLabel: draft.accountLabel.trim() || undefined,
                baseUrl: draft.baseUrl.trim() || undefined,
            });
            updateIntegrationDraft(integration.provider, "accessToken", "");
            await refetchIntegrations();
            toast.success(`${integration.display_name} is ready to import.`, {
                id: toastId,
            });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : `Failed to save ${integration.display_name}.`,
                { id: toastId },
            );
        } finally {
            setIntegrationBusy(null);
        }
    }

    async function handleDisconnectIntegration(
        integration: IntegrationConnectionData,
    ) {
        if (!canMutateProject) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        if (!activeProjectId) return;
        setIntegrationBusy(`${integration.provider}:disconnect`);
        const toastId = toast.loading(
            `Disconnecting ${integration.display_name}...`,
        );
        try {
            await deleteProjectIntegrationConnection({
                projectId: activeProjectId,
                provider: integration.provider,
            });
            await refetchIntegrations();
            toast.success(`${integration.display_name} disconnected.`, {
                id: toastId,
            });
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : `Failed to disconnect ${integration.display_name}.`,
                { id: toastId },
            );
        } finally {
            setIntegrationBusy(null);
        }
    }

    async function handleImportIntegration(
        integration: IntegrationConnectionData,
    ) {
        if (!canMutateProject) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        if (!activeProjectId) return;
        const draft = integrationDrafts[integration.provider] ?? {
            accountLabel: "",
            accessToken: "",
            baseUrl: "",
            itemReference: "",
        };
        const itemReference = draft.itemReference.trim();
        if (!itemReference) {
            toast.error(
                `Enter a ${integration.reference_label.toLowerCase()} first.`,
            );
            return;
        }

        setIntegrationBusy(`${integration.provider}:import`);
        const toastId = toast.loading(
            `Importing from ${integration.display_name}...`,
        );
        try {
            let importedCount = 0;
            let failedCount = 0;

            if (
                integration.provider === "google_drive" &&
                itemReference.startsWith(GOOGLE_DRIVE_FOLDER_PREFIX)
            ) {
                const folderId = itemReference
                    .slice(GOOGLE_DRIVE_FOLDER_PREFIX.length)
                    .trim();
                if (!folderId) {
                    toast.error("Selected folder is invalid.", { id: toastId });
                    return;
                }

                const targets =
                    await resolveGoogleDriveFolderImportTargets(folderId);
                if (!targets.length) {
                    toast.error(
                        "No supported files found in the selected folder.",
                        {
                            id: toastId,
                        },
                    );
                    return;
                }

                for (const targetId of targets) {
                    try {
                        await importProjectIntegrationSource({
                            projectId: activeProjectId,
                            provider: integration.provider,
                            itemReference: targetId,
                        });
                        importedCount += 1;
                    } catch {
                        failedCount += 1;
                    }
                }
            } else {
                await importProjectIntegrationSource({
                    projectId: activeProjectId,
                    provider: integration.provider,
                    itemReference,
                });
                importedCount = 1;
            }

            updateIntegrationDraft(integration.provider, "itemReference", "");
            await refetch();
            if (failedCount > 0) {
                toast.error(
                    `Imported ${importedCount} items, ${failedCount} items failed.`,
                    { id: toastId },
                );
            } else {
                toast.success(
                    `${integration.display_name} content imported. Run processing to index it.`,
                    { id: toastId },
                );
            }
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : `Failed to import from ${integration.display_name}.`,
                { id: toastId },
            );
        } finally {
            setIntegrationBusy(null);
        }
    }

    async function handleOAuthConnect(integration: IntegrationConnectionData) {
        if (!canMutateProject) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        if (!activeProjectId) {
            return;
        }

        setIntegrationBusy(`${integration.provider}:connect`);
        const toastId = toast.loading(
            `Connecting ${integration.display_name}...`,
        );
        try {
            const response = await startProjectIntegrationOAuth({
                projectId: activeProjectId,
                provider: integration.provider,
            });
            window.location.href = response.data.redirect_url;
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : `Failed to start ${integration.display_name} OAuth flow.`,
                { id: toastId },
            );
            setIntegrationBusy(null);
        }
    }

    if (!activeProjectId) {
        return (
            <PageWrapper
                title="Knowledge Sources"
                description="Manage documents to feed into the AI."
            >
                <Card className="border-dashed shadow-none bg-muted/30">
                    <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                        <div className="rounded-full bg-primary/10 p-3 mb-4">
                            <FileText className="h-6 w-6 text-primary" />
                        </div>
                        <h3 className="text-lg font-medium mb-1">
                            No Active Project
                        </h3>
                        <p className="text-sm text-muted-foreground max-w-sm mb-4">
                            You need to select or create a project before you
                            can manage sources.
                        </p>
                        <Button
                            onClick={() => (window.location.href = "/projects")}
                        >
                            Go to Projects
                        </Button>
                    </CardContent>
                </Card>
            </PageWrapper>
        );
    }

    return (
        <PageWrapper
            title="Knowledge Sources"
            description={`Manage documents for: ${activeProjectName}`}
        >
            {!canMutateProject ? (
                <div className="mb-4 rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
                    You have viewer access for this project. Upload, import,
                    processing, and delete actions are disabled.
                </div>
            ) : null}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column: Input Forms */}
                <div className="flex flex-col gap-6 lg:col-span-1">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Upload className="h-4 w-4" /> Upload PDF
                            </CardTitle>
                            <CardDescription>
                                Upload local files for processing.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form
                                onSubmit={handleFileSubmit}
                                className="flex flex-col gap-4"
                            >
                                <div className="flex flex-col gap-1.5">
                                    <Label htmlFor="file-upload">
                                        Select File
                                    </Label>
                                    <Input
                                        id="file-upload"
                                        type="file"
                                        accept=".pdf,application/pdf"
                                        onChange={(e) =>
                                            setFile(e.target.files?.[0] || null)
                                        }
                                        disabled={busy || !canMutateProject}
                                        className="cursor-pointer"
                                    />
                                    {file && (
                                        <p className="text-xs text-muted-foreground mt-1 text-right">
                                            {Math.round(file.size / 1024)} KB
                                        </p>
                                    )}
                                </div>
                                <Button
                                    type="submit"
                                    disabled={
                                        !file || busy || !canMutateProject
                                    }
                                    title={
                                        canMutateProject
                                            ? undefined
                                            : "Requires editor role"
                                    }
                                    className="w-full"
                                >
                                    {busy && file ? (
                                        <Spinner size="sm" className="mr-2" />
                                    ) : null}
                                    Upload to Project
                                </Button>
                            </form>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Link2 className="h-4 w-4" /> Web Source
                            </CardTitle>
                            <CardDescription>
                                Ingest content from a URL.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form
                                onSubmit={handleUrlSubmit}
                                className="flex flex-col gap-4"
                            >
                                <div className="flex flex-col gap-1.5">
                                    <Label htmlFor="url-input">
                                        Source URL
                                    </Label>
                                    <Input
                                        id="url-input"
                                        type="url"
                                        placeholder="https://example.com/article"
                                        value={url}
                                        onChange={(e) => setUrl(e.target.value)}
                                        required
                                        disabled={busy || !canMutateProject}
                                    />
                                </div>
                                <Button
                                    type="submit"
                                    disabled={!url || busy || !canMutateProject}
                                    title={
                                        canMutateProject
                                            ? undefined
                                            : "Requires editor role"
                                    }
                                    variant="outline"
                                    className="w-full"
                                >
                                    {busy && url ? (
                                        <Spinner size="sm" className="mr-2" />
                                    ) : null}
                                    Ingest URL
                                </Button>
                            </form>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <PlugZap className="h-4 w-4" /> One-Click
                                Integrations
                            </CardTitle>
                            <CardDescription>
                                Connect Google Drive, then import a file
                                directly into this project.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="flex flex-col gap-4">
                            {loadingIntegrations ? (
                                <div className="flex justify-center py-6">
                                    <Spinner size="sm" />
                                </div>
                            ) : (
                                integrations.map((integration) => {
                                    const draft = integrationDrafts[
                                        integration.provider
                                    ] ?? {
                                        accountLabel: "",
                                        accessToken: "",
                                        baseUrl: "",
                                        itemReference: "",
                                    };

                                    return (
                                        <div
                                            key={integration.provider}
                                            className="rounded-xl border border-border bg-muted/20 p-4"
                                        >
                                            <div className="flex items-start gap-3">
                                                <div className="mt-0.5 rounded-lg bg-primary/10 p-2">
                                                    <FolderSymlink className="h-4 w-4 text-primary" />
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <h3 className="text-sm font-semibold">
                                                            {
                                                                integration.display_name
                                                            }
                                                        </h3>
                                                        <Badge
                                                            variant={
                                                                integration.configured
                                                                    ? "success"
                                                                    : "outline"
                                                            }
                                                        >
                                                            {integration.configured
                                                                ? "Connected"
                                                                : "Not connected"}
                                                        </Badge>
                                                    </div>
                                                    <p className="mt-1 text-xs text-muted-foreground">
                                                        {
                                                            integration.description
                                                        }
                                                    </p>
                                                </div>
                                            </div>

                                            <div className="mt-4 grid gap-3">
                                                {integration.supports_oauth ? (
                                                    <div className="rounded-lg border border-dashed border-border bg-background/70 p-3 text-sm">
                                                        <p className="font-medium">
                                                            OAuth connection
                                                        </p>
                                                        <p className="mt-1 text-xs text-muted-foreground">
                                                            Click connect to
                                                            authorize{" "}
                                                            {
                                                                integration.display_name
                                                            }{" "}
                                                            with your Google
                                                            account. Access and
                                                            refresh tokens are
                                                            stored automatically
                                                            after approval.
                                                        </p>
                                                        {integration.configured ? (
                                                            <p className="mt-2 text-xs text-muted-foreground">
                                                                Connected as{" "}
                                                                <span className="font-medium text-foreground">
                                                                    {integration.account_label ||
                                                                        integration.display_name}
                                                                </span>
                                                            </p>
                                                        ) : null}
                                                    </div>
                                                ) : (
                                                    <>
                                                        <div className="grid gap-1.5">
                                                            <Label
                                                                htmlFor={`${integration.provider}-account`}
                                                            >
                                                                Account label
                                                            </Label>
                                                            <Input
                                                                id={`${integration.provider}-account`}
                                                                value={
                                                                    draft.accountLabel
                                                                }
                                                                onChange={(
                                                                    event,
                                                                ) =>
                                                                    updateIntegrationDraft(
                                                                        integration.provider,
                                                                        "accountLabel",
                                                                        event
                                                                            .target
                                                                            .value,
                                                                    )
                                                                }
                                                                placeholder={`${integration.display_name} workspace`}
                                                                disabled={
                                                                    !canMutateProject
                                                                }
                                                            />
                                                        </div>
                                                        {integration.supports_base_url ? (
                                                            <div className="grid gap-1.5">
                                                                <Label
                                                                    htmlFor={`${integration.provider}-base-url`}
                                                                >
                                                                    Base URL
                                                                </Label>
                                                                <Input
                                                                    id={`${integration.provider}-base-url`}
                                                                    value={
                                                                        draft.baseUrl
                                                                    }
                                                                    onChange={(
                                                                        event,
                                                                    ) =>
                                                                        updateIntegrationDraft(
                                                                            integration.provider,
                                                                            "baseUrl",
                                                                            event
                                                                                .target
                                                                                .value,
                                                                        )
                                                                    }
                                                                    placeholder="https://your-domain.atlassian.net"
                                                                    disabled={
                                                                        !canMutateProject
                                                                    }
                                                                />
                                                            </div>
                                                        ) : null}
                                                        <div className="grid gap-1.5">
                                                            <Label
                                                                htmlFor={`${integration.provider}-token`}
                                                            >
                                                                Access token
                                                            </Label>
                                                            <Input
                                                                id={`${integration.provider}-token`}
                                                                type="password"
                                                                value={
                                                                    draft.accessToken
                                                                }
                                                                onChange={(
                                                                    event,
                                                                ) =>
                                                                    updateIntegrationDraft(
                                                                        integration.provider,
                                                                        "accessToken",
                                                                        event
                                                                            .target
                                                                            .value,
                                                                    )
                                                                }
                                                                placeholder={
                                                                    integration.configured
                                                                        ? `Saved token: ${integration.masked_access_token || "configured"}`
                                                                        : "Paste access token"
                                                                }
                                                                disabled={
                                                                    !canMutateProject
                                                                }
                                                            />
                                                        </div>
                                                    </>
                                                )}
                                                <div className="flex flex-wrap gap-2">
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        onClick={() =>
                                                            integration.supports_oauth
                                                                ? handleOAuthConnect(
                                                                      integration,
                                                                  )
                                                                : void handleSaveIntegration(
                                                                      integration,
                                                                  )
                                                        }
                                                        disabled={
                                                            !canMutateProject ||
                                                            integrationBusy ===
                                                                `${integration.provider}:connect`
                                                        }
                                                        title={
                                                            canMutateProject
                                                                ? undefined
                                                                : "Requires editor role"
                                                        }
                                                    >
                                                        {integration.supports_oauth
                                                            ? integration.configured
                                                                ? "Reconnect with Google"
                                                                : "Connect with Google"
                                                            : integrationBusy ===
                                                                `${integration.provider}:connect`
                                                              ? "Saving..."
                                                              : integration.configured
                                                                ? "Update connection"
                                                                : "Connect"}
                                                    </Button>
                                                    {integration.configured ? (
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() =>
                                                                void handleDisconnectIntegration(
                                                                    integration,
                                                                )
                                                            }
                                                            disabled={
                                                                !canMutateProject ||
                                                                integrationBusy ===
                                                                    `${integration.provider}:disconnect`
                                                            }
                                                        >
                                                            {integrationBusy ===
                                                            `${integration.provider}:disconnect`
                                                                ? "Disconnecting..."
                                                                : "Disconnect"}
                                                        </Button>
                                                    ) : null}
                                                </div>
                                                <Separator />
                                                {integration.provider ===
                                                "google_drive" ? (
                                                    <div className="flex items-center justify-between gap-2 rounded-md border border-dashed border-border bg-background/60 p-2">
                                                        <p className="text-xs text-muted-foreground">
                                                            Use picker to choose
                                                            a file or folder
                                                            directly from Drive.
                                                        </p>
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() =>
                                                                void handleOpenGoogleDrivePicker(
                                                                    integration,
                                                                )
                                                            }
                                                            disabled={
                                                                !integration.configured ||
                                                                !canMutateProject
                                                            }
                                                        >
                                                            Browse Drive
                                                        </Button>
                                                    </div>
                                                ) : null}
                                                <div className="grid gap-1.5">
                                                    <Label
                                                        htmlFor={`${integration.provider}-reference`}
                                                    >
                                                        {
                                                            integration.reference_label
                                                        }
                                                    </Label>
                                                    <Input
                                                        id={`${integration.provider}-reference`}
                                                        value={
                                                            draft.itemReference
                                                        }
                                                        onChange={(event) =>
                                                            updateIntegrationDraft(
                                                                integration.provider,
                                                                "itemReference",
                                                                event.target
                                                                    .value,
                                                            )
                                                        }
                                                        placeholder={
                                                            integration.reference_label
                                                        }
                                                        disabled={
                                                            !integration.configured ||
                                                            !canMutateProject
                                                        }
                                                    />
                                                    <p className="text-xs text-muted-foreground">
                                                        Supports Google Docs,
                                                        PDF files, and plain
                                                        text files from Drive.
                                                        Selecting a folder
                                                        imports supported files
                                                        inside that folder tree.
                                                    </p>
                                                </div>
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="secondary"
                                                    onClick={() =>
                                                        void handleImportIntegration(
                                                            integration,
                                                        )
                                                    }
                                                    disabled={
                                                        !integration.configured ||
                                                        !canMutateProject ||
                                                        integrationBusy ===
                                                            `${integration.provider}:import`
                                                    }
                                                    title={
                                                        canMutateProject
                                                            ? undefined
                                                            : "Requires editor role"
                                                    }
                                                >
                                                    {integrationBusy ===
                                                    `${integration.provider}:import`
                                                        ? "Importing..."
                                                        : "Import into project"}
                                                </Button>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Right Column: Source List */}
                <div className="lg:col-span-2">
                    <Card className="h-full flex flex-col">
                        <CardHeader className="pb-3 break-words flex flex-row items-center justify-between">
                            <div>
                                <CardTitle className="text-base">
                                    Project Sources
                                </CardTitle>
                                <CardDescription>
                                    All sources ingested into this project.
                                </CardDescription>
                            </div>
                            <div className="flex items-center gap-2">
                                {selectedIds.size > 0 && (
                                    <Button
                                        variant="destructive"
                                        size="sm"
                                        onClick={handleDeleteSelected}
                                        disabled={busy || !canMutateProject}
                                        title={
                                            canMutateProject
                                                ? undefined
                                                : "Requires editor role"
                                        }
                                    >
                                        <Trash2 className="h-4 w-4 mr-1" />
                                        Delete ({selectedIds.size})
                                    </Button>
                                )}
                                <Button
                                    onClick={handleProcessAll}
                                    disabled={
                                        busy ||
                                        sources.length === 0 ||
                                        !canMutateProject
                                    }
                                    title={
                                        canMutateProject
                                            ? undefined
                                            : "Requires editor role"
                                    }
                                    size="sm"
                                >
                                    {busy && !file && !url ? (
                                        <Spinner size="sm" className="mr-2" />
                                    ) : null}
                                    Process All
                                </Button>
                            </div>
                        </CardHeader>
                        <Separator />
                        <CardContent className="p-0 overflow-auto flex-1 min-h-[300px]">
                            {isLoading ? (
                                <div className="flex items-center justify-center h-full min-h-[200px]">
                                    <Spinner />
                                </div>
                            ) : sources.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-full text-center p-8 text-muted-foreground min-h-[200px]">
                                    <Globe className="h-8 w-8 mb-3 opacity-20" />
                                    <p>No sources yet.</p>
                                    <p className="text-sm">
                                        Upload a file or add a URL to get
                                        started.
                                    </p>
                                </div>
                            ) : (
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="w-12 text-center">
                                                <Checkbox
                                                    checked={
                                                        selectedIds.size ===
                                                            sources.length &&
                                                        sources.length > 0
                                                    }
                                                    onCheckedChange={
                                                        toggleSelectAll
                                                    }
                                                    aria-label="Select all"
                                                />
                                            </TableHead>
                                            <TableHead>File / URL</TableHead>
                                            <TableHead className="w-24">
                                                Type
                                            </TableHead>
                                            <TableHead className="w-32">
                                                Status
                                            </TableHead>
                                            <TableHead className="w-32 hidden md:table-cell">
                                                Date
                                            </TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {sources.map((source) => (
                                            <TableRow
                                                key={source.id}
                                                className="group"
                                            >
                                                <TableCell className="text-center">
                                                    <Checkbox
                                                        checked={selectedIds.has(
                                                            source.id,
                                                        )}
                                                        onCheckedChange={() =>
                                                            toggleSelectOne(
                                                                source.id,
                                                            )
                                                        }
                                                        aria-label={`Select ${source.file_name}`}
                                                    />
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    <div className="flex items-center gap-2 px-1 max-w-[200px] sm:max-w-xs md:max-w-sm lg:max-w-md truncate">
                                                        {source.type ===
                                                        "url" ? (
                                                            <Globe className="h-3 w-3 text-muted-foreground shrink-0" />
                                                        ) : (
                                                            <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                                                        )}
                                                        <span
                                                            className="truncate"
                                                            title={
                                                                source.file_name
                                                            }
                                                        >
                                                            {source.file_name}
                                                        </span>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge
                                                        variant="outline"
                                                        className="uppercase text-[10px] tracking-wider"
                                                    >
                                                        {source.provider ||
                                                            source.type}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    {source.status ===
                                                    "completed" ? (
                                                        <Badge
                                                            variant="success"
                                                            className="font-normal"
                                                        >
                                                            Completed
                                                        </Badge>
                                                    ) : source.status ===
                                                          "processing" ||
                                                      source.status ===
                                                          "chunking" ||
                                                      source.status ===
                                                          "embedding" ? (
                                                        <Badge
                                                            variant="secondary"
                                                            className="font-normal bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                                                        >
                                                            <Spinner
                                                                size="sm"
                                                                className="mr-1 inline-block"
                                                            />
                                                            {source.status}
                                                        </Badge>
                                                    ) : source.status ===
                                                      "failed" ? (
                                                        <Badge
                                                            variant="destructive"
                                                            className="font-normal"
                                                        >
                                                            Failed
                                                        </Badge>
                                                    ) : (
                                                        <Badge
                                                            variant="outline"
                                                            className="font-normal text-muted-foreground"
                                                        >
                                                            {source.status ||
                                                                "Pending"}
                                                        </Badge>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-xs text-muted-foreground hidden md:table-cell">
                                                    {source.created_at
                                                        ? new Date(
                                                              source.created_at,
                                                          ).toLocaleDateString()
                                                        : ""}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            )}
                        </CardContent>
                    </Card>
                </div>
            </div>
            {drivePickerOpen ? (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
                    <div className="w-full max-w-3xl rounded-xl border border-border bg-background shadow-xl">
                        <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
                            <div>
                                <h3 className="text-sm font-semibold">
                                    Google Drive Picker
                                </h3>
                                <p className="text-xs text-muted-foreground">
                                    Select one file to import immediately, or
                                    select a folder to import all supported
                                    files inside it.
                                </p>
                            </div>
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => setDrivePickerOpen(false)}
                            >
                                Close
                            </Button>
                        </div>

                        <div className="border-b px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                <span className="font-medium text-foreground">
                                    Path:
                                </span>
                                {drivePickerPath.map((segment, index) => (
                                    <span key={`${segment.id}-${index}`}>
                                        {index > 0 ? " / " : ""}
                                        {segment.name}
                                    </span>
                                ))}
                            </div>
                            <form
                                className="mt-2 flex flex-col gap-2 sm:flex-row"
                                onSubmit={handleDrivePickerSearchSubmit}
                            >
                                <Input
                                    value={drivePickerSearch}
                                    onChange={(event) =>
                                        setDrivePickerSearch(event.target.value)
                                    }
                                    placeholder="Search in current folder"
                                />
                                <div className="flex gap-2">
                                    <Button
                                        type="submit"
                                        size="sm"
                                        variant="outline"
                                        disabled={drivePickerLoading}
                                    >
                                        Search
                                    </Button>
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant="ghost"
                                        disabled={drivePickerLoading}
                                        onClick={() => {
                                            const currentFolder =
                                                drivePickerPath.at(-1);
                                            if (!currentFolder) {
                                                return;
                                            }
                                            setDrivePickerSearch("");
                                            void loadDrivePickerItems(
                                                currentFolder.id,
                                            );
                                        }}
                                    >
                                        Clear
                                    </Button>
                                </div>
                            </form>
                        </div>

                        <div className="max-h-[420px] overflow-y-auto px-4 py-3">
                            <div className="mb-3 flex items-center gap-2">
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    onClick={() => void handleDrivePickerBack()}
                                    disabled={
                                        drivePickerPath.length <= 1 ||
                                        drivePickerLoading
                                    }
                                >
                                    Back
                                </Button>
                                {drivePickerPath.length > 1 ? (
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant="secondary"
                                        disabled={drivePickerLoading}
                                        onClick={() => {
                                            const currentFolder =
                                                drivePickerPath.at(-1);
                                            if (!currentFolder) {
                                                return;
                                            }
                                            handleSelectDriveFolder({
                                                id: currentFolder.id,
                                                name: currentFolder.name,
                                                mime_type:
                                                    "application/vnd.google-apps.folder",
                                                web_view_link: "",
                                                modified_time: null,
                                                size: null,
                                                icon_link: null,
                                                is_folder: true,
                                                is_supported_import: false,
                                            });
                                        }}
                                    >
                                        Select This Folder
                                    </Button>
                                ) : null}
                            </div>

                            {drivePickerLoading ? (
                                <div className="flex items-center justify-center py-12">
                                    <Spinner />
                                </div>
                            ) : drivePickerItems.length === 0 ? (
                                <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
                                    No items found in this folder.
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {drivePickerItems.map((item) => (
                                        <div
                                            key={item.id}
                                            className="flex flex-col gap-2 rounded-md border px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                                        >
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2">
                                                    {item.is_folder ? (
                                                        <Folder className="h-4 w-4 text-amber-600" />
                                                    ) : (
                                                        <FileText className="h-4 w-4 text-muted-foreground" />
                                                    )}
                                                    <p
                                                        className="truncate text-sm font-medium"
                                                        title={item.name}
                                                    >
                                                        {item.name}
                                                    </p>
                                                </div>
                                                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                                    <span>
                                                        {item.mime_type}
                                                    </span>
                                                    {item.size ? (
                                                        <span>
                                                            {(
                                                                Number(
                                                                    item.size,
                                                                ) / 1024
                                                            ).toFixed(1)}{" "}
                                                            KB
                                                        </span>
                                                    ) : null}
                                                    {item.is_supported_import ? (
                                                        <Badge variant="outline">
                                                            Supported
                                                        </Badge>
                                                    ) : null}
                                                </div>
                                            </div>
                                            <div className="flex gap-2">
                                                {item.is_folder ? (
                                                    <>
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() =>
                                                                void handleOpenDriveFolder(
                                                                    item,
                                                                )
                                                            }
                                                        >
                                                            Open
                                                        </Button>
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="secondary"
                                                            onClick={() =>
                                                                handleSelectDriveFolder(
                                                                    item,
                                                                )
                                                            }
                                                        >
                                                            Select Folder
                                                        </Button>
                                                    </>
                                                ) : (
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        disabled={
                                                            !item.is_supported_import
                                                        }
                                                        onClick={() =>
                                                            handleSelectDriveFile(
                                                                item,
                                                            )
                                                        }
                                                    >
                                                        Select File
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            ) : null}
        </PageWrapper>
    );
}
