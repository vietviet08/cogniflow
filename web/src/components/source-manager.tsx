"use client";

import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { Upload, Link2, Play, FileText, Globe } from "lucide-react";

import { ingestSourceUrl, processSources, uploadSourceFile } from "@/lib/api/client";
import { getActiveProject } from "@/lib/project-store";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { PageWrapper } from "@/components/layout/page-wrapper";

interface LocalSourceItem {
  id: string;
  kind: string;
  status: string;
}

export function SourceManager() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sources, setSources] = useState<LocalSourceItem[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectName(active.name);
    }
  }, []);

  async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProjectId) {
      toast.error("Create or select a project first.");
      return;
    }
    setBusy(true);
    const toastId = toast.loading("Ingesting remote source...");
    try {
      const response = await ingestSourceUrl({ projectId: activeProjectId, url });
      const source = response.data;
      setSources((current) => [...current, { id: source.source_id, kind: source.source_type, status: source.status }]);
      setUrl("");
      toast.success(`Source ingested. Run processing to index it.`, { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to ingest URL.", { id: toastId });
    } finally {
      setBusy(false);
    }
  }

  async function handleFileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
      const response = await uploadSourceFile({ projectId: activeProjectId, file });
      const source = response.data;
      setSources((current) => [...current, { id: source.source_id, kind: source.source_type, status: source.status }]);
      setFile(null);
      toast.success("File uploaded. Run processing to index it.", { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to upload file.", { id: toastId });
    } finally {
      setBusy(false);
    }
  }

  async function handleProcessAll() {
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
        sourceIds: sources.map((s) => s.id),
      });
      toast.success(
        `Done! ${response.data.documents_created} docs · ${response.data.chunks_created} chunks indexed.`,
        { id: toastId },
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to process sources.", { id: toastId });
    } finally {
      setBusy(false);
    }
  }

  const statusBadge = (status: string) => {
    if (status === "ready") return <Badge variant="success">{status}</Badge>;
    if (status === "pending") return <Badge variant="warning">{status}</Badge>;
    return <Badge variant="secondary">{status}</Badge>;
  };

  return (
    <PageWrapper
      title="Sources"
      description={
        activeProjectName
          ? `Project: ${activeProjectName}`
          : "Select a project first, then upload a PDF or ingest a URL."
      }
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Upload PDF */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/10">
                <FileText className="h-4 w-4 text-violet-500" />
              </div>
              <div>
                <CardTitle className="text-base">Upload PDF</CardTitle>
                <CardDescription>Upload a local PDF file</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleFileSubmit} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pdf-file">PDF file</Label>
                <input
                  id="pdf-file"
                  type="file"
                  accept=".pdf"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="text-sm file:mr-3 file:cursor-pointer file:rounded-md file:border file:border-border file:bg-muted file:px-3 file:py-1.5 file:text-xs file:font-medium file:transition-colors hover:file:bg-accent"
                />
              </div>
              <Button type="submit" disabled={busy || !file} size="sm" className="w-fit gap-2">
                {busy ? <Spinner size="sm" /> : <Upload className="h-3.5 w-3.5" />}
                Upload file
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Ingest URL */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
                <Globe className="h-4 w-4 text-blue-500" />
              </div>
              <div>
                <CardTitle className="text-base">Ingest URL</CardTitle>
                <CardDescription>arXiv link or any URL</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUrlSubmit} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="source-url">URL</Label>
                <Input
                  id="source-url"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://arxiv.org/abs/1234.5678"
                  disabled={busy}
                />
              </div>
              <Button type="submit" disabled={busy} size="sm" className="w-fit gap-2">
                {busy ? <Spinner size="sm" /> : <Link2 className="h-3.5 w-3.5" />}
                Ingest URL
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* Sources list */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Session Sources</CardTitle>
              <CardDescription>
                {sources.length === 0
                  ? "No sources ingested yet."
                  : `${sources.length} source${sources.length > 1 ? "s" : ""} ready to process.`}
              </CardDescription>
            </div>
            {sources.length > 0 && (
              <Button
                type="button"
                disabled={busy}
                onClick={handleProcessAll}
                size="sm"
                className="gap-2"
              >
                {busy ? <Spinner size="sm" /> : <Play className="h-3.5 w-3.5" />}
                Process all
              </Button>
            )}
          </div>
        </CardHeader>
        {sources.length > 0 && (
          <CardContent className="p-0">
            {sources.map((source, index) => (
              <div key={source.id}>
                {index > 0 && <Separator />}
                <div className="flex items-center gap-3 px-6 py-3">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-mono text-muted-foreground truncate">{source.id}</p>
                    <p className="text-xs text-muted-foreground">{source.kind}</p>
                  </div>
                  {statusBadge(source.status)}
                </div>
              </div>
            ))}
          </CardContent>
        )}
      </Card>
    </PageWrapper>
  );
}
