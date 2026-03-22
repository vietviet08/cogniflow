"use client";

import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { Send, BookOpen, Quote, ExternalLink } from "lucide-react";

import { listProjectProviderSettings, queryKnowledge } from "@/lib/api/client";
import type { CitationData, ProviderSettingData } from "@/lib/api/types";
import { getActiveProject } from "@/lib/project-store";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { PageWrapper } from "@/components/layout/page-wrapper";

export function QueryConsole() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<CitationData[]>([]);
  const [provider, setProvider] = useState("openai");
  const [answerProvider, setAnswerProvider] = useState("");
  const [answerModel, setAnswerModel] = useState("");
  const [providerSettings, setProviderSettings] = useState<ProviderSettingData[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectName(active.name);
    }
  }, []);

  useEffect(() => {
    if (!activeProjectId) {
      return;
    }

    let ignore = false;
    listProjectProviderSettings(activeProjectId)
      .then((response) => {
        if (!ignore) {
          setProviderSettings(response.data.items);
        }
      })
      .catch(() => {
        if (!ignore) {
          setProviderSettings([]);
        }
      });

    return () => {
      ignore = true;
    };
  }, [activeProjectId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProjectId) {
      toast.error("Create or select a project first.");
      return;
    }
    setBusy(true);
    const toastId = toast.loading(`Retrieving context and generating answer with ${provider}...`);
    try {
      const response = await queryKnowledge({
        projectId: activeProjectId,
        query,
        provider,
        topK: 5,
      });
      setAnswer(response.data.answer);
      setCitations(response.data.citations);
      setAnswerProvider(response.data.provider);
      setAnswerModel(response.data.model);
      toast.success(`Run ${response.data.run_id} completed with ${response.data.provider}.`, {
        id: toastId,
      });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to query the knowledge base.",
        { id: toastId },
      );
    } finally {
      setBusy(false);
    }
  }

  const providerState = providerSettings.find((item) => item.provider === provider);
  const openaiState = providerSettings.find((item) => item.provider === "openai");

  return (
    <PageWrapper
      title="Query"
      description={
        activeProjectName
          ? `Querying: ${activeProjectName}`
          : "Select a project, then ask questions across your indexed knowledge base."
      }
    >
      {/* Query input */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Ask a Question</CardTitle>
          <CardDescription>
            Use natural language to search across your indexed documents, then choose which model
            answers from the retrieved context.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="provider-select">Answer provider</Label>
                <select
                  id="provider-select"
                  value={provider}
                  onChange={(event) => setProvider(event.target.value)}
                  disabled={busy}
                  className={
                    "flex h-9 w-full rounded-md border border-input bg-transparent "
                    + "px-3 py-1 text-sm shadow-sm transition-colors "
                    + "focus-visible:outline-none focus-visible:ring-2 "
                    + "focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  }
                >
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Gemini</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="provider-status">Provider status</Label>
                <Input
                  id="provider-status"
                  value={
                    providerState
                      ? `${providerState.configured ? "Configured" : "Missing"} `
                        + `via ${providerState.configured_source}`
                      : "Unknown"
                  }
                  readOnly
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="query-input">Question</Label>
              <Textarea
                id="query-input"
                required
                rows={4}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="What are the main findings across the indexed documents?"
                disabled={busy}
              />
            </div>
            {provider === "gemini" ? (
              <p className="text-xs text-muted-foreground">
                Gemini is used for answer generation. Retrieval still depends on this project being
                indexed with OpenAI embeddings, so an OpenAI key must also be configured.
                {openaiState
                  ? ` Current OpenAI status: ${openaiState.configured ? "configured" : "missing"}.`
                  : ""}
              </p>
            ) : null}
            {providerState?.chat_model ? (
              <p className="text-xs text-muted-foreground">
                Selected model from settings:{" "}
                <span className="font-mono">{providerState.chat_model}</span>
              </p>
            ) : null}
            <Button type="submit" disabled={busy || !activeProjectId} className="w-fit gap-2">
              {busy ? <Spinner size="sm" /> : <Send className="h-4 w-4" />}
              {busy ? "Searching..." : "Ask"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Answer */}
      {(answer || busy) && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">Answer</CardTitle>
              {answerProvider ? (
                <Badge variant="secondary" className="ml-auto">
                  {answerProvider}
                </Badge>
              ) : null}
              {answerModel ? <Badge variant="outline">{answerModel}</Badge> : null}
            </div>
          </CardHeader>
          <CardContent>
            {busy ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner size="sm" />
                Generating answer...
              </div>
            ) : (
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{answer}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Citations */}
      {citations.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Quote className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Citations</CardTitle>
              <Badge variant="secondary" className="ml-auto">{citations.length}</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {citations.map((citation, index) => (
              <div key={citation.chunk_id}>
                {index > 0 && <Separator />}
                <div className="flex flex-col gap-1 px-6 py-4">
                  <p className="text-sm font-medium">{citation.title || citation.chunk_id}</p>
                  <p className="text-xs font-mono text-muted-foreground">{citation.chunk_id}</p>
                  {citation.url && (
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <ExternalLink className="h-3 w-3" />
                      {citation.url}
                    </a>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </PageWrapper>
  );
}
