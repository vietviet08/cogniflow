import { describe, expect, it } from "vitest";

import { appRoutes } from "../src/lib/routes";

describe("app route shell", () => {
  it("includes all core workflow route placeholders", () => {
    const hrefs = appRoutes.map((route) => route.href);

    expect(hrefs).toContain("/projects");
    expect(hrefs).toContain("/sources");
    expect(hrefs).toContain("/query");
    expect(hrefs).toContain("/insights");
    expect(hrefs).toContain("/reports");
  });
});
