"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { KeyRound, Sparkles, Trash2, Save, Bot, Brain } from "lucide-react";

import {
  deleteProjectProviderKey,
  listProjectProviderSettings,
  saveProjectProviderKey,
} from "@/lib/api/client";
import type { ProviderSettingData } from "@/lib/api/types";
import { getActiveProject } from "@/lib/project-store";

import { PageWrapper } from "@/components/layout/page-wrapper";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

const providerIcons = {
  openai: Sparkles,
  gemini: Bot,
} as const;

export function ProviderSettingsManager() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [settings, setSettings] = useState<ProviderSettingData[]>([]);
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [draftBaseUrls, setDraftBaseUrls] = useState<Record<string, string>>({});
  const [draftChatModels, setDraftChatModels] = useState<Record<string, string>>({});
  const [draftEmbeddingModels, setDraftEmbeddingModels] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [removingProvider, setRemovingProvider] = useState<string | null>(null);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectName(active.name);
      return;
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!activeProjectId) {
      return;
    }

    let ignore = false;
    setLoading(true);
    listProjectProviderSettings(activeProjectId)
      .then((response) => {
        if (!ignore) {
          setSettings(response.data.items);
          setDraftBaseUrls(
            Object.fromEntries(
              response.data.items.map((item) => [item.provider, item.base_url ?? ""]),
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
        }
      })
      .catch((error) => {
        if (!ignore) {
          toast.error(error instanceof Error ? error.message : "Failed to load provider settings.");
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
    () => [...settings].sort((left, right) => left.provider.localeCompare(right.provider)),
    [settings],
  );

  async function handleSave(
    event: FormEvent<HTMLFormElement>,
    provider: string,
  ) {
    event.preventDefault();
    if (!activeProjectId) {
      toast.error("Create or select a project first.");
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
        current.map((item) => (item.provider === provider ? response.data : item)),
      );
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
      toast.success(`${response.data.display_name} key saved for this project.`, { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save provider key.", {
        id: toastId,
      });
    } finally {
      setSavingProvider(null);
    }
  }

  async function handleDelete(provider: string) {
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
        current.map((item) => (item.provider === provider ? response.data : item)),
      );
      setDraftKeys((current) => ({ ...current, [provider]: "" }));
      setDraftBaseUrls((current) => ({ ...current, [provider]: "" }));
      toast.success(`${response.data.display_name} override removed.`, { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to remove provider key.", {
        id: toastId,
      });
    } finally {
      setRemovingProvider(null);
    }
  }

  return (
    <PageWrapper
      title="Provider Settings"
      description={
        activeProjectName
          ? `Manage API keys for ${activeProjectName}`
          : "Select a project, then configure provider API keys "
            + "without hardcoding them in env files."
      }
    >
      {!activeProjectId ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No active project</CardTitle>
            <CardDescription>
              Create or select a project first, then come back here to attach provider API keys.
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
              Keys saved here are scoped to the active project and take priority over environment
              defaults.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={
                "flex items-center gap-3 rounded-xl border border-border "
                + "bg-muted/40 px-4 py-3"
              }
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <KeyRound className="h-4 w-4 text-primary" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium">{activeProjectName}</p>
                <p className="text-xs font-mono text-muted-foreground">{activeProjectId}</p>
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
          providerIcons[providerSetting.provider as keyof typeof providerIcons] ?? Sparkles;
        const isSaving = savingProvider === providerSetting.provider;
        const isRemoving = removingProvider === providerSetting.provider;

        return (
          <Card key={providerSetting.provider}>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-3">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10"
                >
                  <ProviderIcon className="h-5 w-5 text-primary" />
                </div>
                <div className="min-w-0">
                  <CardTitle className="text-base">{providerSetting.display_name}</CardTitle>
                  <CardDescription>
                    {providerSetting.provider === "openai"
                      ? "Currently used for embeddings and answer generation "
                        + "in the RAG pipeline."
                      : "Stored now for future multi-provider query and insight flows."}
                  </CardDescription>
                </div>
                <Badge
                  variant={providerSetting.configured ? "success" : "secondary"}
                  className="ml-auto"
                >
                  {providerSetting.configured ? "Configured" : "Missing"}
                </Badge>
                <Badge variant="outline">{providerSetting.configured_source}</Badge>
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
                  {providerSetting.configured_source === "project" && providerSetting.masked_api_key
                    ? `Project override saved as ${providerSetting.masked_api_key}.`
                    : "No key configured yet for this provider."}
                </p>
              </div>

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
                {providerSetting.available_embedding_models.length > 0 ? (
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
                onSubmit={(event) => void handleSave(event, providerSetting.provider)}
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
                    disabled={isSaving || isRemoving}
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
                      disabled={isSaving || isRemoving}
                    />
                    <p className="text-xs text-muted-foreground">
                      Optional. Leave blank to use the default OpenAI API base URL.
                    </p>
                  </div>
                ) : null}

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor={`${providerSetting.provider}-chat-model`}>
                    {providerSetting.display_name} chat model
                  </Label>
                  <select
                    id={`${providerSetting.provider}-chat-model`}
                    value={draftChatModels[providerSetting.provider] ?? ""}
                    onChange={(event) =>
                      setDraftChatModels((current) => ({
                        ...current,
                        [providerSetting.provider]: event.target.value,
                      }))
                    }
                    disabled={isSaving || isRemoving}
                    className={
                      "flex h-9 w-full rounded-md border border-input "
                      + "bg-transparent px-3 py-1 text-sm shadow-sm "
                      + "transition-colors focus-visible:outline-none focus-visible:ring-2 "
                      + "focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    }
                  >
                    {providerSetting.available_chat_models.map((modelName) => (
                      <option key={modelName} value={modelName}>
                        {modelName}
                      </option>
                    ))}
                  </select>
                </div>

                {providerSetting.available_embedding_models.length > 0 ? (
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor={`${providerSetting.provider}-embedding-model`}>
                      {providerSetting.display_name} embedding model
                    </Label>
                    <select
                      id={`${providerSetting.provider}-embedding-model`}
                      value={draftEmbeddingModels[providerSetting.provider] ?? ""}
                      onChange={(event) =>
                        setDraftEmbeddingModels((current) => ({
                          ...current,
                          [providerSetting.provider]: event.target.value,
                        }))
                      }
                      disabled={isSaving || isRemoving}
                      className={
                        "flex h-9 w-full rounded-md border border-input "
                        + "bg-transparent px-3 py-1 text-sm shadow-sm "
                        + "transition-colors focus-visible:outline-none focus-visible:ring-2 "
                        + "focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                      }
                    >
                      {providerSetting.available_embedding_models.map((modelName) => (
                        <option key={modelName} value={modelName}>
                          {modelName}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}

                <div className="flex flex-wrap gap-3">
                  <Button
                    type="submit"
                    disabled={isSaving || isRemoving}
                    className="gap-2"
                  >
                    {isSaving ? <Spinner size="sm" /> : <Save className="h-4 w-4" />}
                    {isSaving ? "Saving..." : "Save project key"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={
                      isSaving ||
                      isRemoving ||
                      providerSetting.configured_source !== "project"
                    }
                    onClick={() => void handleDelete(providerSetting.provider)}
                    className="gap-2"
                  >
                    {isRemoving ? <Spinner size="sm" /> : <Trash2 className="h-4 w-4" />}
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
