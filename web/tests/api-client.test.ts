import { afterEach, describe, expect, it } from "vitest";

import { createApiUrl } from "../src/lib/api/client";

const ORIGINAL_ENV = process.env.NEXT_PUBLIC_API_BASE_URL;

describe("api client configuration", () => {
  afterEach(() => {
    if (ORIGINAL_ENV) {
      process.env.NEXT_PUBLIC_API_BASE_URL = ORIGINAL_ENV;
    } else {
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
    }
  });

  it("uses default base URL when env is not set", () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;

    expect(createApiUrl("/health")).toBe("http://localhost:8000/api/v1/health");
  });

  it("uses NEXT_PUBLIC_API_BASE_URL when provided", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:9999/api/v1";

    expect(createApiUrl("health")).toBe("http://localhost:9999/api/v1/health");
  });
});
