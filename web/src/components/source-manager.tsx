"use client";

import { FormEvent, useEffect, useState } from "react";

import { ingestSourceUrl, processSources, uploadSourceFile } from "@/lib/api/client";
import { getActiveProject } from "@/lib/project-store";

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
  const [status, setStatus] = useState("Select a project, then upload a PDF or ingest a URL.");
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
      setStatus("Create or select a project first.");
      return;
    }

    setBusy(true);
    setStatus("Ingesting remote source...");
    try {
      const response = await ingestSourceUrl({ projectId: activeProjectId, url });
      const source = response.data;
      setSources((current) => [...current, { id: source.source_id, kind: source.source_type, status: source.status }]);
      setUrl("");
      setStatus(`Source ${source.source_id} ingested. Run processing to chunk and index it.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to ingest URL.");
    } finally {
      setBusy(false);
    }
  }

  async function handleFileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProjectId) {
      setStatus("Create or select a project first.");
      return;
    }
    if (!file) {
      setStatus("Select a PDF file first.");
      return;
    }

    setBusy(true);
    setStatus("Uploading file...");
    try {
      const response = await uploadSourceFile({ projectId: activeProjectId, file });
      const source = response.data;
      setSources((current) => [...current, { id: source.source_id, kind: source.source_type, status: source.status }]);
      setFile(null);
      setStatus(`File source ${source.source_id} uploaded. Run processing to chunk and index it.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to upload file.");
    } finally {
      setBusy(false);
    }
  }

  async function handleProcessAll() {
    if (!activeProjectId) {
      setStatus("Create or select a project first.");
      return;
    }
    if (sources.length === 0) {
      setStatus("Ingest at least one source before processing.");
      return;
    }

    setBusy(true);
    setStatus("Processing sources...");
    try {
      const response = await processSources({
        projectId: activeProjectId,
        sourceIds: sources.map((source) => source.id),
      });
      setStatus(
        `Processing complete: ${response.data.documents_created} documents and ${response.data.chunks_created} chunks indexed.`,
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to process sources.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={{ display: "grid", gap: 24 }}>
      <div>
        <h2 style={{ marginBottom: 8 }}>Sources</h2>
        <p style={{ marginTop: 0, color: "#586069" }}>
          Active project: {activeProjectName ? `${activeProjectName} (${activeProjectId})` : "none"}
        </p>
      </div>

      <form onSubmit={handleFileSubmit} style={cardStyle}>
        <strong>Upload PDF</strong>
        <input type="file" accept=".pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <button type="submit" disabled={busy} style={buttonStyle}>
          Upload file
        </button>
      </form>

      <form onSubmit={handleUrlSubmit} style={cardStyle}>
        <strong>Ingest URL or arXiv link</strong>
        <input
          required
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://arxiv.org/abs/1234.5678"
          style={fieldStyle}
        />
        <button type="submit" disabled={busy} style={buttonStyle}>
          Ingest URL
        </button>
      </form>

      <div style={cardStyle}>
        <strong>Current session sources</strong>
        {sources.length === 0 ? <p style={{ margin: 0 }}>No sources ingested in this session yet.</p> : null}
        {sources.map((source) => (
          <div key={source.id} style={{ padding: "10px 0", borderTop: "1px solid #dde3eb" }}>
            <div>{source.id}</div>
            <div style={{ color: "#586069" }}>
              {source.kind} · {source.status}
            </div>
          </div>
        ))}
        <button type="button" disabled={busy} onClick={handleProcessAll} style={buttonStyle}>
          Process all session sources
        </button>
      </div>

      <p style={{ margin: 0, color: "#1d4f91" }}>{status}</p>
    </section>
  );
}

const cardStyle = {
  display: "grid",
  gap: 12,
  padding: 16,
  border: "1px solid #d7dce2",
  borderRadius: 12,
  background: "#f7f9fc",
} as const;

const fieldStyle = {
  border: "1px solid #c4ccd6",
  borderRadius: 10,
  padding: 12,
  font: "inherit",
} as const;

const buttonStyle = {
  background: "#0f5fc2",
  color: "#fff",
  border: "none",
  borderRadius: 10,
  padding: "12px 16px",
  font: "inherit",
  cursor: "pointer",
  width: "fit-content",
} as const;
