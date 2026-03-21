"use client";

import { FormEvent, useEffect, useState } from "react";

import { createProject } from "@/lib/api/client";
import type { ProjectData } from "@/lib/api/types";
import { getActiveProject, listStoredProjects, setActiveProject } from "@/lib/project-store";

export function ProjectManager() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [activeProject, setActiveProjectState] = useState<ProjectData | null>(null);
  const [storedProjects, setStoredProjects] = useState<ProjectData[]>([]);
  const [status, setStatus] = useState<string>("Create a project before ingesting documents.");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const current = getActiveProject();
    const stored = listStoredProjects();
    setActiveProjectState(
      current
        ? {
            id: current.id,
            name: current.name,
            description: current.description,
            created_at: null,
          }
        : null,
    );
    setStoredProjects(
      stored.map((project) => ({
        id: project.id,
        name: project.name,
        description: project.description,
        created_at: null,
      })),
    );
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setStatus("Creating project...");

    try {
      const response = await createProject({ name, description });
      const project = response.data;
      setActiveProject(project);
      setActiveProjectState(project);
      setStoredProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
      setName("");
      setDescription("");
      setStatus(`Active project set to ${project.name}.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to create project.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleSelect(project: ProjectData) {
    setActiveProject(project);
    setActiveProjectState(project);
    setStatus(`Active project set to ${project.name}.`);
  }

  return (
    <section style={{ display: "grid", gap: 24 }}>
      <div>
        <h2 style={{ marginBottom: 8 }}>Projects</h2>
        <p style={{ color: "#586069", marginTop: 0 }}>
          Create one project and reuse it across source ingestion and query.
        </p>
      </div>

      <div
        style={{
          padding: 16,
          border: "1px solid #d7dce2",
          borderRadius: 12,
          background: "#f6f8fb",
        }}
      >
        <strong>Active project</strong>
        <p style={{ marginBottom: 0 }}>
          {activeProject ? `${activeProject.name} (${activeProject.id})` : "No active project selected."}
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12, maxWidth: 640 }}>
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Project name"
          style={fieldStyle}
        />
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Short description"
          rows={4}
          style={fieldStyle}
        />
        <button type="submit" disabled={submitting} style={buttonStyle}>
          {submitting ? "Creating..." : "Create project"}
        </button>
      </form>

      {storedProjects.length > 0 ? (
        <div style={{ display: "grid", gap: 12 }}>
          <strong>Recent projects</strong>
          {storedProjects.map((project) => (
            <button key={project.id} type="button" onClick={() => handleSelect(project)} style={secondaryButton}>
              {project.name}
            </button>
          ))}
        </div>
      ) : null}

      <p style={{ margin: 0, color: "#1d4f91" }}>{status}</p>
    </section>
  );
}

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

const secondaryButton = {
  ...buttonStyle,
  background: "#eef4ff",
  color: "#0f3f7f",
  border: "1px solid #c7d9fb",
} as const;
