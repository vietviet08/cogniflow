import { describe, expect, it } from "vitest";

import { canDeleteProject, canEditProject, hasMinimumRole } from "../src/lib/permissions";

describe("permissions", () => {
  it("checks minimum role ordering", () => {
    expect(hasMinimumRole("owner", "editor")).toBe(true);
    expect(hasMinimumRole("editor", "editor")).toBe(true);
    expect(hasMinimumRole("viewer", "editor")).toBe(false);
    expect(hasMinimumRole(null, "viewer")).toBe(false);
  });

  it("maps edit and delete permissions", () => {
    expect(canEditProject("owner")).toBe(true);
    expect(canEditProject("editor")).toBe(true);
    expect(canEditProject("viewer")).toBe(false);

    expect(canDeleteProject("owner")).toBe(true);
    expect(canDeleteProject("editor")).toBe(false);
    expect(canDeleteProject("viewer")).toBe(false);
  });
});
