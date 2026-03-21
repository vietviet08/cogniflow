import { beforeEach, describe, expect, it } from "vitest";

import { getActiveProject, listStoredProjects, setActiveProject } from "../src/lib/project-store";

describe("project store", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("stores and retrieves the active project", () => {
    setActiveProject({ id: "prj-1", name: "Demo", description: "desc" });

    expect(getActiveProject()).toEqual({ id: "prj-1", name: "Demo", description: "desc" });
    expect(listStoredProjects()).toHaveLength(1);
  });
});
