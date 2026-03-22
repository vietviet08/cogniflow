"use client";

import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { Plus, FolderOpen, CheckCircle2, Trash2, Edit2 } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { createProject, listProjects, updateProject, deleteProject } from "@/lib/api/client";
import { getActiveProject, setActiveProject } from "@/lib/project-store";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { PageWrapper } from "@/components/layout/page-wrapper";

export function ProjectManager() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "name">("newest");

  const activeProject = getActiveProject();

  const { data: projectsData, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(),
  });

  const projects = projectsData?.data.items || [];

  const filteredProjects = projects
    .filter(p => p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                 (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return sortBy === "newest" ? timeB - timeA : timeA - timeB;
    });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    const toastId = toast.loading("Creating project...");

    try {
      const response = await createProject({ name, description });
      const project = response.data;
      setActiveProject({ id: project.id, name: project.name, description: project.description });
      setName("");
      setDescription("");
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success(`Project "${project.name}" created and set as active.`, { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create project.", { id: toastId });
    } finally {
      setSubmitting(false);
    }
  }

  function handleSelect(project: any) {
    setActiveProject({ id: project.id, name: project.name, description: project.description });
    toast.success(`Switched to "${project.name}".`);
    // re-render the page to show new active project
    window.location.reload(); 
  }

  async function handleDelete(projectId: string, projectName: string) {
    if (!confirm(`Are you sure you want to delete "${projectName}"? This will delete all its sources and reports.`)) return;
    const toastId = toast.loading("Deleting project...");
    try {
      await deleteProject(projectId);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      if (activeProject?.id === projectId) {
        window.localStorage.removeItem("cogniflow.active-project");
        window.location.reload();
      }
      toast.success("Project deleted.", { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete project.", { id: toastId });
    }
  }

  async function handleRenameSubmit(projectId: string) {
    if (!newName.trim()) return;
    const toastId = toast.loading("Renaming project...");
    try {
      await updateProject(projectId, { name: newName });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      setRenamingId(null);
      
      // Update active project label if needed
      if (activeProject?.id === projectId) {
        setActiveProject({ ...activeProject, name: newName });
      }

      toast.success("Project renamed.", { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to rename project.", { id: toastId });
    }
  }

  return (
    <PageWrapper
      title="Projects Dashboard"
      description="Manage your research projects, organize sources, and maintain separate working environments."
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Create New Project */}
        <div className="md:col-span-1 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-success" />
                <CardTitle className="text-base">Active Project</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {activeProject ? (
                <div className="flex items-center gap-3 bg-muted/50 p-3 rounded-md">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                    <FolderOpen className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{activeProject.name}</p>
                    <p className="text-xs text-muted-foreground font-mono truncate w-32">{activeProject.id}</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No active project selected. Create one below.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Create Project</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="project-name">Project name</Label>
                  <Input
                    id="project-name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. RAG Evaluation Review"
                    disabled={submitting}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="project-description">Description (optional)</Label>
                  <Textarea
                    id="project-description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Short description..."
                    rows={2}
                    disabled={submitting}
                  />
                </div>
                <Button type="submit" disabled={submitting} className="w-full gap-2 border-primary">
                  {submitting ? <Spinner size="sm" /> : <Plus className="h-4 w-4" />}
                  {submitting ? "Creating..." : "Create project"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: All Projects Grid */}
        <div className="md:col-span-2">
          <Card className="h-full">
            <CardHeader className="pb-3">
              <div className="flex justify-between items-center mb-4">
                <CardTitle className="text-base">All Projects</CardTitle>
                <div className="text-xs text-muted-foreground">{filteredProjects.length} Total</div>
              </div>
              <div className="flex gap-2">
                <Input 
                  placeholder="Search projects..." 
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="h-8 text-sm"
                />
                <select 
                  className="h-8 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={sortBy}
                  onChange={e => setSortBy(e.target.value as any)}
                >
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                  <option value="name">A-Z</option>
                </select>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex justify-center p-8"><Spinner /></div>
              ) : projects.length === 0 ? (
                <div className="text-center py-10 border border-dashed rounded-md">
                  <p className="text-muted-foreground text-sm">No projects found. Create one to get started.</p>
                </div>
              ) : filteredProjects.length === 0 ? (
                <div className="text-center py-10 border border-dashed rounded-md">
                  <p className="text-muted-foreground text-sm">No matching projects found.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
                  {filteredProjects.map((project) => (
                    <div 
                      key={project.id} 
                      className={`relative flex flex-col p-4 rounded-xl border transition-all ${
                        activeProject?.id === project.id 
                          ? 'border-primary bg-primary/5 shadow-sm' 
                          : 'border-border hover:border-foreground/20 hover:bg-accent/30 cursor-pointer'
                      }`}
                      onClick={() => {
                        if (activeProject?.id !== project.id && renamingId !== project.id) {
                          handleSelect(project);
                        }
                      }}
                    >
                      <div className="flex justify-between items-start mb-2">
                        {renamingId === project.id ? (
                          <div className="flex gap-2 w-full" onClick={e => e.stopPropagation()}>
                            <Input 
                              size={1} className="h-7 text-sm flex-1" autoFocus 
                              value={newName} onChange={e => setNewName(e.target.value)} 
                              onKeyDown={e => e.key === 'Enter' && handleRenameSubmit(project.id)}
                            />
                            <Button size="sm" variant="secondary" className="h-7 px-2" onClick={() => handleRenameSubmit(project.id)}>Save</Button>
                            <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => setRenamingId(null)}>Cancel</Button>
                          </div>
                        ) : (
                          <div className="font-semibold text-base line-clamp-1 pr-8">{project.name}</div>
                        )}
                        
                        {renamingId !== project.id && (
                          <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 hover-opacity-override" 
                               onClick={e => e.stopPropagation()}>
                            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => { setRenamingId(project.id); setNewName(project.name); }}>
                              <Edit2 className="h-3.5 w-3.5 text-muted-foreground" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-7 w-7 hover:bg-destructive/10 hover:text-destructive" onClick={() => handleDelete(project.id, project.name)}>
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        )}
                        <style>{`.hover-opacity-override { opacity: 1 !important; }`}</style>
                      </div>

                      <div className="text-xs text-muted-foreground mb-4 line-clamp-2 min-h-8">
                        {project.description || "No description provided."}
                      </div>

                      <div className="mt-auto flex justify-between items-center text-xs">
                        <div className="flex gap-3 text-muted-foreground">
                          <span className="flex items-center gap-1" title="Documents">📄 {project.source_count || 0}</span>
                          <span className="flex items-center gap-1" title="Reports">📊 {project.report_count || 0}</span>
                        </div>
                        <div className="text-[10px] text-muted-foreground/60">
                          {project.created_at ? new Date(project.created_at).toLocaleDateString() : ""}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </PageWrapper>
  );
}
