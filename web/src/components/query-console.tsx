"use client";

import { FormEvent, useEffect, useState } from "react";

import { queryKnowledge } from "@/lib/api/client";
import type { CitationData } from "@/lib/api/types";
import { getActiveProject } from "@/lib/project-store";

export function QueryConsole() {
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectName, setActiveProjectName] = useState("");
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<CitationData[]>([]);
  const [status, setStatus] = useState("Ask a question after processing at least one source.");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectName(active.name);
    }
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProjectId) {
      setStatus("Create or select a project first.");
      return;
    }

    setBusy(true);
    setStatus("Retrieving context and generating answer...");
    try {
      const response = await queryKnowledge({ projectId: activeProjectId, query, topK: 5 });
      setAnswer(response.data.answer);
      setCitations(response.data.citations);
      setStatus(`Query run ${response.data.run_id} completed.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to query the knowledge base.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={{ display: "grid", gap: 24 }}>
      <div>
        <h2 style={{ marginBottom: 8 }}>Query</h2>
        <p style={{ marginTop: 0, color: "#586069" }}>
          Active project: {activeProjectName ? `${activeProjectName} (${activeProjectId})` : "none"}
        </p>
      </div>

      <form onSubmit={handleSubmit} style={cardStyle}>
        <textarea
          required
          rows={5}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="What are the main findings across the indexed documents?"
          style={fieldStyle}
        />
        <button type="submit" disabled={busy} style={buttonStyle}>
          Ask
        </button>
      </form>

      <div style={cardStyle}>
        <strong>Answer</strong>
        <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{answer || "No answer yet."}</p>
      </div>

      <div style={cardStyle}>
        <strong>Citations</strong>
        {citations.length === 0 ? <p style={{ margin: 0 }}>No citations yet.</p> : null}
        {citations.map((citation) => (
          <div key={citation.chunk_id} style={{ padding: "10px 0", borderTop: "1px solid #dde3eb" }}>
            <div>{citation.title || citation.chunk_id}</div>
            <div style={{ color: "#586069" }}>{citation.chunk_id}</div>
            {citation.url ? (
              <a href={citation.url} target="_blank" rel="noreferrer" style={{ color: "#0f5fc2" }}>
                {citation.url}
              </a>
            ) : null}
          </div>
        ))}
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
