"use client";

export interface StoredProject {
    id: string;
    name: string;
    description: string | null;
}

const ACTIVE_PROJECT_KEY = "cogniflow.active-project";

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
}

// export function listStoredProjects is removed in Phase 4
// Projects are now fetched from the backend `/projects` API.
