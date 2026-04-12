import type { AuthUserData } from "@/lib/api/types";

const AUTH_TOKEN_KEY = "notemesh.auth.token";
const AUTH_USER_KEY = "notemesh.auth.user";
export const AUTH_CHANGED_EVENT = "notemesh:auth-changed";

function emitAuthChanged(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setStoredAuthToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  emitAuthChanged();
}

export function clearStoredAuthToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  emitAuthChanged();
}

export function getStoredAuthUser(): AuthUserData | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(AUTH_USER_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthUserData;
  } catch {
    return null;
  }
}

export function setStoredAuthUser(user: AuthUserData): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  emitAuthChanged();
}

export function clearStoredAuthUser(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_USER_KEY);
  emitAuthChanged();
}

export function clearStoredAuthSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_USER_KEY);
  emitAuthChanged();
}
