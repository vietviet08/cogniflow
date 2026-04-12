"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { bootstrapAuth, getCurrentUser } from "@/lib/api/client";
import type { AuthUserData } from "@/lib/api/types";
import {
  AUTH_CHANGED_EVENT,
  clearStoredAuthSession,
  getStoredAuthToken,
  getStoredAuthUser,
  setStoredAuthToken,
  setStoredAuthUser,
} from "@/lib/auth-session";

interface AuthContextValue {
  user: AuthUserData | null;
  token: string | null;
  isLoading: boolean;
  setTokenAndFetchUser: (token: string) => Promise<void>;
  bootstrapFirstUser: (payload: { email: string; displayName: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUserData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshCurrentUser = useCallback(async () => {
    const storedToken = getStoredAuthToken();
    if (!storedToken) {
      setToken(null);
      setUser(null);
      setIsLoading(false);
      return;
    }

    setToken(storedToken);
    try {
      const response = await getCurrentUser();
      setUser(response.data.user);
      setStoredAuthUser(response.data.user);
    } catch {
      clearStoredAuthSession();
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const storedToken = getStoredAuthToken();
    const storedUser = getStoredAuthUser();

    if (storedToken) {
      setToken(storedToken);
    }
    if (storedUser) {
      setUser(storedUser);
    }

    void refreshCurrentUser();
  }, [refreshCurrentUser]);

  useEffect(() => {
    function onAuthChanged() {
      const nextToken = getStoredAuthToken();
      const nextUser = getStoredAuthUser();
      setToken(nextToken);
      setUser(nextUser);
    }

    window.addEventListener(AUTH_CHANGED_EVENT, onAuthChanged);
    window.addEventListener("storage", onAuthChanged);
    return () => {
      window.removeEventListener(AUTH_CHANGED_EVENT, onAuthChanged);
      window.removeEventListener("storage", onAuthChanged);
    };
  }, []);

  const setTokenAndFetchUser = useCallback(async (rawToken: string) => {
    setStoredAuthToken(rawToken);
    setToken(rawToken);
    const response = await getCurrentUser();
    setUser(response.data.user);
    setStoredAuthUser(response.data.user);
  }, []);

  const bootstrapFirstUser = useCallback(
    async (payload: { email: string; displayName: string }) => {
      const response = await bootstrapAuth(payload);
      setStoredAuthToken(response.data.token);
      setStoredAuthUser(response.data.user);
      setToken(response.data.token);
      setUser(response.data.user);
    },
    [],
  );

  const logout = useCallback(() => {
    clearStoredAuthSession();
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      token,
      isLoading,
      setTokenAndFetchUser,
      bootstrapFirstUser,
      logout,
    }),
    [user, token, isLoading, setTokenAndFetchUser, bootstrapFirstUser, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
