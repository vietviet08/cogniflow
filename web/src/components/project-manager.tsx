"use client";

import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, FolderOpen, CheckCircle2 } from "lucide-react";

import { createProject } from "@/lib/api/client";
import type { ProjectData } from "@/lib/api/types";
import { getActiveProject, listStoredProjects, setActiveProject } from "@/lib/project-store";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { PageWrapper } from "@/components/layout/page-wrapper";

export function ProjectManager() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [activeProject, setActiveProjectState] = useState<ProjectData | null>(null);
  const [storedProjects, setStoredProjects] = useState<ProjectData[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const current = getActiveProject();
    const stored = listStoredProjects();
    setActiveProjectState(
      current
        ? { id: current.id, name: current.name, description: current.description, created_at: null }
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
    const toastId = toast.loading("Creating project...");

    try {
      const response = await createProject({ name, description });
      const project = response.data;
      setActiveProject(project);
      setActiveProjectState(project);
      setStoredProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
      setName("");
      setDescription("");
      toast.success(`Project "${project.name}" created and set as active.`, { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create project.", { id: toastId });
    } finally {
      setSubmitting(false);
    }
  }

  function handleSelect(project: ProjectData) {
    setActiveProject(project);
    setActiveProjectState(project);
    toast.success(`Switched to "${project.name}".`);
  }

  return (
    <PageWrapper
      title="Projects"
      description="Create one project and reuse it across source ingestion and query."
    >
      {/* Active project */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-success" />
            <CardTitle className="text-base">Active Project</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {activeProject ? (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                <FolderOpen className="h-4 w-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium">{activeProject.name}</p>
                <p className="text-xs text-muted-foreground font-mono">{activeProject.id}</p>
              </div>
              <Badge variant="success" className="ml-auto">Active</Badge>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No active project selected. Create one below.</p>
          )}
        </CardContent>
      </Card>

      {/* Create new project */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Create New Project</CardTitle>
          <CardDescription>Fill in the details and click create.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-xl">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="project-name">Project name</Label>
              <Input
                id="project-name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Transformer Architecture Review"
                disabled={submitting}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="project-description">Description <span className="text-muted-foreground">(optional)</span></Label>
              <Textarea
                id="project-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Short description of this research project..."
                rows={3}
                disabled={submitting}
              />
            </div>
            <Button type="submit" disabled={submitting} className="w-fit gap-2">
              {submitting ? <Spinner size="sm" /> : <Plus className="h-4 w-4" />}
              {submitting ? "Creating..." : "Create project"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Recent projects */}
      {storedProjects.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Projects</CardTitle>
            <CardDescription>Click to set as active project.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-0 p-0">
            {storedProjects.map((project, index) => (
              <div key={project.id}>
                {index > 0 && <Separator />}
                <button
                  type="button"
                  onClick={() => handleSelect(project)}
                  className="group flex w-full items-center gap-3 px-6 py-4 text-left transition-colors hover:bg-accent/50"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted">
                    <FolderOpen className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{project.name}</p>
                    {project.description && (
                      <p className="text-xs text-muted-foreground truncate">{project.description}</p>
                    )}
                  </div>
                  {activeProject?.id === project.id && (
                    <Badge variant="success" className="shrink-0">Active</Badge>
                  )}
                </button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </PageWrapper>
  );
}
