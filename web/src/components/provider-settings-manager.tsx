"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Bot,
  Brain,
  KeyRound,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
} from "lucide-react";

import {
  createPersonalToken,
  deleteProjectProviderKey,
  discoverProjectProviderModels,
  listProjectProviderSettings,
  saveProjectProviderKey,
} from "@/lib/api/client";
import type { ProjectRole, ProviderSettingData } from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject } from "@/lib/project-store";
import { useAuth } from "@/components/auth-provider";

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

const providerIcons = {
  openai: Sparkles,
  gemini: Bot,
} as const;

type ModelCatalog = {
  chatModels: string[];
  embeddingModels: string[];
};

export function ProviderSettingsManager() {
  const { user } = useAuth();
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [activeProjectRole, setActiveProjectRole] =
    useState<ProjectRole | null>(null);
  const [tokenName, setTokenName] = useState("default");
  const [issuingToken, setIssuingToken] = useState(false);
  const [issuedToken, setIssuedToken] = useState<string | null>(null);
  const [issuedTokenLastFour, setIssuedTokenLastFour] = useState<string | null>(
    null,
  );
  const [settings, setSettings] = useState<ProviderSettingData[]>([]);
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [draftBaseUrls, setDraftBaseUrls] = useState<Record<string, string>>(
    {},
  );
  const [draftChatModels, setDraftChatModels] = useState<
    Record<string, string>
  >({});
  const [draftEmbeddingModels, setDraftEmbeddingModels] = useState<
    Record<string, string>
  >({});
  const [modelCatalogs, setModelCatalogs] = useState<
    Record<string, ModelCatalog>
  >({});
  const [modelErrors, setModelErrors] = useState<Record<string, string | null>>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [loadingModelsProvider, setLoadingModelsProvider] = useState<
    string | null
  >(null);
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [removingProvider, setRemovingProvider] = useState<string | null>(null);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectName(active.name);
      setActiveProjectRole(active.role ?? "viewer");
      return;
    }
    setLoading(false);
  }, []);

  const canMutateProject = canEditProject(activeProjectRole);

  useEffect(() => {
    if (!activeProjectId) {
      return;
    }

    let ignore = false;
    setLoading(true);
    listProjectProviderSettings(activeProjectId)
      .then((response) => {
        if (ignore) {
          return;
        }

        setSettings(response.data.items);
        setModelCatalogs(
          Object.fromEntries(
            response.data.items.map((item) => [
              item.provider,
              {
                chatModels: item.available_chat_models,
                embeddingModels: item.available_embedding_models,
              },
            ]),
          ),
        );
        setModelErrors(
          Object.fromEntries(
            response.data.items.map((item) => [
              item.provider,
              item.model_discovery_error,
            ]),
          ),
        );
        setDraftBaseUrls(
          Object.fromEntries(
            response.data.items.map((item) => [
              item.provider,
              item.base_url ?? "",
            ]),
          ),
        );
        setDraftChatModels(
          Object.fromEntries(
            response.data.items.map((item) => [
              item.provider,
              item.chat_model ?? item.available_chat_models[0] ?? "",
            ]),
          ),
        );
        setDraftEmbeddingModels(
          Object.fromEntries(
            response.data.items.map((item) => [
              item.provider,
              item.embedding_model ?? item.available_embedding_models[0] ?? "",
            ]),
          ),
        );
      })
      .catch((error) => {
        if (!ignore) {
          toast.error(
            error instanceof Error
              ? error.message
              : "Failed to load provider settings.",
          );
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [activeProjectId]);

  const sortedSettings = useMemo(
    () =>
      [...settings].sort((left, right) =>
        left.provider.localeCompare(right.provider),
      ),
    [settings],
  );

  function buildModelOptions(currentValue: string, values: string[]) {
    const cleanedCurrentValue = currentValue.trim();
    if (cleanedCurrentValue && !values.includes(cleanedCurrentValue)) {
      return [cleanedCurrentValue, ...values];
    }
    return values;
  }

  async function handleLoadModels(provider: string) {
    if (!canMutateProject) {
      toast.error("This action requires editor role or higher.");
      return;
    }
    if (!activeProjectId) {
      toast.error("Create or select a project first.");
      return;
    }

    setLoadingModelsProvider(provider);
    const toastId = toast.loading(`Loading ${provider} models...`);
    try {
      const response = await discoverProjectProviderModels({
        projectId: activeProjectId,
        provider,
        apiKey: draftKeys[provider]?.trim() || undefined,
        baseUrl: draftBaseUrls[provider]?.trim() || undefined,
      });
      setModelCatalogs((current) => ({
        ...current,
        [provider]: {
          chatModels: response.data.available_chat_models,
          embeddingModels: response.data.available_embedding_models,
        },
      }));
      setModelErrors((current) => ({ ...current, [provider]: null }));
      setDraftChatModels((current) => ({
        ...current,
        [provider]: resolveSelectedModel(
          current[provider] ?? "",
          response.data.available_chat_models,
        ),
      }));
      setDraftEmbeddingModels((current) => ({
        ...current,
        [provider]: resolveSelectedModel(
          current[provider] ?? "",
          response.data.available_embedding_models,
        ),
      }));
      toast.success(
        `${response.data.display_name} models loaded from ${response.data.source}.`,
        {
          id: toastId,
        },
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to fetch provider models.";
      setModelErrors((current) => ({ ...current, [provider]: message }));
      toast.error(message, { id: toastId });
    } finally {
      setLoadingModelsProvider(null);
    }
  }

  async function handleSave(
    event: FormEvent<HTMLFormElement>,
    provider: string,
  ) {
    event.preventDefault();
    if (!canMutateProject) {
      toast.error("This action requires editor role or higher.");
      return;
    }
    if (!activeProjectId) {
      toast.error("Create or select a project first.");
      return;
    }

    const providerSetting = settings.find((item) => item.provider === provider);
    if (!providerSetting) {
      toast.error("Provider settings are unavailable.");
      return;
    }

    const apiKey = draftKeys[provider]?.trim() ?? "";
    if (!apiKey) {
      toast.error("Enter an API key before saving.");
      return;
    }

    const chatModel = draftChatModels[provider]?.trim() ?? "";
    const embeddingModel = draftEmbeddingModels[provider]?.trim() ?? "";
    const baseUrl = draftBaseUrls[provider]?.trim() ?? "";
    if (!chatModel) {
      toast.error("Load models and choose a chat model before saving.");
      return;
    }
    if (providerSetting.supports.includes("embeddings") && !embeddingModel) {
      toast.error("Load models and choose an embedding model before saving.");
      return;
    }

    setSavingProvider(provider);
    const toastId = toast.loading(`Saving ${provider} key...`);
    try {
      const response = await saveProjectProviderKey({
        projectId: activeProjectId,
        provider,
        apiKey,
        baseUrl: baseUrl || undefined,
        chatModel,
        embeddingModel: embeddingModel || undefined,
      });
      setSettings((current) =>
        current.map((item) =>
          item.provider === provider ? response.data : item,
        ),
      );
      setModelCatalogs((current) => ({
        ...current,
        [provider]: {
          chatModels: response.data.available_chat_models,
          embeddingModels: response.data.available_embedding_models,
        },
      }));
      setModelErrors((current) => ({
        ...current,
        [provider]: response.data.model_discovery_error,
      }));
      setDraftKeys((current) => ({ ...current, [provider]: "" }));
      setDraftBaseUrls((current) => ({
        ...current,
        [provider]: response.data.base_url ?? "",
      }));
      setDraftChatModels((current) => ({
        ...current,
        [provider]: response.data.chat_model ?? current[provider] ?? "",
      }));
      setDraftEmbeddingModels((current) => ({
        ...current,
        [provider]: response.data.embedding_model ?? current[provider] ?? "",
      }));
      toast.success(
        `${response.data.display_name} key saved for this project.`,
        { id: toastId },
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to save provider key.",
        {
          id: toastId,
        },
      );
    } finally {
      setSavingProvider(null);
    }
  }

  async function handleDelete(provider: string) {
    if (!canMutateProject) {
      toast.error("This action requires editor role or higher.");
      return;
    }
    if (!activeProjectId) {
      toast.error("Create or select a project first.");
      return;
    }

    setRemovingProvider(provider);
    const toastId = toast.loading(`Removing ${provider} override...`);
    try {
      const response = await deleteProjectProviderKey({
        projectId: activeProjectId,
        provider,
      });
      setSettings((current) =>
        current.map((item) =>
          item.provider === provider ? response.data : item,
        ),
      );
      setModelCatalogs((current) => ({
        ...current,
        [provider]: {
          chatModels: [],
          embeddingModels: [],
        },
      }));
      setModelErrors((current) => ({ ...current, [provider]: null }));
      setDraftKeys((current) => ({ ...current, [provider]: "" }));
      setDraftBaseUrls((current) => ({ ...current, [provider]: "" }));
      setDraftChatModels((current) => ({ ...current, [provider]: "" }));
      setDraftEmbeddingModels((current) => ({ ...current, [provider]: "" }));
      toast.success(`${response.data.display_name} override removed.`, {
        id: toastId,
      });
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to remove provider key.",
        {
          id: toastId,
        },
      );
    } finally {
      setRemovingProvider(null);
    }
  }

  async function handleCreateToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedTokenName = tokenName.trim();
    if (!trimmedTokenName) {
      toast.error("Token name is required.");
      return;
    }

    setIssuingToken(true);
    const toastId = toast.loading("Issuing personal token...");
    try {
      const response = await createPersonalToken(trimmedTokenName);
      setIssuedToken(response.data.token);
      setIssuedTokenLastFour(response.data.token_last_four);
      toast.success("Token created. Copy it now, it will not be shown again.", {
        id: toastId,
      });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to create token.",
        {
          id: toastId,
        },
      );
    } finally {
      setIssuingToken(false);
    }
  }

  async function handleCopyIssuedToken() {
    if (!issuedToken) {
      return;
    }
    await navigator.clipboard.writeText(issuedToken);
    toast.success("Token copied to clipboard.");
  }

  return (
    <PageWrapper
      title="Provider Settings"
      description={
        activeProjectName
          ? `Manage API keys for ${activeProjectName}`
          : "Select a project, then configure provider API keys " +
            "without hardcoding them in env files."
      }
    >
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Personal Access Token</CardTitle>
          <CardDescription>
            Create a bearer token for this account and use it in the login
            screen.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-sm">
            <p className="font-medium">Current user</p>
            <p className="text-muted-foreground">
              {user?.display_name || "Unknown user"}
              {user?.email ? ` (${user.email})` : ""}
            </p>
          </div>
          <form
            className="flex flex-col gap-3 md:flex-row"
            onSubmit={handleCreateToken}
          >
            <div className="flex-1">
              <Label htmlFor="token-name">Token name</Label>
              <Input
                id="token-name"
                value={tokenName}
                onChange={(event) => setTokenName(event.target.value)}
                placeholder="default"
                disabled={issuingToken}
              />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={issuingToken} className="gap-2">
                {issuingToken ? <Spinner size="sm" /> : null}
                {issuingToken ? "Creating..." : "Create token"}
              </Button>
            </div>
          </form>
          {issuedToken ? (
            <div className="rounded-xl border border-amber-300/40 bg-amber-500/10 px-4 py-3">
              <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
                New token (last 4: {issuedTokenLastFour || "n/a"})
              </p>
              <p className="mt-2 break-all font-mono text-xs text-amber-900 dark:text-amber-200">
                {issuedToken}
              </p>
              <div className="mt-3">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void handleCopyIssuedToken()}
                >
                  Copy token
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {!canMutateProject && activeProjectId ? (
        <div className="rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          You have viewer access for this project. Provider configuration is
          read-only.
        </div>
      ) : null}

      {!activeProjectId ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No active project</CardTitle>
            <CardDescription>
              Create or select a project first, then come back here to attach
              provider API keys.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {activeProjectId ? (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">Project Scope</CardTitle>
            </div>
            <CardDescription>
              Keys saved here are scoped to the active project and take priority
              over environment defaults.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={
                "flex items-center gap-3 rounded-xl border border-border " +
                "bg-muted/40 px-4 py-3"
              }
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <KeyRound className="h-4 w-4 text-primary" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium">{activeProjectName}</p>
                <p className="text-xs font-mono text-muted-foreground">
                  {activeProjectId}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {loading && activeProjectId ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner size="sm" />
          Loading provider settings...
        </div>
      ) : null}

      {sortedSettings.map((providerSetting) => {
        const ProviderIcon =
          providerIcons[
            providerSetting.provider as keyof typeof providerIcons
          ] ?? Sparkles;
        const isLoadingModels =
          loadingModelsProvider === providerSetting.provider;
        const isSaving = savingProvider === providerSetting.provider;
        const isRemoving = removingProvider === providerSetting.provider;
        const modelCatalog = modelCatalogs[providerSetting.provider] ?? {
          chatModels: providerSetting.available_chat_models,
          embeddingModels: providerSetting.available_embedding_models,
        };
        const chatModelOptions = buildModelOptions(
          draftChatModels[providerSetting.provider] ?? "",
          modelCatalog.chatModels,
        );
        const embeddingModelOptions = buildModelOptions(
          draftEmbeddingModels[providerSetting.provider] ?? "",
          modelCatalog.embeddingModels,
        );
        const modelError =
          modelErrors[providerSetting.provider] ??
          providerSetting.model_discovery_error;

        return (
          <Card key={providerSetting.provider}>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                  <ProviderIcon className="h-5 w-5 text-primary" />
                </div>
                <div className="min-w-0">
                  <CardTitle className="text-base">
                    {providerSetting.display_name}
                  </CardTitle>
                  <CardDescription>
                    Retrieval now uses a local multilingual embedding backend.
                    This provider is used only for answer generation.
                  </CardDescription>
                </div>
                <Badge
                  variant={providerSetting.configured ? "success" : "secondary"}
                  className="ml-auto"
                >
                  {providerSetting.configured ? "Configured" : "Missing"}
                </Badge>
                <Badge variant="outline">
                  {providerSetting.configured_source}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-2">
                {providerSetting.supports.map((capability) => (
                  <Badge key={capability} variant="secondary">
                    {capability}
                  </Badge>
                ))}
              </div>

              <div className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-sm">
                <p className="font-medium">Current status</p>
                <p className="text-muted-foreground">
                  {providerSetting.configured_source === "project" &&
                  providerSetting.masked_api_key
                    ? `Project override saved as ${providerSetting.masked_api_key}.`
                    : "No key configured yet for this provider."}
                </p>
              </div>

              {modelError ? (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3">
                  <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
                    Model discovery issue
                  </p>
                  <p className="text-sm text-amber-800/80 dark:text-amber-200/80">
                    {modelError}
                  </p>
                </div>
              ) : null}

              <div
                className={
                  providerSetting.supports_base_url
                    ? "grid gap-3 md:grid-cols-3"
                    : "grid gap-3 md:grid-cols-2"
                }
              >
                <div className="rounded-xl border border-border bg-muted/20 px-4 py-3 text-sm">
                  <p className="font-medium">Current chat model</p>
                  <p className="text-muted-foreground">
                    {providerSetting.chat_model ?? "Not configured"}
                  </p>
                </div>
                {providerSetting.supports.includes("embeddings") ? (
                  <div className="rounded-xl border border-border bg-muted/20 px-4 py-3 text-sm">
                    <p className="font-medium">Current embedding model</p>
                    <p className="text-muted-foreground">
                      {providerSetting.embedding_model ?? "Not configured"}
                    </p>
                  </div>
                ) : null}
                {providerSetting.supports_base_url ? (
                  <div className="rounded-xl border border-border bg-muted/20 px-4 py-3 text-sm">
                    <p className="font-medium">Current base URL</p>
                    <p className="break-all text-muted-foreground">
                      {providerSetting.base_url ?? "Default OpenAI API URL"}
                    </p>
                  </div>
                ) : null}
              </div>

              <form
                onSubmit={(event) =>
                  void handleSave(event, providerSetting.provider)
                }
                className="flex flex-col gap-3"
              >
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor={`${providerSetting.provider}-api-key`}>
                    {providerSetting.display_name} API key
                  </Label>
                  <Input
                    id={`${providerSetting.provider}-api-key`}
                    type="password"
                    autoComplete="off"
                    value={draftKeys[providerSetting.provider] ?? ""}
                    onChange={(event) =>
                      setDraftKeys((current) => ({
                        ...current,
                        [providerSetting.provider]: event.target.value,
                      }))
                    }
                    placeholder={`Paste ${providerSetting.display_name} API key`}
                    disabled={
                      isSaving ||
                      isRemoving ||
                      isLoadingModels ||
                      !canMutateProject
                    }
                  />
                </div>

                {providerSetting.supports_base_url ? (
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor={`${providerSetting.provider}-base-url`}>
                      {providerSetting.display_name} base URL
                    </Label>
                    <Input
                      id={`${providerSetting.provider}-base-url`}
                      type="url"
                      autoComplete="off"
                      value={draftBaseUrls[providerSetting.provider] ?? ""}
                      onChange={(event) =>
                        setDraftBaseUrls((current) => ({
                          ...current,
                          [providerSetting.provider]: event.target.value,
                        }))
                      }
                      placeholder="https://proxy.example.com/v1"
                      disabled={
                        isSaving ||
                        isRemoving ||
                        isLoadingModels ||
                        !canMutateProject
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Optional. Leave blank to use the default OpenAI API base
                      URL.
                    </p>
                  </div>
                ) : null}

                <div className="flex flex-col gap-1.5 md:self-start">
                  <Label className="opacity-0">Load models</Label>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={
                      isSaving ||
                      isRemoving ||
                      isLoadingModels ||
                      !canMutateProject
                    }
                    onClick={() =>
                      void handleLoadModels(providerSetting.provider)
                    }
                    className="gap-2"
                    title={
                      canMutateProject ? undefined : "Requires editor role"
                    }
                  >
                    {isLoadingModels ? (
                      <Spinner size="sm" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                    {isLoadingModels ? "Loading..." : "Load models"}
                  </Button>
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor={`${providerSetting.provider}-chat-model`}>
                    {providerSetting.display_name} chat model
                  </Label>
                  <Select
                    value={draftChatModels[providerSetting.provider] ?? ""}
                    onValueChange={(value) =>
                      setDraftChatModels((current) => ({
                        ...current,
                        [providerSetting.provider]: value,
                      }))
                    }
                    disabled={
                      isSaving ||
                      isRemoving ||
                      isLoadingModels ||
                      !canMutateProject
                    }
                  >
                    <SelectTrigger
                      id={`${providerSetting.provider}-chat-model`}
                      title={
                        canMutateProject ? undefined : "Requires editor role"
                      }
                    >
                      <SelectValue placeholder="Load models first" />
                    </SelectTrigger>
                    <SelectContent>
                      {chatModelOptions.map((modelName) => (
                        <SelectItem key={modelName} value={modelName}>
                          {modelName}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {providerSetting.supports.includes("embeddings") ? (
                  <div className="flex flex-col gap-1.5">
                    <Label
                      htmlFor={`${providerSetting.provider}-embedding-model`}
                    >
                      {providerSetting.display_name} embedding model
                    </Label>
                    <Select
                      value={
                        draftEmbeddingModels[providerSetting.provider] ?? ""
                      }
                      onValueChange={(value) =>
                        setDraftEmbeddingModels((current) => ({
                          ...current,
                          [providerSetting.provider]: value,
                        }))
                      }
                      disabled={
                        isSaving ||
                        isRemoving ||
                        isLoadingModels ||
                        !canMutateProject
                      }
                    >
                      <SelectTrigger
                        id={`${providerSetting.provider}-embedding-model`}
                        title={
                          canMutateProject ? undefined : "Requires editor role"
                        }
                      >
                        <SelectValue placeholder="Load models first" />
                      </SelectTrigger>
                      <SelectContent>
                        {embeddingModelOptions.map((modelName) => (
                          <SelectItem key={modelName} value={modelName}>
                            {modelName}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : null}

                <div className="flex flex-wrap gap-3">
                  <Button
                    type="submit"
                    disabled={
                      isSaving ||
                      isRemoving ||
                      isLoadingModels ||
                      !canMutateProject
                    }
                    className="gap-2"
                    title={
                      canMutateProject ? undefined : "Requires editor role"
                    }
                  >
                    {isSaving ? (
                      <Spinner size="sm" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    {isSaving ? "Saving..." : "Save project key"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={
                      isSaving ||
                      isRemoving ||
                      isLoadingModels ||
                      !canMutateProject ||
                      providerSetting.configured_source !== "project"
                    }
                    onClick={() => void handleDelete(providerSetting.provider)}
                    className="gap-2"
                    title={
                      canMutateProject ? undefined : "Requires editor role"
                    }
                  >
                    {isRemoving ? (
                      <Spinner size="sm" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                    {isRemoving ? "Removing..." : "Remove override"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        );
      })}
    </PageWrapper>
  );
}

function resolveSelectedModel(currentValue: string, availableModels: string[]) {
  const cleanedCurrentValue = currentValue.trim();
  if (cleanedCurrentValue && availableModels.includes(cleanedCurrentValue)) {
    return cleanedCurrentValue;
  }
  return availableModels[0] ?? "";
}
