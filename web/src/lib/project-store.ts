"use client";

import type { ProjectRole } from "@/lib/api/types";

export interface StoredProject {
    id: string;
    organization_id?: string | null;
    name: string;
    description: string | null;
    role?: ProjectRole;
}

const ACTIVE_PROJECT_KEY = "cogniflow.active-project";

export function getActiveProject(): StoredProject | null {
    if (typeof globalThis.window === "undefined") {
        return null;
    }

    const raw = globalThis.localStorage.getItem(ACTIVE_PROJECT_KEY);
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
    if (typeof globalThis.window === "undefined") {
        return;
    }
    globalThis.localStorage.setItem(
        ACTIVE_PROJECT_KEY,
        JSON.stringify(project),
    );
}

export function clearActiveProject(): void {
    if (typeof globalThis.window === "undefined") {
        return;
    }
    globalThis.localStorage.removeItem(ACTIVE_PROJECT_KEY);
}

// export function listStoredProjects is removed in Phase 4
// Projects are now fetched from the backend `/projects` API.
