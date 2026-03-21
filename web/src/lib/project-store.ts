"use client";

export interface StoredProject {
  id: string;
  name: string;
  description: string | null;
}

const ACTIVE_PROJECT_KEY = "notemesh.active-project";
const PROJECT_LIST_KEY = "notemesh.projects";

export function getActiveProject(): StoredProject | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(ACTIVE_PROJECT_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as StoredProject;
  } catch {
    return null;
  }
}

export function setActiveProject(project: StoredProject): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(ACTIVE_PROJECT_KEY, JSON.stringify(project));
  const existing = listStoredProjects().filter((item) => item.id !== project.id);
  window.localStorage.setItem(PROJECT_LIST_KEY, JSON.stringify([project, ...existing]));
}

export function listStoredProjects(): StoredProject[] {
  if (typeof window === "undefined") {
    return [];
  }

  const raw = window.localStorage.getItem(PROJECT_LIST_KEY);
  if (!raw) {
    return [];
  }

  try {
    return JSON.parse(raw) as StoredProject[];
  } catch {
    return [];
  }
}
