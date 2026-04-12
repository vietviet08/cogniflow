import type { ProjectRole } from "@/lib/api/types";

const ROLE_ORDER: Record<ProjectRole, number> = {
  viewer: 10,
  editor: 20,
  owner: 30,
};

export function hasMinimumRole(
  role: ProjectRole | null | undefined,
  minimum: ProjectRole,
): boolean {
  if (!role) {
    return false;
  }
  return ROLE_ORDER[role] >= ROLE_ORDER[minimum];
}

export function canEditProject(role: ProjectRole | null | undefined): boolean {
  return hasMinimumRole(role, "editor");
}

export function canDeleteProject(role: ProjectRole | null | undefined): boolean {
  return hasMinimumRole(role, "owner");
}
