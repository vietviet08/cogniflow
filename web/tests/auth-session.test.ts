import { beforeEach, describe, expect, it } from "vitest";

import {
  clearStoredAuthSession,
  getStoredAuthToken,
  getStoredAuthUser,
  setStoredAuthToken,
  setStoredAuthUser,
} from "../src/lib/auth-session";

describe("auth session storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("stores and reads auth token", () => {
    setStoredAuthToken("tok_123");
    expect(getStoredAuthToken()).toBe("tok_123");
  });

  it("stores and reads auth user", () => {
    setStoredAuthUser({
      id: "u1",
      email: "owner@example.com",
      display_name: "Owner",
      is_active: true,
      created_at: "2026-04-12T10:00:00Z",
    });

    expect(getStoredAuthUser()).toEqual({
      id: "u1",
      email: "owner@example.com",
      display_name: "Owner",
      is_active: true,
      created_at: "2026-04-12T10:00:00Z",
    });
  });

  it("clears session", () => {
    setStoredAuthToken("tok_123");
    setStoredAuthUser({
      id: "u1",
      email: "owner@example.com",
      display_name: "Owner",
      is_active: true,
      created_at: "2026-04-12T10:00:00Z",
    });

    clearStoredAuthSession();

    expect(getStoredAuthToken()).toBeNull();
    expect(getStoredAuthUser()).toBeNull();
  });
});
